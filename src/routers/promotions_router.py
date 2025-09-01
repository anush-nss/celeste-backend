from fastapi import APIRouter, Depends, status
from typing import Annotated, List
from src.services.promotion_service import PromotionService, PromotionSchema
from src.core.exceptions import ResourceNotFoundException
from src.core.responses import success_response

promotions_router = APIRouter(prefix="/promotions", tags=["Promotions"])
promotion_service = PromotionService()

@promotions_router.get("/", summary="Get all active promotions", response_model=List[PromotionSchema])
async def get_all_promotions():
    promotions = await promotion_service.get_all_promotions()
    return success_response([p.model_dump(mode='json') for p in promotions], status_code=status.HTTP_200_OK)

@promotions_router.get("/{id}", summary="Get a specific promotion", response_model=PromotionSchema)
async def get_promotion_by_id(id: str):
    promotion = await promotion_service.get_promotion_by_id(id)
    if not promotion:
        raise ResourceNotFoundException(detail=f"Promotion with ID {id} not found")
    return success_response(promotion.model_dump(mode='json'), status_code=status.HTTP_200_OK)
