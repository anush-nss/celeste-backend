from typing import List, Optional

from sqlalchemy import desc
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.api.tiers.service import TierService
from src.database.models.search_interaction import SearchInteraction
from src.database.models.favorite import Favorite
from src.api.products.models import EnhancedProductSchema
from src.api.products.service import ProductService

# Import all models to ensure relationships are properly registered
from src.api.users.models import (
    AddressCreationSchema,
    AddressResponseSchema,
    CreateUserSchema,
    UserSchema,
)
from src.api.users.services import UserAddressService
from src.config.constants import UserRole
from src.database.connection import AsyncSessionLocal
from src.database.models.user import User
from src.shared.error_handler import ErrorHandler, handle_service_errors
from src.shared.exceptions import (
    ConflictException,
    ResourceNotFoundException,
    ValidationException,
)
from src.shared.sqlalchemy_utils import safe_model_validate


def _user_to_dict(
    user: User,
    include_addresses: bool = False,
    include_favorites: bool = False,
    favorites_data: Optional[List[EnhancedProductSchema]] = None,
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
        "favorites": None,
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
                    AddressResponseSchema.model_validate(addr)
                    for addr in user.addresses
                ]
            else:
                user_dict["addresses"] = []
        except Exception:
            user_dict["addresses"] = []

    if include_favorites and favorites_data:
        user_dict["favorites"] = favorites_data

    return user_dict


class UserService:
    def __init__(self):
        self.tier_service = TierService()
        self.address_service = UserAddressService()
        self.product_service = ProductService()
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
        self,
        user_id: str,
        include_addresses: bool = False,
        include_favorites: bool = False,
    ) -> UserSchema | None:
        if not user_id or not user_id.strip():
            raise ValidationException(detail="Valid user ID is required")

        async with AsyncSessionLocal() as session:
            query = select(User).filter(User.firebase_uid == user_id.strip())

            if include_addresses:
                query = query.options(selectinload(User.addresses))

            # Don't need to load favorites relationship eagerly if we are just fetching IDs,
            # but if we want to include it in the response, we might.
            # However, favorites logic is handled via helper to fetch products.

            result = await session.execute(query)
            user = result.scalars().first()

            if user:
                favorites_data = None
                if include_favorites:
                    favorites_data = await self.get_favorites(
                        user_id, include_products=True
                    )

                # Convert SQLAlchemy model to Pydantic schema using safe converter
                include_rels = {"addresses"} if include_addresses else set()
                user_schema_data = safe_model_validate(
                    UserSchema, user, include_relationships=include_rels
                )

                if include_favorites and favorites_data:
                    user_schema_data.favorites = favorites_data

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
        self, user_id: str, address_data: AddressCreationSchema
    ) -> AddressResponseSchema:
        """Add a new address for a user"""
        return await self.address_service.add_address(user_id, address_data)

    async def get_addresses(self, user_id: str) -> List[AddressResponseSchema]:
        """Get all addresses for a user"""
        return await self.address_service.get_addresses(user_id)

    async def get_address_by_id(
        self, user_id: str, address_id: int
    ) -> AddressResponseSchema | None:
        """Get a specific address by ID for a user"""
        return await self.address_service.get_address_by_id(user_id, address_id)

    async def delete_address(self, user_id: str, address_id: int) -> bool:
        """Delete an address"""
        return await self.address_service.delete_address(user_id, address_id)

    async def set_default_address(
        self, user_id: str, address_id: int
    ) -> AddressResponseSchema | None:
        """Set an address as the default for a user"""
        return await self.address_service.set_default_address(user_id, address_id)

    @handle_service_errors("retrieving search history")
    async def get_search_history(self, user_id: str, limit: int = 10) -> List[str]:
        """
        Retrieves the recent search queries for a given user.

        Args:
            user_id: The Firebase UID of the user.
            limit: The maximum number of search queries to return.

        Returns:
            A list of recent search query strings.
        """
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(SearchInteraction.query)
                .filter(SearchInteraction.user_id == user_id)
                .order_by(desc(SearchInteraction.timestamp))
                .limit(limit)
            )
            return [row.query for row in result.fetchall()]

    @handle_service_errors("adding favorite")
    async def add_favorite(self, user_id: str, product_id: int) -> List[int]:
        """Add a product to user's favorites"""
        if not user_id:
            raise ValidationException(detail="User ID is required")

        async with AsyncSessionLocal() as session:
            # Check if product exists
            product_exists = await self.product_service.get_product_by_id(product_id)
            if not product_exists:
                raise ValidationException(
                    detail=f"Product with ID {product_id} not found"
                )

            stmt = select(Favorite).filter(Favorite.user_id == user_id)
            result = await session.execute(stmt)
            favorite = result.scalars().first()

            if not favorite:
                favorite = Favorite(user_id=user_id, product_ids=[product_id])
                session.add(favorite)
            else:
                current_ids = list(favorite.product_ids)
                if product_id not in current_ids:
                    # Create a new list to ensure change detection works
                    favorite.product_ids = current_ids + [product_id]

            await session.commit()
            await session.refresh(favorite)
            return favorite.product_ids

    @handle_service_errors("removing favorite")
    async def remove_favorite(self, user_id: str, product_id: int) -> List[int]:
        """Remove a product from user's favorites"""
        if not user_id:
            raise ValidationException(detail="User ID is required")

        async with AsyncSessionLocal() as session:
            stmt = select(Favorite).filter(Favorite.user_id == user_id)
            result = await session.execute(stmt)
            favorite = result.scalars().first()

            if not favorite or not favorite.product_ids:
                raise ResourceNotFoundException(
                    detail=f"Product with ID {product_id} not found in favorites"
                )

            current_ids = list(favorite.product_ids)
            if product_id not in current_ids:
                raise ResourceNotFoundException(
                    detail=f"Product with ID {product_id} not found in favorites"
                )

            current_ids.remove(product_id)
            favorite.product_ids = current_ids
            await session.commit()
            await session.refresh(favorite)
            return favorite.product_ids

    @handle_service_errors("retrieving favorites")
    async def get_favorites(
        self,
        user_id: str,
        include_products: bool = True,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        store_ids: Optional[List[int]] = None,
    ) -> List[EnhancedProductSchema] | List[int] | List[dict]:
        """Get user's favorites, optionally fetching full product details"""
        if not user_id:
            raise ValidationException(detail="User ID is required")

        async with AsyncSessionLocal() as session:
            stmt = select(Favorite).filter(Favorite.user_id == user_id)
            result = await session.execute(stmt)
            favorite = result.scalars().first()

            product_ids = favorite.product_ids if favorite else []

        if not product_ids:
            return []

        if include_products:
            # Reusing ProductService to get enhanced product details (inventory, pricing, etc.)
            # We assume current user's tier for pricing if needed,
            # but getting user tier requires user object.
            # For simplicity, we'll let product service handle defaults or we fetch user first.

            # Fetch user to get tier
            user = await self.get_user_by_id(user_id)
            customer_tier = user.tier_id if user else None

            # Resolve store_ids if not provided but location is available
            if not store_ids and latitude and longitude:
                (
                    fetched_store_ids,
                    _,  # is_nearby_store
                ) = await self.product_service.store_service.get_store_ids_by_location(
                    latitude, longitude
                )
                # Ensure store_ids is a list of ints
                if fetched_store_ids:
                    store_ids = [
                        s_id for s_id in fetched_store_ids if isinstance(s_id, int)
                    ]

            # We need to use query service directly or add method to product service
            # ProductService.get_products_by_ids uses query service which supports enhanced details
            return await self.product_service.query_service.get_products_by_ids(
                product_ids=product_ids,
                customer_tier=customer_tier,
                include_pricing=True,
                include_inventory=True,
                include_categories=True,
                include_tags=True,
                latitude=latitude,
                longitude=longitude,
                store_ids=store_ids,
            )

        return product_ids
