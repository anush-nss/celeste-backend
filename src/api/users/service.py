from typing import Optional, List
from sqlalchemy.future import select
from sqlalchemy import update
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

            # Use database-level atomic operation to update or insert
            from sqlalchemy import text
            # Try to update existing cart item
            update_result = await session.execute(
                text("""
                    UPDATE cart 
                    SET quantity = LEAST(quantity + :quantity, 1000)
                    WHERE user_id = :user_id AND product_id = :product_id
                """),
                {
                    "user_id": user_id.strip(),
                    "product_id": product_id.strip(),
                    "quantity": quantity
                }
            )
            
            # If no rows were updated, insert a new cart item
            if update_result.rowcount == 0:
                # Check if we would exceed the quantity limit
                cart_item_query = await session.execute(
                    select(Cart).filter_by(user_id=user_id.strip(), product_id=product_id.strip())
                )
                existing_item = cart_item_query.scalars().first()
                
                if existing_item:
                    # Race condition - item was created between our check and update
                    new_quantity = min(existing_item.quantity + quantity, 1000)
                    existing_item.quantity = new_quantity
                    await session.commit()
                    await session.refresh(existing_item)
                    item_to_return = existing_item
                else:
                    # Insert new cart item
                    item_to_return = Cart(
                        user_id=user_id.strip(),
                        product_id=product_id.strip(),
                        quantity=quantity
                    )
                    session.add(item_to_return)
                    await session.commit()
                    await session.refresh(item_to_return)
            else:
                # Refresh the updated item
                cart_item_query = await session.execute(
                    select(Cart).filter_by(user_id=user_id.strip(), product_id=product_id.strip())
                )
                item_to_return = cart_item_query.scalars().first()
                await session.refresh(item_to_return)

            return {
                "user_id": item_to_return.user_id,
                "product_id": item_to_return.product_id,
                "quantity": item_to_return.quantity
            }

    async def update_cart_item(self, user_id: str, product_id: str, quantity: int) -> dict:
        if quantity <= 0 or quantity > 1000:
            raise ValidationException(detail="Quantity must be between 1 and 1000")
            
        async with AsyncSessionLocal() as session:
            # Use database-level atomic operation to update
            from sqlalchemy import text
            result = await session.execute(
                text("""
                    UPDATE cart 
                    SET quantity = :quantity
                    WHERE user_id = :user_id AND product_id = :product_id
                """),
                {
                    "user_id": user_id,
                    "product_id": product_id,
                    "quantity": quantity
                }
            )
            
            await session.commit()
            
            if result.rowcount == 0:
                raise ResourceNotFoundException(detail=f"Product {product_id} not found in user's cart")
            
            # Fetch the updated item
            cart_item = await session.execute(
                select(Cart).filter_by(user_id=user_id, product_id=product_id)
            )
            existing_item = cart_item.scalars().first()
            
            return {"user_id": existing_item.user_id, "product_id": existing_item.product_id, "quantity": existing_item.quantity}

    async def remove_from_cart(self, user_id: str, product_id: str, quantity: Optional[int] = None) -> dict:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import text
            
            if quantity is None:
                # Remove completely
                result = await session.execute(
                    text("""
                        DELETE FROM cart 
                        WHERE user_id = :user_id AND product_id = :product_id
                    """),
                    {
                        "user_id": user_id,
                        "product_id": product_id
                    }
                )
                
                await session.commit()
                
                if result.rowcount == 0:
                    raise ResourceNotFoundException(detail=f"Product {product_id} not found in user's cart")
                
                return {
                    "action": "removed_completely",
                    "previous_quantity": 0,  # We don't know the previous quantity in this approach
                    "new_quantity": 0
                }
            else:
                # Partial removal - update quantity
                # First get current quantity
                cart_item = await session.execute(
                    select(Cart).filter_by(user_id=user_id, product_id=product_id)
                )
                existing_item = cart_item.scalars().first()
                
                if not existing_item:
                    raise ResourceNotFoundException(detail=f"Product {product_id} not found in user's cart")
                
                current_quantity = existing_item.quantity
                result = {"action": "", "previous_quantity": current_quantity}
                
                if quantity >= current_quantity:
                    # Remove completely
                    await session.execute(
                        text("""
                            DELETE FROM cart 
                            WHERE user_id = :user_id AND product_id = :product_id
                        """),
                        {
                            "user_id": user_id,
                            "product_id": product_id
                        }
                    )
                    result["action"] = "removed_completely"
                    result["new_quantity"] = 0
                else:
                    # Reduce quantity
                    new_quantity = current_quantity - quantity
                    await session.execute(
                        text("""
                            UPDATE cart 
                            SET quantity = :quantity
                            WHERE user_id = :user_id AND product_id = :product_id
                        """),
                        {
                            "user_id": user_id,
                            "product_id": product_id,
                            "quantity": new_quantity
                        }
                    )
                    result["action"] = "quantity_reduced"
                    result["new_quantity"] = new_quantity
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
            # If new address is default, atomically set all other addresses for this user to not default
            if address_data.is_default:
                await session.execute(
                    update(Address).where(Address.user_id == user_id).values(is_default=False)
                )

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
            # First verify the address exists and belongs to the user
            result = await session.execute(
                select(Address).filter_by(user_id=user_id, id=address_id)
            )
            address = result.scalars().first()

            if not address:
                raise ResourceNotFoundException(detail=f"Address with ID {address_id} not found for user {user_id}")

            # Handle is_default logic atomically
            update_data = address_data.model_dump(exclude_unset=True)
            if update_data.get("is_default") is True and not address.is_default:
                # If this address is being set to default, unset others atomically
                await session.execute(
                    update(Address).where(Address.user_id == user_id).where(Address.id != address_id).values(is_default=False)
                )

            # Update the specific address with all provided fields
            for field, value in update_data.items():
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
                return False

            await session.delete(address)
            await session.commit()
            return True

    async def set_default_address(self, user_id: str, address_id: int) -> AddressSchema | None:
        async with AsyncSessionLocal() as session:
            # Atomically unset current default address and set new default in one transaction
            # First verify the address exists and belongs to the user
            result = await session.execute(
                select(Address).filter_by(user_id=user_id, id=address_id)
            )
            address = result.scalars().first()

            if not address:
                raise ResourceNotFoundException(detail=f"Address with ID {address_id} not found for user {user_id}")

            # Atomically update all addresses for this user:
            # 1. Set the specified address as default
            # 2. Set all other addresses as non-default
            await session.execute(
                update(Address).where(Address.user_id == user_id).where(Address.id == address_id).values(is_default=True)
            )
            await session.execute(
                update(Address).where(Address.user_id == user_id).where(Address.id != address_id).values(is_default=False)
            )

            await session.commit()
            
            # Refresh the specific address we're returning
            await session.refresh(address)
            # Convert SQLAlchemy model to dict, then to Pydantic schema
            address_dict = _address_to_dict(address)
            return AddressSchema.model_validate(address_dict)