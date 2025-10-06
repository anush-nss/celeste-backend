"""
Checkout validation service with modular validations
"""

from typing import Any, Dict, List, Tuple

from src.api.users.models import MultiCartCheckoutSchema
from src.shared.error_handler import ErrorHandler


class CheckoutValidationService:
    """Modular checkout validation service"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)

    async def validate_checkout_request(
        self, checkout_data: MultiCartCheckoutSchema, cart_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Main validation orchestrator"""

        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "location_type": checkout_data.location.mode,
            "target_id": checkout_data.location.store_id if checkout_data.location.mode == "pickup" else checkout_data.location.address_id,
            "requires_splitting": False,
            "store_assignments": {},
            "distance_restrictions": [],
        }

        # Validate location mode
        if checkout_data.location.mode not in ["delivery", "pickup"]:
            validation_result["errors"].append(
                "Invalid location mode. Must be 'delivery' or 'pickup'"
            )
            validation_result["is_valid"] = False

        # Validate mode-specific fields
        if checkout_data.location.mode == "pickup" and not checkout_data.location.store_id:
            validation_result["errors"].append(
                "store_id is required for pickup mode"
            )
            validation_result["is_valid"] = False
        elif checkout_data.location.mode == "delivery" and not checkout_data.location.address_id:
            validation_result["errors"].append(
                "address_id is required for delivery mode"
            )
            validation_result["is_valid"] = False

        # Validate cart items exist and have products
        if not cart_items:
            validation_result["errors"].append("No items found in selected carts")
            validation_result["is_valid"] = False

        return validation_result

    async def validate_product_availability(
        self, cart_items: List[Dict[str, Any]], store_id: int
    ) -> Dict[str, Any]:
        """Validate product availability at specific store"""

        # Placeholder for product availability validation
        availability_result = {
            "available_items": [],
            "unavailable_items": [],
            "partial_availability": [],
        }

        # TODO: Implement actual inventory checking
        # For now, assume all items are available
        availability_result["available_items"] = cart_items

        return availability_result

    async def validate_product_distance_restrictions(
        self, cart_items: List[Dict[str, Any]], delivery_distance_km: float
    ) -> Dict[str, Any]:
        """Validate fresh product distance restrictions using tags"""

        restrictions_result = {
            "allowed_items": [],
            "restricted_items": [],
            "max_distance_violations": [],
        }

        # TODO: Implement tag-based distance validation
        # Check product tags for fresh items and distance limits
        # Placeholder logic:
        for item in cart_items:
            # Assume fresh products have max 10km delivery distance
            product_tags = item.get("product_tags", [])
            is_fresh = any(
                tag.get("tag_type") == "product_type"
                and "fresh" in tag.get("name", "").lower()
                for tag in product_tags
            )

            if is_fresh and delivery_distance_km > 10:
                restrictions_result["restricted_items"].append(
                    {
                        "product_id": item["product_id"],
                        "reason": f"Fresh product delivery distance ({delivery_distance_km}km) exceeds maximum (10km)",
                        "max_distance": 10,
                    }
                )
                restrictions_result["max_distance_violations"].append(
                    item["product_id"]
                )
            else:
                restrictions_result["allowed_items"].append(item)

        return restrictions_result

    async def validate_pickup_store_selection(
        self, store_id: int, cart_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate pickup store selection and availability"""

        # Placeholder for pickup validation
        pickup_result = {
            "store_valid": True,
            "store_active": True,
            "all_items_available": True,
            "unavailable_items": [],
            "estimated_pickup_time": "30 minutes",
        }

        # TODO: Implement actual store and availability validation
        return pickup_result

    def calculate_delivery_distance(
        self, address_coords: Tuple[float, float], store_coords: Tuple[float, float]
    ) -> float:
        """Calculate distance between address and store (placeholder)"""

        # Simple Euclidean distance calculation (placeholder)
        # TODO: Implement proper geographic distance calculation
        lat1, lon1 = address_coords
        lat2, lon2 = store_coords

        # Very basic distance calculation (not accurate for real use)
        distance_km = (
            (lat2 - lat1) ** 2 + (lon2 - lon1) ** 2
        ) ** 0.5 * 111  # Rough km conversion

        return distance_km
