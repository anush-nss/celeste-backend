from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status

from src.api.riders.models import (
    RiderProfileSchema,
    UpdateRiderSchema,
    VerifyRiderSchema,
)
from src.api.riders.services.query_service import RiderQueryService
from src.api.riders.services.rider_service import RiderService
from src.config.constants import UserRole
from src.dependencies.auth import RoleChecker
from src.shared.responses import success_response

riders_router = APIRouter(prefix="/riders", tags=["Riders"])
rider_service = RiderService()
query_service = RiderQueryService()


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
