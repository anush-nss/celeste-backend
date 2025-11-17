from typing import List, Optional

from fastapi import APIRouter, Depends, status

from src.api.promotions.models import (
    CreatePromotionSchema,
    PromotionSchema,
    UpdatePromotionSchema,
)
from src.api.promotions.service import PromotionService
from src.config.constants import PromotionType, UserRole
from src.dependencies.auth import RoleChecker
from src.shared.responses import success_response

promotions_router = APIRouter(prefix="/promotions", tags=["Promotions"])
promotion_service = PromotionService()


# Public endpoints
@promotions_router.get(
    "/active/random",
    summary="Get a single random active promotion",
    response_model=Optional[PromotionSchema],
)
async def get_random_active_promotion(
    promotion_type: PromotionType,
    product_id: Optional[int] = None,
    category_id: Optional[int] = None,
):
    promotion = await promotion_service.get_active_promotion_random(
        promotion_type, product_id, category_id
    )
    return success_response(promotion.model_dump(mode="json") if promotion else None)


@promotions_router.get(
    "/active/all",
    summary="Get all active promotions",
    response_model=List[PromotionSchema],
)
async def get_all_active_promotions(
    promotion_type: PromotionType,
    product_id: Optional[int] = None,
    category_id: Optional[int] = None,
):
    promotions = await promotion_service.get_active_promotions_all(
        promotion_type, product_id, category_id
    )
    return success_response([p.model_dump(mode="json") for p in promotions])


# Admin endpoints
@promotions_router.post(
    "/",
    summary="Create a new promotion (Admin only)",
    response_model=PromotionSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_promotion(promotion_data: CreatePromotionSchema):
    new_promotion = await promotion_service.create_promotion(promotion_data)
    return success_response(
        new_promotion.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


@promotions_router.get(
    "/",
    summary="List all promotions (Admin only)",
    response_model=List[PromotionSchema],
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def get_all_promotions():
    promotions = await promotion_service.get_all_promotions()
    return success_response([p.model_dump(mode="json") for p in promotions])


@promotions_router.get(
    "/{promotion_id}",
    summary="Get a specific promotion (Admin only)",
    response_model=PromotionSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def get_promotion_by_id(promotion_id: int):
    promotion = await promotion_service.get_promotion_by_id(promotion_id)
    return success_response(promotion.model_dump(mode="json"))


@promotions_router.put(
    "/{promotion_id}",
    summary="Update a promotion (Admin only)",
    response_model=PromotionSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_promotion(promotion_id: int, promotion_data: UpdatePromotionSchema):
    updated_promotion = await promotion_service.update_promotion(
        promotion_id, promotion_data
    )
    return success_response(updated_promotion.model_dump(mode="json"))


@promotions_router.delete(
    "/{promotion_id}",
    summary="Delete a promotion (Admin only)",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_promotion(promotion_id: int):
    await promotion_service.delete_promotion(promotion_id)
    return success_response(None, status_code=status.HTTP_204_NO_CONTENT)
