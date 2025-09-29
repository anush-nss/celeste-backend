from typing import Optional, List, Dict, Any, Sequence, Union
from sqlalchemy import text
from src.database.connection import AsyncSessionLocal
from src.api.products.models import (
    ProductQuerySchema,
    EnhancedProductSchema,
    PaginatedProductsResponse,
)
from src.api.tags.service import TagService
from src.shared.error_handler import ErrorHandler
from src.shared.cache_service import cache_service
import asyncio
import json


class ProductQueryService:
    """Product query service with advanced SQL optimization and caching"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.tag_service = TagService(entity_type="product")
        self.cache = cache_service

    async def get_products_with_criteria(
        self,
        query_params: ProductQuerySchema,
        customer_tier: Optional[int] = None,
        store_ids: Optional[List[int]] = None,
    ) -> PaginatedProductsResponse:
        """Execute comprehensive product query with integrated pricing and inventory data"""

        # Generate cache key
        cache_key = self._generate_cache_key(query_params, customer_tier, store_ids)

        # Try cache first
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            return PaginatedProductsResponse.model_validate(cached_result)

        async with AsyncSessionLocal() as session:
            # Build comprehensive SQL query with joins
            sql_query, params = self._build_comprehensive_sql(query_params, customer_tier, store_ids)

            # Execute single query
            result = await session.execute(text(sql_query), params)
            rows = result.fetchall()

            # Process results efficiently
            products, pagination = await self._process_results_fast(rows, query_params)

            response = PaginatedProductsResponse(
                products=products,
                pagination=pagination
            )

            # Cache result for 5 minutes
            await self.cache.set(cache_key, response.model_dump(mode="json"), ttl=300)

            return response

    def _build_comprehensive_sql(
        self,
        query_params: ProductQuerySchema,
        customer_tier: Optional[int] = None,
        store_ids: Optional[List[int]] = None
    ) -> tuple[str, Dict[str, Any]]:
        """Build comprehensive SQL query with integrated joins and filtering"""

        # Base SELECT with all needed fields
        select_fields = [
            "p.id", "p.ref", "p.name", "p.description", "p.brand",
            "p.base_price", "p.unit_measure", "p.image_urls",
            "p.ecommerce_category_id", "p.ecommerce_subcategory_id",
            "p.created_at", "p.updated_at"
        ]

        # Add category fields if requested
        if query_params.include_categories:
            select_fields.extend([
                "STRING_AGG(DISTINCT CONCAT(c.id, '|', c.name, '|', COALESCE(c.description, ''), '|', COALESCE(c.sort_order::text, ''), '|', COALESCE(c.image_url, ''), '|', COALESCE(c.parent_category_id::text, '')), ';') as categories_data"
            ])

        # Add tag fields if requested
        if query_params.include_tags:
            select_fields.extend([
                "STRING_AGG(DISTINCT CONCAT(t.id, '|', t.tag_type, '|', t.name, '|', t.slug, '|', COALESCE(t.description, ''), '|', COALESCE(pt.value, '')), ';') as tags_data"
            ])

        # Add inventory fields if requested
        if query_params.include_inventory and store_ids:
            select_fields.extend([
                "STRING_AGG(DISTINCT CONCAT(inv.store_id, '|', inv.quantity_available, '|', inv.quantity_on_hold, '|', inv.quantity_reserved), ';') as inventory_data"
            ])

        # Add pricing fields if requested
        if query_params.include_pricing and customer_tier:
            select_fields.extend([
                "COALESCE(pricing.final_price, p.base_price) as final_price",
                "COALESCE(pricing.savings, 0) as savings",
                "COALESCE(pricing.discount_percentage, 0) as discount_percentage",
                "pricing.price_list_names"
            ])

        # Build FROM clause with optimal JOINs
        joins = ["FROM products p"]

        if query_params.include_categories:
            joins.append("LEFT JOIN product_categories pc ON p.id = pc.product_id")
            joins.append("LEFT JOIN categories c ON pc.category_id = c.id")

        if query_params.include_tags:
            joins.append("LEFT JOIN product_tags pt ON p.id = pt.product_id")
            joins.append("LEFT JOIN tags t ON pt.tag_id = t.id")

        if query_params.include_inventory and store_ids:
            joins.append(f"LEFT JOIN inventory inv ON p.id = inv.product_id AND inv.store_id = ANY(ARRAY{store_ids})")

        if query_params.include_pricing and customer_tier:
            # Integrated pricing calculation subquery
            pricing_cte = f"""
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
            joins.append("LEFT JOIN pricing ON p.id = pricing.product_id AND pricing.rn = 1")

        # Build WHERE conditions
        where_conditions = []
        params: Dict[str, Any] = {"customer_tier": customer_tier} if customer_tier else {}

        if query_params.category_ids:
            where_conditions.append("p.id IN (SELECT product_id FROM product_categories WHERE category_id = ANY(:category_ids))")
            params["category_ids"] = list(query_params.category_ids)

        if query_params.tags:
            tag_filter_result = self.tag_service.parse_tag_filters(query_params.tags)
            if tag_filter_result['conditions']:
                tag_conditions = " OR ".join([
                    f"(t.tag_type = :{param} AND t.name = :{param}_name)"
                    for param in tag_filter_result['params'].keys()
                    if not param.endswith('_name')
                ])
                if tag_conditions:
                    where_conditions.append(f"p.id IN (SELECT DISTINCT pt.product_id FROM product_tags pt JOIN tags t ON pt.tag_id = t.id WHERE {tag_conditions})")
                    params.update(tag_filter_result['params'])

        if query_params.min_price is not None:
            where_conditions.append("p.base_price >= :min_price")
            params["min_price"] = int(query_params.min_price)

        if query_params.max_price is not None:
            where_conditions.append("p.base_price <= :max_price")
            params["max_price"] = int(query_params.max_price)

        if query_params.cursor is not None:
            where_conditions.append("p.id > :cursor")
            params["cursor"] = query_params.cursor

        if query_params.only_discounted and query_params.include_pricing:
            where_conditions.append("pricing.savings > 0")

        # Build complete query
        where_clause = f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""

        limit = query_params.limit if query_params.limit is not None else 20
        params["limit"] = limit + 1  # +1 to check if more exist

        # Add discount percentage calculation
        if query_params.include_pricing and customer_tier:
            select_fields.append("CASE WHEN p.base_price > 0 THEN (pricing.savings / p.base_price) * 100 ELSE 0 END as discount_percentage")

        sql_query = f"""
        {joins[0] if 'WITH' in joins[0] else ''}
        SELECT {', '.join(select_fields)}
        {' '.join(joins[1:] if 'WITH' in joins[0] else joins)}
        {where_clause}
        GROUP BY p.id, p.ref, p.name, p.description, p.brand, p.base_price,
                 p.unit_measure, p.image_urls, p.ecommerce_category_id,
                 p.ecommerce_subcategory_id, p.created_at, p.updated_at
                 {', pricing.final_price, pricing.savings, pricing.price_list_names' if query_params.include_pricing and customer_tier else ''}
        ORDER BY p.id
        LIMIT :limit
        """

        return sql_query, params

    async def _process_results_fast(
        self,
        rows: Sequence[Any],
        query_params: ProductQuerySchema
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
            batch = actual_rows[i:i + batch_size]
            task = self._process_row_batch(batch, query_params)
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
        query_params: ProductQuerySchema
    ) -> List[EnhancedProductSchema]:
        """Process a batch of rows efficiently"""
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
                "created_at": row.created_at,
                "updated_at": row.updated_at,
                "categories": [],
                "product_tags": [],
                "pricing": None,
                "inventory": None
            }

            # Parse categories efficiently
            if query_params.include_categories and hasattr(row, 'categories_data') and row.categories_data:
                categories = []
                for cat_data in row.categories_data.split(';'):
                    if cat_data:
                        parts = cat_data.split('|')
                        if len(parts) >= 6:
                            categories.append({
                                "id": int(parts[0]),
                                "name": parts[1],
                                "description": parts[2] or None,
                                "sort_order": int(parts[3]) if parts[3] else None,
                                "image_url": parts[4] or None,
                                "parent_category_id": int(parts[5]) if parts[5] else None
                            })
                product_data["categories"] = categories

            # Parse tags efficiently
            if query_params.include_tags and hasattr(row, 'tags_data') and row.tags_data:
                tags = []
                for tag_data in row.tags_data.split(';'):
                    if tag_data:
                        parts = tag_data.split('|')
                        if len(parts) >= 6:
                            tags.append({
                                "id": int(parts[0]),
                                "tag_type": parts[1],
                                "name": parts[2],
                                "slug": parts[3],
                                "description": parts[4] or None,
                                "value": parts[5] or None
                            })
                product_data["product_tags"] = tags

            # Parse inventory efficiently
            if query_params.include_inventory and hasattr(row, 'inventory_data') and row.inventory_data:
                inventory = []
                for inv_data in row.inventory_data.split(';'):
                    if inv_data:
                        parts = inv_data.split('|')
                        if len(parts) >= 4:
                            inventory.append({
                                "store_id": int(parts[0]),
                                "in_stock": int(parts[1]) > 0,
                                "quantity_available": int(parts[1]),
                                "quantity_on_hold": int(parts[2]),
                                "quantity_reserved": int(parts[3])
                            })
                product_data["inventory"] = inventory

            # Parse pricing efficiently
            if query_params.include_pricing and hasattr(row, 'final_price'):
                product_data["pricing"] = {
                    "base_price": float(row.base_price),
                    "final_price": float(row.final_price) if row.final_price else float(row.base_price),
                    "discount_applied": float(row.savings) if hasattr(row, 'savings') and row.savings else 0.0,
                    "discount_percentage": float(row.discount_percentage) if hasattr(row, 'discount_percentage') and row.discount_percentage else 0.0,
                    "applied_price_lists": row.price_list_names.split(';') if hasattr(row, 'price_list_names') and row.price_list_names else []
                }

            products.append(EnhancedProductSchema(**product_data))

        return products

    def _generate_cache_key(
        self,
        query_params: ProductQuerySchema,
        customer_tier: Optional[int],
        store_ids: Optional[List[int]]
    ) -> str:
        """Generate cache key for query parameters"""
        key_parts = [
            f"products_v2",
            f"limit_{query_params.limit or 20}",
            f"cursor_{query_params.cursor or 0}",
            f"pricing_{query_params.include_pricing}",
            f"categories_{query_params.include_categories}",
            f"tags_{query_params.include_tags}",
            f"inventory_{query_params.include_inventory}",
            f"tier_{customer_tier or 0}",
            f"stores_{','.join(map(str, store_ids or []))}",
            f"cat_ids_{','.join(map(str, query_params.category_ids or []))}",
            f"tags_{','.join(query_params.tags or [])}",
            f"min_price_{query_params.min_price or 0}",
            f"max_price_{query_params.max_price or 0}",
            f"discounted_{query_params.only_discounted}",
        ]
        return ":".join(key_parts)