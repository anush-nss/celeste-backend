from fastapi import APIRouter, Depends, status, HTTPException
from typing import Annotated, List
from src.api.tiers.models import (
    TierSchema,
    CreateTierSchema,
    UpdateTierSchema,
    UserTierProgressSchema,
    UserTierInfoSchema,
    TierEvaluationSchema,
    BenefitSchema,
    CreateBenefitSchema,
    UpdateBenefitSchema,
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
    "/", summary="Get all customer tiers", response_model=List[TierSchema]
)
async def get_all_tiers(active_only: bool = True):
    """
    Get all customer tiers (public endpoint for displaying tier information).

    - **active_only**: Filter to show only active tiers
    """
    tiers = await tier_service.get_all_tiers(active_only=active_only)
    return success_response([tier.model_dump(mode="json") for tier in tiers])


@router.get(
    "/{tier_id}", summary="Get customer tier by ID", response_model=TierSchema
)
async def get_tier_by_id(tier_id: int):
    """Get a specific customer tier by ID (public endpoint)"""
    tier = await tier_service.get_tier_by_id(tier_id)
    if not tier:
        raise ResourceNotFoundException(
            detail=f"Customer tier with ID {tier_id} not found"
        )
    return success_response(tier.model_dump(mode="json"))


# Admin-only Endpoints
@router.post(
    "/",
    summary="Create a new customer tier",
    response_model=TierSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_tier(tier_data: CreateTierSchema):
    """
    Create a new customer tier (Admin only).

    - **name**: Tier name (e.g., 'Gold', 'Platinum')
    - **description**: Tier description
    - **sort_order**: Sorting order
    - **is_active**: Is the tier active
    - **min_total_spent**: Minimum total spent to achieve tier
    - **min_orders_count**: Minimum number of orders to achieve tier
    """
    try:
        new_tier = await tier_service.create_tier(tier_data)
        return success_response(
            new_tier.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put(
    "/{tier_id}",
    summary="Update a customer tier",
    response_model=TierSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_tier(tier_id: int, tier_data: UpdateTierSchema):
    """Update an existing customer tier (Admin only)"""
    updated_tier = await tier_service.update_tier(tier_id, tier_data)
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
async def delete_tier(tier_id: int):
    """Delete a customer tier (Admin only)"""
    success = await tier_service.delete_tier(tier_id)
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
    response_model=List[TierSchema],
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

    tier_info = await tier_service.get_user_tier_info(user_id)
    return success_response(tier_info.model_dump(mode="json"))


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

    progress = await tier_service.get_user_tier_progress(user_id)
    return success_response(progress.model_dump(mode="json"))


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
    tier_info = await tier_service.get_user_tier_info(user_id)
    return success_response(tier_info.model_dump(mode="json"))


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
async def manually_update_user_tier(user_id: str, new_tier_id: int):
    """Manually update a user's tier (Admin only)"""
    success = await tier_service.update_user_tier(user_id, new_tier_id)
    if not success:
        raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")
    return success_response(
        {
            "user_id": user_id,
            "new_tier_id": new_tier_id,
            "message": "User tier updated successfully",
        }
    )


# Benefits CRUD Endpoints (Admin only)
@router.get(
    "/benefits/",
    summary="Get all benefits",
    response_model=List[BenefitSchema],
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def get_all_benefits(active_only: bool = False):
    """
    Get all benefits (Admin only).

    - **active_only**: Filter to show only active benefits
    """
    benefits = await tier_service.get_all_benefits(active_only=active_only)
    return success_response([benefit.model_dump(mode="json") for benefit in benefits])


@router.get(
    "/benefits/{benefit_id}",
    summary="Get benefit by ID",
    response_model=BenefitSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def get_benefit_by_id(benefit_id: int):
    """Get a specific benefit by ID (Admin only)"""
    benefit = await tier_service.get_benefit_by_id(benefit_id)
    if not benefit:
        raise ResourceNotFoundException(
            detail=f"Benefit with ID {benefit_id} not found"
        )
    return success_response(benefit.model_dump(mode="json"))


@router.post(
    "/benefits/",
    summary="Create a new benefit",
    response_model=BenefitSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_benefit(benefit_data: CreateBenefitSchema):
    """
    Create a new benefit (Admin only).

    - **benefit_type**: Type of benefit (order_discount or delivery_discount)
    - **discount_type**: Type of discount (flat or percentage)
    - **discount_value**: Discount amount or percentage
    - **max_discount_amount**: Maximum discount amount (for percentage discounts)
    - **min_order_value**: Minimum order value required
    - **min_items**: Minimum number of items required
    - **is_active**: Whether the benefit is active
    """
    try:
        new_benefit = await tier_service.create_benefit(benefit_data)
        return success_response(
            new_benefit.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put(
    "/benefits/{benefit_id}",
    summary="Update a benefit",
    response_model=BenefitSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_benefit(benefit_id: int, benefit_data: UpdateBenefitSchema):
    """Update an existing benefit (Admin only)"""
    updated_benefit = await tier_service.update_benefit(benefit_id, benefit_data)
    if not updated_benefit:
        raise ResourceNotFoundException(
            detail=f"Benefit with ID {benefit_id} not found"
        )
    return success_response(updated_benefit.model_dump(mode="json"))


@router.delete(
    "/benefits/{benefit_id}",
    summary="Delete a benefit",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_benefit(benefit_id: int):
    """Delete a benefit (Admin only)"""
    success = await tier_service.delete_benefit(benefit_id)
    if not success:
        raise ResourceNotFoundException(
            detail=f"Benefit with ID {benefit_id} not found"
        )
    return success_response(
        {"id": benefit_id, "message": "Benefit deleted successfully"}
    )


# Tier-Benefit Association Endpoints (Admin only)
@router.get(
    "/{tier_id}/benefits",
    summary="Get benefits for a tier",
    response_model=List[BenefitSchema],
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def get_tier_benefits(tier_id: int):
    """Get all benefits associated with a specific tier (Admin only)"""
    benefits = await tier_service.get_tier_benefits(tier_id)
    return success_response([benefit.model_dump(mode="json") for benefit in benefits])


@router.post(
    "/{tier_id}/benefits/{benefit_id}",
    summary="Associate benefit with tier",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def associate_benefit_to_tier(tier_id: int, benefit_id: int):
    """Associate a benefit with a tier (Admin only)"""
    is_new = await tier_service.associate_benefit_to_tier(tier_id, benefit_id)
    if is_new:
        return success_response({
            "tier_id": tier_id,
            "benefit_id": benefit_id,
            "message": "Benefit associated with tier successfully"
        }, status_code=status.HTTP_201_CREATED)


@router.delete(
    "/{tier_id}/benefits/{benefit_id}",
    summary="Remove benefit from tier",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def remove_benefit_from_tier(tier_id: int, benefit_id: int):
    """Remove a benefit from a tier (Admin only)"""
    success = await tier_service.remove_benefit_from_tier(tier_id, benefit_id)
    if not success:
        raise ResourceNotFoundException(
            detail="Benefit association not found or tier/benefit doesn't exist"
        )
    return success_response({
        "tier_id": tier_id,
        "benefit_id": benefit_id,
        "message": "Benefit removed from tier successfully"
    })
