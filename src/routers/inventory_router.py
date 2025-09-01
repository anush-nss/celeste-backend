from fastapi import APIRouter, Depends, status, Query
from typing import Annotated, List, Optional
from src.models.inventory_models import InventorySchema, CreateInventorySchema, UpdateInventorySchema
from src.services.inventory_service import InventoryService
from src.auth.dependencies import RoleChecker, get_current_user
from src.shared.constants import UserRole
from src.core.exceptions import ResourceNotFoundException
from src.core.responses import success_response

inventory_router = APIRouter(prefix="/inventory", tags=["Inventory"])
inventory_service = InventoryService()

@inventory_router.get("/", summary="Get all inventory items", response_model=List[InventorySchema], dependencies=[Depends(get_current_user)])
async def get_all_inventory(
    productId: Optional[str] = Query(None, description="Filter by product ID"),
    storeId: Optional[str] = Query(None, description="Filter by store ID"),
):
    query_params = {}
    if productId is not None:
        query_params["product_id"] = productId
    if storeId is not None:
        query_params["store_id"] = storeId
    inventory_items = await inventory_service.get_all_inventory(**query_params)
    return success_response([item.model_dump() for item in inventory_items])

@inventory_router.get("/{id}", summary="Get an inventory item by ID", response_model=InventorySchema, dependencies=[Depends(get_current_user)])
async def get_inventory_by_id(id: str):
    inventory_item = await inventory_service.get_inventory_by_id(id)
    if not inventory_item:
        raise ResourceNotFoundException(detail=f"Inventory item with ID {id} not found")
    return success_response(inventory_item.model_dump())

@inventory_router.post("/", summary="Create a new inventory item", response_model=InventorySchema, status_code=status.HTTP_201_CREATED, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def create_inventory(inventory_data: CreateInventorySchema):
    new_inventory = await inventory_service.create_inventory(inventory_data)
    return success_response(new_inventory.model_dump(), status_code=status.HTTP_201_CREATED)

@inventory_router.put("/{id}", summary="Update an inventory item", response_model=InventorySchema, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def update_inventory(id: str, inventory_data: UpdateInventorySchema):
    updated_inventory = await inventory_service.update_inventory(id, inventory_data)
    if not updated_inventory:
        raise ResourceNotFoundException(detail=f"Inventory item with ID {id} not found")
    return success_response(updated_inventory.model_dump())

@inventory_router.delete("/{id}", summary="Delete an inventory item", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def delete_inventory(id: str):
    if not await inventory_service.delete_inventory(id):
        raise ResourceNotFoundException(detail=f"Inventory item with ID {id} not found")
    return success_response({"id": id, "message": "Inventory item deleted successfully"})
