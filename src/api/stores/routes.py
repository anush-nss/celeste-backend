from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.stores.models import (
    CreateStoreSchema,
    StoreLocationResponse,
    StoreQuerySchema,
    StoreSchema,
    StoreTagSchema,
    UpdateStoreSchema,
)
from src.api.stores.service import StoreService
from src.api.tags.models import CreateTagSchema, TagSchema, UpdateTagSchema
from src.config.constants import (
    DEFAULT_SEARCH_RADIUS_KM,
    DEFAULT_STORES_LIMIT,
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MAX_SEARCH_RADIUS_KM,
    MAX_STORES_LIMIT,
    MIN_LATITUDE,
    MIN_LONGITUDE,
    UserRole,
)
from src.dependencies.auth import RoleChecker
from src.shared.exceptions import ResourceNotFoundException
from src.shared.responses import success_response

stores_router = APIRouter(prefix="/stores", tags=["Stores"])
store_service = StoreService()


# ===== STORE TAG CRUD ROUTES (must come before /{id} route) =====


@stores_router.post(
    "/tags",
    summary="Create one or more new store tags",
    response_model=Union[TagSchema, List[TagSchema]],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_store_tags(payload: Union[CreateTagSchema, List[CreateTagSchema]]):
    """Create one or more new tags for stores (Admin only)."""
    is_list = isinstance(payload, list)
    tags_to_create = payload if is_list else [payload]

    if not tags_to_create:
        raise HTTPException(
            status_code=400, detail="Request body cannot be an empty list."
        )

    created_tags = await store_service.create_store_tags(tags_to_create)

    if is_list:
        return success_response(
            [t.model_dump(mode="json") for t in created_tags],
            status_code=status.HTTP_201_CREATED,
        )
    else:
        return success_response(
            created_tags[0].model_dump(mode="json"), status_code=status.HTTP_201_CREATED
        )


@stores_router.get(
    "/tags",
    summary="Get all store tags",
    response_model=List[TagSchema],
)
async def get_store_tags(
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    tag_type_suffix: Optional[str] = Query(
        None, description="Filter by tag type suffix (e.g., 'features', 'amenities')"
    ),
):
    """Get all store tags."""
    tags = await store_service.get_store_tags(
        is_active=is_active if is_active is not None else True,
        tag_type_suffix=tag_type_suffix,
    )
    return success_response(
        [TagSchema.model_validate(tag).model_dump(mode="json") for tag in tags]
    )


@stores_router.get(
    "/tags/types",
    summary="Get all available store tag types",
    response_model=List[str],
)
async def get_store_tag_types():
    """Get all unique tag types for stores only"""
    from src.database.connection import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        from sqlalchemy import distinct
        from sqlalchemy.future import select

        from src.database.models.product import Tag

        query = (
            select(distinct(Tag.tag_type))
            .filter(Tag.is_active, Tag.tag_type.like("store_%"))
            .order_by(Tag.tag_type)
        )
        result = await session.execute(query)
        tag_types = result.scalars().all()

    return success_response(list(tag_types))


@stores_router.get(
    "/tags/{tag_id}",
    summary="Get a store tag by ID",
    response_model=TagSchema,
)
async def get_store_tag_by_id(tag_id: int):
    """Get a specific store tag by ID"""
    tag = await store_service.tag_service.get_tag_by_id(tag_id)

    if not tag:
        raise ResourceNotFoundException(detail=f"Store tag with ID {tag_id} not found")

    return success_response(TagSchema.model_validate(tag).model_dump(mode="json"))


@stores_router.put(
    "/tags/{tag_id}",
    summary="Update a store tag",
    response_model=TagSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_store_tag(tag_id: int, tag_data: UpdateTagSchema):
    """Update an existing store tag"""
    updated_tag = await store_service.tag_service.update_tag(tag_id, tag_data)

    if not updated_tag:
        raise ResourceNotFoundException(detail=f"Store tag with ID {tag_id} not found")

    return success_response(
        TagSchema.model_validate(updated_tag).model_dump(mode="json")
    )


@stores_router.delete(
    "/tags/{tag_id}",
    summary="Delete a store tag",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_store_tag(tag_id: int):
    """Delete a store tag (soft delete by setting is_active to False)"""
    success = await store_service.tag_service.deactivate_tag(tag_id)

    if not success:
        raise ResourceNotFoundException(detail=f"Store tag with ID {tag_id} not found")

    return success_response(
        {"id": tag_id, "message": "Store tag deactivated successfully"}
    )


# ===== STORE ROUTES =====


@stores_router.get(
    "/",
    summary="Get all stores with optional location filtering",
    response_model=StoreLocationResponse,
)
async def get_all_stores(
    latitude: Optional[float] = Query(
        None,
        ge=MIN_LATITUDE,
        le=MAX_LATITUDE,
        description="User latitude for distance calculations",
    ),
    longitude: Optional[float] = Query(
        None,
        ge=MIN_LONGITUDE,
        le=MAX_LONGITUDE,
        description="User longitude for distance calculations",
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
    is_active: Optional[bool] = Query(True, description="Filter by store status"),
    tags: Optional[List[str]] = Query(
        None,
        description="Filter by tags (flexible syntax: 'organic', 'id:5', 'type:amenities', 'value:wifi')",
    ),
    include_distance: Optional[bool] = Query(
        True, description="Include distance calculations (requires lat/lon)"
    ),
    include_tags: Optional[bool] = Query(False, description="Include tag information"),
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
        is_active=is_active,
        tags=tags,
        include_distance=include_distance
        if (latitude is not None and longitude is not None)
        else False,
        include_tags=include_tags,
    )

    # If location AND radius provided, use location-based search for filtering
    # If only location provided, use get_all_stores with distance calculations
    if latitude is not None and longitude is not None and radius is not None:
        stores_list, is_nearby_store = await store_service.get_store_ids_by_location(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius,
            return_full_stores=True,
            include_distance=include_distance,
        )
        # get_store_ids_by_location returns List[Dict[str, Any]], so return it directly
        return success_response(stores_list, status_code=status.HTTP_200_OK)
    else:
        result = await store_service.get_all_stores(query_params)
        # get_all_stores returns StoreLocationResponse, so convert to JSON
        return success_response(
            result.model_dump(mode="json"), status_code=status.HTTP_200_OK
        )


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
    tags: Optional[List[str]] = Query(
        None,
        description="Filter by tags (flexible syntax: 'organic', 'id:5', 'type:amenities', 'value:wifi')",
    ),
    include_distance: Optional[bool] = Query(
        True, description="Include distance calculations"
    ),
    include_tags: Optional[bool] = Query(False, description="Include tag information"),
):
    """
    Optimized endpoint for finding nearby stores.

    - **Required**: latitude, longitude
    - **Efficient**: Uses bounding box filtering for optimal coverage
    - **Sorted**: Results ordered by distance
    """
    result, is_nearby_store = await store_service.get_store_ids_by_location(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius,
        return_full_stores=True,
        include_distance=include_distance,
    )
    return success_response(result, status_code=status.HTTP_200_OK)


@stores_router.get("/{store_id}", summary="Get store by ID", response_model=StoreSchema)
async def get_store_by_id(
    store_id: int,
    include_tags: Optional[bool] = Query(False, description="Include tag information"),
):
    """Get detailed information about a specific store."""
    store = await store_service.get_store_by_id(store_id, include_tags=include_tags)
    if not store:
        raise ResourceNotFoundException(detail=f"Store with ID {store_id} not found")

    return success_response(
        store.model_dump(mode="json"), status_code=status.HTTP_200_OK
    )


@stores_router.get(
    "/{store_id}/distance", summary="Calculate distance to specific store"
)
async def get_store_distance(
    store_id: int,
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

    from src.shared.geo_utils import GeoUtils

    distance = GeoUtils.calculate_distance(
        latitude, longitude, store.latitude, store.longitude
    )

    return success_response(
        {
            "store_id": store_id,
            "store_name": store.name,
            "user_location": {"latitude": latitude, "longitude": longitude},
            "store_location": {
                "latitude": store.latitude,
                "longitude": store.longitude,
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
    new_store = await store_service.create_store(store_data)
    return success_response(
        new_store.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


@stores_router.put(
    "/{store_id}",
    summary="Update a store",
    response_model=StoreSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_store(store_id: int, store_data: UpdateStoreSchema):
    """
    Update an existing store (Admin only).

    - **Location update**: Updates latitude and longitude coordinates if location changes
    - **Partial updates**: Only updates provided fields
    """
    updated_store = await store_service.update_store(store_id, store_data)
    if not updated_store:
        raise ResourceNotFoundException(detail=f"Store with ID {store_id} not found")
    return success_response(
        updated_store.model_dump(mode="json"), status_code=status.HTTP_200_OK
    )


@stores_router.delete(
    "/{store_id}",
    summary="Delete a store",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_store(store_id: int):
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


# Store-Tag assignment routes (tag CRUD is handled by /tags API)


@stores_router.post(
    "/{store_id}/tags/{tag_id}",
    summary="Assign a tag to a store",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def assign_tag_to_store(
    store_id: int,
    tag_id: int,
    value: Optional[str] = Query(None, description="Optional tag value"),
):
    """Assign a tag to a store (Admin only)."""
    await store_service.assign_tag_to_store(store_id, tag_id, value)
    return success_response(
        {"store_id": store_id, "tag_id": tag_id, "message": "Tag assigned successfully"}
    )


@stores_router.delete(
    "/{store_id}/tags/{tag_id}",
    summary="Remove a tag from a store",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def remove_tag_from_store(store_id: int, tag_id: int):
    """Remove a tag from a store (Admin only)."""
    if not await store_service.remove_tag_from_store(store_id, tag_id):
        raise ResourceNotFoundException(
            detail=f"Tag {tag_id} is not assigned to store {store_id}"
        )
    return success_response(
        {"store_id": store_id, "tag_id": tag_id, "message": "Tag removed successfully"}
    )


@stores_router.get(
    "/{store_id}/tags",
    summary="Get all tags assigned to a store",
    response_model=List[StoreTagSchema],
)
async def get_store_tags_by_id(store_id: int):
    """Get all tags assigned to a specific store."""
    store = await store_service.get_store_by_id(store_id, include_tags=True)
    if not store:
        raise ResourceNotFoundException(detail=f"Store with ID {store_id} not found")

    if not store.store_tags:
        return success_response([])

    return success_response(
        [
            StoreTagSchema.model_validate(tag).model_dump(mode="json")
            for tag in store.store_tags
        ]
    )
