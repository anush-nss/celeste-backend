import asyncio
from typing import Dict, List

from sqlalchemy import text

from src.api.products.models import EnhancedProductSchema, InventoryInfoSchema
from src.database.connection import AsyncSessionLocal
from src.shared.cache_service import cache_service
from src.shared.error_handler import ErrorHandler


class ProductInventoryService:
    """Product inventory service with bulk operations and spatial queries"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.cache = cache_service

    async def add_inventory_to_products_bulk(
        self, products: List[EnhancedProductSchema], store_ids: List[int]
    ) -> List[EnhancedProductSchema]:
        """Add inventory to multiple products using single comprehensive query"""
        if not store_ids or not products:
            return products

        # Generate cache key for inventory data
        product_ids = [p.id for p in products]
        filtered_product_ids = [pid for pid in product_ids if pid is not None]
        filtered_store_ids = [sid for sid in store_ids if sid is not None]
        cache_key = f"inventory:bulk:{','.join(map(str, sorted(filtered_product_ids)))}:{','.join(map(str, sorted(filtered_store_ids)))}"

        # Try cache first
        cached_inventory = await self.cache.get(cache_key)
        if cached_inventory:
            return self._apply_cached_inventory(products, cached_inventory)

        # Single comprehensive query for all inventory data
        inventory_dict = await self._get_bulk_inventory(
            filtered_product_ids, filtered_store_ids
        )

        # Cache inventory data for 2 minutes
        await self.cache.set(cache_key, inventory_dict, ttl=120)

        # Apply inventory to products
        return self._apply_inventory_to_products(products, inventory_dict)

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

    def _apply_inventory_to_products(
        self,
        products: List[EnhancedProductSchema],
        inventory_dict: Dict[int, List[Dict]],
    ) -> List[EnhancedProductSchema]:
        """Apply inventory data to products efficiently"""
        for product in products:
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
                        )
                    )
                product.inventory = inventory_list

        return products

    def _apply_cached_inventory(
        self,
        products: List[EnhancedProductSchema],
        cached_inventory: Dict[int, List[Dict]],
    ) -> List[EnhancedProductSchema]:
        """Apply cached inventory data to products"""
        return self._apply_inventory_to_products(products, cached_inventory)

    async def get_stores_by_location(
        self, latitude: float, longitude: float, radius_km: float = 10.0
    ) -> List[int]:
        """Get stores near location using spatial query with caching"""
        cache_key = f"stores:location:{latitude:.6f}:{longitude:.6f}:{radius_km}"

        # Try cache first (cache for 10 minutes)
        cached_stores = await self.cache.get(cache_key)
        if cached_stores:
            return cached_stores

        async with AsyncSessionLocal() as session:
            # Advanced spatial query using PostGIS functions
            query = """
            SELECT id
            FROM stores
            WHERE is_active = true
              AND ST_DWithin(
                  ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                  ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
                  :radius_meters
              )
            ORDER BY ST_Distance(
                ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
            )
            LIMIT 20
            """

            result = await session.execute(
                text(query),
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius_meters": radius_km * 1000,  # Convert km to meters
                },
            )

            store_ids = [row.id for row in result.fetchall()]

            # Cache result for 10 minutes
            await self.cache.set(cache_key, store_ids, ttl=600)

            return store_ids

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
