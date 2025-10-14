import asyncio
from typing import Dict, List

from sqlalchemy import text

from src.api.products.models import EnhancedProductSchema, InventoryInfoSchema
from src.config.constants import NEXT_DAY_DELIVERY_ONLY_TAG_ID
from src.database.connection import AsyncSessionLocal
from src.shared.cache_service import cache_service
from src.shared.error_handler import ErrorHandler


class ProductInventoryService:
    """Product inventory service with bulk operations and spatial queries"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.cache = cache_service

    async def add_inventory_to_products_bulk(
        self,
        products: List[EnhancedProductSchema],
        store_ids: List[int],
        is_nearby_store: bool = True,
    ) -> List[EnhancedProductSchema]:
        """Add inventory to multiple products using single comprehensive query"""
        if not store_ids or not products:
            return products

        # Generate cache key for inventory data
        product_ids = [p.id for p in products]
        filtered_product_ids = [pid for pid in product_ids if pid is not None]
        filtered_store_ids = [sid for sid in store_ids if sid is not None]
        cache_key = f"inventory:bulk:{','.join(map(str, sorted(filtered_product_ids)))}:{','.join(map(str, sorted(filtered_store_ids)))}:{is_nearby_store}"

        # Try cache first
        cached_inventory = await self.cache.get(cache_key)
        if cached_inventory:
            return self._apply_cached_inventory(
                products, cached_inventory, is_nearby_store
            )

        # If using default stores (not nearby), check for excluded products
        excluded_product_ids = set()
        if not is_nearby_store:
            excluded_product_ids = await self._get_excluded_products(
                filtered_product_ids
            )

        # Single comprehensive query for all inventory data
        inventory_dict = await self._get_bulk_inventory(
            filtered_product_ids, filtered_store_ids
        )

        # Cache inventory data for 2 minutes
        await self.cache.set(cache_key, inventory_dict, ttl=120)

        # Apply inventory to products
        return self._apply_inventory_to_products(
            products, inventory_dict, is_nearby_store, excluded_product_ids
        )

    async def _get_bulk_inventory(
        self, product_ids: List[int], store_ids: List[int]
    ) -> Dict[int, List[Dict]]:
        """Get inventory for multiple products and stores in single query"""
        async with AsyncSessionLocal() as session:
            # Comprehensive single query with aggregation
            query = """
            SELECT
                product_id,
                store_id,
                quantity_available,
                quantity_on_hold,
                quantity_reserved,
                updated_at
            FROM inventory
            WHERE product_id = ANY(:product_ids)
              AND store_id = ANY(:store_ids)
              AND quantity_available >= 0
            ORDER BY product_id, store_id
            """

            result = await session.execute(
                text(query), {"product_ids": product_ids, "store_ids": store_ids}
            )

            # Group by product_id efficiently
            inventory_dict = {}
            for row in result.fetchall():
                if row.product_id not in inventory_dict:
                    inventory_dict[row.product_id] = []

                inventory_dict[row.product_id].append(
                    {
                        "store_id": row.store_id,
                        "in_stock": row.quantity_available > 0,
                        "quantity_available": row.quantity_available,
                        "quantity_on_hold": row.quantity_on_hold,
                        "quantity_reserved": row.quantity_reserved,
                        "updated_at": row.updated_at,
                    }
                )

            return inventory_dict

    async def _get_excluded_products(self, product_ids: List[int]) -> set:
        """Get products that have the NEXT_DAY_DELIVERY_ONLY_TAG_ID"""
        if not product_ids:
            return set()

        async with AsyncSessionLocal() as session:
            query = """
            SELECT DISTINCT product_id
            FROM product_tags
            WHERE product_id = ANY(:product_ids)
              AND tag_id = :excluded_tag_id
            """

            result = await session.execute(
                text(query),
                {
                    "product_ids": product_ids,
                    "excluded_tag_id": NEXT_DAY_DELIVERY_ONLY_TAG_ID,
                },
            )

            return {row.product_id for row in result.fetchall()}

    def _apply_inventory_to_products(
        self,
        products: List[EnhancedProductSchema],
        inventory_dict: Dict[int, List[Dict]],
        is_nearby_store: bool = True,
        excluded_product_ids: set = set(),
    ) -> List[EnhancedProductSchema]:
        """Apply inventory data to products efficiently"""
        if excluded_product_ids is None:
            excluded_product_ids = set()

        for product in products:
            # If product is excluded and using default stores, set inventory to null
            if not is_nearby_store and product.id in excluded_product_ids:
                product.inventory = None
                continue

            if product.id in inventory_dict:
                inventory_list = []
                for inv_data in inventory_dict[product.id]:
                    inventory_list.append(
                        InventoryInfoSchema(
                            store_id=inv_data["store_id"],
                            in_stock=inv_data["in_stock"],
                            quantity_available=inv_data["quantity_available"],
                            quantity_on_hold=inv_data["quantity_on_hold"],
                            quantity_reserved=inv_data["quantity_reserved"],
                            is_nearby_store=is_nearby_store,
                        )
                    )
                product.inventory = inventory_list

        return products

    def _apply_cached_inventory(
        self,
        products: List[EnhancedProductSchema],
        cached_inventory: Dict[int, List[Dict]],
        is_nearby_store: bool = True,
    ) -> List[EnhancedProductSchema]:
        """Apply cached inventory data to products"""
        # Note: excluded_product_ids are not cached, so we need to recalculate
        excluded_product_ids = set()
        if not is_nearby_store:
            # This will be recalculated, but for cached data we accept this tradeoff
            product_ids = [p.id for p in products if p.id is not None]
            import asyncio

            excluded_product_ids = asyncio.create_task(
                self._get_excluded_products(product_ids)
            )
            try:
                excluded_product_ids = asyncio.get_event_loop().run_until_complete(
                    excluded_product_ids
                )
            except Exception:
                excluded_product_ids = set()

        return self._apply_inventory_to_products(
            products, cached_inventory, is_nearby_store, excluded_product_ids
        )

    async def add_inventory_to_single_product(
        self, product: EnhancedProductSchema, store_id: int
    ) -> EnhancedProductSchema:
        """Add inventory to single product with caching"""
        cache_key = f"inventory:single:{product.id}:{store_id}"

        # Try cache first
        cached_inventory = await self.cache.get(cache_key)
        if cached_inventory:
            if cached_inventory:
                product.inventory = [InventoryInfoSchema(**cached_inventory)]
            return product

        async with AsyncSessionLocal() as session:
            query = """
            SELECT
                store_id,
                quantity_available,
                quantity_on_hold,
                quantity_reserved
            FROM inventory
            WHERE product_id = :product_id
              AND store_id = :store_id
            """

            result = await session.execute(
                text(query), {"product_id": product.id, "store_id": store_id}
            )

            row = result.fetchone()
            if row:
                inventory_data = {
                    "store_id": row.store_id,
                    "in_stock": row.quantity_available > 0,
                    "quantity_available": row.quantity_available,
                    "quantity_on_hold": row.quantity_on_hold,
                    "quantity_reserved": row.quantity_reserved,
                }

                # Cache for 2 minutes
                await self.cache.set(cache_key, inventory_data, ttl=120)

                product.inventory = [InventoryInfoSchema(**inventory_data)]

        return product

    async def preload_inventory_cache(
        self, product_ids: List[int], store_ids: List[int]
    ) -> None:
        """Preload inventory cache for common queries"""
        # Split into batches to avoid large queries
        batch_size = 100
        tasks = []

        for i in range(0, len(product_ids), batch_size):
            batch_product_ids = product_ids[i : i + batch_size]
            task = self._preload_batch(batch_product_ids, store_ids)
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _preload_batch(
        self, product_ids: List[int], store_ids: List[int]
    ) -> None:
        """Preload a batch of inventory data"""
        try:
            cache_key = f"inventory:bulk:{','.join(map(str, sorted(product_ids)))}:{','.join(map(str, sorted(store_ids)))}"

            # Skip if already cached
            if await self.cache.get(cache_key):
                return

            inventory_dict = await self._get_bulk_inventory(product_ids, store_ids)
            await self.cache.set(cache_key, inventory_dict, ttl=120)

        except Exception:
            # Log error but don't fail the request
            pass
