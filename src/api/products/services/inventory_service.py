from typing import Dict, List, Optional

from sqlalchemy import text

from src.api.products.models import EnhancedProductSchema, InventoryInfoSchema
from src.config.constants import NEXT_DAY_DELIVERY_ONLY_TAG_ID
from src.database.connection import AsyncSessionLocal
from src.shared.error_handler import ErrorHandler


class ProductInventoryService:
    """Product inventory service with aggregated availability logic"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)

    async def add_inventory_to_products_bulk(
        self,
        products: List[EnhancedProductSchema],
        store_ids: Optional[List[int]],
        is_nearby_store: bool = True,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> List[EnhancedProductSchema]:
        """Add aggregated inventory to multiple products"""
        if not products:
            return products

        product_ids = [p.id for p in products if p.id is not None]
        if not product_ids:
            return products

        # Get products with next-day delivery tag
        next_day_only_products = await self._get_products_with_next_day_tag(product_ids)

        # Get inventory data with safety stock
        inventory_dict = await self._get_bulk_inventory_with_safety_stock(
            product_ids, store_ids
        )

        # Apply aggregated inventory to each product
        for product in products:
            if product.id is None:
                continue

            has_next_day_tag = product.id in next_day_only_products
            inventory_data = inventory_dict.get(product.id, [])

            product.inventory = self._calculate_aggregated_inventory(
                inventory_data=inventory_data,
                is_nearby_store=is_nearby_store,
                has_next_day_tag=has_next_day_tag,
                has_location=latitude is not None and longitude is not None,
            )

        return products

    async def get_aggregated_inventory_for_product(
        self,
        product_id: int,
        store_ids: Optional[List[int]],
        is_nearby_store: bool = True,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> InventoryInfoSchema:
        """Get aggregated inventory for a single product"""

        # Check if product has next-day delivery tag
        next_day_only_products = await self._get_products_with_next_day_tag(
            [product_id]
        )
        has_next_day_tag = product_id in next_day_only_products

        # Get inventory data
        inventory_dict = await self._get_bulk_inventory_with_safety_stock(
            [product_id], store_ids
        )
        inventory_data = inventory_dict.get(product_id, [])

        return self._calculate_aggregated_inventory(
            inventory_data=inventory_data,
            is_nearby_store=is_nearby_store,
            has_next_day_tag=has_next_day_tag,
            has_location=latitude is not None and longitude is not None,
        )

    def _calculate_aggregated_inventory(
        self,
        inventory_data: List[Dict],
        is_nearby_store: bool,
        has_next_day_tag: bool,
        has_location: bool,
    ) -> InventoryInfoSchema:
        """
        Calculate aggregated inventory based on the comprehensive logic:

        1. If product has NEXT_DAY_DELIVERY_ONLY_TAG and no location provided
           → can_order=False, reason="requires location"

        2. If product has NEXT_DAY_DELIVERY_ONLY_TAG and no nearby stores
           → can_order=False, reason="no nearby stores"

        3. If product has NEXT_DAY_DELIVERY_ONLY_TAG and nearby stores exist
           → Check inventory from nearby stores only

        4. If product doesn't have tag and has nearby stores with stock
           → Use nearby stores

        5. If product doesn't have tag and no nearby stock
           → Fall back to default stores (if is_nearby_store=False)
        """

        # Case 1: Next-day delivery product without location
        if has_next_day_tag and not has_location:
            if inventory_data:
                # Calculate max available across all stores
                max_available = 0
                for inv in inventory_data:
                    usable_qty = max(0, inv["quantity_available"] - inv["safety_stock"])
                    if usable_qty > max_available:
                        max_available = usable_qty
                
                return InventoryInfoSchema(
                    can_order=False,  # Cannot order without location
                    max_available=max_available,  # But show actual available quantity
                    in_stock=max_available > 0,
                    ondemand_delivery_available=False,
                    reason_unavailable="Product requires location for on-demand delivery",
                )
            else:
                return InventoryInfoSchema(
                    can_order=False,
                    max_available=0,
                    in_stock=False,
                    ondemand_delivery_available=False,
                    reason_unavailable="Product requires location for on-demand delivery",
                )

        # Case 2: Next-day delivery product with no nearby stores
        # Still calculate actual inventory for display, but indicate it can't be ordered
        if has_next_day_tag and not is_nearby_store:
            if inventory_data:
                # Calculate max available across all stores
                max_available = 0
                for inv in inventory_data:
                    usable_qty = max(0, inv["quantity_available"] - inv["safety_stock"])
                    if usable_qty > max_available:
                        max_available = usable_qty
                
                return InventoryInfoSchema(
                    can_order=False,  # Cannot order due to location constraint
                    max_available=max_available,  # But show actual available quantity
                    in_stock=max_available > 0,
                    ondemand_delivery_available=False,
                    reason_unavailable="Product only available with on-demand delivery. No nearby stores found.",
                )
            else:
                return InventoryInfoSchema(
                    can_order=False,
                    max_available=0,
                    in_stock=False,
                    ondemand_delivery_available=False,
                    reason_unavailable="Product only available with on-demand delivery. No nearby stores found.",
                )

        # Calculate usable quantities (quantity_available - safety_stock)
        if not inventory_data:
            # No inventory data available
            if has_next_day_tag:
                reason = "Out of stock at nearby stores"
            else:
                reason = "Out of stock" if not is_nearby_store else "Out of stock at nearby stores"

            return InventoryInfoSchema(
                can_order=False,
                max_available=0,
                in_stock=False,
                ondemand_delivery_available=False,
                reason_unavailable=reason,
            )

        # Calculate max available across all stores
        max_available = 0
        for inv in inventory_data:
            usable_qty = max(0, inv["quantity_available"] - inv["safety_stock"])
            if usable_qty > max_available:
                max_available = usable_qty

        # Determine if product can be ordered
        can_order = max_available > 0
        in_stock = max_available > 0

        # Determine delivery availability
        ondemand_delivery_available = is_nearby_store and in_stock

        # Set reason if unavailable
        reason_unavailable = None
        if not can_order:
            if has_next_day_tag:
                reason_unavailable = "Out of stock at nearby stores"
            else:
                reason_unavailable = "Out of stock"

        return InventoryInfoSchema(
            can_order=can_order,
            max_available=max_available,
            in_stock=in_stock,
            ondemand_delivery_available=ondemand_delivery_available,
            reason_unavailable=reason_unavailable,
        )

    async def _get_bulk_inventory_with_safety_stock(
        self, product_ids: List[int], store_ids: Optional[List[int]]
    ) -> Dict[int, List[Dict]]:
        """Get inventory with safety stock for multiple products"""
        if not product_ids:
            return {}

        if not store_ids:
            # No stores specified, return empty
            return {}

        async with AsyncSessionLocal() as session:
            query = """
            SELECT
                product_id,
                store_id,
                quantity_available,
                quantity_on_hold,
                quantity_reserved,
                COALESCE(safety_stock, 0) as safety_stock,
                updated_at
            FROM inventory
            WHERE product_id = ANY(:product_ids)
              AND store_id = ANY(:store_ids)
            ORDER BY product_id, store_id
            """

            result = await session.execute(
                text(query), {"product_ids": product_ids, "store_ids": store_ids}
            )

            # Group by product_id
            inventory_dict = {}
            for row in result.fetchall():
                if row.product_id not in inventory_dict:
                    inventory_dict[row.product_id] = []

                inventory_dict[row.product_id].append(
                    {
                        "store_id": row.store_id,
                        "quantity_available": row.quantity_available,
                        "quantity_on_hold": row.quantity_on_hold,
                        "quantity_reserved": row.quantity_reserved,
                        "safety_stock": row.safety_stock,
                        "updated_at": row.updated_at,
                    }
                )

            return inventory_dict

    async def _get_products_with_next_day_tag(self, product_ids: List[int]) -> set:
        """Get products that have the NEXT_DAY_DELIVERY_ONLY_TAG_ID"""
        if not product_ids:
            return set()

        async with AsyncSessionLocal() as session:
            query = """
            SELECT DISTINCT product_id
            FROM product_tags
            WHERE product_id = ANY(:product_ids)
              AND tag_id = :tag_id
            """

            result = await session.execute(
                text(query),
                {
                    "product_ids": product_ids,
                    "tag_id": NEXT_DAY_DELIVERY_ONLY_TAG_ID,
                },
            )

            return {row.product_id for row in result.fetchall()}
