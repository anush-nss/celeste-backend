import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import update
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.api.carts.service import CartService
from src.api.inventory.service import InventoryService
from src.api.orders.models import CreateOrderSchema, OrderSchema, UpdateOrderSchema
from src.api.orders.services.payment_service import PaymentService
from src.api.orders.services.store_selection_service import StoreSelectionService
from src.api.pricing.service import PricingService
from src.api.users.models import (
    CartGroupSchema,
    CheckoutResponseSchema,
    MultiCartCheckoutSchema,
)
from src.config.constants import CartStatus, OrderStatus
from src.database.connection import AsyncSessionLocal
from src.database.models.cart import Cart
from src.database.models.order import Order, OrderItem
from src.database.models.product import Product
from src.database.models.store import Store
from src.database.models.user import User
from src.shared.error_handler import ErrorHandler, handle_service_errors
from src.shared.exceptions import ResourceNotFoundException, ValidationException


class OrderService:
    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.inventory_service = InventoryService()
        self.pricing_service = PricingService()
        self.payment_service = PaymentService()
        self.store_selection_service = StoreSelectionService()

    def calculate_delivery_charge(self, store_deliveries: List[Dict]) -> Decimal:
        """
        Calculate delivery charge based on stores and their distances.
        For prototyping: use max distance store and calculate base on that.

        Args:
            store_deliveries: List of dict with keys: 'store_id', 'store_name', 'store_lat', 'store_lng',
                             'delivery_lat', 'delivery_lng', 'items', 'store_total'

        Returns:
            Decimal: Total delivery charge
        """
        if not store_deliveries:
            return Decimal("0.00")

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
    ) -> List[Dict]:
        """
        Determine optimal store assignments using StoreSelectionService
        Returns list of store assignment dicts with cart_ids, store info, and totals
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

            return [
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
            ]

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

            return store_assignments

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
            return [OrderSchema.model_validate(order) for order in orders]

    @handle_service_errors("retrieving order")
    async def get_order_by_id(self, order_id: int) -> OrderSchema | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Order)
                .options(selectinload(Order.items))
                .filter(Order.id == order_id)
            )
            order = result.scalars().first()
            return OrderSchema.model_validate(order) if order else None

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
                    status=OrderStatus.PENDING,
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

                if order.status == status_update.status:
                    return OrderSchema.model_validate(order)  # No change

                # Logic for status transitions
                if status_update.status == OrderStatus.CONFIRMED:
                    if order.status != OrderStatus.PENDING:
                        raise ValidationException(
                            "Order must be PENDING to be CONFIRMED."
                        )
                    for item in order.items:
                        await self.inventory_service.confirm_reservation(
                            product_id=item.product_id,
                            store_id=item.store_id,
                            quantity=item.quantity,
                            session=session,
                        )
                elif status_update.status == OrderStatus.CANCELLED:
                    if order.status == OrderStatus.PENDING:
                        # Release the hold
                        for item in order.items:
                            await self.inventory_service.release_hold(
                                product_id=item.product_id,
                                store_id=item.store_id,
                                quantity=item.quantity,
                                session=session,
                            )
                    elif order.status == OrderStatus.CONFIRMED:
                        # This would be a more complex "cancellation" that might
                        # involve releasing a reservation. For now, let's assume
                        # only PENDING orders can be cancelled.
                        raise ValidationException(
                            "Cannot cancel a CONFIRMED order directly. Process a return instead."
                        )
                elif status_update.status == OrderStatus.SHIPPED:
                    if order.status != OrderStatus.CONFIRMED:
                        raise ValidationException(
                            "Order must be CONFIRMED to be SHIPPED."
                        )
                    for item in order.items:
                        await self.inventory_service.fulfill_order(
                            product_id=item.product_id,
                            store_id=item.store_id,
                            quantity=item.quantity,
                            session=session,
                        )

                order.status = status_update.status
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

        # STEP 4: Calculate totals
        total_amount = Decimal("0.00")
        for group in cart_groups:
            total_amount += Decimal(str(group.cart_total))

        # STEP 5: Now proceed with order creation in a separate transaction
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # STEP 6: Determine store assignments for order fulfillment
                location_obj = validation_data["location_obj"]
                store_assignments = await self._determine_store_assignments(
                    session, cart_groups, checkout_data.location, location_obj
                )

                if not store_assignments:
                    raise ValidationException(
                        "Could not find any stores to fulfill the order."
                    )

                # STEP 7: Calculate delivery charges (only for delivery mode)
                delivery_charge = Decimal("0.00")
                if checkout_data.location.mode == "delivery":
                    delivery_charge = self.calculate_delivery_charge(store_assignments)
                final_total = total_amount + delivery_charge

                # STEP 8: Create main order record
                # Use the first store as the main store for the order
                main_store_id = store_assignments[0]["store_id"]
                new_order = Order(
                    user_id=user_id,
                    store_id=main_store_id,
                    total_amount=final_total,
                    status=OrderStatus.PENDING,
                )
                session.add(new_order)
                await session.flush()

                # STEP 9: Create order items and place inventory holds
                placed_holds = []  # Track holds for error rollback

                # Build product-to-store mapping from store assignments
                product_store_map = {}
                for store_assignment in store_assignments:
                    # Map each product to its assigned store
                    for product_id in store_assignment.get("product_ids", []):
                        product_store_map[product_id] = store_assignment

                try:
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

                            # Place inventory hold at the assigned store
                            await self.inventory_service.place_hold(
                                product_id=item.product_id,
                                store_id=assigned_store["store_id"],
                                quantity=item.quantity,
                                session=session,
                            )

                            # Track successful hold for potential rollback
                            placed_holds.append(
                                {
                                    "product_id": item.product_id,
                                    "store_id": assigned_store["store_id"],
                                    "quantity": item.quantity,
                                }
                            )

                    # STEP 10: Update cart statuses to ordered
                    for cart_id in checkout_data.cart_ids:
                        await session.execute(
                            update(Cart)
                            .where(Cart.id == cart_id)
                            .values(
                                status=CartStatus.ORDERED, ordered_at=datetime.now(timezone.utc)
                            )
                        )

                    await session.refresh(new_order)
                except Exception as e:
                    # If anything fails, release all placed holds
                    for hold in placed_holds:
                        try:
                            await self.inventory_service.release_hold(
                                product_id=hold["product_id"],
                                store_id=hold["store_id"],
                                quantity=hold["quantity"],
                                session=session,
                            )
                        except Exception:
                            # Log but don't fail the rollback
                            pass
                    raise e

            # STEP 10: Initiate payment process outside transaction
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
            )

    @handle_service_errors("processing payment callback")
    async def process_payment_callback(self, callback_data: Dict) -> Dict[str, Any]:
        """Process payment gateway callback and update order status"""

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
