from typing import List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.inventory.models import (
    AdjustInventorySchema,
    CreateInventorySchema,
    InventorySchema,
    UpdateInventorySchema,
)
from src.api.inventory.service import InventoryService
from src.config.constants import UserRole
from src.dependencies.auth import RoleChecker, get_current_user
from src.shared.exceptions import ResourceNotFoundException
from src.database.connection import AsyncSessionLocal
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
    return success_response([item.model_dump(mode="json") for item in inventory_items])


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
    return success_response(inventory_item.model_dump(mode="json"))


@inventory_router.post(
    "/",
    summary="Create one or more new inventory items",
    response_model=Union[InventorySchema, List[InventorySchema]],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_inventory(
    payload: Union[CreateInventorySchema, List[CreateInventorySchema]],
):
    """
    Create one or more new inventory items.

    - **product_id**: Product ID
    - **store_id**: Store ID
    - **quantity_available**: Available quantity (must be >= 0)
    - **quantity_reserved**: Reserved quantity (default: 0)
    - **quantity_on_hold**: On-hold quantity (default: 0)
    """
    is_list = isinstance(payload, list)
    inventory_items_to_create = payload if is_list else [payload]

    if not inventory_items_to_create:
        raise HTTPException(
            status_code=400, detail="Request body cannot be an empty list."
        )

    created_inventory = await inventory_service.create_inventory_items(
        inventory_items_to_create
    )

    if is_list:
        return success_response(
            [item.model_dump(mode="json") for item in created_inventory],
            status_code=status.HTTP_201_CREATED,
        )
    else:
        return success_response(
            created_inventory[0].model_dump(mode="json"),
            status_code=status.HTTP_201_CREATED,
        )


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
    return success_response(updated_inventory.model_dump(mode="json"))


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
    async with AsyncSessionLocal() as session:
        updated_inventory = await inventory_service.adjust_inventory_stock(
            adjustment_data, session
        )
        return success_response(updated_inventory.model_dump(mode="json"))


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
