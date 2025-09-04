from fastapi import APIRouter, Depends, status, Query
from typing import Annotated, List, Optional
from src.api.stores.models import StoreSchema, CreateStoreSchema, UpdateStoreSchema
from src.api.stores.service import StoreService
from src.dependencies.auth import RoleChecker
from src.config.constants import UserRole
from src.shared.exceptions import ResourceNotFoundException
from src.shared.responses import success_response

stores_router = APIRouter(prefix="/stores", tags=["Stores"])
store_service = StoreService()


@stores_router.get("/", summary="Get all stores", response_model=List[StoreSchema])
async def get_all_stores(
    includeInventory: Optional[bool] = Query(
        None, description="Include inventory for each store"
    ),
):
    # TODO: Implement logic to include inventory if requested
    stores = await store_service.get_all_stores()
    return success_response(
        [s.model_dump(mode="json") for s in stores], status_code=status.HTTP_200_OK
    )


@stores_router.get("/{id}", summary="Get a store by ID", response_model=StoreSchema)
async def get_store_by_id(
    id: str,
    includeInventory: Optional[bool] = Query(
        None, description="Include inventory for the store"
    ),
):
    store = await store_service.get_store_by_id(id)
    if not store:
        raise ResourceNotFoundException(detail=f"Store with ID {id} not found")
    # TODO: Implement logic to include inventory if requested
    return success_response(
        store.model_dump(mode="json"), status_code=status.HTTP_200_OK
    )


@stores_router.post(
    "/",
    summary="Create a new store",
    response_model=StoreSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_store(store_data: CreateStoreSchema):
    new_store = await store_service.create_store(store_data)
    return success_response(
        new_store.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


@stores_router.put(
    "/{id}",
    summary="Update a store",
    response_model=StoreSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_store(id: str, store_data: UpdateStoreSchema):
    updated_store = await store_service.update_store(id, store_data)
    if not updated_store:
        raise ResourceNotFoundException(detail=f"Store with ID {id} not found")
    return success_response(
        updated_store.model_dump(mode="json"), status_code=status.HTTP_200_OK
    )


@stores_router.delete(
    "/{id}",
    summary="Delete a store",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_store(id: str):
    if not await store_service.delete_store(id):
        raise ResourceNotFoundException(detail=f"Store with ID {id} not found")
    return success_response(
        {"id": id, "message": "Store deleted successfully"},
        status_code=status.HTTP_200_OK,
    )
