import asyncio
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import text

from src.api.products.models import (
    EnhancedProductSchema,
    PaginatedProductsResponse,
    ProductQuerySchema,
)
from src.api.tags.service import TagService
from src.config.cache_config import CacheConfig
from src.database.connection import AsyncSessionLocal
from src.shared.cache_service import cache_service
from src.shared.error_handler import ErrorHandler


class ProductQueryService:
    """Product query service with advanced SQL optimization and caching"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.tag_service = TagService(entity_type="product")
        self.cache = cache_service
        # Import here to avoid circular dependency
        from src.api.products.services.inventory_service import (
            ProductInventoryService,
        )

        self.inventory_service = ProductInventoryService()

    async def get_products_with_criteria(
        self,
        query_params: ProductQuerySchema,
        customer_tier: Optional[int] = None,
        store_ids: Optional[List[int]] = None,
        is_nearby_store: bool = True,
    ) -> PaginatedProductsResponse:
        """Execute comprehensive product query with integrated pricing and inventory data"""

        # Create a query without inventory for caching
        query_without_inventory = ProductQuerySchema(
            **{**query_params.model_dump(), "include_inventory": False}
        )

        # Generate cache key for products without inventory
        cache_key = self._generate_cache_key(
            query_without_inventory, customer_tier, None, is_nearby_store
        )

        # Try cache first for product data
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            products = [EnhancedProductSchema(**p) for p in cached_result["products"]]
            pagination = cached_result["pagination"]
        else:
            async with AsyncSessionLocal() as session:
                # Build comprehensive SQL query without inventory
                sql_query, params = self._build_comprehensive_sql(
                    query_without_inventory, customer_tier, None
                )

                # Execute single query
                result = await session.execute(text(sql_query), params)
                rows = result.fetchall()

                # Process results efficiently
                products, pagination = await self._process_results_fast(
                    rows, query_without_inventory, is_nearby_store
                )

            # Cache product data (without inventory)
            cache_data = {
                "products": [p.model_dump(mode="json") for p in products],
                "pagination": pagination,
            }
            await self.cache.set(
                cache_key, cache_data, ttl=CacheConfig.PRODUCT_DATA_TTL
            )

        # Add real-time inventory if requested OR if filters require it
        needs_inventory = query_params.include_inventory or query_params.has_inventory

        # Determine if we need to apply inventory filtering
        has_inventory_filter = query_params.has_inventory is not None

        if needs_inventory and store_ids:
            products = await self.inventory_service.add_inventory_to_products_bulk(
                products=products,
                store_ids=store_ids,
                is_nearby_store=is_nearby_store,
                latitude=query_params.latitude,
                longitude=query_params.longitude,
            )

            # Apply inventory filters only if we're filtering by has_inventory
            if has_inventory_filter:
                products = [
                    p
                    for p in products
                    if p.inventory
                    and (
                        p.inventory.can_order
                        if query_params.has_inventory
                        else not p.inventory.can_order
                    )
                ]

            # Update pagination total_returned after filtering
            pagination["total_returned"] = len(products)

        # Remove inventory from response if not explicitly requested
        if not query_params.include_inventory:
            for product in products:
                product.inventory = None

        response = PaginatedProductsResponse(products=products, pagination=pagination)

        return response

    def _build_comprehensive_sql(
        self,
        query_params: ProductQuerySchema,
        customer_tier: Optional[int] = None,
        store_ids: Optional[List[int]] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """Build comprehensive SQL query with integrated joins and filtering"""

        # Base SELECT with all needed fields
        select_fields = [
            "p.id",
            "p.ref",
            "p.name",
            "p.description",
            "p.brand",
            "p.base_price",
            "p.unit_measure",
            "p.image_urls",
            "p.ecommerce_category_id",
            "p.ecommerce_subcategory_id",
            "p.alternative_product_ids",
            "p.created_at",
            "p.updated_at",
        ]

        # Add category fields if requested
        if query_params.include_categories:
            select_fields.extend(
                [
                    "STRING_AGG(DISTINCT CONCAT(c.id, '|', c.name, '|', COALESCE(c.description, ''), '|', COALESCE(c.sort_order::text, ''), '|', COALESCE(c.image_url, ''), '|', COALESCE(c.parent_category_id::text, '')), ';') as categories_data"
                ]
            )

        # Add tag fields if requested
        if query_params.include_tags:
            select_fields.extend(
                [
                    "STRING_AGG(DISTINCT CONCAT(t.id::text, '|', COALESCE(t.tag_type, ''), '|', COALESCE(t.name, ''), '|', COALESCE(t.slug, ''), '|', COALESCE(t.description, ''), '|', COALESCE(pt.value, '')), ';') as tags_data"
                ]
            )

        # Note: Inventory is handled separately by ProductInventoryService (not in SQL)

        # Add pricing fields if requested
        if query_params.include_pricing and customer_tier:
            select_fields.extend(
                [
                    "COALESCE(pricing.final_price, p.base_price) as final_price",
                    "COALESCE(pricing.savings, 0) as savings",
                    "COALESCE(pricing.discount_percentage, 0) as discount_percentage",
                    "pricing.price_list_names",
                ]
            )

        # Build FROM clause with optimal JOINs
        joins = ["FROM products p"]

        if query_params.include_categories:
            joins.append("LEFT JOIN product_categories pc ON p.id = pc.product_id")
            joins.append("LEFT JOIN categories c ON pc.category_id = c.id")

        if query_params.include_tags:
            joins.append("LEFT JOIN product_tags pt ON p.id = pt.product_id")
            joins.append("LEFT JOIN tags t ON pt.tag_id = t.id")

        # Note: Inventory JOIN removed - handled separately by ProductInventoryService

        if query_params.include_pricing and customer_tier:
            # Integrated pricing calculation subquery
            pricing_cte = """
            WITH pricing AS (
                SELECT
                    p.id as product_id,
                    p.base_price,
                    CASE
                        WHEN pll.discount_type = 'percentage' THEN
                            GREATEST(0, p.base_price - (LEAST(p.base_price * (pll.discount_value / 100), COALESCE(pll.max_discount_amount, p.base_price))))
                        WHEN pll.discount_type = 'flat' THEN
                            GREATEST(0, p.base_price - pll.discount_value)
                        WHEN pll.discount_type = 'fixed_price' THEN
                            pll.discount_value
                        ELSE p.base_price
                    END as final_price,
                    CASE
                        WHEN pll.discount_type = 'percentage' THEN
                            LEAST(p.base_price * (pll.discount_value / 100), COALESCE(pll.max_discount_amount, p.base_price))
                        WHEN pll.discount_type = 'flat' THEN
                            pll.discount_value
                        WHEN pll.discount_type = 'fixed_price' THEN
                            GREATEST(0, p.base_price - pll.discount_value)
                        ELSE 0
                    END as savings,
                    CASE
                        WHEN p.base_price > 0 THEN
                            CASE
                                WHEN pll.discount_type = 'percentage' THEN
                                    LEAST(pll.discount_value, (COALESCE(pll.max_discount_amount, p.base_price) / p.base_price) * 100)
                                WHEN pll.discount_type = 'flat' THEN
                                    (pll.discount_value / p.base_price) * 100
                                WHEN pll.discount_type = 'fixed_price' THEN
                                    ((p.base_price - pll.discount_value) / p.base_price) * 100
                                ELSE 0
                            END
                        ELSE 0
                    END as discount_percentage,
                    STRING_AGG(pl.name, ';') as price_list_names,
                    ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY pl.priority DESC, pll.id) as rn
                FROM products p
                LEFT JOIN price_list_lines pll ON (
                    pll.product_id = p.id OR
                    (pll.product_id IS NULL AND pll.category_id IN (SELECT category_id FROM product_categories WHERE product_id = p.id)) OR
                    (pll.product_id IS NULL AND pll.category_id IS NULL)
                )
                LEFT JOIN price_lists pl ON pll.price_list_id = pl.id
                LEFT JOIN tier_price_lists tpl ON pl.id = tpl.price_list_id
                WHERE pl.is_active = true
                  AND tpl.tier_id = :customer_tier
                  AND (pl.valid_from IS NULL OR pl.valid_from <= NOW())
                  AND (pl.valid_until IS NULL OR pl.valid_until >= NOW())
                  AND pll.is_active = true
                  AND pll.min_quantity <= 1
                GROUP BY p.id, p.base_price, pll.discount_type, pll.discount_value, pll.max_discount_amount, pl.priority, pll.id
            )
            """
            joins.insert(0, pricing_cte)
            joins.append(
                "LEFT JOIN pricing ON p.id = pricing.product_id AND pricing.rn = 1"
            )

        # Build WHERE conditions
        where_conditions = []
        params: Dict[str, Any] = (
            {"customer_tier": customer_tier} if customer_tier else {}
        )

        if query_params.category_ids:
            where_conditions.append(
                "p.id IN (SELECT product_id FROM product_categories WHERE category_id = ANY(:category_ids))"
            )
            params["category_ids"] = list(query_params.category_ids)

        if query_params.tags:
            tag_filter_result = self.tag_service.parse_tag_filters(query_params.tags)
            if tag_filter_result["conditions"]:
                # Use the conditions generated by tag service directly
                tag_conditions = " OR ".join(tag_filter_result["conditions"])
                if tag_conditions:
                    where_conditions.append(
                        f"p.id IN (SELECT DISTINCT pt.product_id FROM product_tags pt JOIN tags t ON pt.tag_id = t.id WHERE {tag_conditions})"
                    )
                    params.update(tag_filter_result["params"])

        if query_params.min_price is not None:
            where_conditions.append("p.base_price >= :min_price")
            params["min_price"] = int(query_params.min_price)

        if query_params.max_price is not None:
            where_conditions.append("p.base_price <= :max_price")
            params["max_price"] = int(query_params.max_price)

        if query_params.cursor is not None:
            where_conditions.append("p.id > :cursor")
            params["cursor"] = query_params.cursor

        if (
            query_params.only_discounted
            and query_params.include_pricing
            and customer_tier
        ):
            where_conditions.append("pricing.savings > 0")

        # Build complete query
        where_clause = (
            f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        limit = query_params.limit if query_params.limit is not None else 20
        params["limit"] = limit + 1  # +1 to check if more exist

        sql_query = f"""
        {joins[0] if "WITH" in joins[0] else ""}
        SELECT {", ".join(select_fields)}
        {" ".join(joins[1:] if "WITH" in joins[0] else joins)}
        {where_clause}
        GROUP BY p.id, p.ref, p.name, p.description, p.brand, p.base_price,
                 p.unit_measure, p.image_urls, p.ecommerce_category_id,
                 p.ecommerce_subcategory_id, p.alternative_product_ids, p.created_at, p.updated_at
                 {", pricing.final_price, pricing.savings, pricing.discount_percentage, pricing.price_list_names" if query_params.include_pricing and customer_tier else ""}
        ORDER BY p.id
        LIMIT :limit
        """

        return sql_query, params

    async def _process_results_fast(
        self,
        rows: Sequence[Any],
        query_params: ProductQuerySchema,
        is_nearby_store: bool = True,
    ) -> tuple[List[EnhancedProductSchema], Dict]:
        """Fast result processing without ORM overhead"""

        if not rows:
            return [], {
                "current_cursor": query_params.cursor,
                "next_cursor": None,
                "has_more": False,
                "total_returned": 0,
            }

        limit = query_params.limit if query_params.limit is not None else 20
        has_more = len(rows) > limit
        actual_rows = rows[:limit] if has_more else rows

        products = []

        # Process rows in parallel batches for CPU-bound operations
        batch_size = 50
        tasks = []

        for i in range(0, len(actual_rows), batch_size):
            batch = actual_rows[i : i + batch_size]
            task = self._process_row_batch(batch, query_params, is_nearby_store)
            tasks.append(task)

        if tasks:
            batch_results = await asyncio.gather(*tasks)
            for batch_products in batch_results:
                products.extend(batch_products)

        next_cursor = None
        if has_more and actual_rows:
            next_cursor = actual_rows[-1].id

        pagination = {
            "current_cursor": query_params.cursor,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total_returned": len(products),
        }

        return products, pagination

    async def _process_row_batch(
        self,
        rows: Sequence[Any],
        query_params: ProductQuerySchema,
        is_nearby_store: bool = True,
    ) -> List[EnhancedProductSchema]:
        """Process a batch of rows efficiently"""

        # Note: Inventory is handled separately, no need to check for excluded products here

        products = []

        for row in rows:
            # Build product data efficiently
            product_data = {
                "id": row.id,
                "ref": row.ref,
                "name": row.name,
                "description": row.description,
                "brand": row.brand,
                "base_price": float(row.base_price),
                "unit_measure": row.unit_measure,
                "image_urls": row.image_urls or [],
                "ecommerce_category_id": row.ecommerce_category_id,
                "ecommerce_subcategory_id": row.ecommerce_subcategory_id,
                "alternative_product_ids": row.alternative_product_ids or [],
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "categories": [],
                "product_tags": [],
                "pricing": None,
                "inventory": None,
            }

            # Parse categories efficiently
            if (
                query_params.include_categories
                and hasattr(row, "categories_data")
                and row.categories_data
            ):
                categories = []
                for cat_data in row.categories_data.split(";"):
                    if cat_data:
                        parts = cat_data.split("|")
                        if len(parts) >= 6:
                            try:
                                categories.append(
                                    {
                                        "id": int(parts[0])
                                        if parts[0].strip()
                                        else None,
                                        "name": parts[1],
                                        "description": parts[2] or None,
                                        "sort_order": int(parts[3])
                                        if parts[3].strip()
                                        else None,
                                        "image_url": parts[4] or None,
                                        "parent_category_id": int(parts[5])
                                        if parts[5].strip()
                                        else None,
                                    }
                                )
                            except (ValueError, IndexError):
                                # Skip malformed category data
                                continue
                product_data["categories"] = categories

            # Parse tags efficiently
            if query_params.include_tags:
                tags = []
                if hasattr(row, "tags_data") and row.tags_data:
                    for tag_data in row.tags_data.split(";"):
                        if tag_data.strip():  # Only process non-empty tag data
                            parts = tag_data.split("|")
                            if len(parts) >= 6:
                                try:
                                    # Skip entries where essential fields are empty
                                    if not parts[0].strip():  # Skip if no tag ID
                                        continue
                                    tags.append(
                                        {
                                            "id": int(parts[0].strip()),
                                            "tag_type": parts[1],
                                            "name": parts[2],
                                            "slug": parts[3],
                                            "description": parts[4] or None,
                                            "value": parts[5] or None,
                                        }
                                    )
                                except (ValueError, IndexError):
                                    # Skip malformed tag data
                                    continue
                product_data["product_tags"] = tags

            # Note: Inventory is added separately by ProductInventoryService, not parsed here

            # Parse pricing efficiently
            if query_params.include_pricing and hasattr(row, "final_price"):
                try:
                    base_price = (
                        float(row.base_price) if row.base_price is not None else 0.0
                    )
                    final_price = (
                        float(row.final_price)
                        if row.final_price is not None
                        else base_price
                    )
                    savings = (
                        float(row.savings)
                        if hasattr(row, "savings") and row.savings is not None
                        else 0.0
                    )
                    discount_percentage = (
                        float(row.discount_percentage)
                        if hasattr(row, "discount_percentage")
                        and row.discount_percentage is not None
                        else 0.0
                    )
                    price_list_names = (
                        row.price_list_names.split(";")
                        if hasattr(row, "price_list_names") and row.price_list_names
                        else []
                    )

                    product_data["pricing"] = {
                        "base_price": base_price,
                        "final_price": final_price,
                        "discount_applied": savings,
                        "discount_percentage": discount_percentage,
                        "applied_price_lists": price_list_names,
                    }
                except (ValueError, TypeError):
                    # Skip pricing if data is malformed
                    product_data["pricing"] = None

            products.append(EnhancedProductSchema(**product_data))

        return products

    async def _get_excluded_products(self, product_ids: List[int]) -> set:
        """Get products that have the NEXT_DAY_DELIVERY_ONLY_TAG_ID"""
        from src.config.constants import NEXT_DAY_DELIVERY_ONLY_TAG_ID
        from src.database.connection import AsyncSessionLocal

        if not product_ids:
            return set()

        async with AsyncSessionLocal() as session:
            query = text("""
                SELECT DISTINCT product_id
                FROM product_tags
                WHERE product_id = ANY(:product_ids)
                  AND tag_id = :excluded_tag_id
            """)

            result = await session.execute(
                query,
                {
                    "product_ids": product_ids,
                    "excluded_tag_id": NEXT_DAY_DELIVERY_ONLY_TAG_ID,
                },
            )

            return {row.product_id for row in result.fetchall()}

    def _generate_cache_key(
        self,
        query_params: ProductQuerySchema,
        customer_tier: Optional[int],
        store_ids: Optional[List[int]],
        is_nearby_store: bool = True,
    ) -> str:
        """Generate cache key for query parameters"""
        key_parts = [
            "products_v2",
            f"limit_{query_params.limit or 20}",
            f"cursor_{query_params.cursor or 0}",
            f"pricing_{query_params.include_pricing}",
            f"categories_{query_params.include_categories}",
            f"tags_{query_params.include_tags}",
            f"inventory_{query_params.include_inventory}",
            f"tier_{customer_tier or 0}",
            f"stores_{','.join(map(str, store_ids or []))}",
            f"nearby_{is_nearby_store}",
            f"cat_ids_{','.join(map(str, query_params.category_ids or []))}",
            f"tags_{','.join(query_params.tags or [])}",
            f"min_price_{query_params.min_price or 0}",
            f"max_price_{query_params.max_price or 0}",
            f"discounted_{query_params.only_discounted}",
        ]
        return ":".join(key_parts)

    async def get_single_product_by_id(
        self,
        product_id: int,
        query_params: ProductQuerySchema,
        customer_tier: Optional[int] = None,
        store_ids: Optional[List[int]] = None,
        quantity: int = 1,
        is_nearby_store: bool = True,
    ) -> Optional[EnhancedProductSchema]:
        """Get single product by ID using the same comprehensive SQL as bulk query"""

        # Create query without inventory for fetching product data
        query_without_inventory = ProductQuerySchema(
            **{**query_params.model_dump(), "include_inventory": False}
        )

        async with AsyncSessionLocal() as session:
            # Build SQL query with product ID filter (without inventory)
            sql_query, params = self._build_single_product_sql(
                product_id=product_id,
                query_params=query_without_inventory,
                customer_tier=customer_tier,
                store_ids=None,
                quantity=quantity,
            )

            # Execute query
            result = await session.execute(text(sql_query), params)
            row = result.fetchone()

            if not row:
                return None

            # Process single result using same logic as bulk
            products = await self._process_single_row(row, query_without_inventory)
            if not products:
                return None

            product = products[0]

        # Add real-time inventory if requested
        if query_params.include_inventory and store_ids:
            products_with_inventory = (
                await self.inventory_service.add_inventory_to_products_bulk(
                    products=[product],
                    store_ids=store_ids,
                    is_nearby_store=is_nearby_store,
                    latitude=query_params.latitude,
                    longitude=query_params.longitude,
                )
            )
            product = products_with_inventory[0] if products_with_inventory else product

        return product

    async def get_single_product_by_ref(
        self,
        ref: str,
        query_params: ProductQuerySchema,
        customer_tier: Optional[int] = None,
        store_ids: Optional[List[int]] = None,
        quantity: int = 1,
        is_nearby_store: bool = True,
    ) -> Optional[EnhancedProductSchema]:
        """Get single product by ref using the same comprehensive SQL as bulk query"""

        # Create query without inventory for fetching product data
        query_without_inventory = ProductQuerySchema(
            **{**query_params.model_dump(), "include_inventory": False}
        )

        async with AsyncSessionLocal() as session:
            # Build SQL query with product ref filter (without inventory)
            sql_query, params = self._build_single_product_sql(
                product_ref=ref,
                query_params=query_without_inventory,
                customer_tier=customer_tier,
                store_ids=None,
                quantity=quantity,
            )

            # Execute query
            result = await session.execute(text(sql_query), params)
            row = result.fetchone()

            if not row:
                return None

            # Process single result using same logic as bulk
            products = await self._process_single_row(row, query_without_inventory)
            if not products:
                return None

            product = products[0]

        # Add real-time inventory if requested
        if query_params.include_inventory and store_ids:
            products_with_inventory = (
                await self.inventory_service.add_inventory_to_products_bulk(
                    products=[product],
                    store_ids=store_ids,
                    is_nearby_store=is_nearby_store,
                    latitude=query_params.latitude,
                    longitude=query_params.longitude,
                )
            )
            product = products_with_inventory[0] if products_with_inventory else product

        return product

    def _build_single_product_sql(
        self,
        query_params: ProductQuerySchema,
        customer_tier: Optional[int] = None,
        store_ids: Optional[List[int]] = None,
        quantity: int = 1,
        product_id: Optional[int] = None,
        product_ref: Optional[str] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """Build SQL for single product retrieval (similar to _build_comprehensive_sql)"""

        # Base SELECT with all needed fields
        select_fields = [
            "p.id",
            "p.ref",
            "p.name",
            "p.description",
            "p.brand",
            "p.base_price",
            "p.unit_measure",
            "p.image_urls",
            "p.ecommerce_category_id",
            "p.ecommerce_subcategory_id",
            "p.alternative_product_ids",
            "p.created_at",
            "p.updated_at",
        ]

        # Add category fields if requested
        if query_params.include_categories:
            select_fields.extend(
                [
                    "STRING_AGG(DISTINCT CONCAT(c.id, '|', c.name, '|', COALESCE(c.description, ''), '|', COALESCE(c.sort_order::text, ''), '|', COALESCE(c.image_url, ''), '|', COALESCE(c.parent_category_id::text, '')), ';') as categories_data"
                ]
            )

        # Add tag fields if requested
        if query_params.include_tags:
            select_fields.extend(
                [
                    "STRING_AGG(DISTINCT CONCAT(t.id::text, '|', COALESCE(t.tag_type, ''), '|', COALESCE(t.name, ''), '|', COALESCE(t.slug, ''), '|', COALESCE(t.description, ''), '|', COALESCE(pt.value, '')), ';') as tags_data"
                ]
            )

        # Note: Inventory is handled separately by ProductInventoryService (not in SQL)

        # Add pricing fields if requested
        if query_params.include_pricing and customer_tier:
            select_fields.extend(
                [
                    "COALESCE(pricing.final_price, p.base_price) as final_price",
                    "COALESCE(pricing.savings, 0) as savings",
                    "COALESCE(pricing.discount_percentage, 0) as discount_percentage",
                    "pricing.price_list_names",
                ]
            )

        # Build FROM clause with optimal JOINs
        joins = ["FROM products p"]

        if query_params.include_categories:
            joins.append("LEFT JOIN product_categories pc ON p.id = pc.product_id")
            joins.append("LEFT JOIN categories c ON pc.category_id = c.id")

        if query_params.include_tags:
            joins.append("LEFT JOIN product_tags pt ON p.id = pt.product_id")
            joins.append("LEFT JOIN tags t ON pt.tag_id = t.id")

        # Note: Inventory JOIN removed - handled separately by ProductInventoryService

        if query_params.include_pricing and customer_tier:
            # Use same pricing CTE as bulk query
            pricing_cte = """
            WITH pricing AS (
                SELECT
                    p.id as product_id,
                    p.base_price,
                    CASE
                        WHEN pll.discount_type = 'percentage' THEN
                            GREATEST(0, p.base_price - (LEAST(p.base_price * (pll.discount_value / 100), COALESCE(pll.max_discount_amount, p.base_price))))
                        WHEN pll.discount_type = 'flat' THEN
                            GREATEST(0, p.base_price - pll.discount_value)
                        WHEN pll.discount_type = 'fixed_price' THEN
                            pll.discount_value
                        ELSE p.base_price
                    END as final_price,
                    CASE
                        WHEN pll.discount_type = 'percentage' THEN
                            LEAST(p.base_price * (pll.discount_value / 100), COALESCE(pll.max_discount_amount, p.base_price))
                        WHEN pll.discount_type = 'flat' THEN
                            pll.discount_value
                        WHEN pll.discount_type = 'fixed_price' THEN
                            GREATEST(0, p.base_price - pll.discount_value)
                        ELSE 0
                    END as savings,
                    CASE
                        WHEN p.base_price > 0 THEN
                            CASE
                                WHEN pll.discount_type = 'percentage' THEN
                                    LEAST(pll.discount_value, (COALESCE(pll.max_discount_amount, p.base_price) / p.base_price) * 100)
                                WHEN pll.discount_type = 'flat' THEN
                                    (pll.discount_value / p.base_price) * 100
                                WHEN pll.discount_type = 'fixed_price' THEN
                                    ((p.base_price - pll.discount_value) / p.base_price) * 100
                                ELSE 0
                            END
                        ELSE 0
                    END as discount_percentage,
                    STRING_AGG(pl.name, ';') as price_list_names,
                    ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY pl.priority DESC, pll.id) as rn
                FROM products p
                LEFT JOIN price_list_lines pll ON (
                    pll.product_id = p.id OR
                    (pll.product_id IS NULL AND pll.category_id IN (SELECT category_id FROM product_categories WHERE product_id = p.id)) OR
                    (pll.product_id IS NULL AND pll.category_id IS NULL)
                )
                LEFT JOIN price_lists pl ON pll.price_list_id = pl.id
                LEFT JOIN tier_price_lists tpl ON pl.id = tpl.price_list_id
                WHERE pl.is_active = true
                  AND tpl.tier_id = :customer_tier
                  AND (pl.valid_from IS NULL OR pl.valid_from <= NOW())
                  AND (pl.valid_until IS NULL OR pl.valid_until >= NOW())
                  AND pll.is_active = true
                  AND pll.min_quantity <= :quantity
                GROUP BY p.id, p.base_price, pll.discount_type, pll.discount_value, pll.max_discount_amount, pl.priority, pll.id
            )
            """
            joins.insert(0, pricing_cte)
            joins.append(
                "LEFT JOIN pricing ON p.id = pricing.product_id AND pricing.rn = 1"
            )

        # Build WHERE conditions for single product
        where_conditions = []
        params: Dict[str, Any] = (
            {"customer_tier": customer_tier, "quantity": quantity}
            if customer_tier
            else {"quantity": quantity}
        )

        # Add product filter (ID or ref)
        if product_id is not None:
            where_conditions.append("p.id = :product_id")
            params["product_id"] = product_id
        elif product_ref is not None:
            where_conditions.append("p.ref = :product_ref")
            params["product_ref"] = product_ref

        # Build complete query
        where_clause = (
            f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        sql_query = f"""
        {joins[0] if "WITH" in joins[0] else ""}
        SELECT {", ".join(select_fields)}
        {" ".join(joins[1:] if "WITH" in joins[0] else joins)}
        {where_clause}
        GROUP BY p.id, p.ref, p.name, p.description, p.brand, p.base_price,
                 p.unit_measure, p.image_urls, p.ecommerce_category_id,
                 p.ecommerce_subcategory_id, p.alternative_product_ids, p.created_at, p.updated_at
                 {", pricing.final_price, pricing.savings, pricing.discount_percentage, pricing.price_list_names" if query_params.include_pricing and customer_tier else ""}
        """

        return sql_query, params

    async def _process_single_row(
        self, row: Any, query_params: ProductQuerySchema
    ) -> List[EnhancedProductSchema]:
        """Process single row result using same logic as bulk processing"""
        return await self._process_row_batch([row], query_params)

    async def get_products_by_ids(
        self,
        product_ids: List[int],
        customer_tier: Optional[int] = None,
        store_ids: Optional[List[int]] = None,
        is_nearby_store: bool = True,
        include_pricing: bool = True,
        include_categories: bool = False,
        include_tags: bool = False,
        include_inventory: bool = False,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> List[EnhancedProductSchema]:
        """Get products by a list of IDs."""

        if not product_ids:
            return []

        async with AsyncSessionLocal() as session:
            # Step 1: Build comprehensive SQL for these products using existing infrastructure
            sql_query, params = self._build_recent_products_sql(
                product_ids=product_ids,
                customer_tier=customer_tier,
                store_ids=store_ids,
                include_pricing=include_pricing,
                include_categories=include_categories,
                include_tags=include_tags,
                include_inventory=include_inventory,
            )

            # Step 2: Execute query
            result = await session.execute(text(sql_query), params)
            rows = result.fetchall()

            if not rows:
                return []

            # Step 3: Process results using existing logic
            from src.api.products.models import ProductQuerySchema

            query_params = ProductQuerySchema(
                limit=len(product_ids),
                cursor=None,
                store_id=store_ids,
                include_pricing=include_pricing,
                include_inventory=include_inventory,
                include_categories=include_categories,
                include_tags=include_tags,
                latitude=latitude,
                longitude=longitude,
            )

            products = await self._process_row_batch(rows, query_params)

            # Step 4: Add inventory if requested (consistent with get_products_with_criteria)
            if include_inventory and store_ids:
                products = await self.inventory_service.add_inventory_to_products_bulk(
                    products=products,
                    store_ids=store_ids,
                    is_nearby_store=is_nearby_store,
                    latitude=latitude,
                    longitude=longitude,
                )

            return products

    async def get_recent_products_for_user(
        self,
        user_id: str,
        limit: int,
        customer_tier: Optional[int] = None,
        store_ids: Optional[List[int]] = None,
        include_pricing: bool = True,
        include_categories: bool = False,
        include_tags: bool = False,
        include_inventory: bool = False,
        is_nearby_store: bool = True,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> List[EnhancedProductSchema]:
        """Get recently bought products for a user from ordered carts"""

        async with AsyncSessionLocal() as session:
            # Step 1: Get recent product IDs from ordered carts
            recent_products_query = """
            SELECT DISTINCT ON (ci.product_id)
                ci.product_id
            FROM cart_items ci
            JOIN carts c ON ci.cart_id = c.id
            WHERE c.created_by = :user_id
              AND c.status = 'ordered'
            ORDER BY ci.product_id, c.ordered_at DESC
            LIMIT :limit
            """

            result = await session.execute(
                text(recent_products_query), {"user_id": user_id, "limit": limit}
            )
            product_rows = result.fetchall()

            if not product_rows:
                return []

            product_ids = [row.product_id for row in product_rows]

            # Step 2: Build comprehensive SQL for these products using existing infrastructure
            sql_query, params = self._build_recent_products_sql(
                product_ids=product_ids,
                customer_tier=customer_tier,
                store_ids=store_ids,
                include_pricing=include_pricing,
                include_categories=include_categories,
                include_tags=include_tags,
                include_inventory=include_inventory,
            )

            # Step 3: Execute query
            result = await session.execute(text(sql_query), params)
            rows = result.fetchall()

            if not rows:
                return []

            # Step 4: Process results using existing logic
            from src.api.products.models import ProductQuerySchema

            query_params = ProductQuerySchema(
                limit=limit,
                cursor=None,
                store_id=store_ids,
                include_pricing=include_pricing,
                include_inventory=include_inventory,
                include_categories=include_categories,
                include_tags=include_tags,
                category_ids=None,
                tags=None,
                min_price=None,
                max_price=None,
                only_discounted=False,
                latitude=latitude,
                longitude=longitude,
            )

            products = await self._process_row_batch(rows, query_params)

            # Step 5: Add inventory if requested (consistent with get_products_with_criteria)
            if include_inventory and store_ids:
                products = await self.inventory_service.add_inventory_to_products_bulk(
                    products=products,
                    store_ids=store_ids,
                    is_nearby_store=is_nearby_store,
                    latitude=latitude,
                    longitude=longitude,
                )

            # Step 6: Reorder products to match the original recent order
            product_order_map = {pid: idx for idx, pid in enumerate(product_ids)}
            products.sort(key=lambda p: product_order_map.get(p.id, len(product_ids)))

            return products

    def _build_recent_products_sql(
        self,
        product_ids: List[int],
        customer_tier: Optional[int] = None,
        store_ids: Optional[List[int]] = None,
        include_pricing: bool = True,
        include_categories: bool = True,
        include_tags: bool = False,
        include_inventory: bool = False,
    ) -> tuple[str, Dict[str, Any]]:
        """Build SQL for recent products (similar to _build_comprehensive_sql but for specific product IDs)"""

        # Base SELECT with all needed fields
        select_fields = [
            "p.id",
            "p.ref",
            "p.name",
            "p.description",
            "p.brand",
            "p.base_price",
            "p.unit_measure",
            "p.image_urls",
            "p.ecommerce_category_id",
            "p.ecommerce_subcategory_id",
            "p.alternative_product_ids",
            "p.created_at",
            "p.updated_at",
        ]

        # Add category fields if requested
        if include_categories:
            select_fields.extend(
                [
                    "STRING_AGG(DISTINCT CONCAT(c.id, '|', c.name, '|', COALESCE(c.description, ''), '|', COALESCE(c.sort_order::text, ''), '|', COALESCE(c.image_url, ''), '|', COALESCE(c.parent_category_id::text, '')), ';') as categories_data"
                ]
            )

        # Add tag fields if requested
        if include_tags:
            select_fields.extend(
                [
                    "STRING_AGG(DISTINCT CONCAT(t.id::text, '|', COALESCE(t.tag_type, ''), '|', COALESCE(t.name, ''), '|', COALESCE(t.slug, ''), '|', COALESCE(t.description, ''), '|', COALESCE(pt.value, '')), ';') as tags_data"
                ]
            )

        # Add inventory fields if requested
        if include_inventory and store_ids:
            select_fields.extend(
                [
                    "STRING_AGG(DISTINCT CONCAT(inv.store_id, '|', inv.quantity_available, '|', inv.quantity_on_hold, '|', inv.quantity_reserved), ';') as inventory_data"
                ]
            )

        # Add pricing fields if requested
        if include_pricing and customer_tier:
            select_fields.extend(
                [
                    "COALESCE(pricing.final_price, p.base_price) as final_price",
                    "COALESCE(pricing.savings, 0) as savings",
                    "COALESCE(pricing.discount_percentage, 0) as discount_percentage",
                    "pricing.price_list_names",
                ]
            )

        # Build FROM clause with optimal JOINs
        joins = ["FROM products p"]

        if include_categories:
            joins.append("LEFT JOIN product_categories pc ON p.id = pc.product_id")
            joins.append("LEFT JOIN categories c ON pc.category_id = c.id")

        if include_tags:
            joins.append("LEFT JOIN product_tags pt ON p.id = pt.product_id")
            joins.append("LEFT JOIN tags t ON pt.tag_id = t.id")

        if include_inventory and store_ids:
            joins.append(
                f"LEFT JOIN inventory inv ON p.id = inv.product_id AND inv.store_id = ANY(ARRAY{store_ids})"
            )

        if include_pricing and customer_tier:
            # Integrated pricing calculation subquery
            pricing_cte = """
            WITH pricing AS (
                SELECT
                    p.id as product_id,
                    p.base_price,
                    CASE
                        WHEN pll.discount_type = 'percentage' THEN
                            GREATEST(0, p.base_price - (LEAST(p.base_price * (pll.discount_value / 100), COALESCE(pll.max_discount_amount, p.base_price))))
                        WHEN pll.discount_type = 'flat' THEN
                            GREATEST(0, p.base_price - pll.discount_value)
                        WHEN pll.discount_type = 'fixed_price' THEN
                            pll.discount_value
                        ELSE p.base_price
                    END as final_price,
                    CASE
                        WHEN pll.discount_type = 'percentage' THEN
                            LEAST(p.base_price * (pll.discount_value / 100), COALESCE(pll.max_discount_amount, p.base_price))
                        WHEN pll.discount_type = 'flat' THEN
                            pll.discount_value
                        WHEN pll.discount_type = 'fixed_price' THEN
                            GREATEST(0, p.base_price - pll.discount_value)
                        ELSE 0
                    END as savings,
                    CASE
                        WHEN p.base_price > 0 THEN
                            CASE
                                WHEN pll.discount_type = 'percentage' THEN
                                    LEAST(pll.discount_value, (COALESCE(pll.max_discount_amount, p.base_price) / p.base_price) * 100)
                                WHEN pll.discount_type = 'flat' THEN
                                    (pll.discount_value / p.base_price) * 100
                                WHEN pll.discount_type = 'fixed_price' THEN
                                    ((p.base_price - pll.discount_value) / p.base_price) * 100
                                ELSE 0
                            END
                        ELSE 0
                    END as discount_percentage,
                    STRING_AGG(pl.name, ';') as price_list_names,
                    ROW_NUMBER() OVER (PARTITION BY p.id ORDER BY pl.priority DESC, pll.id) as rn
                FROM products p
                LEFT JOIN price_list_lines pll ON (
                    pll.product_id = p.id OR
                    (pll.product_id IS NULL AND pll.category_id IN (SELECT category_id FROM product_categories WHERE product_id = p.id)) OR
                    (pll.product_id IS NULL AND pll.category_id IS NULL)
                )
                LEFT JOIN price_lists pl ON pll.price_list_id = pl.id
                LEFT JOIN tier_price_lists tpl ON pl.id = tpl.price_list_id
                WHERE pl.is_active = true
                  AND tpl.tier_id = :customer_tier
                  AND (pl.valid_from IS NULL OR pl.valid_from <= NOW())
                  AND (pl.valid_until IS NULL OR pl.valid_until >= NOW())
                  AND pll.is_active = true
                  AND pll.min_quantity <= 1
                  AND p.id = ANY(:product_ids)
                GROUP BY p.id, p.base_price, pll.discount_type, pll.discount_value, pll.max_discount_amount, pl.priority, pll.id
            )
            """
            joins.insert(0, pricing_cte)
            joins.append(
                "LEFT JOIN pricing ON p.id = pricing.product_id AND pricing.rn = 1"
            )

        # Build WHERE conditions
        params: Dict[str, Any] = {"product_ids": product_ids}
        if customer_tier:
            params["customer_tier"] = customer_tier

        where_clause = "WHERE p.id = ANY(:product_ids)"

        sql_query = f"""
        {joins[0] if "WITH" in joins[0] else ""}
        SELECT {", ".join(select_fields)}
        {" ".join(joins[1:] if "WITH" in joins[0] else joins)}
        {where_clause}
        GROUP BY p.id, p.ref, p.name, p.description, p.brand, p.base_price,
                 p.unit_measure, p.image_urls, p.ecommerce_category_id,
                 p.ecommerce_subcategory_id, p.alternative_product_ids, p.created_at, p.updated_at
                 {", pricing.final_price, pricing.savings, pricing.discount_percentage, pricing.price_list_names" if include_pricing and customer_tier else ""}
        """

        return sql_query, params
