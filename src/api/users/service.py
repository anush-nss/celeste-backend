from typing import Optional, List
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from src.database.connection import AsyncSessionLocal
from src.database.models.user import User
from src.database.models.cart import Cart
from src.database.models.address import Address
# Import all models to ensure relationships are properly registered
import src.database.models
from src.api.users.models import CreateUserSchema, UserSchema, AddToCartSchema, UpdateCartItemSchema, AddressSchema, UpdateAddressSchema, CartItemSchema
from src.config.constants import UserRole, DEFAULT_FALLBACK_TIER
from src.api.tiers.service import TierService
from src.shared.exceptions import ResourceNotFoundException, ConflictException, ValidationException
from src.shared.sqlalchemy_utils import safe_model_validate, safe_model_validate_list
from src.shared.error_handler import ErrorHandler, handle_service_errors
from sqlalchemy.exc import IntegrityError


def _user_to_dict(user: User, include_addresses: bool = False, include_cart: bool = False) -> dict:
    """Convert SQLAlchemy User to dictionary, handling relationships properly"""
    user_dict = {
        "firebase_uid": user.firebase_uid,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "tier_id": user.tier_id,
        "total_orders": getattr(user, 'total_orders', 0),
        "lifetime_value": getattr(user, 'lifetime_value', 0.0),
        "created_at": getattr(user, 'created_at', None),
        "last_order_at": getattr(user, 'last_order_at', None),
        "is_delivery": getattr(user, 'is_delivery', None),
        "addresses": None,
        "cart": None
    }
    
    # Only add addresses if they are loaded and requested
    if include_addresses:
        try:
            if hasattr(user, '__dict__') and 'addresses' in user.__dict__ and user.addresses is not None:
                user_dict["addresses"] = [_address_to_dict(addr) for addr in user.addresses]
            else:
                user_dict["addresses"] = []
        except Exception:
            user_dict["addresses"] = []
    
    return user_dict


def _address_to_dict(address: Address) -> dict:
    """Convert SQLAlchemy Address to dictionary"""
    return {
        "id": address.id,
        "address": address.address,
        "latitude": address.latitude,
        "longitude": address.longitude,
        "is_default": address.is_default,
        "created_at": getattr(address, 'created_at', None),
        "updated_at": getattr(address, 'updated_at', None)
    }


def _cart_to_dict(cart: Cart) -> dict:
    """Convert SQLAlchemy Cart to dictionary"""
    return {
        "user_id": cart.user_id,
        "product_id": cart.product_id,
        "quantity": cart.quantity,
        "created_at": getattr(cart, 'created_at', None),
        "updated_at": getattr(cart, 'updated_at', None)
    }


class UserService:
    def __init__(self):
        self.tier_service = TierService()
        self._error_handler = ErrorHandler(__name__)

    @handle_service_errors("creating user")
    async def create_user(self, user_data: CreateUserSchema, uid: str) -> UserSchema:
        if not uid or not uid.strip():
            raise ValidationException(detail="Valid Firebase UID is required")

        if not user_data.name or not user_data.name.strip():
            raise ValidationException(detail="Valid user name is required")

        async with AsyncSessionLocal() as session:
            # Check if user already exists
            existing_user = await session.execute(
                select(User).filter(User.firebase_uid == uid.strip())
            )
            if existing_user.scalars().first():
                raise ConflictException(detail=f"User with UID {uid} already exists")

            # Try to set default customer tier when creating user, but allow null if no tiers exist
            default_tier = None
            try:
                default_tier = await self.tier_service.get_default_tier()
            except Exception:
                # If no tiers exist, leave tier_id as None
                pass

            new_user = User(
                firebase_uid=uid.strip(),
                name=user_data.name.strip(),
                email=user_data.email,
                phone=user_data.phone,
                role=user_data.role.value,
                tier_id=default_tier,
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)

            # Convert SQLAlchemy model to dict, then to Pydantic schema
            user_dict = _user_to_dict(new_user)
            return UserSchema.model_validate(user_dict)

    @handle_service_errors("retrieving user by ID")
    async def get_user_by_id(self, user_id: str, include_cart: bool = False, include_addresses: bool = False) -> UserSchema | None:
        if not user_id or not user_id.strip():
            raise ValidationException(detail="Valid user ID is required")

        async with AsyncSessionLocal() as session:
            query = select(User).filter(User.firebase_uid == user_id.strip())

            if include_addresses:
                query = query.options(selectinload(User.addresses))

            result = await session.execute(query)
            user = result.scalars().first()

            if user:
                # Convert SQLAlchemy model to Pydantic schema using safe converter
                include_rels = {'addresses'} if include_addresses else set()
                user_schema_data = safe_model_validate(
                    UserSchema,
                    user,
                    include_relationships=include_rels
                )

                if include_cart: # Only fetch and assign if include_cart is True
                    cart_result = await session.execute(
                        select(Cart).filter(Cart.user_id == user_id.strip())
                    )
                    cart_items = cart_result.scalars().all()
                    user_schema_data.cart = safe_model_validate_list(CartItemSchema, cart_items)

                return user_schema_data
            return None

    async def update_user(self, user_id: str, user_data: dict) -> UserSchema | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).filter(User.firebase_uid == user_id))
            user = result.scalars().first()
            if user:
                for key, value in user_data.items():
                    if key == "role" and isinstance(value, UserRole):
                        setattr(user, key, value.value) # Store enum value as string
                    else:
                        setattr(user, key, value)
                await session.commit()
                await session.refresh(user)
                # Convert SQLAlchemy model to Pydantic schema using safe converter
                return safe_model_validate(UserSchema, user)
            return None

    @handle_service_errors("adding to cart")
    async def add_to_cart(self, user_id: str, product_id: str, quantity: int) -> dict:
        if not user_id or not user_id.strip():
            raise ValidationException(detail="Valid user ID is required")

        if not product_id or not product_id.strip():
            raise ValidationException(detail="Valid product ID is required")

        if quantity <= 0 or quantity > 1000:
            raise ValidationException(detail="Quantity must be between 1 and 1000")

        async with AsyncSessionLocal() as session:
            # Verify user exists
            user_exists = await session.execute(
                select(User).filter(User.firebase_uid == user_id.strip())
            )
            if not user_exists.scalars().first():
                raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")

            cart_item_query = await session.execute(
                select(Cart).filter_by(user_id=user_id.strip(), product_id=product_id.strip())
            )
            item_to_return = cart_item_query.scalars().first()

            if item_to_return:
                new_quantity = item_to_return.quantity + quantity
                if new_quantity > 1000:
                    raise ValidationException(detail="Cart item quantity cannot exceed 1000")
                item_to_return.quantity = new_quantity
            else:
                item_to_return = Cart(
                    user_id=user_id.strip(),
                    product_id=product_id.strip(),
                    quantity=quantity
                )
                session.add(item_to_return)

            await session.commit()
            await session.refresh(item_to_return)

            return {
                "user_id": item_to_return.user_id,
                "product_id": item_to_return.product_id,
                "quantity": item_to_return.quantity
            }

    async def update_cart_item(self, user_id: str, product_id: str, quantity: int) -> dict:
        async with AsyncSessionLocal() as session:
            cart_item = await session.execute(
                select(Cart).filter_by(user_id=user_id, product_id=product_id)
            )
            existing_item = cart_item.scalars().first()

            if not existing_item:
                raise ResourceNotFoundException(detail=f"Product {product_id} not found in user's cart")

            existing_item.quantity = quantity
            await session.commit()
            await session.refresh(existing_item)
            return {"user_id": existing_item.user_id, "product_id": existing_item.product_id, "quantity": existing_item.quantity}

    async def remove_from_cart(self, user_id: str, product_id: str, quantity: Optional[int] = None) -> dict:
        async with AsyncSessionLocal() as session:
            cart_item = await session.execute(
                select(Cart).filter_by(user_id=user_id, product_id=product_id)
            )
            existing_item = cart_item.scalars().first()

            if not existing_item:
                raise ResourceNotFoundException(detail=f"Product {product_id} not found in user's cart")

            result = {"action": "", "previous_quantity": existing_item.quantity}

            if quantity is None or quantity >= existing_item.quantity:
                await session.delete(existing_item)
                result["action"] = "removed_completely"
                result["new_quantity"] = 0
            else:
                existing_item.quantity = existing_item.quantity - quantity
                result["action"] = "quantity_reduced"
                result["new_quantity"] = existing_item.quantity
                result["quantity_removed"] = quantity

            await session.commit()
            return result

    async def get_cart(self, user_id: str) -> List[dict]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Cart).filter_by(user_id=user_id)
            )
            cart_items = result.scalars().all()
            return [{
                "user_id": item.user_id,
                "product_id": item.product_id,
                "quantity": item.quantity
            } for item in cart_items]

    async def add_address(self, user_id: str, address_data: AddressSchema) -> AddressSchema:
        async with AsyncSessionLocal() as session:
            # If new address is default, set all other addresses for this user to not default
            if address_data.is_default:
                result = await session.execute(
                    select(Address).filter_by(user_id=user_id, is_default=True)
                )
                for addr in result.scalars().all(): # Iterate over the result of the query
                    setattr(addr, "is_default", False) # Fixed Pylance error

            new_address = Address(
                user_id=user_id,
                address=address_data.address,
                latitude=address_data.latitude,
                longitude=address_data.longitude,
                is_default=address_data.is_default
            )
            session.add(new_address)
            await session.commit()
            await session.refresh(new_address)
            return AddressSchema.model_validate(new_address)

    async def get_addresses(self, user_id: str) -> List[AddressSchema]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Address).filter_by(user_id=user_id)
            )
            addresses = result.scalars().all()
            return safe_model_validate_list(AddressSchema, addresses)

    async def get_address_by_id(self, user_id: str, address_id: int) -> AddressSchema | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Address).filter_by(user_id=user_id, id=address_id)
            )
            address = result.scalars().first()
            if address:
                # Convert SQLAlchemy model to dict, then to Pydantic schema
                address_dict = _address_to_dict(address)
                return AddressSchema.model_validate(address_dict)
            return None

    async def update_address(self, user_id: str, address_id: int, address_data: UpdateAddressSchema) -> AddressSchema | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Address).filter_by(user_id=user_id, id=address_id)
            )
            address = result.scalars().first()

            if not address:
                raise ResourceNotFoundException(detail=f"Address with ID {address_id} not found for user {user_id}")

            # Handle is_default logic
            if address_data.is_default is True and not address.is_default:
                # If this address is being set to default, unset others
                for addr in (await session.execute(select(Address).filter_by(user_id=user_id, is_default=True))).scalars().all():
                    setattr(addr, "is_default", False) # Fixed Pylance error

            for field, value in address_data.model_dump(exclude_unset=True).items():
                setattr(address, field, value)

            await session.commit()
            await session.refresh(address)
            # Convert SQLAlchemy model to dict, then to Pydantic schema
            address_dict = _address_to_dict(address)
            return AddressSchema.model_validate(address_dict)

    async def delete_address(self, user_id: str, address_id: int) -> bool:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Address).filter_by(user_id=user_id, id=address_id)
            )
            address = result.scalars().first()

            if not address:
                raise ResourceNotFoundException(detail=f"Address with ID {address_id} not found for user {user_id}")

            await session.delete(address)
            await session.commit()
            return True

    async def set_default_address(self, user_id: str, address_id: int) -> AddressSchema | None:
        async with AsyncSessionLocal() as session:
            # Unset current default address for the user
            for addr in (await session.execute(select(Address).filter_by(user_id=user_id, is_default=True))).scalars().all():
                setattr(addr, "is_default", False) # Fixed Pylance error

            # Set the new default address
            result = await session.execute(
                select(Address).filter_by(user_id=user_id, id=address_id)
            )
            address = result.scalars().first()

            if not address:
                raise ResourceNotFoundException(detail=f"Address with ID {address_id} not found for user {user_id}")

            setattr(address, "is_default", True) # Fixed Pylance error
            await session.commit()
            await session.refresh(address)
            # Convert SQLAlchemy model to dict, then to Pydantic schema
            address_dict = _address_to_dict(address)
            return AddressSchema.model_validate(address_dict)