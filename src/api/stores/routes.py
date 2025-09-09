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


@stores_router.get("/", summary="Get all stores with optional location filtering", response_model=StoreLocationResponse)
async def get_all_stores(
    latitude: Optional[float] = Query(
        None, ge=MIN_LATITUDE, le=MAX_LATITUDE, description="User latitude for distance calculations"
    ),
    longitude: Optional[float] = Query(
        None, ge=MIN_LONGITUDE, le=MAX_LONGITUDE, description="User longitude for distance calculations"
    ),
    radius: Optional[float] = Query(
        None,
        ge=0.1,
        le=MAX_SEARCH_RADIUS_KM,
        description="Search radius in km for filtering (optional, requires lat/lon)",
    ),
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
    includeDistance: Optional[bool] = Query(
        True, description="Include distance calculations (requires lat/lon)"
    ),
    includeOpenStatus: Optional[bool] = Query(
        False, description="Include open/closed status"
    ),
):
    """
    Get all stores with optional location-based filtering and distance calculations.

    - **Flexible**: Works with or without location parameters
    - **Multi-filter**: Combine location, features, status
    - **Configurable**: Control what data is included in response
    - **Performance optimized**: Cached results for non-location queries
    
    If latitude/longitude provided, acts like nearby search with radius filtering.
    If no location provided, returns all stores (cached for performance).
    """

    # Validate location parameters if provided
    if (latitude is not None) != (longitude is not None):
        raise HTTPException(
            status_code=400,
            detail="Both latitude and longitude must be provided together",
        )

    # Build query parameters
    query_params = StoreQuerySchema(
        latitude=latitude,
        longitude=longitude,
        radius=radius,
        limit=limit,
        isActive=isActive,
        features=features,
        includeDistance=includeDistance if (latitude is not None and longitude is not None) else False,
        includeOpenStatus=includeOpenStatus,
    )

    try:
        # If location AND radius provided, use location-based search for filtering
        # If only location provided, use get_all_stores with distance calculations
        if latitude is not None and longitude is not None and radius is not None:
            result = await store_service.get_stores_by_location(query_params)
        else:
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
    - **Efficient**: Uses bounding box filtering for optimal coverage
    - **Sorted**: Results ordered by distance
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

    distance = GeoUtils.calculate_distance(
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

    - **Location storage**: Stores latitude and longitude coordinates
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

    - **Location update**: Updates latitude and longitude coordinates if location changes
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

    - **Soft validation**: Checks if store exists before deletion
    """
    if not await store_service.delete_store(store_id):
        raise ResourceNotFoundException(detail=f"Store with ID {store_id} not found")
    return success_response(
        {"store_id": store_id, "message": "Store deleted successfully"},
        status_code=status.HTTP_200_OK,
    )
