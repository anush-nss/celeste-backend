from typing import Any, Dict, List, Optional

from sqlalchemy import and_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.api.stores.models import (
    CreateStoreSchema,
    StoreLocationResponse,
    StoreQuerySchema,
    StoreSchema,
    UpdateStoreSchema,
)
from src.api.tags.models import CreateTagSchema
from src.api.tags.service import TagService
from src.config.cache_config import CacheConfig
from src.config.constants import (
    DEFAULT_SEARCH_RADIUS_KM,
    DEFAULT_STORE_IDS,
)
from src.database.connection import AsyncSessionLocal
from src.database.models.product import Tag
from src.database.models.store import Store
from src.database.models.store_tag import StoreTag
from src.shared.cache_service import cache_service
from src.shared.error_handler import ErrorHandler, handle_service_errors
from src.shared.exceptions import ConflictException, ValidationException
from src.shared.geo_utils import GeoUtils
from src.shared.performance_utils import async_timer


class StoreService:
    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.tag_service = TagService(entity_type="store")
        self.cache = cache_service

    def calculate_bounding_box(self, lat: float, lng: float, radius_km: float) -> dict:
        """Calculate bounding box for efficient spatial filtering"""
        min_lat, max_lat, min_lng, max_lng = GeoUtils.get_bounding_box(
            lat, lng, radius_km
        )
        return {
            "lat_min": min_lat,
            "lat_max": max_lat,
            "lng_min": min_lng,
            "lng_max": max_lng,
        }

    async def get_all_stores(
        self, query_params: Optional[StoreQuerySchema] = None
    ) -> StoreLocationResponse:
        """Get all stores without location-based filtering or distances"""
        async with AsyncSessionLocal() as session:
            # Build base query
            query = select(Store)

            # Include tag relationships if needed
            if query_params and (query_params.include_tags or query_params.tags):
                query = query.options(
                    selectinload(Store.store_tags).selectinload(StoreTag.tag)
                )

            # Apply filters
            conditions = []

            if query_params and query_params.is_active is not None:
                conditions.append(Store.is_active == query_params.is_active)

            # Handle new tag filtering
            tag_params = {}
            if query_params and query_params.tags:
                tag_filter_result = self.tag_service.parse_tag_filters(
                    query_params.tags
                )
                if tag_filter_result["needs_joins"] and tag_filter_result["conditions"]:
                    # Join with store_tags and tags tables
                    query = query.join(Store.store_tags).join(StoreTag.tag)
                    # Add tag filter conditions
                    tag_conditions_str = " OR ".join(tag_filter_result["conditions"])
                    conditions.append(text(f"({tag_conditions_str})"))
                    tag_params.update(tag_filter_result["params"])

            if conditions:
                query = query.filter(and_(*conditions))

            # Apply limit
            if query_params and query_params.limit:
                query = query.limit(query_params.limit)

            # Execute query
            result = await session.execute(query, tag_params)
            store_models = result.scalars().unique().all()

            # Convert to schemas and add dynamic fields
            stores = []
            for store_model in store_models:
                store_dict = {
                    "id": store_model.id,
                    "name": store_model.name,
                    "description": store_model.description,
                    "address": store_model.address,
                    "latitude": store_model.latitude,
                    "longitude": store_model.longitude,
                    "email": store_model.email,
                    "phone": store_model.phone,
                    "is_active": store_model.is_active,
                    "created_at": store_model.created_at,
                    "updated_at": store_model.updated_at,
                }

                # Add distance if location provided
                if (
                    query_params
                    and query_params.include_distance
                    and query_params.latitude is not None
                    and query_params.longitude is not None
                ):
                    distance = GeoUtils.calculate_distance(
                        query_params.latitude,
                        query_params.longitude,
                        store_model.latitude,
                        store_model.longitude,
                    )
                    store_dict["distance"] = round(distance, 1)

                # Add tags if requested
                if query_params and query_params.include_tags:
                    store_dict["store_tags"] = [
                        {
                            "id": st.tag.id,
                            "tag_type": st.tag.tag_type,
                            "name": st.tag.name,
                            "slug": st.tag.slug,
                            "description": st.tag.description,
                            "value": st.value,
                        }
                        for st in store_model.store_tags
                    ]

                stores.append(StoreSchema(**store_dict))

            return self._build_location_response(stores, query_params)

    @handle_service_errors("retrieving store IDs by location")
    async def get_store_ids_by_location(
        self,
        latitude: float,
        longitude: float,
        radius_km: Optional[float] = DEFAULT_SEARCH_RADIUS_KM,
        return_full_stores: Optional[bool] = False,
        include_distance: Optional[bool] = False,
    ) -> tuple[List[int] | List[Dict[str, Any]], bool]:
        """
        Get store IDs (or full store data) near location using PostGIS spatial query with caching and default fallback.

        This method is optimized for inventory queries where only store IDs are needed,
        but can also return full store objects for store listing endpoints.

        Args:
            latitude: User's latitude
            longitude: User's longitude
            radius_km: Search radius in kilometers (default from constants)
            return_full_stores: If True, returns full store data instead of just IDs
            include_distance: If True and return_full_stores=True, includes distance field

        Returns:
            tuple: (stores_data, is_nearby_store)
                - stores_data: List of store IDs (default) or List of store dicts (if return_full_stores=True)
                - is_nearby_store: True if stores found within radius, False if using default fallback
        """
        # Validate coordinates
        if not GeoUtils.validate_coordinates(latitude, longitude):
            raise ValidationException(detail="Invalid coordinates provided")

        # Generate cache key (different for IDs vs full stores)
        cache_key_suffix = "full" if return_full_stores else "ids"
        cache_key = f"stores:location:{latitude:.6f}:{longitude:.6f}:{radius_km}:{cache_key_suffix}"

        # Try cache first (10 minutes TTL)
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            return cached_result

        async with AsyncSessionLocal() as session:
            # Use PostGIS spatial query for accurate distance calculation
            if return_full_stores:
                # Query with full store data and distance
                query = """
                SELECT
                    id,
                    name,
                    description,
                    address,
                    latitude,
                    longitude,
                    email,
                    phone,
                    is_active,
                    created_at,
                    updated_at,
                    ST_Distance(
                        ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                        ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
                    ) / 1000.0 as distance_km
                FROM stores
                WHERE is_active = true
                  AND ST_DWithin(
                      ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                      ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
                      :radius_meters
                  )
                ORDER BY distance_km
                LIMIT 20
                """
            else:
                # Query with just IDs
                query = """
                SELECT id
                FROM stores
                WHERE is_active = true
                  AND ST_DWithin(
                      ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                      ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
                      :radius_meters
                  )
                ORDER BY ST_Distance(
                    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
                )
                LIMIT 20
                """

            result = await session.execute(
                text(query),
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius_meters": (radius_km or DEFAULT_SEARCH_RADIUS_KM)
                    * 1000,  # Convert km to meters
                },
            )

            rows = result.fetchall()

            # Process results based on mode
            if return_full_stores:
                stores_data = []
                for row in rows:
                    store_dict = {
                        "id": row.id,
                        "name": row.name,
                        "description": row.description,
                        "address": row.address,
                        "latitude": float(row.latitude),
                        "longitude": float(row.longitude),
                        "email": row.email,
                        "phone": row.phone,
                        "is_active": row.is_active,
                        "created_at": row.created_at,
                        "updated_at": row.updated_at,
                    }
                    if include_distance:
                        store_dict["distance"] = round(float(row.distance_km), 1)
                    stores_data.append(store_dict)
            else:
                stores_data = [row.id for row in rows]

            # If no stores found nearby, use default stores as fallback
            is_nearby_store = True
            if not stores_data and DEFAULT_STORE_IDS:
                if return_full_stores:
                    # Fetch full data for default stores
                    default_query = select(Store).where(Store.id.in_(DEFAULT_STORE_IDS))
                    default_result = await session.execute(default_query)
                    default_stores = default_result.scalars().all()

                    stores_data = []
                    for store in default_stores:
                        store_dict = {
                            "id": store.id,
                            "name": store.name,
                            "description": store.description,
                            "address": store.address,
                            "latitude": float(store.latitude),
                            "longitude": float(store.longitude),
                            "email": store.email,
                            "phone": store.phone,
                            "is_active": store.is_active,
                            "created_at": store.created_at,
                            "updated_at": store.updated_at,
                        }
                        # Don't include distance for default stores
                        stores_data.append(store_dict)
                else:
                    stores_data = DEFAULT_STORE_IDS
                is_nearby_store = False

            result_tuple = (stores_data, is_nearby_store)

            # Cache result
            await self.cache.set(
                cache_key, result_tuple, ttl=CacheConfig.STORE_LOCATION_TTL
            )

            return result_tuple

    def _build_location_response(
        self,
        stores: List[StoreSchema],
        query_params: Optional[StoreQuerySchema],
        total_found: Optional[int] = None,
    ) -> StoreLocationResponse:
        """Build standardized location response"""
        user_location = None
        search_radius = None

        if query_params and query_params.latitude and query_params.longitude:
            user_location = {
                "latitude": query_params.latitude,
                "longitude": query_params.longitude,
            }
            search_radius = query_params.radius or DEFAULT_SEARCH_RADIUS_KM

        return StoreLocationResponse(
            stores=stores,
            user_location=user_location,
            search_radius=search_radius,
            total_found=total_found or len(stores),
            returned=len(stores),
        )

    async def get_store_by_id(
        self, store_id: int, include_tags: Optional[bool] = False
    ) -> Optional[StoreSchema]:
        """Get store by ID"""
        async with AsyncSessionLocal() as session:
            query = select(Store).filter(Store.id == store_id)

            if include_tags:
                query = query.options(
                    selectinload(Store.store_tags).selectinload(StoreTag.tag)
                )

            result = await session.execute(query)
            store_model = result.scalars().first()

            if not store_model:
                return None

            store_dict = {
                "id": store_model.id,
                "name": store_model.name,
                "description": store_model.description,
                "address": store_model.address,
                "latitude": store_model.latitude,
                "longitude": store_model.longitude,
                "email": store_model.email,
                "phone": store_model.phone,
                "is_active": store_model.is_active,
                "created_at": store_model.created_at,
                "updated_at": store_model.updated_at,
            }

            if include_tags:
                store_dict["store_tags"] = [
                    {
                        "id": st.tag.id,
                        "tag_type": st.tag.tag_type,
                        "name": st.tag.name,
                        "slug": st.tag.slug,
                        "description": st.tag.description,
                        "value": st.value,
                    }
                    for st in store_model.store_tags
                ]

            return StoreSchema(**store_dict)

    @handle_service_errors("creating store")
    @async_timer("create_store")
    async def create_store(self, store_data: CreateStoreSchema) -> StoreSchema:
        """Create a new store with tag associations"""
        if not store_data.name or not store_data.name.strip():
            raise ValidationException(detail="Store name is required")

        if not store_data.address or not store_data.address.strip():
            raise ValidationException(detail="Store address is required")

        if not GeoUtils.validate_coordinates(store_data.latitude, store_data.longitude):
            raise ValidationException(detail="Invalid coordinates provided")

        async with AsyncSessionLocal() as session:
            try:
                # Create store
                new_store = Store(
                    name=store_data.name,
                    description=store_data.description,
                    address=store_data.address,
                    latitude=store_data.latitude,
                    longitude=store_data.longitude,
                    email=store_data.email,
                    phone=store_data.phone,
                    is_active=store_data.is_active,
                )

                session.add(new_store)
                await session.flush()  # Get the ID

                # Add tag associations
                if store_data.tag_ids:
                    for tag_id in store_data.tag_ids:
                        store_tag = StoreTag(store_id=new_store.id, tag_id=tag_id)
                        session.add(store_tag)

                await session.commit()
                await session.refresh(new_store)

                return StoreSchema(
                    id=new_store.id,
                    name=new_store.name,
                    description=new_store.description,
                    address=new_store.address,
                    latitude=new_store.latitude,
                    longitude=new_store.longitude,
                    email=new_store.email,
                    phone=new_store.phone,
                    is_active=new_store.is_active,
                    created_at=new_store.created_at,
                    updated_at=new_store.updated_at,
                    distance=None,
                )

            except IntegrityError as e:
                await session.rollback()
                self._error_handler.logger.error(f"Failed to create store: {str(e)}")
                raise ConflictException(
                    detail="Store creation failed due to constraint violation"
                )
            except Exception as e:
                await session.rollback()
                self._error_handler.logger.error(f"Failed to create store: {str(e)}")
                raise ValidationException(
                    detail="Failed to create store due to database error"
                )

    async def update_store(
        self, store_id: int, store_data: UpdateStoreSchema
    ) -> Optional[StoreSchema]:
        """Update an existing store"""
        async with AsyncSessionLocal() as session:
            try:
                # Get existing store
                result = await session.execute(
                    select(Store).filter(Store.id == store_id)
                )
                store = result.scalars().first()

                if not store:
                    return None

                # Update store fields
                update_dict = store_data.model_dump(
                    exclude_unset=True, exclude={"tag_ids"}
                )
                for field, value in update_dict.items():
                    setattr(store, field, value)

                # Update tag associations if provided
                if store_data.tag_ids is not None:
                    # Remove existing associations
                    await session.execute(
                        select(StoreTag).filter(StoreTag.store_id == store_id)
                    )
                    existing_tags = (
                        (
                            await session.execute(
                                select(StoreTag).filter(StoreTag.store_id == store_id)
                            )
                        )
                        .scalars()
                        .all()
                    )

                    for tag in existing_tags:
                        await session.delete(tag)

                    # Add new associations
                    for tag_id in store_data.tag_ids:
                        store_tag = StoreTag(store_id=store_id, tag_id=tag_id)
                        session.add(store_tag)

                await session.commit()
                await session.refresh(store)

                return StoreSchema(
                    id=store.id,
                    name=store.name,
                    description=store.description,
                    address=store.address,
                    latitude=store.latitude,
                    longitude=store.longitude,
                    email=store.email,
                    phone=store.phone,
                    is_active=store.is_active,
                    created_at=store.created_at,
                    updated_at=store.updated_at,
                    distance=None,
                )

            except Exception as e:
                await session.rollback()
                self._error_handler.logger.error(f"Failed to update store: {str(e)}")
                raise ValidationException(detail="Failed to update store")

    async def delete_store(self, store_id: int) -> bool:
        """Delete a store"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Store).filter(Store.id == store_id))
            store = result.scalars().first()

            if not store:
                return False

            await session.delete(store)
            await session.commit()
            return True

    # Tag management methods
    async def create_store_tag(
        self,
        name: str,
        tag_type_suffix: str,
        slug: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """Create a new store tag with specific type (e.g., 'features', 'amenities')"""
        from src.api.tags.models import CreateTagSchema

        tag_data = CreateTagSchema(
            tag_type=tag_type_suffix,  # Will become "store_{tag_type_suffix}"
            name=name,
            slug=slug,
            description=description,
        )
        return await self.tag_service.create_tag(tag_data)

    async def create_store_tags(self, tags_data: list[CreateTagSchema]) -> list[Tag]:
        """Create multiple new store tags with specific type (e.g., 'features', 'amenities')"""
        return await self.tag_service.create_tags(tags_data)

    async def get_store_tags(
        self, is_active: bool = True, tag_type_suffix: Optional[str] = None
    ):
        """Get store tags, optionally filtered by type suffix (e.g., 'features', 'amenities')"""
        return await self.tag_service.get_tags_by_type(is_active, tag_type_suffix)

    async def assign_tag_to_store(
        self, store_id: int, tag_id: int, value: Optional[str] = None
    ):
        """Assign a tag to a store using shared TagService"""
        await self.tag_service.assign_tag_to_entity(store_id, tag_id, value)

    async def remove_tag_from_store(self, store_id: int, tag_id: int) -> bool:
        """Remove a tag from a store using shared TagService"""
        return await self.tag_service.remove_tag_from_entity(store_id, tag_id)
