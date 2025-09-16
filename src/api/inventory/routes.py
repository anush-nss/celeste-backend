from fastapi import APIRouter, Depends, status, Query
from typing import List, Optional
from src.api.inventory.models import (
    InventorySchema,
    CreateInventorySchema,
    UpdateInventorySchema,
    AdjustInventorySchema,
)
from src.api.inventory.service import InventoryService
from src.dependencies.auth import RoleChecker, get_current_user
from src.config.constants import UserRole
from src.shared.exceptions import ResourceNotFoundException
from src.shared.responses import success_response

inventory_router = APIRouter(prefix="/inventory", tags=["Inventory"])
inventory_service = InventoryService()


@inventory_router.get(
    "/",
    summary="Get all inventory items",
    response_model=List[InventorySchema],
    dependencies=[Depends(get_current_user)],
)
async def get_all_inventory(
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    store_id: Optional[int] = Query(None, description="Filter by store ID"),
):
    inventory_items = await inventory_service.get_all_inventory(
        product_id=product_id, store_id=store_id
    )
    return success_response(inventory_items)


@inventory_router.get(
    "/{inventory_id}",
    summary="Get an inventory item by ID",
    response_model=InventorySchema,
    dependencies=[Depends(get_current_user)],
)
async def get_inventory_by_id(inventory_id: int):
    inventory_item = await inventory_service.get_inventory_by_id(inventory_id)
    if not inventory_item:
        raise ResourceNotFoundException(
            detail=f"Inventory item with ID {inventory_id} not found"
        )
    return success_response(inventory_item)


@inventory_router.post(
    "/",
    summary="Create a new inventory item",
    response_model=InventorySchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_inventory(inventory_data: CreateInventorySchema):
    new_inventory = await inventory_service.create_inventory(inventory_data)
    return success_response(new_inventory, status_code=status.HTTP_201_CREATED)


@inventory_router.put(
    "/{inventory_id}",
    summary="Update an inventory item",
    response_model=InventorySchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_inventory(inventory_id: int, inventory_data: UpdateInventorySchema):
    updated_inventory = await inventory_service.update_inventory(
        inventory_id, inventory_data
    )
    return success_response(updated_inventory)


@inventory_router.post(
    "/adjust",
    summary="Adjust inventory stock levels",
    response_model=InventorySchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def adjust_inventory(adjustment_data: AdjustInventorySchema):
    """
    Atomically adjust inventory levels for a product at a specific store.
    - `available_change`: Change in the number of items available for sale.
    - `on_hold_change`: Change in the number of items held for pending orders.
    - `reserved_change`: Change in the number of items reserved for confirmed orders.
    """
    updated_inventory = await inventory_service.adjust_inventory_stock(adjustment_data)
    return success_response(updated_inventory)


@inventory_router.delete(
    "/{inventory_id}",
    summary="Delete an inventory item",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_inventory(inventory_id: int):
    if not await inventory_service.delete_inventory(inventory_id):
        raise ResourceNotFoundException(
            detail=f"Inventory item with ID {inventory_id} not found"
        )
    return success_response(None, status_code=status.HTTP_204_NO_CONTENT)
