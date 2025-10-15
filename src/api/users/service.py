from typing import List

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.api.tiers.service import TierService

# Import all models to ensure relationships are properly registered
from src.api.users.models import (
    AddressSchema,
    CreateUserSchema,
    UpdateAddressSchema,
    UserSchema,
)
from src.api.users.services import UserAddressService
from src.config.constants import UserRole
from src.database.connection import AsyncSessionLocal
from src.database.models.user import User
from src.shared.error_handler import ErrorHandler, handle_service_errors
from src.shared.exceptions import ConflictException, ValidationException
from src.shared.sqlalchemy_utils import safe_model_validate


def _user_to_dict(
    user: User, include_addresses: bool = False, include_cart: bool = False
) -> dict:
    """Convert SQLAlchemy User to dictionary, handling relationships properly"""
    user_dict = {
        "firebase_uid": user.firebase_uid,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role,
        "tier_id": user.tier_id,
        "total_orders": getattr(user, "total_orders", 0),
        "lifetime_value": getattr(user, "lifetime_value", 0.0),
        "created_at": getattr(user, "created_at", None),
        "last_order_at": getattr(user, "last_order_at", None),
        "is_delivery": getattr(user, "is_delivery", None),
        "addresses": None,
        "cart": None,
    }

    # Only add addresses if they are loaded and requested
    if include_addresses:
        try:
            if (
                hasattr(user, "__dict__")
                and "addresses" in user.__dict__
                and user.addresses is not None
            ):
                user_dict["addresses"] = [
                    AddressSchema.model_validate(addr) for addr in user.addresses
                ]
            else:
                user_dict["addresses"] = []
        except Exception:
            user_dict["addresses"] = []

    return user_dict


class UserService:
    def __init__(self):
        self.tier_service = TierService()
        self.address_service = UserAddressService()
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

            # Set default customer tier when creating user
            # First try to get the system default tier, fall back to DEFAULT_FALLBACK_TIER_ID
            default_tier = None
            try:
                default_tier = await self.tier_service.get_default_tier()
            except Exception:
                # If there's an error getting default tier, use the fallback tier
                pass
            
            # If no default tier was found from the system, use the fallback tier
            if default_tier is None:
                from src.config.constants import DEFAULT_FALLBACK_TIER_ID
                default_tier = DEFAULT_FALLBACK_TIER_ID

            new_user = User(
                firebase_uid=uid.strip(),
                name=user_data.name.strip(),
                email=user_data.email,
                phone=user_data.phone,
                role=user_data.role.value,
                tier_id=default_tier,
                is_delivery=None,
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)

            # Convert SQLAlchemy model to dict, then to Pydantic schema
            user_dict = _user_to_dict(new_user)
            return UserSchema.model_validate(user_dict)

    @handle_service_errors("retrieving user by ID")
    async def get_user_by_id(
        self, user_id: str, include_addresses: bool = False
    ) -> UserSchema | None:
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
                include_rels = {"addresses"} if include_addresses else set()
                user_schema_data = safe_model_validate(
                    UserSchema, user, include_relationships=include_rels
                )

                return user_schema_data
            return None

    async def update_user(self, user_id: str, user_data: dict) -> UserSchema | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).filter(User.firebase_uid == user_id)
            )
            user = result.scalars().first()
            if user:
                for key, value in user_data.items():
                    if key == "role" and isinstance(value, UserRole):
                        setattr(user, key, value.value)  # Store enum value as string
                    else:
                        setattr(user, key, value)
                await session.commit()
                await session.refresh(user)
                # Convert SQLAlchemy model to Pydantic schema using safe converter
                return safe_model_validate(UserSchema, user)
            return None

    # Address management - delegated to UserAddressService
    async def add_address(
        self, user_id: str, address_data: AddressSchema
    ) -> AddressSchema:
        """Add a new address for a user"""
        return await self.address_service.add_address(user_id, address_data)

    async def get_addresses(self, user_id: str) -> List[AddressSchema]:
        """Get all addresses for a user"""
        return await self.address_service.get_addresses(user_id)

    async def get_address_by_id(
        self, user_id: str, address_id: int
    ) -> AddressSchema | None:
        """Get a specific address by ID for a user"""
        return await self.address_service.get_address_by_id(user_id, address_id)

    async def update_address(
        self, user_id: str, address_id: int, address_data: UpdateAddressSchema
    ) -> AddressSchema | None:
        """Update an existing address"""
        return await self.address_service.update_address(
            user_id, address_id, address_data
        )

    async def delete_address(self, user_id: str, address_id: int) -> bool:
        """Delete an address"""
        return await self.address_service.delete_address(user_id, address_id)

    async def set_default_address(
        self, user_id: str, address_id: int
    ) -> AddressSchema | None:
        """Set an address as the default for a user"""
        return await self.address_service.set_default_address(user_id, address_id)
