"""
Service for handling checkout preview and order creation.
"""

from decimal import Decimal
from fastapi import HTTPException, status

from src.api.orders.service import OrderService
from src.api.orders.services.store_selection_service import StoreSelectionService
from src.api.products.models import ProductSchema
from src.api.products.service import ProductService
from src.api.stores.service import StoreService
from src.api.users.checkout_models import (
    CheckoutCartItemPricingSchema,
    CheckoutRequestSchema,
    CheckoutResponse,
    NonSplitErrorResponse,
    StoreFulfillmentResponse,
    UnavailableItemsErrorResponse,
)
from src.config.constants import FulfillmentMode
from src.database.connection import AsyncSessionLocal


class CheckoutService:
    def __init__(self):
        self.store_selection_service = StoreSelectionService()
        self.order_service = OrderService()
        self.product_service = ProductService()
        self.store_service = StoreService()

    async def preview_order(
        self, user_id: str, request: CheckoutRequestSchema
    ) -> CheckoutResponse:
        """Generates a checkout preview with per-store fulfillment details."""
        async with AsyncSessionLocal() as session:
            plan = await self.store_selection_service.get_fulfillment_plan(
                session, user_id, request
            )

            store_assignments = plan["store_assignments"]
            unavailable_items = plan["unavailable_items"]
            cart_groups = plan["cart_groups"]
            location_obj = plan["location_obj"]
            fulfillment_result = plan["fulfillment_result"]

            fulfillable_stores = []
            overall_total = Decimal("0.00")
            product_pricing_map = {
                (item.product_id, group.cart_id): item
                for group in cart_groups
                for item in group.items
            }

            # Get all product IDs from store_assignments
            product_ids = {
                item["product_id"]
                for items in store_assignments.values()
                for item in items
            }

            # Fetch all products at once
            products = await self.product_service.query_service.get_products_by_ids(
                list(product_ids)
            )
            product_map = {product.id: product for product in products}

            # Fetch all stores at once
            store_ids = store_assignments.keys()
            stores = await self.store_service.get_stores_by_ids(
                session, list(store_ids)
            )
            store_map = {store.id: store for store in stores}

            for store_id, assigned_items_list in store_assignments.items():
                store_subtotal = Decimal("0.00")
                store_items_priced = []
                for assigned_item in assigned_items_list:
                    product_id = assigned_item["product_id"]
                    cart_id = assigned_item["cart_id"]
                    if (product_id, cart_id) in product_pricing_map:
                        priced_item = product_pricing_map[(product_id, cart_id)]
                        store_subtotal += Decimal(str(priced_item.total_price))

                        product = product_map.get(product_id)
                        if not product:
                            raise HTTPException(
                                status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Product with ID {product_id} not found",
                            )

                        checkout_item = CheckoutCartItemPricingSchema(
                            **priced_item.model_dump(),
                            source_cart_id=cart_id,
                            product=ProductSchema.model_validate(product),
                        )
                        store_items_priced.append(checkout_item)

                delivery_cost = Decimal("0.00")
                if request.location.mode in [
                    FulfillmentMode.DELIVERY.value,
                    FulfillmentMode.FAR_DELIVERY.value,
                ]:
                    is_nearby = fulfillment_result.get("is_nearby_store", True)
                    store_info = store_map.get(store_id)

                    if store_info is None:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Store with ID {store_id} not found",
                        )

                    single_store_delivery = [
                        {
                            "store_lat": store_info.latitude,
                            "store_lng": store_info.longitude,
                            "delivery_lat": location_obj.latitude,
                            "delivery_lng": location_obj.longitude,
                        }
                    ]

                    delivery_cost = self.order_service.calculate_delivery_charge(
                        store_deliveries=single_store_delivery,
                        is_nearby_store=is_nearby,
                        service_level=request.location.delivery_service_level,
                    )

                store_total = store_subtotal + delivery_cost
                overall_total += store_total
                store_info = store_map.get(store_id)

                if store_info is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Store with ID {store_id} not found",
                    )

                fulfillable_stores.append(
                    StoreFulfillmentResponse(
                        order_id=None,
                        store_id=store_id,
                        store_name=store_info.name,
                        items=store_items_priced,
                        subtotal=float(store_subtotal),
                        delivery_cost=float(delivery_cost),
                        total=float(store_total),
                    )
                )

            fulfillable_stores.sort(key=lambda s: len(s.items), reverse=True)

            # Determine the final fulfillment mode
            final_fulfillment_mode = request.location.mode
            if request.location.mode == FulfillmentMode.DELIVERY.value:
                is_nearby = fulfillment_result.get("is_nearby_store", True)
                if not is_nearby:
                    final_fulfillment_mode = FulfillmentMode.FAR_DELIVERY.value

            return CheckoutResponse(
                fulfillment_mode=final_fulfillment_mode,
                fulfillable_stores=fulfillable_stores,
                overall_total=float(overall_total),
                unavailable_items=unavailable_items,
            )

    async def create_order(
        self, user_id: str, request: CheckoutRequestSchema
    ) -> CheckoutResponse:
        """Creates one or more orders based on the checkout request."""
        if (
            request.location.mode == FulfillmentMode.PICKUP.value
            and request.split_order
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Splitting an order is not supported for pickup.",
            )

        preview = await self.preview_order(user_id, request)

        if preview.unavailable_items:
            error_response = UnavailableItemsErrorResponse(
                detail="Some items in your cart are unavailable. Please review the items below.",
                unavailable_items=preview.unavailable_items,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_response.model_dump(mode="json"),
            )

        if (
            not request.split_order
            and request.location.mode == FulfillmentMode.DELIVERY.value
        ):
            if len(preview.fulfillable_stores) > 1:
                error_response = NonSplitErrorResponse(
                    detail="No single store can fulfill the entire order. Please review the options below or allow the order to be split.",
                    fulfillment_mode=preview.fulfillment_mode,
                    fulfillable_stores=preview.fulfillable_stores,
                    overall_total=preview.overall_total,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error_response.model_dump(),
                )

        final_fulfillable_stores = []
        for store_fulfillment in preview.fulfillable_stores:
            created_order = await self.order_service.create_single_store_order(
                user_id=user_id,
                store_fulfillment=store_fulfillment,
                location=request.location,
                cart_ids=request.cart_ids,
            )
            # Create a new StoreFulfillmentResponse with the order_id
            fulfillment_with_order_id = StoreFulfillmentResponse(
                order_id=created_order.id,
                **store_fulfillment.model_dump(exclude={"order_id"}),
            )
            final_fulfillable_stores.append(fulfillment_with_order_id)

        return CheckoutResponse(
            fulfillment_mode=preview.fulfillment_mode,
            fulfillable_stores=final_fulfillable_stores,
            overall_total=preview.overall_total,
            unavailable_items=preview.unavailable_items,
        )
