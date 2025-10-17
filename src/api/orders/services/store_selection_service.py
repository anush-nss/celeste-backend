"""
Store selection service with automatic selection and splitting logic
"""

from typing import Any, Dict, List, Optional, Tuple, cast

from sqlalchemy import and_, text
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.config.constants import (
    DEFAULT_SEARCH_RADIUS_KM,
    DEFAULT_STORE_IDS,
    NEXT_DAY_DELIVERY_ONLY_TAG_ID,
    FulfillmentMode,
)
from src.database.models.address import Address
from src.database.models.inventory import Inventory
from src.database.models.product import Product
from src.database.models.store import Store
from src.shared.error_handler import ErrorHandler
from src.shared.exceptions import ValidationException


from src.api.carts.service import CartService
from src.api.products.models import ProductSchema
from src.api.products.service import ProductService
from src.api.products.services import ProductInventoryService
from src.api.users.checkout_models import (
    CheckoutRequestSchema,
    UnavailableItemSchema,
)
from src.api.users.models import (
    MultiCartCheckoutSchema,
    CheckoutLocationSchema,
)


class StoreSelectionService:
    """Automatic store selection with nearest-first and splitting logic"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.cart_service = CartService()
        self.product_service = ProductService()
        self.inventory_service = ProductInventoryService()

    async def get_fulfillment_plan(
        self, session, user_id: str, request: CheckoutRequestSchema
    ) -> dict:
        """Centralized method to get a complete fulfillment plan."""

        location_schema = CheckoutLocationSchema(
            mode=request.location.mode,
            store_id=request.location.store_id,
            address_id=request.location.address_id,
        )
        validation_request = MultiCartCheckoutSchema(
            cart_ids=request.cart_ids, location=location_schema
        )

        validation_data = await self.cart_service.validate_checkout_data(
            session, user_id, validation_request
        )
        pricing_data = (
            await self.cart_service.fetch_products_and_calculate_pricing_with_session(
                session, validation_data
            )
        )
        cart_groups = self.cart_service.build_cart_groups(validation_data, pricing_data)

        location_obj = validation_data["location_obj"]
        all_items = [
            {
                "product_id": item.product_id,
                "quantity": item.quantity,
                "cart_id": group.cart_id,
            }
            for group in cart_groups
            for item in group.items
        ]

        if request.location.mode == FulfillmentMode.PICKUP.value:
            fulfillment_result = await self.validate_pickup_store(
                store_id=location_obj.id,
                cart_items=all_items,
                session=session,
            )
            store_assignments = {location_obj.id: fulfillment_result["available_items"]}
            unavailable_items = fulfillment_result["unavailable_items"]
            fulfillment_result["is_nearby_store"] = True  # Set for pickup
        else:
            fulfillment_result = await self.select_stores_for_delivery(
                address_id=location_obj.id,
                cart_items=all_items,
                mode=request.location.mode,
                session=session,
            )
            store_assignments = fulfillment_result["store_assignments"]
            unavailable_items = fulfillment_result["unavailable_items"]

        if not store_assignments:
            raise ValidationException("Could not find any stores to fulfill the order.")

        return {
            "store_assignments": store_assignments,
            "unavailable_items": unavailable_items,
            "cart_groups": cart_groups,
            "location_obj": location_obj,
            "fulfillment_result": fulfillment_result,
        }

    async def select_stores_for_delivery(
        self, address_id: int, cart_items: List[Dict[str, Any]], mode: str, session
    ) -> Dict[str, Any]:
        """Select optimal stores for delivery with splitting if needed"""

        selection_result = {
            "primary_store": None,
            "store_assignments": {},
            "requires_splitting": False,
            "unavailable_items": [],
            "delivery_distance": 0.0,
            "is_nearby_store": True,  # Track if stores are nearby or default
        }

        try:
            # Get address coordinates
            address_coords = await self._get_address_coordinates(address_id, session)
            if not address_coords:
                raise ValidationException(f"Address with ID {address_id} not found")

            # Get stores based on mode
            if mode == "far_delivery":
                stores, is_nearby = await self._get_default_stores(session), False
            else:  # default to delivery
                stores, is_nearby = await self._get_stores_by_distance(
                    address_coords, session
                )

            if not stores:
                raise ValidationException("No active stores found for delivery")

            # Update tracking flag
            selection_result["is_nearby_store"] = is_nearby

            # If using default stores (not nearby), check for excluded products
            if not is_nearby:
                product_ids = [item["product_id"] for item in cart_items]
                excluded_map = await self._check_products_have_excluded_tag(
                    product_ids, session
                )

                # Filter out items with excluded tag
                available_items = [
                    item
                    for item in cart_items
                    if not excluded_map.get(item["product_id"], False)
                ]
                excluded_items = [
                    item
                    for item in cart_items
                    if excluded_map.get(item["product_id"], False)
                ]

                # If all items are excluded, no fulfillment possible
                if not available_items:
                    raise ValidationException(
                        "No items available for delivery from default stores (all items are next-day delivery only)"
                    )

                # Update cart_items to only include available items
                cart_items = available_items
                
                excluded_items_response = await self._build_unavailable_items_response(
                    excluded_items, "far_delivery_unavailable", session
                )
                selection_result["unavailable_items"] = excluded_items_response

            # Try to fulfill from nearest store first
            nearest_store = stores[0]
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
                    cart_items, stores, session
                )

                # Merge unavailable items from excluded products and stock unavailability
                stock_unavailable_items = await self._build_unavailable_items_response(
                    split_result["unavailable_items"],
                    "out_of_stock",
                    session,
                    store_ids=[s["store_id"] for s in stores],
                )

                all_unavailable = (
                    selection_result["unavailable_items"]
                    + stock_unavailable_items
                )

                selection_result.update(
                    {
                        "primary_store": nearest_store,
                        "store_assignments": split_result["assignments"],
                        "requires_splitting": True,
                        "unavailable_items": all_unavailable,
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
            "available_items": [],
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

            unavailable_items_response = await self._build_unavailable_items_response(
                availability["unavailable_items"],
                "out_of_stock",
                session,
                store_ids=[store_id],
            )

            pickup_result.update(
                {
                    "all_items_available": availability["all_available"],
                    "available_items": availability["available_items"],
                    "unavailable_items": unavailable_items_response,
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
        self, address_coords: Tuple[float, float], session, use_fallback: bool = True
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """
        Get active stores ordered by distance from address (within delivery radius)

        Returns: (stores_list, is_nearby_stores)
            - stores_list: List of store dicts
            - is_nearby_stores: True if stores are within radius, False if using fallback defaults
        """

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
                "radius_meters": DEFAULT_SEARCH_RADIUS_KM
                * 1000,  # Convert km to meters
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

        # If no nearby stores found and fallback enabled, return default stores
        if not stores and use_fallback and DEFAULT_STORE_IDS:
            fallback_stores = await self._get_default_stores(session)
            return fallback_stores, False  # Not nearby stores

        return stores, True  # Nearby stores

    async def _get_default_stores(self, session) -> List[Dict[str, Any]]:
        """Get default fallback stores for distant users"""
        if not DEFAULT_STORE_IDS:
            return []

        store_query = select(Store).where(
            and_(Store.id.in_(DEFAULT_STORE_IDS), Store.is_active)
        )
        result = await session.execute(store_query)
        stores = result.scalars().all()

        return [
            {
                "store_id": store.id,
                "name": store.name,
                "address": store.address,
                "latitude": float(store.latitude),
                "longitude": float(store.longitude),
                "distance_km": None,  # No distance calculation for default stores
            }
            for store in stores
        ]

    async def _check_products_have_excluded_tag(
        self, product_ids: List[int], session
    ) -> Dict[int, bool]:
        """
        Check which products have the NEXT_DAY_DELIVERY_ONLY_TAG_ID

        Returns: Dict mapping product_id -> has_excluded_tag
        """
        if not product_ids:
            return {}

        # Query products with their tags
        products_query = (
            select(Product)
            .where(Product.id.in_(product_ids))
            .options(selectinload(Product.product_tags))
        )
        result = await session.execute(products_query)
        products = result.scalars().all()

        excluded_map = {}
        for product in products:
            # Check if product has the excluded tag
            has_excluded_tag = any(
                pt.tag_id == NEXT_DAY_DELIVERY_ONLY_TAG_ID
                for pt in product.product_tags
            )
            excluded_map[product.id] = has_excluded_tag

        return excluded_map

    async def _check_store_availability(
        self, store_id: int, cart_items: List[Dict[str, Any]], session
    ) -> Dict[str, Any]:
        """Check if all items are available at specific store (bulk optimized, respects safety stock)"""

        availability_result = {
            "all_available": True,
            "available_items": [],
            "unavailable_items": [],
        }

        if not cart_items:
            return availability_result

        # Bulk fetch inventory for all products at this store
        product_ids = [item["product_id"] for item in cart_items]
        inventory_query = select(Inventory).where(
            and_(
                Inventory.product_id.in_(product_ids),
                Inventory.store_id == store_id,
            )
        )

        result = await session.execute(inventory_query)
        inventories = result.scalars().all()

        # Build inventory map: product_id -> usable quantity (considering safety stock)
        inventory_map = {}
        for inv in inventories:
            usable_qty = max(0, inv.quantity_available - (inv.safety_stock or 0))
            inventory_map[inv.product_id] = usable_qty

        # Check availability for each item
        for item in cart_items:
            usable_qty = inventory_map.get(item["product_id"], 0)

            if usable_qty >= item["quantity"]:
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

    async def _build_unavailable_items_response(
        self,
        unavailable_items: List[Dict[str, Any]],
        reason: str,
        session,
        store_ids: Optional[List[int]] = None,
    ) -> List[UnavailableItemSchema]:
        if not unavailable_items:
            return []

        product_ids = [item["product_id"] for item in unavailable_items]
        products = await self.product_service.query_service.get_products_by_ids(
            product_ids
        )

        if reason == "out_of_stock" and store_ids:
            products = await self.inventory_service.add_inventory_to_products_bulk(
                products=products,
                store_ids=store_ids,
                is_nearby_store=True,
            )

        product_map = {product.id: product for product in products}

        unavailable_items_response = []
        for item in unavailable_items:
            product = product_map.get(item["product_id"])
            if product:
                max_available = None
                if product.inventory:
                    max_available = product.inventory.max_available

                unavailable_items_response.append(
                    UnavailableItemSchema(
                        product=ProductSchema.model_validate(product.model_dump()),
                        quantity=item["quantity"],
                        reason=reason,
                        max_available=max_available,
                    )
                )
        return unavailable_items_response

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
        from src.api.stores.service import StoreService

        store_service = StoreService()

        # Get stores sorted by distance (closest first)
        stores_data, is_nearby_store = await store_service.get_store_ids_by_location(
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            return_full_stores=True,
            include_distance=True,
        )
        stores_data = cast(Optional[List[Dict[str, Any]]], stores_data)

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

        # Check each cart item (respecting safety stock)
        fulfillment_info = []
        can_fulfill_all = True

        for item in cart_items:
            product_id = item["product_id"]
            quantity_needed = item["quantity"]

            # Find closest store with sufficient usable stock (considering safety stock)
            fulfilled_store = None
            quantity_available = 0

            for store_id in store_ids:
                inv_key = (product_id, store_id)
                inv = inventory_map.get(inv_key)

                if inv:
                    # Calculate usable quantity (respecting safety stock)
                    usable_qty = max(
                        0, inv.quantity_available - (inv.safety_stock or 0)
                    )

                    if usable_qty >= quantity_needed:
                        # Found store with enough usable stock
                        fulfilled_store = stores_by_id[store_id]
                        quantity_available = usable_qty
                        break

            # If not fully available, find store with maximum usable quantity
            if not fulfilled_store:
                max_available = 0
                best_store = None

                for store_id in store_ids:
                    inv_key = (product_id, store_id)
                    inv = inventory_map.get(inv_key)

                    if inv:
                        # Calculate usable quantity (respecting safety stock)
                        usable_qty = max(
                            0, inv.quantity_available - (inv.safety_stock or 0)
                        )

                        if usable_qty > max_available:
                            max_available = usable_qty
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
