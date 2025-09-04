from fastapi import APIRouter, Depends, status, HTTPException
from typing import Annotated, List
from src.api.tiers.models import (
    CustomerTierSchema,
    CreateCustomerTierSchema,
    UpdateCustomerTierSchema,
    UserTierProgressSchema,
    UserTierInfoSchema,
    TierEvaluationSchema,
)
from src.api.auth.models import DecodedToken
from src.api.tiers.service import TierService
from src.dependencies.auth import get_current_user, RoleChecker
from src.config.constants import UserRole
from src.shared.exceptions import ResourceNotFoundException
from src.shared.responses import success_response

router = APIRouter(prefix="/tiers", tags=["Customer Tiers"])
tier_service = TierService()


# Public Endpoints (No authentication required)
@router.get(
    "/", summary="Get all customer tiers", response_model=List[CustomerTierSchema]
)
async def get_all_customer_tiers(active_only: bool = True):
    """
    Get all customer tiers (public endpoint for displaying tier information).

    - **active_only**: Filter to show only active tiers
    """
    tiers = await tier_service.get_all_customer_tiers(active_only=active_only)
    return success_response([tier.model_dump(mode="json") for tier in tiers])


@router.get(
    "/{tier_id}", summary="Get customer tier by ID", response_model=CustomerTierSchema
)
async def get_customer_tier_by_id(tier_id: str):
    """Get a specific customer tier by ID (public endpoint)"""
    tier = await tier_service.get_customer_tier_by_id(tier_id)
    if not tier:
        raise ResourceNotFoundException(
            detail=f"Customer tier with ID {tier_id} not found"
        )
    return success_response(tier.model_dump(mode="json"))


# Admin-only Endpoints
@router.post(
    "/",
    summary="Create a new customer tier",
    response_model=CustomerTierSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_customer_tier(tier_data: CreateCustomerTierSchema):
    """
    Create a new customer tier (Admin only).

    - **name**: Tier name (e.g., 'Gold', 'Platinum')
    - **tier_code**: Tier code enum value
    - **level**: Tier level (higher = better)
    - **requirements**: Requirements to achieve this tier
    - **benefits**: Benefits of this tier
    - **icon_url**: URL to tier icon (optional)
    - **color**: Tier color (hex code)
    """
    try:
        new_tier = await tier_service.create_customer_tier(tier_data)
        return success_response(
            new_tier.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put(
    "/{tier_id}",
    summary="Update a customer tier",
    response_model=CustomerTierSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_customer_tier(tier_id: str, tier_data: UpdateCustomerTierSchema):
    """Update an existing customer tier (Admin only)"""
    updated_tier = await tier_service.update_customer_tier(tier_id, tier_data)
    if not updated_tier:
        raise ResourceNotFoundException(
            detail=f"Customer tier with ID {tier_id} not found"
        )
    return success_response(updated_tier.model_dump(mode="json"))


@router.delete(
    "/{tier_id}",
    summary="Delete a customer tier",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_customer_tier(tier_id: str):
    """Delete a customer tier (Admin only)"""
    success = await tier_service.delete_customer_tier(tier_id)
    if not success:
        raise ResourceNotFoundException(
            detail=f"Customer tier with ID {tier_id} not found"
        )
    return success_response(
        {"id": tier_id, "message": "Customer tier deleted successfully"}
    )


@router.post(
    "/initialize-defaults",
    summary="Initialize default customer tiers",
    response_model=List[CustomerTierSchema],
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def initialize_default_tiers():
    """Initialize default customer tiers (Admin only)"""
    tiers = await tier_service.initialize_default_tiers()
    return success_response([tier.model_dump(mode="json") for tier in tiers])


# User-specific Endpoints (Require authentication)
@router.get(
    "/users/me/tier",
    summary="Get current user's tier information",
    response_model=UserTierInfoSchema,
)
async def get_my_tier_info(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    """Get complete tier information for the current user"""
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    try:
        tier_info = await tier_service.get_user_tier_info(user_id)
        return success_response(tier_info.model_dump(mode="json"))
    except ValueError as e:
        raise ResourceNotFoundException(detail=str(e))


@router.get(
    "/users/me/tier-progress",
    summary="Get current user's tier progress",
    response_model=UserTierProgressSchema,
)
async def get_my_tier_progress(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    """Get the current user's tier and progress towards next tier"""
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    try:
        progress = await tier_service.get_user_tier_progress(user_id)
        return success_response(progress.model_dump(mode="json"))
    except ValueError as e:
        raise ResourceNotFoundException(detail=str(e))


@router.post(
    "/users/me/evaluate-tier",
    summary="Evaluate current user's tier eligibility",
    response_model=TierEvaluationSchema,
)
async def evaluate_my_tier(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    """Evaluate what tier the current user should be in based on their activity"""
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    evaluation = await tier_service.evaluate_user_tier(user_id)
    return success_response(evaluation.model_dump(mode="json"))


@router.post(
    "/users/me/auto-update-tier",
    summary="Auto-evaluate and update current user's tier",
    response_model=TierEvaluationSchema,
)
async def auto_update_my_tier(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    """Automatically evaluate and update the current user's tier based on their activity"""
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    evaluation = await tier_service.auto_evaluate_and_update_user_tier(user_id)
    return success_response(evaluation.model_dump(mode="json"))


# Admin Endpoints for User Tier Management
@router.get(
    "/users/{user_id}/tier",
    summary="Get user's tier information",
    response_model=UserTierInfoSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def get_user_tier_info(user_id: str):
    """Get complete tier information for a specific user (Admin only)"""
    try:
        tier_info = await tier_service.get_user_tier_info(user_id)
        return success_response(tier_info.model_dump(mode="json"))
    except ValueError as e:
        raise ResourceNotFoundException(detail=str(e))


@router.post(
    "/users/{user_id}/evaluate-tier",
    summary="Evaluate user's tier eligibility",
    response_model=TierEvaluationSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def evaluate_user_tier(user_id: str):
    """Evaluate what tier a specific user should be in (Admin only)"""
    evaluation = await tier_service.evaluate_user_tier(user_id)
    return success_response(evaluation.model_dump(mode="json"))


@router.post(
    "/users/{user_id}/auto-update-tier",
    summary="Auto-evaluate and update user's tier",
    response_model=TierEvaluationSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def auto_update_user_tier(user_id: str):
    """Automatically evaluate and update a specific user's tier (Admin only)"""
    evaluation = await tier_service.auto_evaluate_and_update_user_tier(user_id)
    return success_response(evaluation.model_dump(mode="json"))


@router.put(
    "/users/{user_id}/tier",
    summary="Manually update user's tier",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def manually_update_user_tier(user_id: str, new_tier: str):
    """Manually update a user's tier (Admin only)"""
    success = await tier_service.update_user_tier(user_id, new_tier)
    if not success:
        raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")
    return success_response(
        {
            "user_id": user_id,
            "new_tier": new_tier,
            "message": "User tier updated successfully",
        }
    )
