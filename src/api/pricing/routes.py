from fastapi import APIRouter, Depends, status, HTTPException
from typing import List
from src.api.pricing.models import (
    PriceListSchema,
    CreatePriceListSchema,
    UpdatePriceListSchema,
    PriceListLineSchema,
    CreatePriceListLineSchema,
    UpdatePriceListLineSchema,
)
from src.api.pricing.service import PricingService
from src.shared.exceptions import ResourceNotFoundException
from src.shared.responses import success_response

pricing_router = APIRouter(prefix="/pricing", tags=["Pricing"])
pricing_service = PricingService()


# Price List Management (Admin Only)
@pricing_router.get(
    "/price-lists",
    summary="Get all price lists",
    response_model=List[PriceListSchema],
)
async def get_all_price_lists(active_only: bool = False):
    """
    Get all price lists.

    - **active_only**: Filter to show only active price lists
    """
    price_lists = await pricing_service.get_all_price_lists(active_only=active_only)
    return success_response([pl.model_dump(mode="json") for pl in price_lists])


@pricing_router.get(
    "/price-lists/{price_list_id}",
    summary="Get price list by ID",
    response_model=PriceListSchema,
)
async def get_price_list_by_id(price_list_id: str):
    """Get a specific price list by ID"""
    price_list = await pricing_service.get_price_list_by_id(price_list_id)
    if not price_list:
        raise ResourceNotFoundException(
            detail=f"Price list with ID {price_list_id} not found"
        )
    return success_response(price_list.model_dump(mode="json"))


@pricing_router.post(
    "/price-lists",
    summary="Create a new price list",
    response_model=PriceListSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_price_list(price_list_data: CreatePriceListSchema):
    """
    Create a new price list.

    - **name**: Price list name
    - **priority**: Priority order (1 = highest priority)
    - **active**: Whether this price list is active
    - **valid_from**: When this price list becomes valid
    - **valid_until**: When this price list expires (optional)
    """
    new_price_list = await pricing_service.create_price_list(price_list_data)
    return success_response(
        new_price_list.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


@pricing_router.put(
    "/price-lists/{price_list_id}",
    summary="Update a price list",
    response_model=PriceListSchema,
)
async def update_price_list(price_list_id: str, price_list_data: UpdatePriceListSchema):
    """Update an existing price list"""
    updated_price_list = await pricing_service.update_price_list(
        price_list_id, price_list_data
    )
    if not updated_price_list:
        raise ResourceNotFoundException(
            detail=f"Price list with ID {price_list_id} not found"
        )
    return success_response(updated_price_list.model_dump(mode="json"))


@pricing_router.delete(
    "/price-lists/{price_list_id}",
    summary="Delete a price list",
)
async def delete_price_list(price_list_id: str):
    """Delete a price list and all its lines"""
    success = await pricing_service.delete_price_list(price_list_id)
    if not success:
        raise ResourceNotFoundException(
            detail=f"Price list with ID {price_list_id} not found"
        )
    return success_response(
        {"id": price_list_id, "message": "Price list deleted successfully"}
    )


# Price List Lines Management (Admin Only)
@pricing_router.get(
    "/price-lists/{price_list_id}/lines",
    summary="Get price list lines",
    response_model=List[PriceListLineSchema],
)
async def get_price_list_lines(price_list_id: str):
    """Get all lines for a specific price list"""
    # Verify price list exists
    price_list = await pricing_service.get_price_list_by_id(price_list_id)
    if not price_list:
        raise ResourceNotFoundException(
            detail=f"Price list with ID {price_list_id} not found"
        )

    lines = await pricing_service.get_price_list_lines(price_list_id)
    return success_response([line.model_dump(mode="json") for line in lines])


@pricing_router.post(
    "/price-lists/{price_list_id}/lines",
    summary="Add a price list line",
    response_model=PriceListLineSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_price_list_line(
    price_list_id: str, line_data: CreatePriceListLineSchema
):
    """
    Add a new line to a price list.

    - **type**: Type of price list line (product, category, all)
    - **product_id**: Product ID (required if type='product')
    - **category_id**: Category ID (required if type='category')
    - **discount_type**: Discount type (percentage or flat)
    - **amount**: Discount amount
    - **min_product_qty**: Minimum quantity required
    - **max_product_qty**: Maximum quantity allowed (optional)
    """
    # Verify price list exists
    price_list = await pricing_service.get_price_list_by_id(price_list_id)
    if not price_list:
        raise ResourceNotFoundException(
            detail=f"Price list with ID {price_list_id} not found"
        )

    try:
        new_line = await pricing_service.create_price_list_line(
            price_list_id, line_data
        )
        return success_response(
            new_line.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@pricing_router.put(
    "/price-lists/lines/{line_id}",
    summary="Update a price list line",
    response_model=PriceListLineSchema,
)
async def update_price_list_line(line_id: str, line_data: UpdatePriceListLineSchema):
    """Update an existing price list line"""
    updated_line = await pricing_service.update_price_list_line(line_id, line_data)
    if not updated_line:
        raise ResourceNotFoundException(
            detail=f"Price list line with ID {line_id} not found"
        )
    return success_response(updated_line.model_dump(mode="json"))


@pricing_router.delete(
    "/price-lists/lines/{line_id}",
    summary="Delete a price list line",
)
async def delete_price_list_line(line_id: str):
    """Delete a price list line"""
    success = await pricing_service.delete_price_list_line(line_id)
    if not success:
        raise ResourceNotFoundException(
            detail=f"Price list line with ID {line_id} not found"
        )
    return success_response(
        {"id": line_id, "message": "Price list line deleted successfully"}
    )
