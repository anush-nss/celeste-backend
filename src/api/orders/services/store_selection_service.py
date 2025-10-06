"""
Store selection service with automatic selection and splitting logic
"""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, text
from sqlalchemy.future import select

from src.config.constants import DEFAULT_SEARCH_RADIUS_KM
from src.database.models.address import Address
from src.database.models.inventory import Inventory
from src.database.models.store import Store
from src.shared.error_handler import ErrorHandler
from src.shared.exceptions import ValidationException


class StoreSelectionService:
    """Automatic store selection with nearest-first and splitting logic"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)

    async def select_stores_for_delivery(
        self, address_id: int, cart_items: List[Dict[str, Any]], session
    ) -> Dict[str, Any]:
        """Select optimal stores for delivery with splitting if needed"""

        selection_result = {
            "primary_store": None,
            "store_assignments": {},
            "requires_splitting": False,
            "unavailable_items": [],
            "delivery_distance": 0.0,
        }

        try:
            # Get address coordinates
            address_coords = await self._get_address_coordinates(address_id, session)
            if not address_coords:
                raise ValidationException(f"Address with ID {address_id} not found")

            # Get all active stores with distances
            nearby_stores = await self._get_stores_by_distance(address_coords, session)

            if not nearby_stores:
                raise ValidationException("No active stores found for delivery")

            # Try to fulfill from nearest store first
            nearest_store = nearby_stores[0]
            availability = await self._check_store_availability(
                nearest_store["store_id"], cart_items, session
            )

            if availability["all_available"]:
                # All items available at nearest store
                selection_result.update(
                    {
                        "primary_store": nearest_store,
                        "store_assignments": {nearest_store["store_id"]: cart_items},
                        "requires_splitting": False,
                        "delivery_distance": nearest_store["distance_km"],
                    }
                )
            else:
                # Need to split across multiple stores
                split_result = await self._split_items_across_stores(
                    cart_items, nearby_stores, session
                )
                selection_result.update(
                    {
                        "primary_store": nearest_store,
                        "store_assignments": split_result["assignments"],
                        "requires_splitting": True,
                        "unavailable_items": split_result["unavailable_items"],
                        "delivery_distance": nearest_store["distance_km"],
                    }
                )

        except Exception as e:
            self._error_handler.logger.error(f"Store selection failed: {str(e)}")
            raise ValidationException(f"Store selection failed: {str(e)}")

        return selection_result

    async def validate_pickup_store(
        self, store_id: int, cart_items: List[Dict[str, Any]], session
    ) -> Dict[str, Any]:
        """Validate pickup store selection (no splitting for pickup)"""

        pickup_result = {
            "store_valid": False,
            "store_info": None,
            "all_items_available": False,
            "unavailable_items": [],
            "estimated_pickup_time": "30 minutes",
        }

        try:
            # Validate store exists and is active
            store_query = select(Store).where(
                and_(Store.id == store_id, Store.is_active)
            )
            result = await session.execute(store_query)
            store = result.scalar_one_or_none()

            if not store:
                raise ValidationException(
                    f"Store with ID {store_id} not found or inactive"
                )

            pickup_result["store_valid"] = True
            pickup_result["store_info"] = {
                "store_id": store.id,
                "name": store.name,
                "address": store.address,
            }

            # Check availability for all items (no splitting for pickup)
            availability = await self._check_store_availability(
                store_id, cart_items, session
            )
            pickup_result.update(
                {
                    "all_items_available": availability["all_available"],
                    "unavailable_items": availability["unavailable_items"],
                }
            )

        except Exception as e:
            self._error_handler.logger.error(
                f"Pickup store validation failed: {str(e)}"
            )
            raise ValidationException(f"Pickup store validation failed: {str(e)}")

        return pickup_result

    async def _get_address_coordinates(
        self, address_id: int, session
    ) -> Optional[Tuple[float, float]]:
        """Get address coordinates from database"""

        address_query = select(Address).where(Address.id == address_id)
        result = await session.execute(address_query)
        address: Optional[Address] = result.scalar_one_or_none()

        if address:
            return (float(address.latitude), float(address.longitude))

        return None

    async def _get_stores_by_distance(
        self, address_coords: Tuple[float, float], session
    ) -> List[Dict[str, Any]]:
        """Get active stores ordered by distance from address (within delivery radius)"""

        lat, lon = address_coords

        # Use spatial query to get nearest stores within radius
        query = text("""
            SELECT
                id,
                name,
                address,
                latitude,
                longitude,
                ST_Distance(
                    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                ) / 1000 as distance_km
            FROM stores
            WHERE is_active = true
              AND ST_DWithin(
                  ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography,
                  ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                  :radius_meters
              )
            ORDER BY distance_km
            LIMIT 10
        """)

        result = await session.execute(
            query,
            {
                "lat": lat,
                "lon": lon,
                "radius_meters": DEFAULT_SEARCH_RADIUS_KM * 1000,  # Convert km to meters
            },
        )
        stores = []

        for row in result.fetchall():
            stores.append(
                {
                    "store_id": row.id,
                    "name": row.name,
                    "address": row.address,
                    "latitude": row.latitude,
                    "longitude": row.longitude,
                    "distance_km": float(row.distance_km),
                }
            )

        return stores

    async def _check_store_availability(
        self, store_id: int, cart_items: List[Dict[str, Any]], session
    ) -> Dict[str, Any]:
        """Check if all items are available at specific store"""

        availability_result = {
            "all_available": True,
            "available_items": [],
            "unavailable_items": [],
        }

        for item in cart_items:
            # Check inventory for each product
            inventory_query = select(Inventory).where(
                and_(
                    Inventory.product_id == item["product_id"],
                    Inventory.store_id == store_id,
                    Inventory.quantity_available >= item["quantity"],
                )
            )

            result = await session.execute(inventory_query)
            inventory = result.scalar_one_or_none()

            if inventory:
                availability_result["available_items"].append(item)
            else:
                availability_result["unavailable_items"].append(item)
                availability_result["all_available"] = False

        return availability_result

    async def _split_items_across_stores(
        self,
        cart_items: List[Dict[str, Any]],
        nearby_stores: List[Dict[str, Any]],
        session,
    ) -> Dict[str, Any]:
        """Split items across multiple stores based on availability"""

        split_result = {"assignments": {}, "unavailable_items": []}

        remaining_items = cart_items.copy()

        # Try each store in order of proximity
        for store in nearby_stores:
            if not remaining_items:
                break

            store_id = store["store_id"]
            availability = await self._check_store_availability(
                store_id, remaining_items, session
            )

            if availability["available_items"]:
                split_result["assignments"][store_id] = availability["available_items"]
                # Remove assigned items from remaining
                remaining_items = [
                    item
                    for item in remaining_items
                    if item not in availability["available_items"]
                ]

        # Any items that couldn't be assigned to any store
        split_result["unavailable_items"] = remaining_items

        return split_result

    async def check_inventory_at_nearby_stores(
        self,
        latitude: float,
        longitude: float,
        cart_items: List[Dict[str, Any]],
        session,
        radius_km: float = DEFAULT_SEARCH_RADIUS_KM,
    ) -> Dict[str, Any]:
        """
        Simple inventory check: find nearby stores and check if items can be fulfilled.
        Prioritizes closest store with availability.

        Returns dict with per-product fulfillment info.
        """
        # Reuse StoreService to get nearby stores
        from src.api.stores.models import StoreQuerySchema
        from src.api.stores.service import StoreService

        store_service = StoreService()
        query_params = StoreQuerySchema(
            latitude=latitude,
            longitude=longitude,
            radius=radius_km,
            is_active=True,
            include_distance=True,
            limit=10,
            tags=None,
            include_tags=False,
        )

        # Get stores sorted by distance (closest first)
        stores_data = await store_service.get_stores_by_location(query_params)

        if not stores_data:
            return {
                "can_fulfill": False,
                "items": [],
                "error": "No stores found in delivery range",
            }

        # Build list of store IDs sorted by distance
        store_ids = [s["id"] for s in stores_data]
        stores_by_id = {s["id"]: s for s in stores_data}

        # Query inventory for all products at all nearby stores in one query
        product_ids = [item["product_id"] for item in cart_items]

        inventory_query = select(Inventory).where(
            and_(
                Inventory.product_id.in_(product_ids), Inventory.store_id.in_(store_ids)
            )
        )
        result = await session.execute(inventory_query)
        inventories = result.scalars().all()

        # Build inventory lookup: (product_id, store_id) -> inventory
        inventory_map = {}
        for inv in inventories:
            key = (inv.product_id, inv.store_id)
            inventory_map[key] = inv

        # Check each cart item
        fulfillment_info = []
        can_fulfill_all = True

        for item in cart_items:
            product_id = item["product_id"]
            quantity_needed = item["quantity"]

            # Find closest store with sufficient stock
            fulfilled_store = None
            quantity_available = 0

            for store_id in store_ids:
                inv_key = (product_id, store_id)
                inv = inventory_map.get(inv_key)

                if inv and inv.quantity_available >= quantity_needed:
                    # Found store with enough stock
                    fulfilled_store = stores_by_id[store_id]
                    quantity_available = inv.quantity_available
                    break

            # If not fully available, find store with maximum available quantity
            if not fulfilled_store:
                max_available = 0
                best_store = None

                for store_id in store_ids:
                    inv_key = (product_id, store_id)
                    inv = inventory_map.get(inv_key)

                    if inv and inv.quantity_available > max_available:
                        max_available = inv.quantity_available
                        best_store = stores_by_id[store_id]

                quantity_available = max_available
                fulfilled_store = best_store
                can_fulfill_all = False

            fulfillment_info.append(
                {
                    "product_id": product_id,
                    "quantity_requested": quantity_needed,
                    "quantity_available": quantity_available,
                    "can_fulfill": quantity_available >= quantity_needed,
                    "store_id": fulfilled_store["id"] if fulfilled_store else None,
                    "store_name": fulfilled_store["name"] if fulfilled_store else None,
                    "distance_km": fulfilled_store.get("distance")
                    if fulfilled_store
                    else None,
                }
            )

        return {
            "can_fulfill": can_fulfill_all,
            "items": fulfillment_info,
            "nearby_stores_count": len(stores_data),
        }
