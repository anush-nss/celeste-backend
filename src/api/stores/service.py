from datetime import datetime
from typing import Optional, List, Dict, Any
from google.cloud.firestore_v1.base_query import FieldFilter
from src.shared.database import get_async_db, get_async_collection
from src.shared.geo_utils import GeoUtils
from src.config.cache_config import cache_config
from .cache import stores_cache
from src.api.stores.models import (
    StoreSchema,
    CreateStoreSchema,
    UpdateStoreSchema,
    StoreQuerySchema,
    StoreLocationResponse,
)
from src.config.constants import (
    Collections,
    DEFAULT_SEARCH_RADIUS_KM,
    MAX_SEARCH_RADIUS_KM,
    DEFAULT_STORES_LIMIT,
    MAX_STORES_LIMIT,
    StoreFeatures,
)


class StoreService:
    def __init__(self):
        pass

    async def get_stores_collection(self):
        return await get_async_collection(Collections.STORES)

    async def get_all_stores(
        self, query_params: Optional[StoreQuerySchema] = None
    ) -> StoreLocationResponse:
        """Get all stores without location-based filtering or distances"""

        # Check cache first
        active_only = True  # Default to active only
        if query_params and query_params.isActive is not None:
            active_only = query_params.isActive
        cached_stores = stores_cache.get_all_stores(active_only=active_only)
        if cached_stores is not None:
            stores = [StoreSchema(**store_data) for store_data in cached_stores]
            return self._build_location_response(stores, query_params)

        # Query database
        stores_collection = await self.get_stores_collection()
        query = stores_collection

        # Apply filters
        if query_params:
            if query_params.isActive is not None:
                query = query.where(
                    filter=FieldFilter("isActive", "==", query_params.isActive)
                )

            if query_params.features:
                # Filter by features (stores must have all specified features)
                for feature in query_params.features:
                    query = query.where(
                        filter=FieldFilter("features", "array_contains", feature.value)
                    )

            if query_params.limit:
                query = query.limit(query_params.limit)

        docs = query.stream()
        stores = []
        async for doc in docs:
            doc_data = doc.to_dict()
            if doc_data:
                stores.append(StoreSchema(**doc_data, id=doc.id))

        # Cache results
        stores_data = [store.model_dump() for store in stores]
        stores_cache.set_all_stores(stores_data, active_only=active_only)

        return self._build_location_response(stores, query_params)

    async def get_stores_by_location(
        self, query_params: StoreQuerySchema
    ) -> StoreLocationResponse:
        """Get stores within radius of specified location using geohash optimization"""
        if not query_params.latitude or not query_params.longitude:
            raise ValueError(
                "Latitude and longitude are required for location-based search"
            )

        # Validate coordinates
        if not GeoUtils.validate_coordinates(
            query_params.latitude, query_params.longitude
        ):
            raise ValueError("Invalid coordinates provided")

        radius = query_params.radius or DEFAULT_SEARCH_RADIUS_KM
        radius = min(radius, MAX_SEARCH_RADIUS_KM)

        # Check cache first
        features_list = (
            [f.value for f in query_params.features] if query_params.features else None
        )
        cached_stores = stores_cache.get_location_search(
            query_params.latitude,
            query_params.longitude,
            radius,
            query_params.isActive if query_params.isActive is not None else True,
            features_list,
        )

        if cached_stores is not None:
            stores = [StoreSchema(**store_data) for store_data in cached_stores]
            return self._build_location_response(stores, query_params)

        # Use geohash prefixes for efficient querying
        geohash_prefixes = GeoUtils.get_geohash_prefixes_for_radius(
            query_params.latitude, query_params.longitude, radius
        )

        stores_collection = await self.get_stores_collection()
        all_stores = []

        # Query using geohash prefixes for efficiency
        for prefix in geohash_prefixes:
            query = stores_collection

            # Filter by geohash prefix
            query = query.where(filter=FieldFilter("location.geohash", ">=", prefix))
            query = query.where(
                filter=FieldFilter("location.geohash", "<", prefix + "\uf8ff")
            )

            # Apply other filters
            if query_params.isActive is not None:
                query = query.where(
                    filter=FieldFilter("isActive", "==", query_params.isActive)
                )

            docs = query.stream()
            async for doc in docs:
                doc_data = doc.to_dict()
                if doc_data:
                    all_stores.append({**doc_data, "id": doc.id})

        # Remove duplicates (stores might appear in multiple geohash prefixes)
        unique_stores = {}
        for store in all_stores:
            unique_stores[store["id"]] = store

        # Filter by actual distance and features
        filtered_stores = GeoUtils.filter_by_radius(
            list(unique_stores.values()),
            query_params.latitude,
            query_params.longitude,
            radius,
        )

        # Apply feature filtering if needed
        if query_params.features:
            feature_values = [f.value for f in query_params.features]
            filtered_stores = [
                store
                for store in filtered_stores
                if all(
                    feature in store.get("features", []) for feature in feature_values
                )
            ]

        # Sort by distance
        filtered_stores.sort(key=lambda x: x.get("distance", float("inf")))

        # Apply limit
        limit = query_params.limit or DEFAULT_STORES_LIMIT
        limit = min(limit, MAX_STORES_LIMIT)
        filtered_stores = filtered_stores[:limit]

        # Convert to StoreSchema and add dynamic fields
        stores = []
        for store_data in filtered_stores:
            store = StoreSchema(**store_data)

            # Add dynamic fields based on query parameters
            if query_params.includeDistance:
                store.distance = store_data.get("distance")

            if query_params.includeOpenStatus:
                store.is_open_now, store.next_change = self._calculate_store_status(
                    store
                )

            stores.append(store)

        # Cache results
        stores_data = [store.model_dump() for store in stores]
        stores_cache.set_location_search(
            query_params.latitude,
            query_params.longitude,
            radius,
            stores_data,
            query_params.isActive if query_params.isActive is not None else True,
            features_list,
        )

        return self._build_location_response(stores, query_params, len(filtered_stores))

    def _calculate_store_status(
        self, store: StoreSchema
    ) -> tuple[Optional[bool], Optional[str]]:
        """Calculate if store is currently open and next status change time"""
        if not store.hours:
            return None, None

        # Simplified calculation - in production, consider timezone handling
        from datetime import datetime, time

        now = datetime.now()
        current_day = now.strftime("%A").lower()
        current_time = now.time()

        day_hours = getattr(store.hours, current_day, None)
        if not day_hours or day_hours.closed:
            return False, None

        if not day_hours.open or not day_hours.close:
            return None, None

        try:
            open_time = time.fromisoformat(day_hours.open)
            close_time = time.fromisoformat(day_hours.close)

            is_open = open_time <= current_time <= close_time
            next_change = day_hours.close if is_open else day_hours.open

            return is_open, next_change
        except ValueError:
            return None, None

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

    async def get_store_by_id(self, store_id: str) -> Optional[StoreSchema]:
        # Check cache first
        cached_store = stores_cache.get_store(store_id)
        if cached_store is not None:
            return StoreSchema(**cached_store)

        stores_collection = await self.get_stores_collection()
        doc = await stores_collection.document(store_id).get()
        if doc.exists:
            doc_data = doc.to_dict()
            if doc_data:
                store = StoreSchema(**doc_data, id=doc.id)

                # Cache the store
                stores_cache.set_store(store_id, store.model_dump())

                return store
        return None

    async def create_store(self, store_data: CreateStoreSchema) -> StoreSchema:
        stores_collection = await self.get_stores_collection()
        doc_ref = stores_collection.document()
        store_dict = store_data.model_dump()

        # Generate geohash for location
        if store_data.location:
            geohash = GeoUtils.generate_geohash(
                store_data.location.latitude, store_data.location.longitude
            )
            store_dict["location"]["geohash"] = geohash

        store_dict.update({"created_at": datetime.now(), "updated_at": datetime.now()})

        await doc_ref.set(store_dict)

        # Invalidate cache
        stores_cache.invalidate_stores_cache()

        return StoreSchema(**store_dict, id=doc_ref.id)

    async def update_store(
        self, store_id: str, store_data: UpdateStoreSchema
    ) -> Optional[StoreSchema]:
        stores_collection = await self.get_stores_collection()
        doc_ref = stores_collection.document(store_id)
        store_dict = store_data.model_dump(exclude_unset=True)

        if store_dict:
            # Update geohash if location changed
            if "location" in store_dict and store_dict["location"]:
                location = store_dict["location"]
                if "latitude" in location and "longitude" in location:
                    geohash = GeoUtils.generate_geohash(
                        location["latitude"], location["longitude"]
                    )
                    store_dict["location"]["geohash"] = geohash

            store_dict["updated_at"] = datetime.now()
            await doc_ref.update(store_dict)

            updated_doc = await doc_ref.get()
            if updated_doc.exists:
                updated_data = updated_doc.to_dict()
                if updated_data:
                    # Invalidate cache
                    stores_cache.invalidate_store_cache(store_id)

                    return StoreSchema(**updated_data, id=updated_doc.id)
        return None

    async def delete_store(self, store_id: str) -> bool:
        stores_collection = await self.get_stores_collection()
        doc_ref = stores_collection.document(store_id)
        doc = await doc_ref.get()
        if doc.exists:
            await doc_ref.delete()

            # Invalidate cache
            stores_cache.invalidate_store_cache(store_id)

            return True
        return False
