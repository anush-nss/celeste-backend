import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import update
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.api.carts.service import CartService
from src.api.inventory.service import InventoryService
from src.api.orders.models import CreateOrderSchema, OrderItemSchema, OrderSchema, UpdateOrderSchema
from src.api.orders.services.payment_service import PaymentService
from src.api.orders.services.store_selection_service import StoreSelectionService
from src.api.pricing.service import PricingService
from src.api.products.cache import products_cache
from src.integrations.odoo.order_sync import OdooOrderSync
from src.api.users.models import (
    CartGroupSchema,
    CheckoutResponseSchema,
    MultiCartCheckoutSchema,
)
from src.config.constants import (
    CartStatus,
    FulfillmentMode,
    OrderStatus,
    DELIVERY_PRODUCT_ODOO_ID,
)
from src.database.connection import AsyncSessionLocal
from src.database.models.cart import Cart
from src.database.models.order import Order, OrderItem
from src.database.models.product import Product
from src.database.models.store import Store
from src.database.models.user import User
from src.shared.error_handler import ErrorHandler, handle_service_errors
from src.shared.exceptions import ResourceNotFoundException, ValidationException
from src.shared.sqlalchemy_utils import sqlalchemy_to_dict


class OrderService:
    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.inventory_service = InventoryService()
        self.pricing_service = PricingService()
        self.payment_service = PaymentService()
        self.store_selection_service = StoreSelectionService()
        self.products_cache = products_cache

    def calculate_flat_delivery_charge(
        self,
        store_deliveries: List[Dict],
        delivery_address: Optional[Dict] = None,
        order_details: Optional[Dict] = None,
    ) -> Decimal:
        """
        Calculate flat delivery charge for non-nearby stores (default fallback stores).

        For now, this is a fixed rate. In the future, this can be calculated based on:
        - Delivery address location
        - Order total amount
        - Store locations
        - Number of items
        - etc.

        Args:
            store_deliveries: List of dict with store assignment details
            delivery_address: Dict with delivery location details:
                - latitude: float
                - longitude: float
                - address: str
                - city: str
                - etc.
            order_details: Dict with order information:
                - total_amount: Decimal
                - items_count: int
                - total_weight: float (if available)
                - etc.

        Returns:
            Decimal: Flat delivery charge
        """
        # TODO: Implement dynamic calculation based on:
        # - delivery_address['latitude'], delivery_address['longitude']
        # - order_details['total_amount']
        # - store_deliveries (number of stores, locations)
        # - Distance to nearest distribution center
        # - Urban vs rural area
        # - Order value-based free shipping thresholds

        # For now, return fixed rate
        return Decimal("300.00")

    def calculate_delivery_charge(
        self,
        store_deliveries: List[Dict],
        is_nearby_store: bool = True,
        total_amount: Optional[Decimal] = None,
        items_count: Optional[int] = None,
    ) -> Decimal:
        """
        Calculate delivery charge based on stores and their distances.

        Args:
            store_deliveries: List of dict with keys: 'store_id', 'store_name', 'store_lat', 'store_lng',
                             'delivery_lat', 'delivery_lng', 'items', 'store_total'
            is_nearby_store: Whether delivery is from nearby stores or default fallback stores
            total_amount: Total order amount (for future flat rate calculations)
            items_count: Number of items in order (for future flat rate calculations)

        Returns:
            Decimal: Total delivery charge
        """
        if not store_deliveries:
            return Decimal("0.00")

        # Use flat rate for non-nearby stores
        if not is_nearby_store:
            # Extract delivery address from store_deliveries
            delivery_address = None
            if store_deliveries and "delivery_lat" in store_deliveries[0]:
                delivery_address = {
                    "latitude": store_deliveries[0].get("delivery_lat"),
                    "longitude": store_deliveries[0].get("delivery_lng"),
                }

            # Build order details
            order_details = {}
            if total_amount is not None:
                order_details["total_amount"] = total_amount
            if items_count is not None:
                order_details["items_count"] = items_count

            return self.calculate_flat_delivery_charge(
                store_deliveries, delivery_address, order_details
            )

        # For nearby stores: calculate based on distance using Haversine formula
        # Base delivery charge
        base_charge = Decimal("50.00")  # Rs. 50 base charge
        rate_per_km = Decimal("15.00")  # Rs. 15 per km

        max_distance = Decimal("0.00")

        for delivery in store_deliveries:
            # Calculate distance using Haversine formula
            store_lat = delivery["store_lat"]
            store_lng = delivery["store_lng"]
            delivery_lat = delivery["delivery_lat"]
            delivery_lng = delivery["delivery_lng"]

            # Convert to radians
            lat1, lng1 = math.radians(store_lat), math.radians(store_lng)
            lat2, lng2 = math.radians(delivery_lat), math.radians(delivery_lng)

            # Haversine formula
            dlat = lat2 - lat1
            dlng = lng2 - lng1
            a = (
                math.sin(dlat / 2) ** 2
                + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
            )
            c = 2 * math.asin(math.sqrt(a))
            distance_km = Decimal(str(6371 * c))  # Earth radius in km

            max_distance = max(max_distance, distance_km)

        # Calculate total charge: base + (max_distance * rate)
        total_charge = base_charge + (max_distance * rate_per_km)

        return total_charge.quantize(Decimal("0.01"))

    async def _determine_store_assignments(
        self, session, cart_groups: List[CartGroupSchema], location, location_obj
    ) -> Dict[str, Any]:
        """
        Determine optimal store assignments using StoreSelectionService
        Returns dict with:
            - store_assignments: list of store assignment dicts with cart_ids, store info, and totals
            - is_nearby_store: bool indicating if stores are nearby or default fallback stores
        """
        # Convert cart groups to cart items format for store selection service
        cart_items = []
        for group in cart_groups:
            for item in group.items:
                cart_items.append(
                    {
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                        "cart_id": group.cart_id,
                    }
                )

        if location.mode == "pickup":
            # Use store selection service for pickup validation
            pickup_result = await self.store_selection_service.validate_pickup_store(
                store_id=location_obj.id, cart_items=cart_items, session=session
            )

            if not pickup_result["all_items_available"]:
                unavailable_products = [
                    item["product_id"] for item in pickup_result["unavailable_items"]
                ]
                raise ValidationException(
                    f"Items not available at pickup store: {unavailable_products}"
                )

            # For pickup, all products come from the same store
            all_product_ids = [
                item.product_id for group in cart_groups for item in group.items
            ]

            return {
                "store_assignments": [
                    {
                        "store_id": location_obj.id,
                        "store_name": location_obj.name,
                        "store_lat": float(location_obj.latitude),
                        "store_lng": float(location_obj.longitude),
                        "delivery_lat": None,
                        "delivery_lng": None,
                        "cart_ids": [group.cart_id for group in cart_groups],
                        "store_total": sum(group.cart_total for group in cart_groups),
                        "product_ids": all_product_ids,
                    }
                ],
                "is_nearby_store": True,  # Pickup is always from a chosen nearby store
            }

        else:
            # Delivery mode: use smart store selection
            # Clean cart_items format for store selection service (remove cart_id)
            clean_cart_items = []
            for item in cart_items:
                clean_cart_items.append(
                    {"product_id": item["product_id"], "quantity": item["quantity"]}
                )

            delivery_result = (
                await self.store_selection_service.select_stores_for_delivery(
                    address_id=location_obj.id,
                    cart_items=clean_cart_items,
                    session=session,
                )
            )

            if delivery_result["unavailable_items"]:
                unavailable_products = [
                    item["product_id"] for item in delivery_result["unavailable_items"]
                ]
                raise ValidationException(
                    f"Items not available for delivery: {unavailable_products}"
                )

            # Convert store assignments to expected format
            store_assignments = []

            # Get store details for assignments (bulk query)
            assigned_store_ids = list(delivery_result["store_assignments"].keys())
            if assigned_store_ids:
                stores_query = select(Store).where(Store.id.in_(assigned_store_ids))
                stores_result = await session.execute(stores_query)
                stores_dict = {
                    store.id: store for store in stores_result.scalars().all()
                }
            else:
                stores_dict = {}

            for store_id, assigned_items in delivery_result[
                "store_assignments"
            ].items():
                # Get cart IDs for this store by matching product IDs back to cart_items
                store_cart_ids = []
                product_ids_for_store = []  # Track which products are from this store

                for assigned_item in assigned_items:
                    product_ids_for_store.append(assigned_item["product_id"])
                    for cart_item in cart_items:
                        if (
                            cart_item["product_id"] == assigned_item["product_id"]
                            and cart_item["cart_id"] not in store_cart_ids
                        ):
                            store_cart_ids.append(cart_item["cart_id"])

                # Calculate store total from assigned cart groups
                store_total = sum(
                    group.cart_total
                    for group in cart_groups
                    if group.cart_id in store_cart_ids
                )

                # Get actual store details
                store = stores_dict.get(int(store_id))
                if not store:
                    # Fallback to primary store if store not found
                    primary_store = delivery_result["primary_store"]
                    store_name = primary_store["name"]
                    store_lat = primary_store["latitude"]
                    store_lng = primary_store["longitude"]
                else:
                    store_name = store.name
                    store_lat = float(store.latitude)
                    store_lng = float(store.longitude)

                store_assignments.append(
                    {
                        "store_id": int(store_id),
                        "store_name": store_name,
                        "store_lat": store_lat,
                        "store_lng": store_lng,
                        "delivery_lat": float(location_obj.latitude),
                        "delivery_lng": float(location_obj.longitude),
                        "cart_ids": store_cart_ids,
                        "store_total": store_total,
                        "product_ids": product_ids_for_store,  # Add product IDs to mapping
                    }
                )

            return {
                "store_assignments": store_assignments,
                "is_nearby_store": delivery_result.get("is_nearby_store", True),
            }

    @handle_service_errors("updating user statistics")
    async def update_user_statistics(self, user_id: str, order_total: Decimal) -> None:
        """Update user statistics when an order is confirmed (paid)"""
        async with AsyncSessionLocal() as session:
            # Get current user statistics
            user_result = await session.execute(
                select(User).where(User.firebase_uid == user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                raise ValidationException(f"User {user_id} not found")

            # Update statistics
            new_total_orders = (user.total_orders or 0) + 1
            new_lifetime_value = (user.lifetime_value or 0.0) + float(order_total)

            # Update user record
            await session.execute(
                update(User)
                .where(User.firebase_uid == user_id)
                .values(
                    total_orders=new_total_orders,
                    lifetime_value=new_lifetime_value,
                    last_order_at=datetime.now(),
                )
            )

            await session.commit()

            self._error_handler.logger.info(
                f"Updated user statistics for {user_id} | "
                f"Total Orders: {new_total_orders} | "
                f"Lifetime Value: LKR {new_lifetime_value:.2f}"
            )

    @handle_service_errors("retrieving orders")
    async def get_all_orders(self, user_id: Optional[str] = None) -> List[OrderSchema]:
        async with AsyncSessionLocal() as session:
            query = select(Order).options(selectinload(Order.items))
            if user_id:
                query = query.filter(Order.user_id == user_id)
            result = await session.execute(query)
            orders = result.scalars().unique().all()

            # Filter out delivery product from each order's items
            order_schemas = []
            for order in orders:
                filtered_items = [
                    item
                    for item in order.items
                    if item.product_id != DELIVERY_PRODUCT_ODOO_ID
                ]

                order_dict = {
                    "id": order.id,
                    "user_id": order.user_id,
                    "store_id": order.store_id,
                    "address_id": order.address_id,
                    "total_amount": float(order.total_amount),
                    "delivery_charge": float(order.delivery_charge),
                    "fulfillment_mode": order.fulfillment_mode,
                    "status": order.status,
                    "created_at": order.created_at,
                    "updated_at": order.updated_at,
                    "items": [
                        OrderItemSchema.model_validate(item) for item in filtered_items
                    ],
                }
                order_schemas.append(OrderSchema.model_validate(order_dict))

            return order_schemas

    @handle_service_errors("retrieving order")
    async def get_order_by_id(self, order_id: int) -> OrderSchema | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Order)
                .options(selectinload(Order.items))
                .filter(Order.id == order_id)
            )
            order = result.scalars().first()
            if not order:
                return None

            # Filter out delivery product from items (it's shown as delivery_charge field)
            filtered_items = [
                item
                for item in order.items
                if item.product_id != DELIVERY_PRODUCT_ODOO_ID
            ]

            # Build order dict with filtered items
            order_dict = {
                "id": order.id,
                "user_id": order.user_id,
                "store_id": order.store_id,
                "address_id": order.address_id,
                "total_amount": float(order.total_amount),
                "delivery_charge": float(order.delivery_charge),
                "fulfillment_mode": order.fulfillment_mode,
                "status": order.status,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
                "items": [OrderItemSchema.model_validate(item) for item in filtered_items],
            }

            return OrderSchema.model_validate(order_dict)

    @handle_service_errors("creating order")
    async def create_order(
        self, order_data: CreateOrderSchema, user_id: str
    ) -> OrderSchema:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # 1. Validate items and fetch prices
                product_ids = [item.product_id for item in order_data.items]
                product_result = await session.execute(
                    select(Product).filter(Product.id.in_(product_ids))
                )
                products = product_result.scalars().all()
                product_map = {p.id: p for p in products}

                if len(products) != len(product_ids):
                    raise ResourceNotFoundException("One or more products not found.")

                total_amount = Decimal(0)
                order_items_to_create = []

                # 2. Place holds on inventory for each item
                for item_data in order_data.items:
                    product = product_map[item_data.product_id]

                    # Place hold - this will raise an error if stock is insufficient
                    await self.inventory_service.place_hold(
                        product_id=item_data.product_id,
                        store_id=order_data.store_id,
                        quantity=item_data.quantity,
                        session=session,
                    )

                    unit_price = Decimal(str(product.base_price))
                    total_price = unit_price * item_data.quantity
                    total_amount += total_price
                    order_items_to_create.append(
                        OrderItem(
                            product_id=item_data.product_id,
                            store_id=order_data.store_id,
                            quantity=item_data.quantity,
                            unit_price=unit_price,
                            total_price=total_price,
                        )
                    )

                # 3. Create the order
                new_order = Order(
                    user_id=user_id,
                    store_id=order_data.store_id,
                    total_amount=total_amount,
                    status=OrderStatus.PENDING.value,
                    items=order_items_to_create,
                )
                session.add(new_order)
                await session.flush()
                await session.refresh(new_order, ["items"])

                return OrderSchema.model_validate(new_order)

    @handle_service_errors("updating order status")
    async def update_order_status(
        self, order_id: int, status_update: UpdateOrderSchema
    ) -> OrderSchema:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(Order)
                    .options(selectinload(Order.items))
                    .filter(Order.id == order_id)
                )
                order = result.scalars().first()

                if not order:
                    raise ResourceNotFoundException(
                        f"Order with ID {order_id} not found."
                    )

                # Get status values as strings for comparison
                current_status = order.status
                new_status = status_update.status.value if isinstance(status_update.status, OrderStatus) else status_update.status

                if current_status == new_status:
                    return OrderSchema.model_validate(order)  # No change

                # Logic for status transitions
                if new_status == OrderStatus.CONFIRMED.value:
                    if current_status != OrderStatus.PENDING.value:
                        raise ValidationException(
                            "Order must be PENDING to be CONFIRMED."
                        )
                    for item in order.items:
                        if item.product_id == DELIVERY_PRODUCT_ODOO_ID:
                            continue
                        await self.inventory_service.confirm_reservation(
                            product_id=item.product_id,
                            store_id=item.store_id,
                            quantity=item.quantity,
                            session=session,
                        )

                elif new_status == OrderStatus.PROCESSING.value:
                    if current_status != OrderStatus.CONFIRMED.value:
                        raise ValidationException(
                            "Order must be CONFIRMED to be PROCESSING."
                        )

                elif new_status == OrderStatus.PACKED.value:
                    if current_status != OrderStatus.PROCESSING.value:
                        raise ValidationException(
                            "Order must be PROCESSING to be PACKED."
                        )

                elif new_status == OrderStatus.SHIPPED.value:
                    if current_status != OrderStatus.PACKED.value:
                        raise ValidationException(
                            "Order must be PACKED to be SHIPPED."
                        )
                    # Fulfill inventory when shipped (rider collected from store)
                    for item in order.items:
                        if item.product_id == DELIVERY_PRODUCT_ODOO_ID:
                            continue
                        await self.inventory_service.fulfill_order(
                            product_id=item.product_id,
                            store_id=item.store_id,
                            quantity=item.quantity,
                            session=session,
                        )

                elif new_status == OrderStatus.DELIVERED.value:
                    # Can go from PACKED (pickup) or SHIPPED (delivery)
                    if current_status not in [OrderStatus.PACKED.value, OrderStatus.SHIPPED.value]:
                        raise ValidationException(
                            "Order must be PACKED or SHIPPED to be DELIVERED."
                        )
                    # If coming from PACKED (pickup order), fulfill inventory now
                    if current_status == OrderStatus.PACKED.value:
                        for item in order.items:
                            if item.product_id == DELIVERY_PRODUCT_ODOO_ID:
                                continue
                            await self.inventory_service.fulfill_order(
                                product_id=item.product_id,
                                store_id=item.store_id,
                                quantity=item.quantity,
                                session=session,
                            )

                elif new_status == OrderStatus.CANCELLED.value:
                    if current_status == OrderStatus.PENDING.value:
                        # Release the hold
                        for item in order.items:
                            if item.product_id == DELIVERY_PRODUCT_ODOO_ID:
                                continue
                            await self.inventory_service.release_hold(
                                product_id=item.product_id,
                                store_id=item.store_id,
                                quantity=item.quantity,
                                session=session,
                            )
                    elif current_status in [OrderStatus.CONFIRMED.value, OrderStatus.PROCESSING.value, OrderStatus.PACKED.value]:
                        # Cannot cancel orders that are confirmed or being prepared
                        raise ValidationException(
                            "Cannot cancel a CONFIRMED, PROCESSING, or PACKED order. Please contact support."
                        )

                order.status = status_update.status.value if isinstance(status_update.status, OrderStatus) else status_update.status
                # Note: session.begin() context manager auto-commits on exit
                await session.flush()  # Ensure changes are persisted
                await session.refresh(order)
                return OrderSchema.model_validate(order)

    @handle_service_errors("creating multi-cart order")
    async def create_multi_cart_order(
        self, user_id: str, checkout_data: MultiCartCheckoutSchema
    ) -> CheckoutResponseSchema:
        """Create order from multiple carts using optimized shared logic and exact pricing"""

        # STEP 1: Validate checkout data OUTSIDE transaction
        async with AsyncSessionLocal() as validation_session:
            validation_data = await CartService.validate_checkout_data(
                validation_session, user_id, checkout_data
            )

        # STEP 2: Calculate pricing separately (no session needed)
        pricing_data = await CartService.fetch_products_and_calculate_pricing(
            validation_data
        )

        # STEP 3: Build cart groups with pricing (no DB needed)
        cart_groups = CartService.build_cart_groups(validation_data, pricing_data)

        # STEP 4: Calculate totals and count items
        total_amount = Decimal("0.00")
        items_count = 0
        for group in cart_groups:
            total_amount += Decimal(str(group.cart_total))
            items_count += len(group.items)

        # STEP 5: Now proceed with order creation in a separate transaction
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # STEP 6: Determine store assignments for order fulfillment
                location_obj = validation_data["location_obj"]
                store_result = await self._determine_store_assignments(
                    session, cart_groups, checkout_data.location, location_obj
                )

                store_assignments = store_result["store_assignments"]
                is_nearby_store = store_result["is_nearby_store"]

                if not store_assignments:
                    raise ValidationException(
                        "Could not find any stores to fulfill the order."
                    )

                # STEP 7: Calculate delivery charges (only for delivery mode)
                delivery_charge = Decimal("0.00")
                if checkout_data.location.mode == "delivery":
                    delivery_charge = self.calculate_delivery_charge(
                        store_assignments, is_nearby_store, total_amount, items_count
                    )
                final_total = total_amount + delivery_charge

                # STEP 8: Determine fulfillment mode
                if checkout_data.location.mode == "pickup":
                    fulfillment_mode = FulfillmentMode.PICKUP.value
                elif checkout_data.location.mode == "delivery":
                    # Distinguish between nearby delivery and far delivery
                    fulfillment_mode = (
                        FulfillmentMode.DELIVERY.value
                        if is_nearby_store
                        else FulfillmentMode.FAR_DELIVERY.value
                    )
                else:
                    fulfillment_mode = FulfillmentMode.PICKUP.value  # Default fallback

                # STEP 9: Create main order record
                # Use the first store as the main store for the order
                main_store_id = store_assignments[0]["store_id"]

                # Set address_id for delivery orders, None for pickup
                address_id = None
                if checkout_data.location.mode == "delivery":
                    address_id = checkout_data.location.address_id

                new_order = Order(
                    user_id=user_id,
                    store_id=main_store_id,
                    address_id=address_id,
                    total_amount=final_total,
                    delivery_charge=delivery_charge,
                    fulfillment_mode=fulfillment_mode,
                    status=OrderStatus.PENDING.value,
                )
                session.add(new_order)
                await session.flush()

                # STEP 10: Add delivery charge as a separate order item if applicable
                if delivery_charge > 0:
                    # Try to get the delivery product from cache first
                    delivery_product_dict = self.products_cache.get_delivery_product()
                    delivery_product_id = None

                    if delivery_product_dict:
                        # Extract ID from cached dict (no need to create Product instance)
                        delivery_product_id = delivery_product_dict.get("id")

                    if not delivery_product_id:
                        # Fetch from the database if not in cache
                        delivery_product_result = await session.execute(
                            select(Product).filter(
                                Product.id == DELIVERY_PRODUCT_ODOO_ID
                            )
                        )
                        delivery_product = delivery_product_result.scalar_one_or_none()

                        if delivery_product:
                            delivery_product_id = delivery_product.id
                            # Cache the product for future requests
                            self.products_cache.set_delivery_product(
                                sqlalchemy_to_dict(
                                    delivery_product,
                                    exclude_relationships={
                                        "categories",
                                        "product_tags",
                                        "inventory_levels",
                                    },
                                )
                            )

                    if delivery_product_id:
                        delivery_item = OrderItem(
                            order_id=new_order.id,
                            product_id=delivery_product_id,
                            store_id=main_store_id,  # Assign to the main store
                            quantity=1,
                            unit_price=delivery_charge,
                            total_price=delivery_charge,
                            # Associate with the first cart in the checkout
                            source_cart_id=checkout_data.cart_ids[0],
                        )
                        session.add(delivery_item)
                    else:
                        # Log a warning if the delivery product is not found
                        self._error_handler.logger.warning(
                            f"Delivery product with Odoo ID {DELIVERY_PRODUCT_ODOO_ID} not found. "
                            "Delivery charge will not be added as a line item."
                        )

                # STEP 11: Create order items and collect inventory holds
                holds_to_place = []  # Collect all holds for bulk placement
                placed_holds = []  # Track successfully placed holds for rollback

                # Build product-to-store mapping from store assignments
                product_store_map = {}
                for store_assignment in store_assignments:
                    # Map each product to its assigned store
                    for product_id in store_assignment.get("product_ids", []):
                        product_store_map[product_id] = store_assignment

                try:
                    # First pass: Create all order items and collect holds
                    for cart_group in cart_groups:
                        for item in cart_group.items:
                            # Get the correct assigned store for this specific product
                            assigned_store = product_store_map.get(
                                item.product_id, store_assignments[0]
                            )

                            # Create order item with pricing from preview and assigned store
                            order_item = OrderItem(
                                order_id=new_order.id,
                                source_cart_id=cart_group.cart_id,
                                product_id=item.product_id,
                                store_id=assigned_store["store_id"],
                                quantity=item.quantity,
                                unit_price=Decimal(str(item.final_price)),
                                total_price=Decimal(str(item.total_price)),
                            )
                            session.add(order_item)

                            # Collect hold for bulk placement
                            holds_to_place.append(
                                {
                                    "product_id": item.product_id,
                                    "store_id": assigned_store["store_id"],
                                    "quantity": item.quantity,
                                }
                            )

                    # Place all inventory holds in bulk (optimized single operation)
                    await self.inventory_service.place_holds_bulk(
                        holds_to_place, session
                    )

                    # Track successful holds for potential rollback
                    placed_holds = holds_to_place

                    # STEP 12: Update cart statuses to ordered (bulk update)
                    await session.execute(
                        update(Cart)
                        .where(Cart.id.in_(checkout_data.cart_ids))
                        .values(
                            status=CartStatus.ORDERED,
                            ordered_at=datetime.now(timezone.utc),
                        )
                    )

                    await session.refresh(new_order)
                except Exception as e:
                    # If anything fails, release all placed holds in bulk
                    try:
                        await self.inventory_service.release_holds_bulk(
                            placed_holds, session
                        )
                    except Exception as rollback_error:
                        # Log but don't fail the rollback
                        self._error_handler.logger.error(
                            f"Failed to release holds during rollback: {rollback_error}",
                            exc_info=True,
                        )
                    raise e

            # STEP 13: Initiate payment process outside transaction
            payment_result = await self.payment_service.initiate_payment(
                order_id=new_order.id,
                total_amount=final_total,
                user_id=user_id,
                payment_method="card",
            )

            return CheckoutResponseSchema(
                order_id=new_order.id,
                total_amount=float(new_order.total_amount),
                status=new_order.status,
                cart_groups=cart_groups,
                created_at=new_order.created_at,
                payment_url=payment_result["payment_url"],
                payment_reference=payment_result["payment_reference"],
                payment_expires_at=payment_result["expires_at"],
                is_nearby_store=is_nearby_store,
            )

    async def _background_odoo_sync(self, order_id: int) -> None:
        """Background task to sync order to Odoo (runs after response is sent)"""
        try:
            odoo_sync = OdooOrderSync()
            sync_result = await odoo_sync.sync_order_to_odoo(order_id)
            if sync_result["success"]:
                self._error_handler.logger.info(
                    f"Background sync: Order {order_id} successfully synced to Odoo | "
                    f"Odoo Order ID: {sync_result['odoo_order_id']}"
                )
            else:
                self._error_handler.logger.warning(
                    f"Background sync: Odoo sync failed for order {order_id}: {sync_result['error']}"
                )
        except Exception as e:
            self._error_handler.logger.error(
                f"Background sync: Failed to sync order {order_id} to Odoo: {str(e)}",
                exc_info=True,
            )

    @handle_service_errors("processing payment callback")
    async def process_payment_callback(
        self, callback_data: Dict, background_tasks=None
    ) -> Dict[str, Any]:
        """Process payment gateway callback and update order status

        Args:
            callback_data: Payment gateway callback data
            background_tasks: FastAPI BackgroundTasks for async processing
        """

        # Process callback through payment service
        callback_result = await self.payment_service.process_payment_callback(
            callback_data
        )

        if callback_result["status"] == "error":
            return callback_result

        order_id = callback_result["order_id"]
        payment_status = callback_result["status"]

        if not order_id:
            return {"status": "error", "message": "Order ID not found in callback"}

        # Update order status based on payment result
        if payment_status == "success":
            # Automatically confirm the order (convert holds to reservations)
            update_schema = UpdateOrderSchema(status=OrderStatus.CONFIRMED)
            updated_order = await self.update_order_status(order_id, update_schema)

            # Update user statistics for successful payment
            try:
                await self.update_user_statistics(
                    updated_order.user_id, Decimal(str(updated_order.total_amount))
                )
            except Exception as e:
                # Log but don't fail the payment processing
                self._error_handler.logger.error(
                    f"Failed to update user statistics for order {order_id}: {str(e)}"
                )

            # Queue Odoo sync as background task (non-blocking)
            if background_tasks:
                background_tasks.add_task(self._background_odoo_sync, order_id)
                self._error_handler.logger.info(
                    f"Odoo sync queued as background task for order {order_id}"
                )
            else:
                # Fallback: log warning if BackgroundTasks not provided
                self._error_handler.logger.warning(
                    f"BackgroundTasks not provided - Odoo sync skipped for order {order_id}. "
                    "Use retry endpoint to sync manually."
                )

            return {
                "status": "success",
                "order_id": order_id,
                "order_status": updated_order.status,
                "payment_reference": callback_result["payment_reference"],
                "transaction_id": callback_result["transaction_id"],
            }
        else:
            # Payment failed - cancel order and release holds
            update_schema = UpdateOrderSchema(status=OrderStatus.CANCELLED)
            updated_order = await self.update_order_status(order_id, update_schema)

            return {
                "status": "failed",
                "order_id": order_id,
                "order_status": updated_order.status,
                "payment_reference": callback_result["payment_reference"],
            }
