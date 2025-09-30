"""
Store selection service with automatic selection and splitting logic
"""
from typing import List, Dict, Any, Optional, Tuple
from decimal import Decimal
from sqlalchemy.future import select
from sqlalchemy import and_, text
from src.database.connection import AsyncSessionLocal
from src.database.models.store import Store
from src.database.models.inventory import Inventory
from src.database.models.address import Address
from src.api.users.models import AddressSchema
from src.shared.error_handler import ErrorHandler
from src.shared.exceptions import ValidationException


class StoreSelectionService:
    """Automatic store selection with nearest-first and splitting logic"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)

    async def select_stores_for_delivery(
        self,
        address_id: int,
        cart_items: List[Dict[str, Any]],
        session
    ) -> Dict[str, Any]:
        """Select optimal stores for delivery with splitting if needed"""

        selection_result = {
            "primary_store": None,
            "store_assignments": {},
            "requires_splitting": False,
            "unavailable_items": [],
            "delivery_distance": 0.0
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
            availability = await self._check_store_availability(nearest_store["store_id"], cart_items, session)

            if availability["all_available"]:
                # All items available at nearest store
                selection_result.update({
                    "primary_store": nearest_store,
                    "store_assignments": {nearest_store["store_id"]: cart_items},
                    "requires_splitting": False,
                    "delivery_distance": nearest_store["distance_km"]
                })
            else:
                # Need to split across multiple stores
                split_result = await self._split_items_across_stores(cart_items, nearby_stores, session)
                selection_result.update({
                    "primary_store": nearest_store,
                    "store_assignments": split_result["assignments"],
                    "requires_splitting": True,
                    "unavailable_items": split_result["unavailable_items"],
                    "delivery_distance": nearest_store["distance_km"]
                })

        except Exception as e:
            self._error_handler.logger.error(f"Store selection failed: {str(e)}")
            raise ValidationException(f"Store selection failed: {str(e)}")

        return selection_result

    async def validate_pickup_store(
        self,
        store_id: int,
        cart_items: List[Dict[str, Any]],
        session
    ) -> Dict[str, Any]:
        """Validate pickup store selection (no splitting for pickup)"""

        pickup_result = {
            "store_valid": False,
            "store_info": None,
            "all_items_available": False,
            "unavailable_items": [],
            "estimated_pickup_time": "30 minutes"
        }

        try:
            # Validate store exists and is active
            store_query = select(Store).where(
                and_(Store.id == store_id, Store.is_active == True)
            )
            result = await session.execute(store_query)
            store = result.scalar_one_or_none()

            if not store:
                raise ValidationException(f"Store with ID {store_id} not found or inactive")

            pickup_result["store_valid"] = True
            pickup_result["store_info"] = {
                "store_id": store.id,
                "name": store.name,
                "address": store.address
            }

            # Check availability for all items (no splitting for pickup)
            availability = await self._check_store_availability(store_id, cart_items, session)
            pickup_result.update({
                "all_items_available": availability["all_available"],
                "unavailable_items": availability["unavailable_items"]
            })

        except Exception as e:
            self._error_handler.logger.error(f"Pickup store validation failed: {str(e)}")
            raise ValidationException(f"Pickup store validation failed: {str(e)}")

        return pickup_result

    async def _get_address_coordinates(self, address_id: int, session) -> Optional[Tuple[float, float]]:
        """Get address coordinates from database"""

        address_query = select(Address).where(Address.id == address_id)
        result = await session.execute(address_query)
        address: Optional[Address] = result.scalar_one_or_none()

        if address:
            return (float(address.latitude), float(address.longitude))

        return None

    async def _get_stores_by_distance(
        self,
        address_coords: Tuple[float, float],
        session
    ) -> List[Dict[str, Any]]:
        """Get active stores ordered by distance from address"""

        lat, lon = address_coords

        # Use spatial query to get nearest stores
        # This is a placeholder - real implementation would use PostGIS functions
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
            ORDER BY distance_km
            LIMIT 10
        """)

        result = await session.execute(query, {"lat": lat, "lon": lon})
        stores = []

        for row in result.fetchall():
            stores.append({
                "store_id": row.id,
                "name": row.name,
                "address": row.address,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "distance_km": float(row.distance_km)
            })

        return stores

    async def _check_store_availability(
        self,
        store_id: int,
        cart_items: List[Dict[str, Any]],
        session
    ) -> Dict[str, Any]:
        """Check if all items are available at specific store"""

        availability_result = {
            "all_available": True,
            "available_items": [],
            "unavailable_items": []
        }

        for item in cart_items:
            # Check inventory for each product
            inventory_query = select(Inventory).where(
                and_(
                    Inventory.product_id == item["product_id"],
                    Inventory.store_id == store_id,
                    Inventory.quantity_available >= item["quantity"]
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
        session
    ) -> Dict[str, Any]:
        """Split items across multiple stores based on availability"""

        split_result = {
            "assignments": {},
            "unavailable_items": []
        }

        remaining_items = cart_items.copy()

        # Try each store in order of proximity
        for store in nearby_stores:
            if not remaining_items:
                break

            store_id = store["store_id"]
            availability = await self._check_store_availability(store_id, remaining_items, session)

            if availability["available_items"]:
                split_result["assignments"][store_id] = availability["available_items"]
                # Remove assigned items from remaining
                remaining_items = [item for item in remaining_items
                                 if item not in availability["available_items"]]

        # Any items that couldn't be assigned to any store
        split_result["unavailable_items"] = remaining_items

        return split_result