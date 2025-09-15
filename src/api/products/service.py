from typing import Optional, List, Dict, Any
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import and_, or_, text
from src.api.tags.models import CreateTagSchema
from src.database.connection import AsyncSessionLocal
from src.database.models.product import Product, ProductTag, Tag
from src.api.tags.service import TagService
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
from src.api.categories.models import CategorySchema
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
        self.tag_service = TagService(entity_type="product")

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
        self,
        query_params: ProductQuerySchema,
        customer_tier: Optional[int] = None,
        pricing_service=None,
    ) -> PaginatedProductsResponse:
        """Get products with filtering, pagination, and optional pricing"""
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

            # Fetch categories and tags separately if needed for Pydantic conversion
            product_categories_dict = {}
            product_tags_dict = {}

            if load_categories and actual_products:
                product_ids = [p.id for p in actual_products]
                category_query = select(Category, Product).join(Product.categories).filter(Product.id.in_(product_ids))
                category_result = await session.execute(category_query)
                for category, product in category_result.all():
                    if product.id not in product_categories_dict:
                        product_categories_dict[product.id] = []
                    product_categories_dict[product.id].append(category)

            if load_tags and actual_products:
                product_ids = [p.id for p in actual_products]
                tag_query = select(ProductTag, Tag).join(ProductTag.tag).filter(ProductTag.product_id.in_(product_ids))
                tag_result = await session.execute(tag_query)
                for product_tag, tag in tag_result.all():
                    if product_tag.product_id not in product_tags_dict:
                        product_tags_dict[product_tag.product_id] = []
                    product_tags_dict[product_tag.product_id].append(ProductTagSchema(
                        id=tag.id,
                        tag_type=tag.tag_type,
                        name=tag.name,
                        slug=tag.slug,
                        description=tag.description,
                        value=product_tag.value if hasattr(product_tag, 'value') else None
                    ))

            enhanced_products = []
            
            # Add pricing if requested
            if query_params.include_pricing and pricing_service and customer_tier:
                product_data = []
                for product_row in actual_products:
                    category_ids = [cat.id for cat in product_categories_dict.get(product_row.id, [])]
                    product_data.append({
                        "id": str(product_row.id),
                        "price": float(product_row.base_price),
                        "category_ids": category_ids
                    })
                
                pricing_results = await pricing_service.calculate_bulk_product_pricing_optimized(
                    product_data, customer_tier
                )
                
                pricing_dict = {str(result.product_id): result for result in pricing_results}
                
                for product_row in actual_products:
                    enhanced_product = EnhancedProductSchema(
                        id=product_row.id,
                        name=product_row.name,
                        description=product_row.description,
                        brand=product_row.brand,
                        base_price=float(product_row.base_price),
                        unit_measure=product_row.unit_measure,
                        image_urls=product_row.image_urls,
                        created_at=product_row.created_at,
                        updated_at=product_row.updated_at,
                        categories=[safe_model_validate(CategorySchema, cat).model_dump(mode="json") for cat in product_categories_dict.get(product_row.id, [])] if load_categories else [],
                        product_tags=[tag.model_dump(mode="json") for tag in product_tags_dict.get(product_row.id, [])] if load_tags else [],
                        pricing=None,
                        inventory=None
                    )
                    
                    pricing_info = pricing_dict.get(str(product_row.id))
                    if pricing_info:
                        enhanced_product.pricing = PricingInfoSchema(
                            base_price=pricing_info.base_price,
                            final_price=pricing_info.final_price,
                            discount_applied=pricing_info.savings,
                            discount_percentage=(pricing_info.savings / pricing_info.base_price) * 100 if pricing_info.base_price > 0 else 0,
                            applied_price_lists=[pl["price_list_name"] for pl in pricing_info.applied_discounts]
                        )
                    else:
                        enhanced_product.pricing = PricingInfoSchema(
                            base_price=float(product_row.base_price),
                            final_price=float(product_row.base_price),
                            discount_applied=0.0,
                            discount_percentage=0.0,
                            applied_price_lists=[]
                        )
                    
                    if query_params.only_discounted:
                        if (
                            enhanced_product.pricing
                            and enhanced_product.pricing.discount_applied > 0
                        ):
                            enhanced_products.append(enhanced_product)
                    else:
                        enhanced_products.append(enhanced_product)
            else:
                for product_row in actual_products:
                    enhanced_product = EnhancedProductSchema(
                        id=product_row.id,
                        name=product_row.name,
                        description=product_row.description,
                        brand=product_row.brand,
                        base_price=float(product_row.base_price),
                        unit_measure=product_row.unit_measure,
                        image_urls=product_row.image_urls,
                        created_at=product_row.created_at,
                        updated_at=product_row.updated_at,
                        categories=[safe_model_validate(CategorySchema, cat).model_dump(mode="json") for cat in product_categories_dict.get(product_row.id, [])] if load_categories else [],
                        product_tags=[tag.model_dump(mode="json") for tag in product_tags_dict.get(product_row.id, [])] if load_tags else [],
                        pricing=None,
                        inventory=None
                    )
                    enhanced_products.append(enhanced_product)
            
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

    async def create_products(self, products_data: list[CreateProductSchema]) -> list[ProductSchema]:
        """Create multiple new products with validation and optimization"""
        if not products_data:
            raise ValidationException(detail="Product list cannot be empty")

        async with AsyncSessionLocal() as session:
            # Step 1: Bulk validation
            all_category_ids = {cid for p in products_data for cid in p.category_ids}
            all_tag_ids = {tid for p in products_data for tid in p.tag_ids}
            product_names = {p.name for p in products_data}

            # Check for existing product names
            existing_products = (await session.execute(select(Product).filter(Product.name.in_(product_names)))).scalars().all()
            if existing_products:
                raise ConflictException(f"Products with these names already exist: {[p.name for p in existing_products]}")

            # Check for existing categories
            if all_category_ids:
                categories = (await session.execute(select(Category).filter(Category.id.in_(all_category_ids)))).scalars().all()
                if len(categories) != len(all_category_ids):
                    raise ResourceNotFoundException("One or more categories not found.")

            # Check for existing tags
            if all_tag_ids:
                tags = (await session.execute(select(Tag).filter(Tag.id.in_(all_tag_ids)))).scalars().all()
                if len(tags) != len(all_tag_ids):
                    raise ResourceNotFoundException("One or more tags not found.")

            # Step 2: Create Product ORM objects
            new_products = [Product(**data.model_dump(exclude={'category_ids', 'tag_ids'})) for data in products_data]
            
            session.add_all(new_products)
            await session.flush()  # Assigns IDs

            # Step 3: Create associations using bulk inserts
            product_category_associations = []
            product_tag_associations = []
            for i, product in enumerate(new_products):
                data = products_data[i]
                if data.category_ids:
                    for cid in data.category_ids:
                        product_category_associations.append({'product_id': product.id, 'category_id': cid})
                if data.tag_ids:
                    for tid in data.tag_ids:
                        product_tag_associations.append({'product_id': product.id, 'tag_id': tid, 'created_by': 'system'})

            if product_category_associations:
                from src.database.models.associations import product_categories
                await session.execute(product_categories.insert(), product_category_associations)

            if product_tag_associations:
                await session.execute(ProductTag.__table__.insert(), product_tag_associations)

            await session.commit()

            # Step 4: Fetch created products with relationships for the response
            created_ids = [p.id for p in new_products]
            query = select(Product).where(Product.id.in_(created_ids)).options(
                selectinload(Product.categories),
                selectinload(Product.product_tags).selectinload(ProductTag.tag)
            )
            result = await session.execute(query)
            final_products = result.scalars().unique().all()
            
            pydantic_products = safe_model_validate_list(
                ProductSchema,
                final_products,
                max_depth=3
            )
            
            cache_invalidation_manager.invalidate_entity(Collections.PRODUCTS)
            return pydantic_products

    async def get_products_with_pagination_optimized(
        self,
        query_params: ProductQuerySchema,
        customer_tier: Optional[int] = None,
    ) -> PaginatedProductsResponse:
        """Get products with pagination and pricing using optimized SQL query"""
        async with AsyncSessionLocal() as session:
            # Build the base query with filters
            conditions = []
            joins = []
            
            # Apply price filters
            if query_params.min_price is not None:
                conditions.append("p.base_price >= :min_price")
            if query_params.max_price is not None:
                conditions.append("p.base_price <= :max_price")
            
            # Apply category filter
            if query_params.category_ids:
                joins.append("JOIN product_categories pc ON p.id = pc.product_id")
                conditions.append("pc.category_id = ANY(:category_ids)")
            
            # Apply tag filters
            if query_params.tag_ids:
                joins.append("JOIN product_tags pt ON p.id = pt.product_id")
                conditions.append("pt.tag_id = ANY(:tag_ids)")
            elif query_params.tag_types:
                joins.append("JOIN product_tags pt ON p.id = pt.product_id")
                joins.append("JOIN tags t ON pt.tag_id = t.id")
                conditions.append("t.tag_type = ANY(:tag_types)")
            
            # Apply cursor pagination
            if query_params.cursor is not None:
                conditions.append("p.id > :cursor")
            
            # Build the WHERE clause
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            # Build the JOIN clause
            join_clause = " ".join(joins) if joins else ""
            
            # Determine limit
            limit = query_params.limit if query_params.limit is not None else 20
            # Add 1 to check if there are more results
            query_limit = limit + 1
            
            # Build the main product query
            product_query = f"""
                SELECT DISTINCT p.id, p.name, p.description, p.brand, p.base_price, 
                       p.unit_measure, p.image_urls, p.created_at, p.updated_at
                FROM products p
                {join_clause}
                {where_clause}
                ORDER BY p.id
                LIMIT :limit
            """
            
            # Execute the product query
            product_result = await session.execute(
                text(product_query),
                {
                    "min_price": query_params.min_price,
                    "max_price": query_params.max_price,
                    "category_ids": query_params.category_ids,
                    "tag_ids": query_params.tag_ids,
                    "tag_types": query_params.tag_types,
                    "cursor": query_params.cursor,
                    "limit": query_limit
                }
            )
            products_data = product_result.fetchall()
            
            # Check if there are more results
            has_more = len(products_data) > limit
            actual_products_data = products_data[:limit] if has_more else products_data
            
            if not actual_products_data:
                return PaginatedProductsResponse(
                    products=[],
                    pagination={
                        "current_cursor": query_params.cursor,
                        "next_cursor": None,
                        "has_more": False,
                        "total_returned": 0,
                    }
                )
            
            # Get product IDs for pricing query
            product_ids = [row.id for row in actual_products_data]
            
            # If categories are requested, fetch them in a single query
            product_categories_dict = {}
            if query_params.include_categories and product_ids:
                category_query = """
                    SELECT pc.product_id, c.id, c.name, c.slug, c.description
                    FROM product_categories pc
                    JOIN categories c ON pc.category_id = c.id
                    WHERE pc.product_id = ANY(:product_ids)
                """
                category_result = await session.execute(
                    text(category_query),
                    {"product_ids": product_ids}
                )
                category_rows = category_result.fetchall()
                
                # Group categories by product_id
                for row in category_rows:
                    if row.product_id not in product_categories_dict:
                        product_categories_dict[row.product_id] = []
                    product_categories_dict[row.product_id].append({
                        "id": row.id,
                        "name": row.name,
                        "slug": row.slug,
                        "description": row.description
                    })
            
            # If tags are requested, fetch them in a single query
            product_tags_dict = {}
            if query_params.include_tags and product_ids:
                tag_query = """
                    SELECT pt.product_id, t.id, t.tag_type, t.name, t.slug, t.description
                    FROM product_tags pt
                    JOIN tags t ON pt.tag_id = t.id
                    WHERE pt.product_id = ANY(:product_ids)
                """
                tag_result = await session.execute(
                    text(tag_query),
                    {"product_ids": product_ids}
                )
                tag_rows = tag_result.fetchall()

                # Group tags by product_id
                for row in tag_rows:
                    if row.product_id not in product_tags_dict:
                        product_tags_dict[row.product_id] = []
                    product_tags_dict[row.product_id].append({
                        "id": row.id,
                        "tag_type": row.tag_type,
                        "name": row.name,
                        "slug": row.slug,
                        "description": row.description
                    })
            
            # If pricing is requested and we have a customer tier, get pricing info
            pricing_info_dict = {}
            if query_params.include_pricing and customer_tier and product_ids:
                pricing_query = """
                    WITH active_price_lists AS (
                        SELECT 
                            pl.id as price_list_id,
                            pl.name as price_list_name,
                            pl.priority,
                            tpl.tier_id
                        FROM price_lists pl
                        JOIN tier_price_lists tpl ON pl.id = tpl.price_list_id
                        WHERE pl.is_active = true
                          AND tpl.tier_id = :tier_id
                          AND (pl.valid_from IS NULL OR pl.valid_from <= NOW())
                          AND (pl.valid_until IS NULL OR pl.valid_until >= NOW())
                    ),
                    applicable_price_list_lines AS (
                        SELECT 
                            pll.*,
                            apl.priority as price_list_priority
                        FROM price_list_lines pll
                        JOIN active_price_lists apl ON pll.price_list_id = apl.price_list_id
                        WHERE pll.is_active = true
                          AND pll.min_quantity = 1
                          AND (
                              pll.product_id = ANY(:product_ids) OR
                              (pll.product_id IS NULL AND pll.category_id IN (
                                  SELECT pc.category_id 
                                  FROM product_categories pc 
                                  WHERE pc.product_id = ANY(:product_ids)
                              )) OR
                              (pll.product_id IS NULL AND pll.category_id IS NULL)
                          )
                    ),
                    highest_priority_pricing AS (
                        SELECT
                            p.id as product_id,
                            p.base_price,
                            apll.price_list_id,
                            apl.price_list_name,
                            apll.discount_type,
                            apll.discount_value,
                            apll.max_discount_amount,
                            apll.price_list_priority,
                            CASE
                                WHEN apll.discount_type = 'percentage' THEN
                                    GREATEST(
                                        0,
                                        p.base_price - (
                                            LEAST(
                                                p.base_price * (apll.discount_value / 100),
                                                COALESCE(apll.max_discount_amount, p.base_price * (apll.discount_value / 100))
                                            )
                                        )
                                    )
                                WHEN apll.discount_type = 'flat' THEN
                                    GREATEST(0, p.base_price - apll.discount_value)
                                WHEN apll.discount_type = 'fixed_price' THEN
                                    apll.discount_value
                                ELSE p.base_price
                            END as calculated_final_price,
                            ROW_NUMBER() OVER (
                                PARTITION BY p.id
                                ORDER BY
                                    apll.price_list_priority DESC,
                                    CASE
                                        WHEN apll.product_id IS NOT NULL THEN 1
                                        WHEN apll.category_id IS NOT NULL THEN 2
                                        ELSE 3
                                    END,
                                    apll.id
                            ) as priority_rank
                        FROM products p
                        LEFT JOIN applicable_price_list_lines apll ON (
                            apll.product_id = p.id OR
                            (apll.product_id IS NULL AND apll.category_id IN (
                                SELECT pc.category_id
                                FROM product_categories pc
                                WHERE pc.product_id = p.id
                            )) OR
                            (apll.product_id IS NULL AND apll.category_id IS NULL)
                        )
                        LEFT JOIN active_price_lists apl ON apll.price_list_id = apl.price_list_id
                        WHERE p.id = ANY(:product_ids)
                    ),
                    tier_pricing AS (
                        SELECT
                            product_id,
                            base_price,
                            calculated_final_price as final_price,
                            (base_price - calculated_final_price) as savings,
                            discount_type,
                            discount_value,
                            max_discount_amount,
                            price_list_id,
                            price_list_name,
                            price_list_priority
                        FROM highest_priority_pricing
                        WHERE priority_rank = 1
                    )
                    SELECT
                        tp.product_id,
                        tp.final_price,
                        tp.savings,
                        tp.discount_type,
                        tp.discount_value,
                        tp.max_discount_amount,
                        tp.price_list_id,
                        tp.price_list_name,
                        tp.base_price,
                        tp.price_list_priority
                    FROM tier_pricing tp
                    WHERE tp.product_id = ANY(:product_ids)
                    ORDER BY tp.price_list_priority DESC
                """
                
                pricing_result = await session.execute(
                    text(pricing_query),
                    {
                        "tier_id": customer_tier,
                        "product_ids": product_ids
                    }
                )
                pricing_rows = pricing_result.fetchall()
                
                # Create a dictionary for quick lookup
                for row in pricing_rows:
                    pricing_info_dict[row.product_id] = row
            
            # Convert products to EnhancedProductSchema with pricing
            enhanced_products = []
            for product_row in actual_products_data:
                # Create base product schema
                product_dict = {
                    "id": product_row.id,
                    "name": product_row.name,
                    "description": product_row.description,
                    "brand": product_row.brand,
                    "base_price": float(product_row.base_price),
                    "unit_measure": product_row.unit_measure,
                    "image_urls": product_row.image_urls,
                    "created_at": product_row.created_at,
                    "updated_at": product_row.updated_at,
                    "categories": product_categories_dict.get(product_row.id, []),
                    "product_tags": [ProductTagSchema(
                        id=tag["id"],
                        tag_type=tag["tag_type"],
                        name=tag["name"],
                        slug=tag["slug"],
                        description=tag["description"]
                    ) for tag in product_tags_dict.get(product_row.id, [])] if query_params.include_tags else [],
                    "pricing": None,
                    "inventory": None
                }
                
                # Create enhanced product schema
                enhanced_product = EnhancedProductSchema(**product_dict)
                
                # Add pricing if available
                if query_params.include_pricing and product_row.id in pricing_info_dict:
                    pricing_row = pricing_info_dict[product_row.id]
                    discount_percentage = 0
                    if pricing_row.base_price and pricing_row.base_price > 0:
                        discount_percentage = (float(pricing_row.savings) / float(pricing_row.base_price)) * 100
                    
                    enhanced_product.pricing = PricingInfoSchema(
                        base_price=float(pricing_row.base_price),
                        final_price=float(pricing_row.final_price),
                        discount_applied=float(pricing_row.savings),
                        discount_percentage=discount_percentage,
                        applied_price_lists=[pricing_row.price_list_name] if pricing_row.price_list_name else []
                    )
                elif query_params.include_pricing:
                    # No specific pricing, use base price
                    enhanced_product.pricing = PricingInfoSchema(
                        base_price=float(product_row.base_price),
                        final_price=float(product_row.base_price),
                        discount_applied=0.0,
                        discount_percentage=0.0,
                        applied_price_lists=[]
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
            
            # Build pagination metadata
            next_cursor = None
            if has_more and actual_products_data:
                next_cursor = actual_products_data[-1].id
            
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
            
            # Fetch categories and tags separately if needed for Pydantic conversion
            product_categories_dict = {}
            product_tags_dict = {}

            if load_categories and actual_products:
                product_ids = [p.id for p in actual_products]
                category_query = select(Category, Product).join(Product.categories).filter(Product.id.in_(product_ids))
                category_result = await session.execute(category_query)
                for category, product in category_result.all():
                    if product.id not in product_categories_dict:
                        product_categories_dict[product.id] = []
                    product_categories_dict[product.id].append(category)

            if load_tags and actual_products:
                product_ids = [p.id for p in actual_products]
                tag_query = select(ProductTag, Tag).join(ProductTag.tag).filter(ProductTag.product_id.in_(product_ids))
                tag_result = await session.execute(tag_query)
                for product_tag, tag in tag_result.all():
                    if product_tag.product_id not in product_tags_dict:
                        product_tags_dict[product_tag.product_id] = []
                    product_tags_dict[product_tag.product_id].append(ProductTagSchema(
                        id=tag.id,
                        tag_type=tag.tag_type,
                        name=tag.name,
                        slug=tag.slug,
                        description=tag.description,
                        value=product_tag.value if hasattr(product_tag, 'value') else None
                    ))

            enhanced_products = []
            
            # Add pricing if requested
            if query_params.include_pricing and pricing_service and customer_tier:
                product_data = []
                for product_row in actual_products:
                    category_ids = [cat.id for cat in product_categories_dict.get(product_row.id, [])]
                    product_data.append({
                        "id": str(product_row.id),
                        "price": float(product_row.base_price),
                        "category_ids": category_ids
                    })
                
                pricing_results = await pricing_service.calculate_bulk_product_pricing_optimized(
                    product_data, customer_tier
                )
                
                pricing_dict = {str(result.product_id): result for result in pricing_results}
                
                for product_row in actual_products:
                    enhanced_product = EnhancedProductSchema(
                        id=product_row.id,
                        name=product_row.name,
                        description=product_row.description,
                        brand=product_row.brand,
                        base_price=float(product_row.base_price),
                        unit_measure=product_row.unit_measure,
                        image_urls=product_row.image_urls,
                        created_at=product_row.created_at,
                        updated_at=product_row.updated_at,
                        categories=[safe_model_validate(CategorySchema, cat).model_dump(mode="json") for cat in product_categories_dict.get(product_row.id, [])] if load_categories else [],
                        product_tags=[tag.model_dump(mode="json") for tag in product_tags_dict.get(product_row.id, [])] if load_tags else [],
                        pricing=None,
                        inventory=None
                    )
                    
                    pricing_info = pricing_dict.get(str(product_row.id))
                    if pricing_info:
                        enhanced_product.pricing = PricingInfoSchema(
                            base_price=pricing_info.base_price,
                            final_price=pricing_info.final_price,
                            discount_applied=pricing_info.savings,
                            discount_percentage=(pricing_info.savings / pricing_info.base_price) * 100 if pricing_info.base_price > 0 else 0,
                            applied_price_lists=[pl["price_list_name"] for pl in pricing_info.applied_discounts]
                        )
                    else:
                        enhanced_product.pricing = PricingInfoSchema(
                            base_price=float(product_row.base_price),
                            final_price=float(product_row.base_price),
                            discount_applied=0.0,
                            discount_percentage=0.0,
                            applied_price_lists=[]
                        )
                    
                    if query_params.only_discounted:
                        if (
                            enhanced_product.pricing
                            and enhanced_product.pricing.discount_applied > 0
                        ):
                            enhanced_products.append(enhanced_product)
                    else:
                        enhanced_products.append(enhanced_product)
            else:
                for product_row in actual_products:
                    enhanced_product = EnhancedProductSchema(
                        id=product_row.id,
                        name=product_row.name,
                        description=product_row.description,
                        brand=product_row.brand,
                        base_price=float(product_row.base_price),
                        unit_measure=product_row.unit_measure,
                        image_urls=product_row.image_urls,
                        created_at=product_row.created_at,
                        updated_at=product_row.updated_at,
                        categories=[safe_model_validate(CategorySchema, cat).model_dump(mode="json") for cat in product_categories_dict.get(product_row.id, [])] if load_categories else [],
                        product_tags=[tag.model_dump(mode="json") for tag in product_tags_dict.get(product_row.id, [])] if load_tags else [],
                        pricing=None,
                        inventory=None
                    )
                    enhanced_products.append(enhanced_product)
            
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

    # Tag management methods - delegated to shared TagService
    async def create_product_tag(self, name: str, tag_type_suffix: str, slug: Optional[str] = None, description: Optional[str] = None) -> Tag:
        """Create a new product tag with specific type (e.g., 'color', 'size')"""
        from src.api.tags.models import CreateTagSchema
        tag_data = CreateTagSchema(
            tag_type=tag_type_suffix,  # Will become "product_{tag_type_suffix}"
            name=name,
            slug=slug,
            description=description
        )
        return await self.tag_service.create_tag(tag_data)

    async def create_product_tags(self, tags_data: list[CreateTagSchema]) -> list[Tag]:
        """Create multiple new product tags with specific type (e.g., 'color', 'size')"""
        from src.api.tags.models import CreateTagSchema
        return await self.tag_service.create_tags(tags_data)

    async def get_product_tags(self, is_active: bool = True, tag_type_suffix: Optional[str] = None) -> List[Tag]:
        """Get product tags, optionally filtered by type suffix (e.g., 'color', 'size')"""
        return await self.tag_service.get_tags_by_type(is_active, tag_type_suffix)

    async def assign_tag_to_product(self, product_id: int, tag_id: int, value: Optional[str] = None):
        """Assign a tag to a product using shared TagService"""
        await self.tag_service.assign_tag_to_entity(product_id, tag_id, value)

        # Invalidate cache
        products_cache.invalidate_product_cache(str(product_id))
        cache_invalidation_manager.invalidate_entity(Collections.PRODUCTS, str(product_id))

    async def remove_tag_from_product(self, product_id: int, tag_id: int) -> bool:
        """Remove a tag from a product using shared TagService"""
        success = await self.tag_service.remove_tag_from_entity(product_id, tag_id)

        if success:
            # Invalidate cache
            products_cache.invalidate_product_cache(str(product_id))
            cache_invalidation_manager.invalidate_entity(Collections.PRODUCTS, str(product_id))

        return success