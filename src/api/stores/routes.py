from fastapi import APIRouter, Depends, status, Query, HTTPException
from typing import Annotated, List, Optional
from src.api.stores.models import (
    StoreSchema,
    CreateStoreSchema,
    UpdateStoreSchema,
    StoreQuerySchema,
    StoreLocationResponse,
    StoreFeatures,
)
from src.api.stores.service import StoreService
from src.dependencies.auth import RoleChecker
from src.config.constants import (
    UserRole,
    DEFAULT_SEARCH_RADIUS_KM,
    MAX_SEARCH_RADIUS_KM,
    DEFAULT_STORES_LIMIT,
    MAX_STORES_LIMIT,
    MIN_LATITUDE,
    MAX_LATITUDE,
    MIN_LONGITUDE,
    MAX_LONGITUDE,
)
from src.shared.exceptions import ResourceNotFoundException
from src.shared.responses import success_response

stores_router = APIRouter(prefix="/stores", tags=["Stores"])
store_service = StoreService()


@stores_router.get("/", summary="Get all stores", response_model=StoreLocationResponse)
async def get_all_stores(
    limit: Optional[int] = Query(
        DEFAULT_STORES_LIMIT,
        ge=1,
        le=MAX_STORES_LIMIT,
        description="Maximum number of stores to return",
    ),
    isActive: Optional[bool] = Query(True, description="Filter by store status"),
    features: Optional[List[StoreFeatures]] = Query(
        None, description="Filter by store features"
    ),
    includeOpenStatus: Optional[bool] = Query(
        False, description="Include open/closed status"
    ),
):
    """
    Get all stores without location-based filtering.

    - **Returns all stores** (with caching)
    - **No distance calculations** - use /stores/nearby for location-based search
    - **Filtering available**: By features, active status, etc.
    - **Performance optimized**: Cached results

    For location-based searches with distances, use the /stores/nearby endpoint.
    """

    # Build query parameters
    query_params = StoreQuerySchema(
        latitude=None,
        longitude=None,
        radius=None,
        limit=limit,
        isActive=isActive,
        features=features,
        includeDistance=False,  # No distances in get_all_stores
        includeOpenStatus=includeOpenStatus,
    )

    try:
        result = await store_service.get_all_stores(query_params)
        return success_response(
            result.model_dump(mode="json"), status_code=status.HTTP_200_OK
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@stores_router.get(
    "/nearby",
    summary="Optimized nearby stores search",
    response_model=StoreLocationResponse,
)
async def get_nearby_stores(
    latitude: float = Query(
        ..., ge=MIN_LATITUDE, le=MAX_LATITUDE, description="User latitude"
    ),
    longitude: float = Query(
        ..., ge=MIN_LONGITUDE, le=MAX_LONGITUDE, description="User longitude"
    ),
    radius: Optional[float] = Query(
        DEFAULT_SEARCH_RADIUS_KM,
        ge=0.1,
        le=MAX_SEARCH_RADIUS_KM,
        description="Search radius in km",
    ),
    limit: Optional[int] = Query(
        DEFAULT_STORES_LIMIT,
        ge=1,
        le=MAX_STORES_LIMIT,
        description="Max stores to return",
    ),
    features: Optional[List[StoreFeatures]] = Query(
        None, description="Required store features"
    ),
    includeDistance: Optional[bool] = Query(
        True, description="Include distance calculations"
    ),
    includeOpenStatus: Optional[bool] = Query(
        True, description="Include business hours status"
    ),
):
    """
    Optimized endpoint for finding nearby stores.

    - **Required**: latitude, longitude
    - **Efficient**: Uses geohash neighbors for optimal coverage
    - **Sorted**: Results ordered by distance
    - **Cached**: Results cached for performance
    """
    query_params = StoreQuerySchema(
        latitude=latitude,
        longitude=longitude,
        radius=radius,
        limit=limit,
        isActive=True,  # Only active stores for nearby search
        features=features,
        includeDistance=includeDistance,
        includeOpenStatus=includeOpenStatus,
    )

    try:
        result = await store_service.get_stores_by_location(query_params)
        return success_response(
            result.model_dump(mode="json"), status_code=status.HTTP_200_OK
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@stores_router.get(
    "/search", summary="Advanced store search", response_model=StoreLocationResponse
)
async def search_stores(
    latitude: Optional[float] = Query(
        None, ge=MIN_LATITUDE, le=MAX_LATITUDE, description="User latitude"
    ),
    longitude: Optional[float] = Query(
        None, ge=MIN_LONGITUDE, le=MAX_LONGITUDE, description="User longitude"
    ),
    radius: Optional[float] = Query(
        DEFAULT_SEARCH_RADIUS_KM,
        ge=0.1,
        le=MAX_SEARCH_RADIUS_KM,
        description="Search radius in km",
    ),
    limit: Optional[int] = Query(
        DEFAULT_STORES_LIMIT,
        ge=1,
        le=MAX_STORES_LIMIT,
        description="Max stores to return",
    ),
    isActive: Optional[bool] = Query(None, description="Filter by active status"),
    features: Optional[List[StoreFeatures]] = Query(
        None, description="Required store features"
    ),
    includeDistance: Optional[bool] = Query(
        True, description="Include distance calculations"
    ),
    includeOpenStatus: Optional[bool] = Query(
        False, description="Include business hours status"
    ),
):
    """
    Advanced search with multiple filter combinations.

    - **Flexible**: Works with or without location
    - **Multi-filter**: Combine location, features, status
    - **Configurable**: Control what data is included in response
    """
    # Validate location parameters if provided
    if (latitude is not None) != (longitude is not None):
        raise HTTPException(
            status_code=400,
            detail="Both latitude and longitude must be provided together",
        )

    query_params = StoreQuerySchema(
        latitude=latitude,
        longitude=longitude,
        radius=radius,
        limit=limit,
        isActive=isActive,
        features=features,
        includeDistance=includeDistance,
        includeOpenStatus=includeOpenStatus,
    )

    try:
        result = await store_service.get_all_stores(query_params)
        return success_response(
            result.model_dump(mode="json"), status_code=status.HTTP_200_OK
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@stores_router.get("/{store_id}", summary="Get store by ID", response_model=StoreSchema)
async def get_store_by_id(
    store_id: str,
    includeInventory: Optional[bool] = Query(
        False, description="Include inventory for the store"
    ),
):
    """Get detailed information about a specific store."""
    store = await store_service.get_store_by_id(store_id)
    if not store:
        raise ResourceNotFoundException(detail=f"Store with ID {store_id} not found")

    # TODO: Implement inventory inclusion logic if needed
    return success_response(
        store.model_dump(mode="json"), status_code=status.HTTP_200_OK
    )


@stores_router.get(
    "/{store_id}/distance", summary="Calculate distance to specific store"
)
async def get_store_distance(
    store_id: str,
    latitude: float = Query(
        ..., ge=MIN_LATITUDE, le=MAX_LATITUDE, description="User latitude"
    ),
    longitude: float = Query(
        ..., ge=MIN_LONGITUDE, le=MAX_LONGITUDE, description="User longitude"
    ),
):
    """
    Calculate distance from user location to specific store.

    - **Precise calculation**: Using Haversine formula
    - **Fast response**: Single store lookup with caching
    """
    store = await store_service.get_store_by_id(store_id)
    if not store:
        raise ResourceNotFoundException(detail=f"Store with ID {store_id} not found")

    if not store.location:
        raise HTTPException(status_code=400, detail="Store location not available")

    from src.shared.geo_utils import GeoUtils

    distance = GeoUtils.haversine_distance(
        latitude, longitude, store.location.latitude, store.location.longitude
    )

    return success_response(
        {
            "store_id": store_id,
            "store_name": store.name,
            "user_location": {"latitude": latitude, "longitude": longitude},
            "store_location": {
                "latitude": store.location.latitude,
                "longitude": store.location.longitude,
            },
            "distance_km": round(distance, 1),
            "store_address": store.address,
        }
    )


@stores_router.post(
    "/",
    summary="Create a new store",
    response_model=StoreSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_store(store_data: CreateStoreSchema):
    """
    Create a new store (Admin only).

    - **Geohash generation**: Automatically generates geohash for location indexing
    - **Cache invalidation**: Clears relevant caches
    - **Validation**: Full input validation with location bounds checking
    """
    try:
        new_store = await store_service.create_store(store_data)
        return success_response(
            new_store.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@stores_router.put(
    "/{store_id}",
    summary="Update a store",
    response_model=StoreSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_store(store_id: str, store_data: UpdateStoreSchema):
    """
    Update an existing store (Admin only).

    - **Geohash update**: Regenerates geohash if location changes
    - **Cache invalidation**: Clears store-specific and general caches
    - **Partial updates**: Only updates provided fields
    """
    try:
        updated_store = await store_service.update_store(store_id, store_data)
        if not updated_store:
            raise ResourceNotFoundException(
                detail=f"Store with ID {store_id} not found"
            )
        return success_response(
            updated_store.model_dump(mode="json"), status_code=status.HTTP_200_OK
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@stores_router.delete(
    "/{store_id}",
    summary="Delete a store",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_store(store_id: str):
    """
    Delete a store (Admin only).

    - **Cache cleanup**: Removes all related cache entries
    - **Soft validation**: Checks if store exists before deletion
    """
    if not await store_service.delete_store(store_id):
        raise ResourceNotFoundException(detail=f"Store with ID {store_id} not found")
    return success_response(
        {"store_id": store_id, "message": "Store deleted successfully"},
        status_code=status.HTTP_200_OK,
    )
