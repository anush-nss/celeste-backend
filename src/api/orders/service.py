from typing import List, Optional, Dict, Any
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, update
from src.database.connection import AsyncSessionLocal
from src.database.models.order import Order, OrderItem
from src.database.models.product import Product
from src.database.models.cart import Cart, CartItem
from src.database.models.store import Store
from src.database.models.address import Address
from src.api.orders.models import OrderSchema, CreateOrderSchema, UpdateOrderSchema
from src.api.users.models import MultiCartCheckoutSchema, CheckoutResponseSchema, CartGroupSchema
from src.api.inventory.service import InventoryService
from src.api.carts.service import CartService
from src.api.pricing.service import PricingService
from src.api.orders.services.payment_service import PaymentService
from src.config.constants import OrderStatus, CartStatus
from src.shared.exceptions import ResourceNotFoundException, ValidationException
from src.shared.error_handler import ErrorHandler, handle_service_errors
from decimal import Decimal
import math


class OrderService:
    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.inventory_service = InventoryService()
        self.pricing_service = PricingService()
        self.payment_service = PaymentService()

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
            return Decimal('0.00')

        # Base delivery charge
        base_charge = Decimal('50.00')  # Rs. 50 base charge
        rate_per_km = Decimal('15.00')  # Rs. 15 per km

        max_distance = Decimal('0.00')

        for delivery in store_deliveries:
            # Calculate distance using Haversine formula
            store_lat = delivery['store_lat']
            store_lng = delivery['store_lng']
            delivery_lat = delivery['delivery_lat']
            delivery_lng = delivery['delivery_lng']

            # Convert to radians
            lat1, lng1 = math.radians(store_lat), math.radians(store_lng)
            lat2, lng2 = math.radians(delivery_lat), math.radians(delivery_lng)

            # Haversine formula
            dlat = lat2 - lat1
            dlng = lng2 - lng1
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
            c = 2 * math.asin(math.sqrt(a))
            distance_km = Decimal(str(6371 * c))  # Earth radius in km

            max_distance = max(max_distance, distance_km)

        # Calculate total charge: base + (max_distance * rate)
        total_charge = base_charge + (max_distance * rate_per_km)

        return total_charge.quantize(Decimal('0.01'))

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
                    )

                    price = product.base_price
                    total_amount += price * item_data.quantity
                    order_items_to_create.append(
                        OrderItem(
                            product_id=item_data.product_id,
                            quantity=item_data.quantity,
                            price=price,
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
                    select(Order).options(selectinload(Order.items)).filter(Order.id == order_id)
                )
                order = result.scalars().first()

                if not order:
                    raise ResourceNotFoundException(f"Order with ID {order_id} not found.")

                if order.status == status_update.status:
                    return OrderSchema.model_validate(order) # No change

                # Logic for status transitions
                if status_update.status == OrderStatus.CONFIRMED:
                    if order.status != OrderStatus.PENDING:
                        raise ValidationException("Order must be PENDING to be CONFIRMED.")
                    for item in order.items:
                        await self.inventory_service.confirm_reservation(
                            product_id=item.product_id,
                            store_id=order.store_id,
                            quantity=item.quantity,
                        )
                elif status_update.status == OrderStatus.CANCELLED:
                    if order.status == OrderStatus.PENDING:
                        # Release the hold
                        for item in order.items:
                            await self.inventory_service.release_hold(
                                product_id=item.product_id,
                                store_id=order.store_id,
                                quantity=item.quantity,
                            )
                    elif order.status == OrderStatus.CONFIRMED:
                        # This would be a more complex "cancellation" that might
                        # involve releasing a reservation. For now, let's assume
                        # only PENDING orders can be cancelled.
                        raise ValidationException("Cannot cancel a CONFIRMED order directly. Process a return instead.")
                elif status_update.status == OrderStatus.SHIPPED:
                    if order.status != OrderStatus.CONFIRMED:
                        raise ValidationException("Order must be CONFIRMED to be SHIPPED.")
                    for item in order.items:
                        await self.inventory_service.fulfill_order(
                            product_id=item.product_id,
                            store_id=order.store_id,
                            quantity=item.quantity,
                        )

                order.status = status_update.status
                await session.commit()
                await session.refresh(order)
                return OrderSchema.model_validate(order)

    @handle_service_errors("creating multi-cart order")
    async def create_multi_cart_order(
        self, user_id: str, checkout_data: MultiCartCheckoutSchema
    ) -> CheckoutResponseSchema:
        """Create order from multiple carts with exact pricing, store splitting, and delivery charges"""
        async with AsyncSessionLocal() as session:
            # Get user tier for pricing
            from src.database.models.user import User
            user_query = select(User).where(User.firebase_uid == user_id)
            user_result = await session.execute(user_query)
            user = user_result.scalar_one_or_none()
            user_tier_id = user.tier_id if user else None

            # Get delivery address if needed
            delivery_address = None
            if checkout_data.location.mode == "delivery":
                address_query = select(Address).where(
                    and_(Address.id == checkout_data.location.id, Address.user_id == user_id)
                )
                address_result = await session.execute(address_query)
                delivery_address = address_result.scalar_one_or_none()
                if not delivery_address:
                    raise ValidationException(f"Address {checkout_data.location.id} not found or not owned by user")

            # Validate pickup store if needed
            pickup_store = None
            if checkout_data.location.mode == "pickup":
                store_query = select(Store).where(
                    and_(Store.id == checkout_data.location.id, Store.is_active == True)
                )
                store_result = await session.execute(store_query)
                pickup_store = store_result.scalar_one_or_none()
                if not pickup_store:
                    raise ValidationException(f"Store {checkout_data.location.id} not found or inactive")

            # Get all cart items and prepare for bulk pricing
            all_cart_items = []
            product_data_for_pricing = []
            cart_item_mapping = {}  # Map cart_id -> items

            for cart_id in checkout_data.cart_ids:
                # Verify cart access and get items
                await CartService._check_cart_access(session, user_id, cart_id)

                cart_query = select(Cart).where(
                    and_(Cart.id == cart_id, Cart.status == CartStatus.ACTIVE)
                ).options(selectinload(Cart.items))
                cart_result = await session.execute(cart_query)
                cart = cart_result.scalar_one_or_none()

                if not cart:
                    raise ValidationException(f"Cart {cart_id} not found or not available for checkout")

                cart_item_mapping[cart_id] = {"cart": cart, "items": []}

                for item in cart.items:
                    # Get product with categories for pricing
                    product_query = select(Product).where(Product.id == item.product_id)
                    product_result = await session.execute(product_query)
                    product = product_result.scalar_one_or_none()

                    if not product:
                        raise ValidationException(f"Product {item.product_id} not found")

                    # Prepare for bulk pricing calculation
                    product_data_for_pricing.append({
                        "id": str(product.id),
                        "price": float(product.base_price),
                        "quantity": item.quantity,
                        "category_ids": []  # TODO: Get actual category IDs
                    })

                    all_cart_items.append({
                        "cart_id": cart_id,
                        "cart_item": item,
                        "product": product
                    })

            # Calculate exact pricing using bulk pricing service
            pricing_results = await self.pricing_service.calculate_bulk_product_pricing(
                product_data_for_pricing, user_tier_id
            )

            # Build cart groups with exact pricing
            cart_groups = []
            total_amount = Decimal('0.00')

            cart_item_index = 0
            for cart_id, cart_data in cart_item_mapping.items():
                cart = cart_data["cart"]
                cart_total = Decimal('0.00')
                cart_items = []

                # Process each item in this cart
                for item in cart.items:
                    # Get corresponding pricing result
                    pricing_result = pricing_results[cart_item_index]

                    unit_price = Decimal(str(pricing_result.final_price))
                    item_total = unit_price * item.quantity
                    cart_total += item_total

                    cart_items.append({
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                        "unit_price": float(unit_price),
                        "total_price": float(item_total)
                    })
                    cart_item_index += 1

                cart_groups.append(CartGroupSchema(
                    cart_id=cart.id,
                    cart_name=cart.name,
                    items=cart_items,
                    cart_total=float(cart_total)
                ))
                total_amount += cart_total

            # Determine store assignment and calculate delivery charges
            delivery_charge = Decimal('0.00')
            store_assignments = []

            if checkout_data.location.mode == "pickup":
                # All items go to pickup store
                if not pickup_store:
                    raise ValidationException("Pickup store not found")

                store_assignments = [{
                    "store_id": pickup_store.id,
                    "store_name": pickup_store.name,
                    "store_lat": pickup_store.latitude,
                    "store_lng": pickup_store.longitude,
                    "delivery_lat": None,
                    "delivery_lng": None,
                    "cart_groups": cart_groups,
                    "store_total": float(total_amount)
                }]
            else:
                # For delivery, assign all to first active store (simplified)
                # In production, this would use smart store selection
                store_query = select(Store).where(Store.is_active == True).limit(1)
                store_result = await session.execute(store_query)
                delivery_store = store_result.scalar_one_or_none()

                if not delivery_store:
                    raise ValidationException("No active stores available for delivery")

                store_assignments = [{
                    "store_id": delivery_store.id,
                    "store_name": delivery_store.name,
                    "store_lat": delivery_store.latitude,
                    "store_lng": delivery_store.longitude,
                    "delivery_lat": delivery_address.latitude if delivery_address else 0.0,
                    "delivery_lng": delivery_address.longitude if delivery_address else 0.0,
                    "cart_groups": cart_groups,
                    "store_total": float(total_amount)
                }]

                # Calculate delivery charges
                delivery_charge = self.calculate_delivery_charge(store_assignments)

            # Add delivery charge to total
            final_total = total_amount + delivery_charge

            # Create order with main store
            main_store_id = store_assignments[0]["store_id"]
            new_order = Order(
                user_id=user_id,
                store_id=main_store_id,
                total_amount=final_total,
                status=OrderStatus.PENDING
            )
            session.add(new_order)
            await session.flush()

            # Create order items grouped by cart and place inventory holds
            placed_holds = []  # Track holds for error rollback
            try:
                for cart_group in cart_groups:
                    for item in cart_group.items:
                        order_item = OrderItem(
                            order_id=new_order.id,
                            source_cart_id=cart_group.cart_id,
                            product_id=item["product_id"],
                            quantity=item["quantity"],
                            unit_price=Decimal(str(item["unit_price"])),
                            total_price=Decimal(str(item["total_price"]))
                        )
                        session.add(order_item)

                        # Place inventory hold for this item (PENDING order)
                        await self.inventory_service.place_hold(
                            product_id=item["product_id"],
                            store_id=main_store_id,
                            quantity=item["quantity"]
                        )

                        # Track successful hold for potential rollback
                        placed_holds.append({
                            "product_id": item["product_id"],
                            "store_id": main_store_id,
                            "quantity": item["quantity"]
                        })

                # Update cart statuses to ordered
                from datetime import datetime
                for cart_id in checkout_data.cart_ids:
                    await session.execute(
                        update(Cart).where(Cart.id == cart_id).values(
                            status=CartStatus.ORDERED,
                            ordered_at=datetime.now()
                        )
                    )

                await session.commit()
                await session.refresh(new_order)

            except Exception as e:
                # If anything fails, release all placed holds
                for hold in placed_holds:
                    try:
                        await self.inventory_service.release_hold(
                            product_id=hold["product_id"],
                            store_id=hold["store_id"],
                            quantity=hold["quantity"]
                        )
                    except Exception:
                        # Log but don't fail the rollback
                        pass
                await session.rollback()
                raise e

            # Initiate payment process
            payment_result = await self.payment_service.initiate_payment(
                order_id=new_order.id,
                total_amount=final_total,
                user_id=user_id,
                payment_method="card"
            )

            return CheckoutResponseSchema(
                order_id=new_order.id,
                total_amount=float(new_order.total_amount),
                status=new_order.status,
                cart_groups=cart_groups,
                created_at=new_order.created_at,
                payment_url=payment_result["payment_url"],
                payment_reference=payment_result["payment_reference"],
                payment_expires_at=payment_result["expires_at"]
            )

    @handle_service_errors("processing payment callback")
    async def process_payment_callback(self, callback_data: Dict) -> Dict[str, Any]:
        """Process payment gateway callback and update order status"""

        # Process callback through payment service
        callback_result = await self.payment_service.process_payment_callback(callback_data)

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

            return {
                "status": "success",
                "order_id": order_id,
                "order_status": updated_order.status,
                "payment_reference": callback_result["payment_reference"],
                "transaction_id": callback_result["transaction_id"]
            }
        else:
            # Payment failed - cancel order and release holds
            update_schema = UpdateOrderSchema(status=OrderStatus.CANCELLED)
            updated_order = await self.update_order_status(order_id, update_schema)

            return {
                "status": "failed",
                "order_id": order_id,
                "order_status": updated_order.status,
                "payment_reference": callback_result["payment_reference"]
            }
