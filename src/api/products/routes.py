from fastapi import APIRouter, Depends, status, Query, HTTPException
from typing import Annotated, List, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from src.database.connection import AsyncSessionLocal
from src.api.products.models import (
    ProductSchema,
    CreateProductSchema,
    UpdateProductSchema,
    ProductQuerySchema,
    EnhancedProductSchema,
    PaginatedProductsResponse,
    ProductTagSchema,
    PricingInfoSchema,
)
from src.api.auth.models import DecodedToken
from src.api.products.service import ProductService
from src.api.pricing.service import PricingService
from src.dependencies.auth import RoleChecker, get_current_user
from src.dependencies.tiers import get_user_tier
from src.config.constants import UserRole
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
    cursor: Optional[int] = Query(
        None, description="Cursor for pagination (product ID to start from)"
    ),
    include_pricing: Optional[bool] = Query(
        True, description="Include pricing calculations"
    ),
    include_categories: Optional[bool] = Query(
        False, description="Include category information"
    ),
    include_tags: Optional[bool] = Query(
        False, description="Include tag information"
    ),
    category_ids: Optional[List[int]] = Query(None, description="Filter by category IDs"),
    tag_types: Optional[List[str]] = Query(None, description="Filter by tag types"),
    tag_ids: Optional[List[int]] = Query(None, description="Filter by tag IDs"),
    min_price: Optional[float] = Query(None, description="Filter by minimum price"),
    max_price: Optional[float] = Query(None, description="Filter by maximum price"),
    only_discounted: Optional[bool] = Query(
        False, description="Return only products with discounts applied"
    ),
    user_tier: Optional[int] = Depends(get_user_tier),
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
        include_categories=include_categories,
        include_tags=include_tags,
        category_ids=category_ids,
        tag_types=tag_types,
        tag_ids=tag_ids,
        min_price=min_price,
        max_price=max_price,
        only_discounted=only_discounted,
    )

    result = await product_service.get_products_with_pagination(
        query_params=query_params,
        customer_tier=user_tier,
        pricing_service=pricing_service if include_pricing else None,
    )

    return success_response(result.model_dump(mode="json"))


# ===== TAG MANAGEMENT ROUTES (must come before /{id} route) =====

class CreateTagSchema(BaseModel):
    tag_type: str = Field(..., min_length=1, max_length=50, description="Type of tag (dietary, allergen, analytics, etc.)")
    name: str = Field(..., min_length=1, max_length=100, description="Display name of the tag")
    slug: str = Field(..., min_length=1, max_length=100, description="URL-friendly identifier")
    description: Optional[str] = Field(None, max_length=500, description="Optional description")


class UpdateTagSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None





class TagResponseSchema(BaseModel):
    id: int
    tag_type: str
    name: str
    slug: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


@products_router.post(
    "/tags",
    summary="Create a new tag",
    response_model=TagResponseSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_tag(tag_data: CreateTagSchema):
    """Create a new tag for products"""
    new_tag = await product_service.create_tag(
        tag_type=tag_data.tag_type,
        name=tag_data.name,
        slug=tag_data.slug,
        description=tag_data.description
    )
    return success_response(
        TagResponseSchema.model_validate(new_tag).model_dump(mode="json"), 
        status_code=status.HTTP_201_CREATED
    )


@products_router.get(
    "/tags",
    summary="Get all tags, optionally filtered by type",
    response_model=List[TagResponseSchema],
)
async def get_tags(
    tag_type: Optional[str] = Query(None, description="Filter by tag type"),
    is_active: Optional[bool] = Query(True, description="Filter by active status")
):
    """Get all tags, optionally filtered by type"""
    if tag_type:
        tags = await product_service.get_tags_by_type(tag_type)
    else:
        # Get all active tags
        async with AsyncSessionLocal() as session:
            from sqlalchemy.future import select
            from src.database.models.product import Tag
            
            query = select(Tag)
            if is_active is not None:
                query = query.filter(Tag.is_active == is_active)
            query = query.order_by(Tag.tag_type, Tag.name)
            
            result = await session.execute(query)
            tags = result.scalars().all()
    
    tag_responses = [TagResponseSchema.model_validate(tag) for tag in tags]
    return success_response([tag.model_dump(mode="json") for tag in tag_responses])


@products_router.get(
    "/tags/types",
    summary="Get all available tag types",
    response_model=List[str],
)
async def get_tag_types():
    """Get all unique tag types"""
    async with AsyncSessionLocal() as session:
        from sqlalchemy.future import select
        from sqlalchemy import distinct
        from src.database.models.product import Tag
        
        query = select(distinct(Tag.tag_type)).filter(Tag.is_active == True).order_by(Tag.tag_type)
        result = await session.execute(query)
        tag_types = result.scalars().all()
    
    return success_response(list(tag_types))


@products_router.get(
    "/tags/{tag_id}",
    summary="Get a tag by ID",
    response_model=TagResponseSchema,
)
async def get_tag_by_id(tag_id: int):
    """Get a specific tag by ID"""
    async with AsyncSessionLocal() as session:
        from sqlalchemy.future import select
        from src.database.models.product import Tag
        
        result = await session.execute(select(Tag).filter(Tag.id == tag_id))
        tag = result.scalars().first()
        
        if not tag:
            raise ResourceNotFoundException(detail=f"Tag with ID {tag_id} not found")
        
        return success_response(TagResponseSchema.model_validate(tag).model_dump(mode="json"))


@products_router.put(
    "/tags/{tag_id}",
    summary="Update a tag",
    response_model=TagResponseSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_tag(tag_id: int, tag_data: UpdateTagSchema):
    """Update an existing tag"""
    async with AsyncSessionLocal() as session:
        from sqlalchemy.future import select
        from src.database.models.product import Tag
        
        result = await session.execute(select(Tag).filter(Tag.id == tag_id))
        tag = result.scalars().first()
        
        if not tag:
            raise ResourceNotFoundException(detail=f"Tag with ID {tag_id} not found")
        
        # Update fields
        update_dict = tag_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(tag, field, value)
        
        await session.commit()
        await session.refresh(tag)
        
        return success_response(TagResponseSchema.model_validate(tag).model_dump(mode="json"))


@products_router.delete(
    "/tags/{tag_id}",
    summary="Delete a tag",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_tag(tag_id: int):
    """Delete a tag (soft delete by setting is_active to False)"""
    async with AsyncSessionLocal() as session:
        from sqlalchemy.future import select
        from src.database.models.product import Tag
        
        result = await session.execute(select(Tag).filter(Tag.id == tag_id))
        tag = result.scalars().first()
        
        if not tag:
            raise ResourceNotFoundException(detail=f"Tag with ID {tag_id} not found")
        
        # Soft delete by setting is_active to False
        tag.is_active = False
        await session.commit()
        
        return success_response({"id": tag_id, "message": "Tag deactivated successfully"})


# ===== PRODUCT ROUTES =====

@products_router.get(
    "/{id}",
    summary="Get a product by ID with smart pricing",
    response_model=EnhancedProductSchema,
)
async def get_product_by_id(
    id: int,
    include_pricing: Optional[bool] = Query(
        True, description="Include pricing calculations"
    ),
    quantity: Optional[int] = Query(1, description="Quantity for bulk pricing"),
    user_tier: Optional[int] = Depends(get_user_tier),
):
    """
    Get a single product with OPTIMIZED pricing (sub-30ms target)
    Uses new optimized service methods for maximum performance
    """
    product = await product_service.get_product_by_id(
        id, include_categories=True, include_tags=True
    )
    
    # If pricing is requested and we have user tier, add pricing info
    if include_pricing and user_tier and product:
        if product.id is None:
            raise ValueError("Product ID cannot be None for pricing calculation")
        # Get category ID for pricing calculation
        product_category_ids = [cat_id for cat_id in [cat.get("id") for cat in product.categories] if cat_id is not None] if product.categories else []
        pricing_result = await pricing_service.calculate_product_price(
            product_id=product.id,
            product_category_ids=product_category_ids, # New argument
            user_tier_id=user_tier,
            quantity=quantity or 1
        )
        
        # Convert to enhanced schema with pricing
        enhanced_product = EnhancedProductSchema(**product.model_dump(mode="json"))
        if pricing_result:
            discount_percentage = (pricing_result.savings / pricing_result.base_price) * 100 if pricing_result.base_price > 0 else 0
            enhanced_product.pricing = PricingInfoSchema(
                base_price=pricing_result.base_price,
                final_price=pricing_result.final_price,
                discount_applied=pricing_result.savings,
                discount_percentage=discount_percentage,
                applied_price_lists=[pl["price_list_name"] for pl in pricing_result.applied_discounts]
            )
        
        return success_response(enhanced_product.model_dump(mode="json"))
    
    # Return basic product without pricing
    if not product:
        raise ResourceNotFoundException(detail=f"Product with ID {id} not found")
        
    return success_response(product.model_dump(mode="json"))



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
async def update_product(id: int, product_data: UpdateProductSchema):
    updated_product = await product_service.update_product(id, product_data)
    if not updated_product:
        raise ResourceNotFoundException(detail=f"Product with ID {id} not found")
    return success_response(updated_product.model_dump(mode="json"))


@products_router.delete(
    "/{id}",
    summary="Delete a product",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_product(id: int):
    if not await product_service.delete_product(id):
        raise ResourceNotFoundException(detail=f"Product with ID {id} not found")
    return success_response({"id": id, "message": "Product deleted successfully"})


# ===== PRODUCT-TAG ASSIGNMENT ROUTES =====

@products_router.get(
    "/{product_id}/tags",
    summary="Get all tags assigned to a product",
    response_model=Dict[str, List[ProductTagSchema]],
)
async def get_product_tags(product_id: int):
    """Get all tags assigned to a product, grouped by tag type"""
    product = await product_service.get_product_by_id(
        product_id, include_categories=False, include_tags=True
    )
    
    if not product:
        raise ResourceNotFoundException(detail=f"Product with ID {product_id} not found")
    
    return success_response(product.model_dump(mode="json").get("product_tags",[]))

@products_router.post(
    "/{product_id}/tags/{tag_id}",
    summary="Assign a tag to a product",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def assign_tag_to_product(product_id: int, tag_id: int):
    """Assign a tag to a product"""
    await product_service.assign_tag_to_product(
        product_id=product_id,
        tag_id=tag_id
    )
    return success_response({"message": "Tag assigned successfully"})


@products_router.delete(
    "/{product_id}/tags/{tag_id}",
    summary="Remove a tag from a product",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def remove_tag_from_product(product_id: int, tag_id: int):
    """Remove a tag from a product"""
    async with AsyncSessionLocal() as session:
        from sqlalchemy.future import select
        from src.database.models.product import ProductTag
        
        result = await session.execute(
            select(ProductTag).filter(
                ProductTag.product_id == product_id,
                ProductTag.tag_id == tag_id
            )
        )
        product_tag = result.scalars().first()
        
        if not product_tag:
            raise ResourceNotFoundException(
                detail=f"Tag {tag_id} not found on product {product_id}"
            )
        
        await session.delete(product_tag)
        await session.commit()
        
        return success_response({"message": "Tag removed successfully"})
