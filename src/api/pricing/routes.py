from fastapi import APIRouter, Depends, status, HTTPException
from typing import List, Optional
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
async def get_price_list_by_id(price_list_id: int):
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
async def update_price_list(price_list_id: int, price_list_data: UpdatePriceListSchema):
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
async def delete_price_list(price_list_id: int):
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
async def get_price_list_lines(price_list_id: int):
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
    price_list_id: int, line_data: CreatePriceListLineSchema
):
    """
    Add a new line to a price list.

    - **product_id**: Product ID (null for all products)
    - **category_id**: Category ID (null for all categories)
    - **discount_type**: Discount type (percentage, flat, or fixed_price)
    - **discount_value**: Discount amount or percentage
    - **min_quantity**: Minimum quantity required
    - **min_order_amount**: Minimum order amount required (optional)
    """
    # Verify price list exists
    price_list = await pricing_service.get_price_list_by_id(price_list_id)
    if not price_list:
        raise ResourceNotFoundException(
            detail=f"Price list with ID {price_list_id} not found"
        )

    try:
        new_line = await pricing_service.add_price_list_line(
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
async def update_price_list_line(line_id: int, line_data: UpdatePriceListLineSchema):
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
async def delete_price_list_line(line_id: int):
    """Delete a price list line"""
    success = await pricing_service.delete_price_list_line(line_id)
    if not success:
        raise ResourceNotFoundException(
            detail=f"Price list line with ID {line_id} not found"
        )
    return success_response(
        {"id": line_id, "message": "Price list line deleted successfully"}
    )


# Tier Price List Association Endpoints
@pricing_router.post(
    "/tiers/{tier_id}/price-lists/{price_list_id}",
    summary="Assign price list to tier",
)
async def assign_price_list_to_tier(tier_id: int, price_list_id: int):
    """Assign a price list to a tier"""
    # The service now raises proper exceptions (ResourceNotFoundException, ConflictException)
    # These will be handled by the global exception handler to return proper HTTP status codes
    await pricing_service.assign_price_list_to_tier(tier_id, price_list_id)
    return success_response({
        "tier_id": tier_id,
        "price_list_id": price_list_id,
        "message": "Price list assigned to tier successfully"
    })


@pricing_router.delete(
    "/tiers/{tier_id}/price-lists/{price_list_id}",
    summary="Remove price list from tier",
)
async def remove_price_list_from_tier(tier_id: int, price_list_id: int):
    """Remove a price list from a tier"""
    success = await pricing_service.remove_price_list_from_tier(tier_id, price_list_id)
    if not success:
        raise ResourceNotFoundException(
            detail="Price list assignment not found"
        )
    return success_response({
        "tier_id": tier_id,
        "price_list_id": price_list_id,
        "message": "Price list removed from tier successfully"
    })


@pricing_router.get(
    "/tiers/{tier_id}/price-lists",
    summary="Get price lists for tier",
    response_model=List[PriceListSchema],
)
async def get_tier_price_lists(tier_id: int):
    """Get all price lists assigned to a tier"""
    price_lists = await pricing_service.get_tier_price_lists(tier_id)
    return success_response([pl.model_dump(mode="json") for pl in price_lists])


# Pricing Calculation Endpoints
@pricing_router.get(
    "/calculate/product/{product_id}",
    summary="Calculate product price",
)
async def calculate_product_price(
    product_id: int,
    tier_id: Optional[int] = None,
    quantity: int = 1
):
    """Calculate the final price for a product based on tier and quantity"""
    try:
        from src.api.products.service import ProductService
        product_service = ProductService()
        product = await product_service.get_product_by_id(product_id, include_categories=True)
        if not product:
            raise ResourceNotFoundException(detail=f"Product with ID {product_id} not found")
        
        product_category_ids = [cat_id for cat_id in [cat.get("id") for cat in product.categories] if cat_id is not None] if product.categories else []
        
        pricing = await pricing_service.calculate_product_price(tier_id, product_id, product_category_ids, quantity)
        return success_response(pricing.model_dump(mode="json"))
    except ResourceNotFoundException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating price: {str(e)}"
        )


@pricing_router.post(
    "/calculate/bulk",
    summary="Calculate bulk product pricing",
)
async def calculate_bulk_pricing(
    product_ids: List[int],
    tier_id: Optional[int] = None,
    quantities: Optional[List[int]] = None
):
    """Calculate pricing for multiple products"""
    try:
        from src.api.products.service import ProductService
        product_service = ProductService()

        # Fetch products to get their categories
        products = []
        for p_id in product_ids:
            product = await product_service.get_product_by_id(p_id, include_categories=True)
            if product:
                products.append(product)
        
        # Construct product_data for bulk pricing calculation
        product_data = []
        for i, p in enumerate(products):
            quantity = quantities[i] if quantities and i < len(quantities) else 1
            product_category_ids = []
            if p.categories:
                product_category_ids = []
                for cat in p.categories:
                    # Safely get category ID, ensuring it exists and is not None
                    cat_id = cat.get("id") if isinstance(cat, dict) else getattr(cat, "id", None)
                    if cat_id is not None:
                        product_category_ids.append(cat_id)
            product_data.append({
                "id": p.id,
                "quantity": quantity,
                "category_ids": product_category_ids
            })

        pricing_list = await pricing_service.calculate_bulk_product_pricing(
            product_data, tier_id
        )
        return success_response([p.model_dump(mode="json") for p in pricing_list])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating bulk pricing: {str(e)}"
        )
