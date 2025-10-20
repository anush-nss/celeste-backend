from typing import Annotated, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.auth.models import DecodedToken
from src.api.pricing.service import PricingService
from src.api.products.models import (
    CreateProductSchema,
    EnhancedProductSchema,
    PaginatedProductsResponse,
    ProductQuerySchema,
    ProductSchema,
    ProductTagSchema,
    UpdateProductSchema,
)
from src.api.products.service import ProductService
from src.api.tags.models import CreateTagSchema, TagSchema, UpdateTagSchema
from src.config.constants import UserRole
from src.database.connection import AsyncSessionLocal
from src.dependencies.auth import RoleChecker, get_current_user
from src.dependencies.tiers import get_user_tier
from src.shared.exceptions import ResourceNotFoundException
from src.shared.responses import success_response

products_router = APIRouter(prefix="/products", tags=["Products"])
product_service = ProductService()
pricing_service = PricingService()


@products_router.get(
    "/recents",
    summary="Get recently bought products for the current user",
    response_model=List[EnhancedProductSchema],
)
async def get_recent_products(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
    user_tier: Optional[int] = Depends(get_user_tier),
    limit: int = Query(
        20,
        le=100,
        description="Number of recent products to return (default: 20, max: 100)",
    ),
    include_pricing: bool = Query(True, description="Include pricing calculations"),
    include_categories: bool = Query(False, description="Include category information"),
    include_tags: bool = Query(False, description="Include tag information"),
    include_inventory: bool = Query(
        True, description="Include inventory information (requires store_id or location)"
    ),
    latitude: Optional[float] = Query(
        None, ge=-90, le=90, description="User latitude for location-based inventory"
    ),
    longitude: Optional[float] = Query(
        None, ge=-180, le=180, description="User longitude for location-based inventory"
    ),
):
    """
    Get recently bought products for the authenticated user.

    Returns products from ordered carts, sorted by most recent purchase.
    Each product appears only once, even if purchased multiple times.

    Features:
    - Smart pricing with automatic tier detection from Bearer token
    - Location-based inventory (provide latitude/longitude)
    - Product categories and tags
    - Default limit of 20, maximum 100
    """
    user_id = current_user.uid

    products = await product_service.get_recent_products(
        user_id=user_id,
        limit=limit,
        customer_tier=user_tier,
        include_pricing=include_pricing,
        include_categories=include_categories,
        include_tags=include_tags,
        include_inventory=include_inventory,
        latitude=latitude,
        longitude=longitude,
    )

    return success_response([p.model_dump(mode="json") for p in products])


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
    include_tags: Optional[bool] = Query(False, description="Include tag information"),
    category_ids: Optional[List[int]] = Query(
        None, description="Filter by category IDs"
    ),
    tags: Optional[List[str]] = Query(
        None,
        description="Filter by tags (flexible syntax: 'organic', 'id:5', 'type:dietary', 'value:gluten-free')",
    ),
    min_price: Optional[float] = Query(None, description="Filter by minimum price"),
    max_price: Optional[float] = Query(None, description="Filter by maximum price"),
    only_discounted: Optional[bool] = Query(
        False, description="Return only products with discounts applied"
    ),
    has_inventory: Optional[bool] = Query(
        None,
        description="Filter products with available inventory (quantity > safety_stock)",
    ),
    store_id: Optional[List[int]] = Query(
        None, description="Store IDs for multi-store inventory data"
    ),
    include_inventory: Optional[bool] = Query(
        True,
        description="Include inventory information (requires store_id or location)",
    ),
    latitude: Optional[float] = Query(
        None,
        ge=-90,
        le=90,
        description="User latitude for location-based store finding",
    ),
    longitude: Optional[float] = Query(
        None,
        ge=-180,
        le=180,
        description="User longitude for location-based store finding",
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
        tags=tags,
        min_price=min_price,
        max_price=max_price,
        only_discounted=only_discounted,
        has_inventory=has_inventory,
        store_id=store_id,
        include_inventory=include_inventory,
        latitude=latitude,
        longitude=longitude,
    )

    # Use comprehensive method for all requests
    store_ids = None
    if include_inventory and store_id:
        store_ids = store_id

    # Always use the comprehensive method for best performance
    result = await product_service.get_products_with_criteria(
        query_params=query_params,
        customer_tier=user_tier,
        store_ids=store_ids,
    )

    return success_response(result.model_dump(mode="json"))


# ===== PRODUCT TAG CRUD ROUTES =====


@products_router.get(
    "/tags/types",
    summary="Get all available product tag types",
    response_model=List[str],
)
async def get_tag_types():
    """Get all unique tag types for products only"""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import distinct
        from sqlalchemy.future import select

        from src.database.models.product import Tag

        query = (
            select(distinct(Tag.tag_type))
            .filter(Tag.is_active, Tag.tag_type.like("product_%"))
            .order_by(Tag.tag_type)
        )
        result = await session.execute(query)
        tag_types = result.scalars().all()

    return success_response(list(tag_types))


@products_router.get(
    "/tags/{tag_id}",
    summary="Get a tag by ID",
    response_model=TagSchema,
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

        return success_response(TagSchema.model_validate(tag).model_dump(mode="json"))


@products_router.put(
    "/tags/{tag_id}",
    summary="Update a tag",
    response_model=TagSchema,
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

        return success_response(TagSchema.model_validate(tag).model_dump(mode="json"))


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

        return success_response(
            {"id": tag_id, "message": "Tag deactivated successfully"}
        )


# ===== PRODUCT TAG CRUD ROUTES (must come before /{id} route) =====


@products_router.post(
    "/tags",
    summary="Create one or more new product tags",
    response_model=Union[TagSchema, List[TagSchema]],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_product_tags(payload: Union[CreateTagSchema, List[CreateTagSchema]]):
    """Create one or more new tags for products (Admin only)."""
    is_list = isinstance(payload, list)
    tags_to_create = payload if is_list else [payload]

    if not tags_to_create:
        raise HTTPException(
            status_code=400, detail="Request body cannot be an empty list."
        )

    created_tags = await product_service.create_product_tags(tags_to_create)

    # Convert SQLAlchemy Tag objects to Pydantic TagSchema objects
    tag_schemas = [TagSchema.model_validate(tag) for tag in created_tags]

    if is_list:
        return success_response(
            [t.model_dump(mode="json") for t in tag_schemas],
            status_code=status.HTTP_201_CREATED,
        )
    else:
        return success_response(
            tag_schemas[0].model_dump(mode="json"), status_code=status.HTTP_201_CREATED
        )


@products_router.get(
    "/tags",
    summary="Get all product tags",
    response_model=List[TagSchema],
)
async def get_product_tags(
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
    tag_type_suffix: Optional[str] = Query(
        None, description="Filter by tag type suffix (e.g., 'color', 'size')"
    ),
):
    """Get all product tags."""
    tags = await product_service.get_product_tags(
        is_active=is_active if is_active is not None else True,
        tag_type_suffix=tag_type_suffix,
    )
    return success_response(
        [TagSchema.model_validate(tag).model_dump(mode="json") for tag in tags]
    )


# ===== PRODUCT ROUTES =====


@products_router.get(
    "/ref/{ref}",
    summary="Get a product by reference/SKU with smart pricing and location support",
    response_model=EnhancedProductSchema,
)
async def get_product_by_ref(
    ref: str,
    include_pricing: Optional[bool] = Query(
        True, description="Include pricing calculations"
    ),
    include_categories: Optional[bool] = Query(
        True, description="Include category information"
    ),
    include_tags: Optional[bool] = Query(True, description="Include tag information"),
    include_inventory: Optional[bool] = Query(
        True, description="Include inventory information"
    ),
    include_alternatives: Optional[bool] = Query(
        False, description="Include alternative products"
    ),
    quantity: Optional[int] = Query(1, description="Quantity for bulk pricing"),
    store_id: Optional[List[int]] = Query(
        None, description="Store IDs for inventory info"
    ),
    latitude: Optional[float] = Query(
        None,
        ge=-90,
        le=90,
        description="User latitude for location-based store finding",
    ),
    longitude: Optional[float] = Query(
        None,
        ge=-180,
        le=180,
        description="User longitude for location-based store finding",
    ),
    user_tier: Optional[int] = Depends(get_user_tier),
):
    """
    Get a single product by reference/SKU with comprehensive SQL optimization,
    location-based store finding, and smart pricing integration
    """
    # Use enhanced product retrieval with comprehensive query
    product = await product_service.get_enhanced_product_by_ref(
        ref=ref,
        include_pricing=include_pricing if include_pricing is not None else False,
        include_categories=include_categories
        if include_categories is not None
        else False,
        include_tags=include_tags if include_tags is not None else False,
        include_inventory=include_inventory if include_inventory is not None else False,
        include_alternatives=include_alternatives if include_alternatives is not None else False,
        customer_tier=user_tier,
        store_ids=store_id,
        latitude=latitude,
        longitude=longitude,
        quantity=quantity or 1,
    )

    if not product:
        raise ResourceNotFoundException(detail=f"Product with ref '{ref}' not found")

    return success_response(product.model_dump(mode="json"))


@products_router.get(
    "/{id}",
    summary="Get a product by ID with smart pricing and location support",
    response_model=EnhancedProductSchema,
)
async def get_product_by_id(
    id: int,
    include_pricing: Optional[bool] = Query(
        True, description="Include pricing calculations"
    ),
    include_categories: Optional[bool] = Query(
        True, description="Include category information"
    ),
    include_tags: Optional[bool] = Query(True, description="Include tag information"),
    include_inventory: Optional[bool] = Query(
        True, description="Include inventory information"
    ),
    include_alternatives: Optional[bool] = Query(
        False, description="Include alternative products"
    ),
    quantity: Optional[int] = Query(1, description="Quantity for bulk pricing"),
    store_id: Optional[List[int]] = Query(
        None, description="Store IDs for inventory data"
    ),
    latitude: Optional[float] = Query(
        None,
        ge=-90,
        le=90,
        description="User latitude for location-based store finding",
    ),
    longitude: Optional[float] = Query(
        None,
        ge=-180,
        le=180,
        description="User longitude for location-based store finding",
    ),
    user_tier: Optional[int] = Depends(get_user_tier),
):
    """
    Get a single product with comprehensive SQL optimization,
    location-based store finding, and smart pricing integration
    """
    # Use enhanced product retrieval with comprehensive query
    product = await product_service.get_enhanced_product_by_id(
        product_id=id,
        include_pricing=include_pricing if include_pricing is not None else False,
        include_categories=include_categories
        if include_categories is not None
        else False,
        include_tags=include_tags if include_tags is not None else False,
        include_inventory=include_inventory if include_inventory is not None else False,
        include_alternatives=include_alternatives if include_alternatives is not None else False,
        customer_tier=user_tier,
        store_ids=store_id,
        latitude=latitude,
        longitude=longitude,
        quantity=quantity or 1,
    )

    if not product:
        raise ResourceNotFoundException(detail=f"Product with ID {id} not found")

    return success_response(product.model_dump(mode="json"))


@products_router.post(
    "/",
    summary="Create one or more new products",
    response_model=Union[ProductSchema, List[ProductSchema]],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_products(
    payload: Union[CreateProductSchema, List[CreateProductSchema]],
):
    is_list = isinstance(payload, list)
    products_to_create = payload if is_list else [payload]

    if not products_to_create:
        raise HTTPException(
            status_code=400, detail="Request body cannot be an empty list."
        )

    created_products = await product_service.create_products(products_to_create)

    if is_list:
        return success_response(
            [p.model_dump(mode="json") for p in created_products],
            status_code=status.HTTP_201_CREATED,
        )
    else:
        return success_response(
            created_products[0].model_dump(mode="json"),
            status_code=status.HTTP_201_CREATED,
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
    response_model=List[ProductTagSchema],
)
async def get_product_tags_by_id(product_id: int):
    """Get all tags assigned to a product"""
    product = await product_service.get_product_by_id(
        product_id, include_categories=False, include_tags=True
    )

    if not product:
        raise ResourceNotFoundException(
            detail=f"Product with ID {product_id} not found"
        )

    product_tags = product.model_dump(mode="json").get("product_tags", [])
    if not product_tags:
        return success_response([])

    return success_response(
        [
            ProductTagSchema.model_validate(tag).model_dump(mode="json")
            for tag in product_tags
        ]
    )


@products_router.post(
    "/{product_id}/tags/{tag_id}",
    summary="Assign a tag to a product",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def assign_tag_to_product(
    product_id: int,
    tag_id: int,
    value: Optional[str] = Query(None, description="Optional tag value"),
):
    """Assign a tag to a product with optional value"""
    await product_service.assign_tag_to_product(
        product_id=product_id, tag_id=tag_id, value=value
    )
    return success_response(
        {
            "product_id": product_id,
            "tag_id": tag_id,
            "message": "Tag assigned successfully",
        }
    )


@products_router.delete(
    "/{product_id}/tags/{tag_id}",
    summary="Remove a tag from a product",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def remove_tag_from_product(product_id: int, tag_id: int):
    """Remove a tag from a product"""
    await product_service.remove_tag_from_product(product_id, tag_id)
    return success_response(
        {
            "product_id": product_id,
            "tag_id": tag_id,
            "message": "Tag removed successfully",
        }
    )
