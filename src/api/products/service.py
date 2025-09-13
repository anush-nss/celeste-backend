from typing import Optional, List, Dict, Any
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import and_, or_
from src.database.connection import AsyncSessionLocal
from src.database.models.product import Product, Tag, ProductTag
from src.database.models.category import Category
from src.api.products.models import (
    ProductSchema,
    CreateProductSchema,
    UpdateProductSchema,
    ProductQuerySchema,
    EnhancedProductSchema,
    PaginatedProductsResponse,
    PricingInfoSchema,
    ProductTagSchema,
)
from src.config.constants import Collections
from src.shared.cache_invalidation import cache_invalidation_manager
from src.api.products.cache import products_cache
from src.shared.sqlalchemy_utils import safe_model_validate, safe_model_validate_list
from src.shared.exceptions import ResourceNotFoundException, ConflictException, ValidationException
from src.shared.error_handler import ErrorHandler, handle_service_errors
from sqlalchemy.exc import IntegrityError


class ProductService:
    """Product service with PostgreSQL and generic utilities"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)

    async def _build_product_query(self, query_params: ProductQuerySchema):
        """Build SQLAlchemy query with filters and relationships"""
        query = select(Product)
        
        # Include relationships based on query params
        if query_params.include_categories:
            query = query.options(selectinload(Product.categories))
        if query_params.include_tags:
            query = query.options(
                selectinload(Product.product_tags).selectinload(ProductTag.tag)
            )
        
        # Apply filters
        conditions = []
        
        if query_params.category_ids:
            query = query.join(Product.categories).filter(
                Category.id.in_(query_params.category_ids)
            )
        
        if query_params.tag_ids:
            query = query.join(Product.product_tags).filter(
                ProductTag.tag_id.in_(query_params.tag_ids)
            )
            
        if query_params.tag_types:
            query = query.join(Product.product_tags).join(ProductTag.tag).filter(
                Tag.tag_type.in_(query_params.tag_types)
            )
        
        if query_params.min_price is not None:
            conditions.append(Product.base_price >= query_params.min_price)
        
        if query_params.max_price is not None:
            conditions.append(Product.base_price <= query_params.max_price)
        
        if conditions:
            query = query.filter(and_(*conditions))
        
        # Apply cursor pagination
        if query_params.cursor is not None:
            query = query.filter(Product.id > query_params.cursor)
            
        # Order and limit
        limit = query_params.limit if query_params.limit is not None else 20
        query = query.order_by(Product.id).limit(limit + 1)  # +1 to check if more exist
        
        return query

    async def get_all_products(
        self, query_params: ProductQuerySchema
    ) -> list[ProductSchema]:
        """Get products with filtering and pagination"""
        async with AsyncSessionLocal() as session:
            query = await self._build_product_query(query_params)
            result = await session.execute(query)
            products = result.scalars().unique().all()
            
            # Convert to Pydantic using our generic utility
            include_rels = set()
            if query_params.include_categories:
                include_rels.add('categories')
            if query_params.include_tags:
                include_rels.add('product_tags')
                
            limit = query_params.limit if query_params.limit is not None else 20
            return safe_model_validate_list(
                ProductSchema,
                products[:limit],  # Remove the extra one used for has_more check
                include_relationships=include_rels
            )

    @handle_service_errors("retrieving product by ID")
    async def get_product_by_id(
        self,
        product_id: int,
        include_categories: bool = True,
        include_tags: bool = True
    ) -> ProductSchema | None:
        """Get product by ID with relationships"""
        if product_id <= 0:
            raise ValidationException(detail="Product ID must be a positive integer")

        cached_product = products_cache.get_product(str(product_id))
        if cached_product:
            return ProductSchema.model_validate(cached_product)

        async with AsyncSessionLocal() as session:
            query = select(Product).filter(Product.id == product_id)

            # Include relationships
            if include_categories:
                query = query.options(selectinload(Product.categories))
            if include_tags:
                query = query.options(
                    selectinload(Product.product_tags).selectinload(ProductTag.tag)
                )

            result = await session.execute(query)
            product = result.scalars().first()

            if product:
                include_rels = set()
                if include_categories:
                    include_rels.add('categories')
                if include_tags:
                    include_rels.add('product_tags')

                pydantic_product = safe_model_validate(
                    ProductSchema,
                    product,
                    max_depth=3
                )

                # Cache the product
                products_cache.set_product(str(product_id), pydantic_product.model_dump(mode="json"))
                return pydantic_product

            return None

    @handle_service_errors("creating product")
    async def create_product(self, product_data: CreateProductSchema) -> ProductSchema:
        """Create a new product with categories and tags"""
        # Validate input data
        if not product_data.name or not product_data.name.strip():
            raise ValidationException(detail="Product name is required")

        if not product_data.brand or not product_data.brand.strip():
            raise ValidationException(detail="Product brand is required")

        if product_data.base_price < 0:
            raise ValidationException(detail="Product price cannot be negative")

        if not product_data.unit_measure or not product_data.unit_measure.strip():
            raise ValidationException(detail="Product unit measure is required")

        async with AsyncSessionLocal() as session:
            # Create the product
            new_product = Product(
                name=product_data.name.strip(),
                description=product_data.description.strip() if product_data.description else None,
                brand=product_data.brand.strip(),
                base_price=product_data.base_price,
                unit_measure=product_data.unit_measure.strip(),
                image_urls=product_data.image_urls or []
            )
            session.add(new_product)
            await session.commit()
            await session.refresh(new_product)

            # Add categories if provided
            if product_data.category_ids:
                # Load categories with eager loading
                category_result = await session.execute(
                    select(Category).filter(Category.id.in_(product_data.category_ids))
                )
                categories = category_result.scalars().all()

                # Check if all requested categories exist
                found_category_ids = {cat.id for cat in categories}
                missing_category_ids = set(product_data.category_ids) - found_category_ids
                if missing_category_ids:
                    raise ResourceNotFoundException(
                        detail=f"Categories with IDs {list(missing_category_ids)} not found"
                    )

                # Load the categories relationship first to avoid lazy loading
                await session.refresh(new_product, ["categories"])
                new_product.categories.extend(categories)

            # Add tags if provided
            if product_data.tag_ids:
                # Remove duplicates to avoid unique constraint violations
                unique_tag_ids = list(set(product_data.tag_ids))
                for tag_id in unique_tag_ids:
                    product_tag = ProductTag(
                        product_id=new_product.id,
                        tag_id=tag_id,
                        created_by="system"
                    )
                    session.add(product_tag)

            await session.commit()
            await session.refresh(new_product)

            # Load relationships for response
            await session.refresh(new_product, ["categories", "product_tags"])

            # Convert to Pydantic
            pydantic_product = safe_model_validate(
                ProductSchema,
                new_product,
                max_depth=3
            )

            # Invalidate cache
            cache_invalidation_manager.invalidate_entity(Collections.PRODUCTS)

            return pydantic_product

    async def update_product(
        self, product_id: int, product_data: UpdateProductSchema
    ) -> ProductSchema | None:
        """Update an existing product"""
        async with AsyncSessionLocal() as session:
            try:
                result = await session.execute(select(Product).filter(Product.id == product_id))
                product = result.scalars().first()
                
                if not product:
                    return None
                
                # Update basic fields
                update_dict = product_data.model_dump(mode="json", exclude_unset=True, exclude={'category_ids', 'tag_ids'})
                for field, value in update_dict.items():
                    setattr(product, field, value)
                
                # Update categories if provided
                if product_data.category_ids is not None:
                    # Load the categories relationship first to avoid lazy loading
                    await session.refresh(product, ["categories"])
                    product.categories.clear()
                    if product_data.category_ids:
                        category_result = await session.execute(
                            select(Category).filter(Category.id.in_(product_data.category_ids))
                        )
                        categories = category_result.scalars().all()
                        
                        # Check if all requested categories exist
                        found_category_ids = {cat.id for cat in categories}
                        missing_category_ids = set(product_data.category_ids) - found_category_ids
                        if missing_category_ids:
                            raise ResourceNotFoundException(
                                detail=f"Categories with IDs {list(missing_category_ids)} not found"
                            )
                        
                        product.categories.extend(categories)
                
                # Update tags if provided
                if product_data.tag_ids is not None:
                    # Clear existing tags
                    await session.execute(
                        ProductTag.__table__.delete().where(ProductTag.product_id == product_id)
                    )
                    # Add new tags (remove duplicates to avoid unique constraint violations)
                    unique_tag_ids = list(set(product_data.tag_ids))
                    for tag_id in unique_tag_ids:
                        product_tag = ProductTag(
                            product_id=product_id,
                            tag_id=tag_id,
                            created_by="system"
                        )
                        session.add(product_tag)
                
                await session.commit()
                await session.refresh(product)
                await session.refresh(product, ["categories", "product_tags"])
                
                # Convert to Pydantic
                pydantic_product = safe_model_validate(
                    ProductSchema,
                    product,
                    max_depth=3
                )
                
                # Invalidate cache
                products_cache.invalidate_product_cache(str(product_id))
                cache_invalidation_manager.invalidate_entity(Collections.PRODUCTS, str(product_id))
                
                return pydantic_product
                
            except IntegrityError as e:
                await session.rollback()
                if "tag_id" in str(e.orig) and "is not present" in str(e.orig):
                    raise ResourceNotFoundException(detail="One or more specified tags not found")
                else:
                    # Re-raise if it's a different integrity error
                    raise

    async def delete_product(self, product_id: int) -> bool:
        """Delete a product"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Product).filter(Product.id == product_id))
            product = result.scalars().first()
            
            if not product:
                return False
            
            await session.delete(product)
            await session.commit()
            
            # Invalidate cache
            products_cache.invalidate_product_cache(str(product_id))
            cache_invalidation_manager.invalidate_entity(Collections.PRODUCTS, str(product_id))
            
            return True

    async def get_products_with_pagination(
        self,
        query_params: ProductQuerySchema,
        customer_tier: Optional[int] = None,
        pricing_service=None,
    ) -> PaginatedProductsResponse:
        """Get products with pagination and optional pricing"""
        async with AsyncSessionLocal() as session:
            # Determine what relationships to load
            load_categories = bool(query_params.include_categories or (query_params.include_pricing and pricing_service and customer_tier))
            load_tags = bool(query_params.include_tags)
            
            # Build query with conditional relationship loading
            query_params_copy = query_params.model_copy()
            query_params_copy.include_categories = load_categories
            query_params_copy.include_tags = load_tags
            
            query = await self._build_product_query(query_params_copy)
            result = await session.execute(query)
            products = result.scalars().unique().all()
            
            # Check if there are more results
            limit = query_params.limit if query_params.limit is not None else 20
            has_more = len(products) > limit
            actual_products = products[:limit] if has_more else products
            
            # Convert to Pydantic
            include_rels = set()
            if load_categories:
                include_rels.add('categories')
            if load_tags:
                include_rels.add('product_tags')
                
            enhanced_products = []
            base_products = safe_model_validate_list(
                ProductSchema,
                actual_products,
                max_depth=3
            )
            
            # Add pricing if requested
            if query_params.include_pricing and pricing_service and customer_tier:
                # Convert to dict format for bulk pricing
                product_data = [
                    {
                        "id": str(p.id),
                        "price": p.base_price,
                        "category_ids": [cat.get("id") for cat in p.categories] if p.categories else []
                    }
                    for p in base_products
                ]
                
                # Get pricing for all products in one batch
                pricing_results = await pricing_service.calculate_bulk_product_pricing(
                    product_data, customer_tier
                )
                
                # Combine products with pricing
                for i, product in enumerate(base_products):
                    enhanced_product = EnhancedProductSchema(**product.model_dump(mode="json"))
                    pricing_info = pricing_results[i] if i < len(pricing_results) else None
                    if pricing_info:
                        enhanced_product.pricing = PricingInfoSchema(
                            base_price=pricing_info.base_price,
                            final_price=pricing_info.final_price,
                            discount_applied=pricing_info.savings,
                            discount_percentage=(pricing_info.savings / pricing_info.base_price) * 100 if pricing_info.base_price > 0 else 0,
                            applied_price_lists=[pl["price_list_name"] for pl in pricing_info.applied_discounts]
                        )
                    
                    # Filter discounted products if requested
                    if query_params.only_discounted:
                        if (
                            enhanced_product.pricing
                            and enhanced_product.pricing.discount_applied > 0
                        ):
                            enhanced_products.append(enhanced_product)
                    else:
                        enhanced_products.append(enhanced_product)
            else:
                # No pricing needed, just convert products
                for product in base_products:
                    enhanced_products.append(EnhancedProductSchema(**product.model_dump(mode="json")))
            
            # Build pagination metadata
            next_cursor = None
            if has_more and actual_products:
                next_cursor = actual_products[-1].id
            
            pagination = {
                "current_cursor": query_params.cursor,
                "next_cursor": next_cursor,
                "has_more": has_more,
                "total_returned": len(enhanced_products),
            }
            
            return PaginatedProductsResponse(
                products=enhanced_products, 
                pagination=pagination
            )

    # Tag management methods
    async def create_tag(self, tag_type: str, name: str, slug: str, description: Optional[str] = None) -> Tag:
        """Create a new tag"""
        async with AsyncSessionLocal() as session:
            new_tag = Tag(
                tag_type=tag_type,
                name=name,
                slug=slug,
                description=description
            )
            session.add(new_tag)
            await session.commit()
            await session.refresh(new_tag)
            return new_tag

    async def get_tags_by_type(self, tag_type: str) -> List[Tag]:
        """Get all tags of a specific type"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tag).filter(Tag.tag_type == tag_type, Tag.is_active == True)
            )
            return list(result.scalars().all())

    async def assign_tag_to_product(self, product_id: int, tag_id: int):
        """Assign a tag to a product"""
        async with AsyncSessionLocal() as session:
            try:
                product_tag = ProductTag(
                    product_id=product_id,
                    tag_id=tag_id,
                    created_by="system"
                )
                session.add(product_tag)
                await session.commit()
                
                # Invalidate cache
                products_cache.invalidate_product_cache(str(product_id))
                cache_invalidation_manager.invalidate_entity(Collections.PRODUCTS, str(product_id))
            except IntegrityError as e:
                await session.rollback()
                error_detail = str(e.orig)
                if "product_id" in error_detail and "is not present" in error_detail:
                    raise ResourceNotFoundException(detail=f"Product with ID {product_id} not found")
                elif "tag_id" in error_detail and "is not present" in error_detail:
                    raise ResourceNotFoundException(detail=f"Tag with ID {tag_id} not found")
                elif "duplicate key" in error_detail and "product_tags_pkey" in error_detail:
                    raise ConflictException(detail=f"Product {product_id} already has tag {tag_id}")
                else:
                    # Re-raise if it's a different integrity error
                    raise