from typing import Optional, List, cast
from sqlalchemy.future import select
from sqlalchemy import CursorResult, update
from sqlalchemy.orm import selectinload
from src.database.connection import AsyncSessionLocal
from src.database.models.user import User
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
                user_dict["addresses"] = [AddressSchema.model_validate(addr) for addr in user.addresses]
            else:
                user_dict["addresses"] = []
        except Exception:
            user_dict["addresses"] = []
    
    return user_dict




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
                is_delivery=None
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)

            # Convert SQLAlchemy model to dict, then to Pydantic schema
            user_dict = _user_to_dict(new_user)
            return UserSchema.model_validate(user_dict)

    @handle_service_errors("retrieving user by ID")
    async def get_user_by_id(self, user_id: str, include_addresses: bool = False) -> UserSchema | None:
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

    # Old cart methods removed - use new multi-cart endpoints at /users/me/carts/*


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
                return AddressSchema.model_validate(address)
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

            update_data = address_data.model_dump(exclude_unset=True)
            
            # if no data to update, return early
            if len(update_data) == 0:
                raise ValidationException(detail="No data provided for update")

            # Update the specific address with all provided fields
            for field, value in update_data.items():
                setattr(address, field, value)

            await session.commit()
            await session.refresh(address)
            # Convert SQLAlchemy model to dict, then to Pydantic schema
            return AddressSchema.model_validate(address)

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
            return AddressSchema.model_validate(address)