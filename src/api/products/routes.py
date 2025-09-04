from fastapi import APIRouter, Depends, status, Query, HTTPException
from typing import Annotated, List, Optional
from src.api.products.models import (
    ProductSchema,
    CreateProductSchema,
    UpdateProductSchema,
    ProductQuerySchema,
    EnhancedProductSchema,
    PaginatedProductsResponse,
)
from src.api.pricing.models import PriceCalculationResponse
from src.api.auth.models import DecodedToken
from src.api.products.service import ProductService
from src.api.pricing.service import PricingService
from src.dependencies.auth import RoleChecker, get_current_user
from src.dependencies.tiers import get_user_tier
from src.config.constants import UserRole, CustomerTier
from src.shared.exceptions import ResourceNotFoundException
from src.shared.responses import success_response

products_router = APIRouter(prefix="/products", tags=["Products"])
product_service = ProductService()
pricing_service = PricingService()


@products_router.get(
    "/",
    summary="Get all products with smart pricing and pagination",
    response_model=PaginatedProductsResponse,
)
async def get_all_products(
    limit: Optional[int] = Query(
        20, le=100, description="Number of products to return (default: 20, max: 100)"
    ),
    cursor: Optional[str] = Query(
        None, description="Cursor for pagination (product ID to start from)"
    ),
    include_pricing: Optional[bool] = Query(
        True, description="Include pricing calculations"
    ),
    categoryId: Optional[str] = Query(None, description="Filter by category ID"),
    minPrice: Optional[float] = Query(None, description="Filter by minimum price"),
    maxPrice: Optional[float] = Query(None, description="Filter by maximum price"),
    isFeatured: Optional[bool] = Query(None, description="Filter by featured products"),
    user_tier: Optional[CustomerTier] = Depends(get_user_tier),
):
    """
    Enhanced product listing with:
    - Cursor-based pagination for efficiency
    - Smart pricing with automatic tier detection from Bearer token
    - Default limit of 20, maximum 100
    - Future-ready inventory structure
    """
    query_params = ProductQuerySchema(
        limit=limit,
        cursor=cursor,
        include_pricing=include_pricing,
        categoryId=categoryId,
        minPrice=minPrice,
        maxPrice=maxPrice,
        isFeatured=isFeatured,
    )

    result = await product_service.get_products_with_pagination(
        query_params=query_params,
        customer_tier=user_tier,
        pricing_service=pricing_service if include_pricing else None,
    )

    return success_response(result.model_dump(mode="json"))


@products_router.get(
    "/{id}",
    summary="Get a product by ID with smart pricing",
    response_model=EnhancedProductSchema,
)
async def get_product_by_id(
    id: str,
    include_pricing: Optional[bool] = Query(
        True, description="Include pricing calculations"
    ),
    quantity: Optional[int] = Query(1, description="Quantity for bulk pricing"),
    user_tier: Optional[CustomerTier] = Depends(get_user_tier),
):
    """
    Get a single product with smart pricing based on Bearer token tier detection
    """
    product = await product_service.get_product_by_id(id)
    if not product:
        raise ResourceNotFoundException(detail=f"Product with ID {id} not found")

    # Create enhanced product with pricing if requested
    if include_pricing and pricing_service:
        # Calculate pricing for single product
        product_list = [
            {
                "id": product.id,
                "price": product.price,
                "categoryId": product.categoryId,
                **product.model_dump(),
            }
        ]

        pricing_results = await pricing_service.calculate_bulk_product_pricing(
            product_list, user_tier, quantity or 1
        )

        pricing_info = pricing_results[0] if pricing_results else None
        from src.api.products.models import PricingInfoSchema

        enhanced_product = EnhancedProductSchema(
            **product.model_dump(),
            pricing=PricingInfoSchema(**pricing_info) if pricing_info else None,
        )
    else:
        enhanced_product = EnhancedProductSchema(**product.model_dump())

    return success_response(enhanced_product.model_dump(mode="json"))


@products_router.post(
    "/",
    summary="Create a new product",
    response_model=ProductSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_product(product_data: CreateProductSchema):
    new_product = await product_service.create_product(product_data)
    return success_response(
        new_product.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


@products_router.put(
    "/{id}",
    summary="Update a product",
    response_model=ProductSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_product(id: str, product_data: UpdateProductSchema):
    updated_product = await product_service.update_product(id, product_data)
    if not updated_product:
        raise ResourceNotFoundException(detail=f"Product with ID {id} not found")
    return success_response(updated_product.model_dump(mode="json"))


@products_router.delete(
    "/{id}",
    summary="Delete a product",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_product(id: str):
    if not await product_service.delete_product(id):
        raise ResourceNotFoundException(detail=f"Product with ID {id} not found")
    return success_response({"id": id, "message": "Product deleted successfully"})
