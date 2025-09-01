from fastapi import APIRouter, Depends, status, Query
from typing import Annotated, List, Optional
from src.models.discount_models import DiscountSchema, CreateDiscountSchema, UpdateDiscountSchema, DiscountQuerySchema
from src.services.discount_service import DiscountService
from src.auth.dependencies import RoleChecker
from src.shared.constants import UserRole
from src.core.exceptions import ResourceNotFoundException
from src.core.responses import success_response

discounts_router = APIRouter(prefix="/discounts", tags=["Discounts"])
discount_service = DiscountService()

@discounts_router.get("/", summary="Get all discounts", response_model=List[DiscountSchema])
async def get_all_discounts(
    availableOnly: Optional[bool] = Query(None, description="Filter for currently available discounts"),
    populateReferences: Optional[bool] = Query(None, description="Populate product and category references"),
):
    query_params = DiscountQuerySchema(
        availableOnly=availableOnly,
        populateReferences=populateReferences
    )
    discounts = await discount_service.get_all_discounts(query_params)
    return success_response([d.model_dump() for d in discounts])

@discounts_router.get("/{id}", summary="Get a discount by ID", response_model=DiscountSchema)
async def get_discount_by_id(id: str):
    discount = await discount_service.get_discount_by_id(id)
    if not discount:
        raise ResourceNotFoundException(detail=f"Discount with ID {id} not found")
    return success_response(discount.model_dump())

@discounts_router.post("/", summary="Create a new discount", response_model=DiscountSchema, status_code=status.HTTP_201_CREATED, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def create_discount(discount_data: CreateDiscountSchema):
    new_discount = await discount_service.create_discount(discount_data)
    return success_response(new_discount.model_dump(), status_code=status.HTTP_201_CREATED)

@discounts_router.put("/{id}", summary="Update a discount", response_model=DiscountSchema, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def update_discount(id: str, discount_data: UpdateDiscountSchema):
    updated_discount = await discount_service.update_discount(id, discount_data)
    if not updated_discount:
        raise ResourceNotFoundException(detail=f"Discount with ID {id} not found")
    return success_response(updated_discount.model_dump())

@discounts_router.delete("/{id}", summary="Delete a discount", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def delete_discount(id: str):
    if not await discount_service.delete_discount(id):
        raise ResourceNotFoundException(detail=f"Discount with ID {id} not found")
    return success_response({"id": id, "message": "Discount deleted successfully"})
