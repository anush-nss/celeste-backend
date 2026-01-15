from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status

from src.api.riders.models import (
    RiderProfileSchema,
    UpdateRiderSchema,
    VerifyRiderSchema,
    RiderStatusUpdateSchema,
)
from src.api.riders.services.query_service import RiderQueryService
from src.api.riders.services.rider_service import RiderService
from src.config.constants import UserRole, OrderStatus
from src.dependencies.auth import RoleChecker
from src.shared.responses import success_response

riders_router = APIRouter(prefix="/riders", tags=["Riders"])
rider_service = RiderService()
query_service = RiderQueryService()

from fastapi import HTTPException
from src.api.orders.models import OrderSchema, PaginatedOrdersResponse
from src.api.orders.service import OrderService
from src.dependencies.auth import get_current_user

order_service = OrderService()


# ===== ADMIN ENDPOINTS =====




@riders_router.get(
    "/",
    summary="List all riders (Admin only)",
    response_model=List[RiderProfileSchema],
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def get_riders(
    store_id: Optional[int] = Query(None, description="Filter riders by store assignment"),
):
    """List all riders, optionally filtered by store."""
    riders = await query_service.get_riders(store_id=store_id)
    return success_response([r.model_dump(mode="json") for r in riders])


@riders_router.get(
    "/me/orders",
    summary="Get assigned orders for current rider",
    response_model=PaginatedOrdersResponse,
    response_model_exclude={"orders": {"__all__": {"items"}}},
    dependencies=[Depends(RoleChecker([UserRole.RIDER]))],
)
async def get_rider_orders(
    status: Optional[List[OrderStatus]] = Query(None, description="Filter orders by status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user=Depends(get_current_user)
):
    """List all orders assigned to the authenticated rider."""
    # 1. Get Rider Profile
    rider = await query_service.get_rider_by_user_id(current_user.uid)
    if not rider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rider profile not found for this user."
        )

    # 2. Get Assigned Orders
    result = await order_service.get_orders_paginated(
        rider_id=rider.id,
        status=[s.value for s in status] if status else None,
        page=page,
        limit=limit,
        include_products=False,
        include_stores=True,
        include_addresses=True
    )
    
    # Manually validate/dump orders in list to JSON
    orders_data = [o.model_dump(mode="json") for o in result["orders"]]
    
    return success_response({
        "orders": orders_data,
        "pagination": result["pagination"]
    })


@riders_router.get(
    "/me",
    summary="Get current rider profile",
    response_model=RiderProfileSchema,
    dependencies=[Depends(RoleChecker([UserRole.RIDER]))],
)
async def get_rider_profile(current_user=Depends(get_current_user)):
    """Get full profile details for the authenticated rider."""
    rider = await query_service.get_rider_by_user_id(current_user.uid)
    if not rider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rider profile not found."
        )
    return success_response(rider.model_dump(mode="json"))


@riders_router.patch(
    "/me/status",
    summary="Update rider online status",
    response_model=RiderProfileSchema,
    dependencies=[Depends(RoleChecker([UserRole.RIDER]))],
)
async def update_rider_status(
    status_update: RiderStatusUpdateSchema,
    current_user=Depends(get_current_user)
):
    """Toggle rider online/offline status."""
    rider = await query_service.get_rider_by_user_id(current_user.uid)
    if not rider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rider profile not found."
        )
    
    updated_rider = await rider_service.update_rider_status(rider.id, status_update.is_online)
    return success_response(RiderProfileSchema.model_validate(updated_rider).model_dump(mode="json"))


@riders_router.get(
    "/me/stores",
    summary="Get assigned stores",
    # response_model=List[StoreSchema], # TODO: Add StoreSchema if strict validation needed
    dependencies=[Depends(RoleChecker([UserRole.RIDER]))],
)
async def get_rider_stores(current_user=Depends(get_current_user)):
    """List all stores assigned to the authenticated rider."""
    rider = await query_service.get_rider_by_user_id(current_user.uid)
    if not rider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rider profile not found."
        )
    
    stores = await rider_service.get_assigned_stores(rider.id)
    # Convert store models to dicts/schema as needed. 
    # Store model has to_dict or pydantic validation.
    # For now returning list of dicts manually or via model_dump if they were schemas. 
    # Since they are alchemy models:
    store_list = [
        {
            "id": s.id,
            "name": s.name,
            "address": s.address,
            "phone": s.phone,
            "latitude": s.latitude,
            "longitude": s.longitude
        } for s in stores
    ]
    return success_response(store_list)


@riders_router.put(
    "/{rider_id}",
    summary="Update rider profile (Admin only)",
    response_model=RiderProfileSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_rider(rider_id: int, payload: UpdateRiderSchema):
    """Update an existing rider profile."""
    rider = await rider_service.update_rider(rider_id, payload)
    return success_response(rider.model_dump(mode="json"))


@riders_router.post(
    "/{rider_id}/stores/{store_id}",
    summary="Assign user to a store (Admin only)",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def assign_rider_to_store(rider_id: int, store_id: int):
    """Assign a rider to a specific store."""
    await rider_service.assign_rider_to_store(rider_id, store_id)
    return success_response({"message": "Rider assigned to store successfully"})


@riders_router.delete(
    "/{rider_id}/stores/{store_id}",
    summary="Remove rider from a store (Admin only)",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def remove_rider_from_store(rider_id: int, store_id: int):
    """Remove a rider from a specific store."""
    await rider_service.remove_rider_from_store(rider_id, store_id)
    return success_response({"message": "Rider removed from store successfully"})


# ===== PUBLIC/AUTH ENDPOINTS =====


@riders_router.post(
    "/verify",
    summary="Verify if a phone number belongs to a registered rider",
    response_model=dict,
)
async def verify_rider(payload: VerifyRiderSchema):
    """
    Check if the phone number is in the Admin-created allowlist.
    Returns { "valid": true, "name": "..." } if found, else { "valid": false }.
    """
    rider = await query_service.get_rider_by_phone(payload.phone)
    if rider and rider.is_active:
        return success_response({"valid": True, "name": rider.name})
    return success_response({"valid": False})
