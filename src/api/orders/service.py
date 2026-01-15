import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import update
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.api.interactions.service import InteractionService
from src.api.inventory.service import InventoryService
from src.api.orders.models import (
    CreateOrderSchema,
    OrderItemSchema,
    OrderSchema,
    UpdateOrderSchema,
)
from src.api.orders.services.payment_service import PaymentService
from src.api.orders.services.store_selection_service import StoreSelectionService
from src.api.pricing.service import PricingService
from src.api.products.cache import products_cache
from src.api.products.service import ProductService
from src.api.stores.service import StoreService
from src.api.users.services.address_service import UserAddressService


from src.api.users.checkout_models import LocationSchema, StoreFulfillmentResponse
from src.config.constants import (
    CartStatus,
    FulfillmentMode,
    OrderStatus,
    DELIVERY_PRODUCT_ODOO_ID,
    DeliveryOption,
)
from src.database.connection import AsyncSessionLocal
from src.database.models.cart import Cart
from src.database.models.order import Order, OrderItem
from src.database.models.product import Product
from src.database.models.user import User
from src.database.models.rider import RiderProfile
from src.integrations.odoo.order_sync import OdooOrderSync
from src.shared.error_handler import ErrorHandler, handle_service_errors
from src.shared.exceptions import ResourceNotFoundException, ValidationException


class OrderService:
    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.interaction_service = InteractionService()
        self.inventory_service = InventoryService()
        self.pricing_service = PricingService()
        self.payment_service = PaymentService()
        self.store_selection_service = StoreSelectionService()
        self.products_cache = products_cache
        self.product_service = ProductService()
        self.store_service = StoreService()
        self.address_service = UserAddressService()

    @handle_service_errors("creating single store order")
    async def create_single_store_order(
        self,
        user_id: str,
        store_fulfillment: StoreFulfillmentResponse,
        location: LocationSchema,
        cart_ids: List[int],
        platform: Optional[str] = None,
        delivery_option: Optional[DeliveryOption] = None,
    ) -> OrderSchema:
        """Creates a single order for a specific store's fulfillment."""
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # 1. Determine fulfillment mode and address/store IDs
                if location.mode == FulfillmentMode.PICKUP.value:
                    fulfillment_mode = FulfillmentMode.PICKUP.value
                    address_id = None
                    store_id = location.store_id
                else:  # delivery
                    fulfillment_mode = FulfillmentMode.DELIVERY.value
                    address_id = location.address_id
                    store_id = store_fulfillment.store_id

                # 2. Create main Order record
                new_order = Order(
                    user_id=user_id,
                    store_id=store_id,
                    address_id=address_id,
                    total_amount=Decimal(str(store_fulfillment.total)),
                    delivery_charge=Decimal(str(store_fulfillment.delivery_cost)),
                    fulfillment_mode=fulfillment_mode,
                    delivery_service_level=location.delivery_service_level,
                    platform=platform,
                    delivery_option=delivery_option,
                    status=OrderStatus.PENDING.value,
                )
                session.add(new_order)
                await session.flush()

                # 3. Create OrderItem records
                order_items_to_create = []
                holds_to_place = []

                for item in store_fulfillment.items:
                    order_items_to_create.append(
                        OrderItem(
                            order_id=new_order.id,
                            product_id=item.product.id,
                            store_id=store_id,
                            quantity=item.quantity,
                            unit_price=Decimal(str(item.final_price)),
                            total_price=Decimal(str(item.total_price)),
                            source_cart_id=item.source_cart_id,
                        )
                    )
                    holds_to_place.append(
                        {
                            "product_id": item.product.id,
                            "store_id": store_id,
                            "quantity": item.quantity,
                        }
                    )

                session.add_all(order_items_to_create)

                # 4. Place inventory holds
                await self.inventory_service.place_holds_bulk(holds_to_place, session)

                # 5. Update cart statuses
                await session.execute(
                    update(Cart)
                    .where(Cart.id.in_(cart_ids))
                    .values(
                        status=CartStatus.ORDERED,
                        ordered_at=datetime.now(timezone.utc),
                    )
                )

                # Refresh and load items
                await session.refresh(new_order)

                # Re-query with eager loading of items
                result = await session.execute(
                    select(Order)
                    .options(
                        selectinload(Order.items),
                        selectinload(Order.payment_transaction),
                    )
                    .filter(Order.id == new_order.id)
                )
                order_with_items = result.scalar_one()

            # Use existing enrichment method to properly convert to schema
            enriched_orders = await self._enrich_orders_with_products_and_stores(
                [order_with_items],
                include_products=True,
                include_stores=True,
                include_addresses=False,
            )
            return enriched_orders[0]

    def calculate_flat_delivery_charge(
        self,
        store_deliveries: List[Dict],
        delivery_address: Optional[Dict] = None,
        order_details: Optional[Dict] = None,
        service_level: str = "standard",
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
            service_level: The requested delivery service level.

        Returns:
            Decimal: Flat delivery charge
        """
        base_flat_rate = Decimal("300.00")
        service_level_multipliers = {
            "priority": Decimal("1.5"),
            "premium": Decimal("1.2"),
            "standard": Decimal("1.0"),
        }
        multiplier = service_level_multipliers.get(service_level, Decimal("1.0"))

        # For now, return fixed rate multiplied by service level
        return base_flat_rate * multiplier

    def calculate_delivery_charge(
        self,
        store_deliveries: List[Dict],
        is_nearby_store: bool = True,
        total_amount: Optional[Decimal] = None,
        items_count: Optional[int] = None,
        service_level: str = "standard",
    ) -> Decimal:
        """
        Calculate delivery charge based on stores and their distances.

        Args:
            store_deliveries: List of dict with keys: 'store_id', 'store_name', 'store_lat', 'store_lng',
                             'delivery_lat', 'delivery_lng', 'items', 'store_total'
            is_nearby_store: Whether delivery is from nearby stores or default fallback stores
            total_amount: Total order amount (for future flat rate calculations)
            items_count: Number of items in order (for future flat rate calculations)
            service_level: The requested delivery service level.

        Returns:
            Decimal: Total delivery charge
        """
        if not store_deliveries:
            return Decimal("0.00")

        # Define service level multipliers
        service_level_multipliers = {
            "priority": Decimal("1.5"),
            "premium": Decimal("1.2"),
            "standard": Decimal("1.0"),
        }
        multiplier = service_level_multipliers.get(service_level, Decimal("1.0"))

        # Use flat rate for non-nearby stores
        if not is_nearby_store:
            delivery_address = None
            if store_deliveries and "delivery_lat" in store_deliveries[0]:
                delivery_address = {
                    "latitude": store_deliveries[0].get("delivery_lat"),
                    "longitude": store_deliveries[0].get("delivery_lng"),
                }

            order_details = {}
            if total_amount is not None:
                order_details["total_amount"] = total_amount
            if items_count is not None:
                order_details["items_count"] = items_count

            return self.calculate_flat_delivery_charge(
                store_deliveries, delivery_address, order_details, service_level
            )

        # For nearby stores: calculate based on distance using Haversine formula
        base_charge = Decimal("50.00")
        rate_per_km = Decimal("15.00")

        max_distance = Decimal("0.00")

        for delivery in store_deliveries:
            store_lat = delivery["store_lat"]
            store_lng = delivery["store_lng"]
            delivery_lat = delivery["delivery_lat"]
            delivery_lng = delivery["delivery_lng"]

            lat1, lng1 = math.radians(store_lat), math.radians(store_lng)
            lat2, lng2 = math.radians(delivery_lat), math.radians(delivery_lng)

            dlat = lat2 - lat1
            dlng = lng2 - lng1
            a = (
                math.sin(dlat / 2) ** 2
                + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
            )
            c = 2 * math.asin(math.sqrt(a))
            distance_km = Decimal(str(6371 * c))

            max_distance = max(max_distance, distance_km)

        # Calculate total charge: (base + (max_distance * rate)) * multiplier
        total_charge = (base_charge + (max_distance * rate_per_km)) * multiplier

        return total_charge.quantize(Decimal("0.01"))

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

    async def _enrich_orders_with_products_and_stores(
        self,
        orders: List[Order],
        include_products: bool = True,
        include_stores: bool = True,
        include_addresses: bool = True,
    ) -> List[OrderSchema]:
        """
        Enrich orders with full product, store, and address details using bulk queries.

        Efficiently fetches data in single queries to avoid N+1.
        Each type of data can be optionally excluded for performance.

        Args:
            orders: List of Order models to enrich
            include_products: Fetch and populate full product details
            include_stores: Fetch and populate full store details
            include_addresses: Fetch and populate full address details

        Returns:
            List of enriched OrderSchema objects
        """
        if not orders:
            return []

        # Collect all unique product IDs, store IDs, and address IDs
        all_product_ids = set()
        all_store_ids = set()
        all_address_ids = set()

        for order in orders:
            if include_stores:
                all_store_ids.add(order.store_id)
            if include_addresses and order.address_id:
                all_address_ids.add(order.address_id)
            if include_products:
                for item in order.items:
                    if item.product_id != DELIVERY_PRODUCT_ODOO_ID:
                        all_product_ids.add(item.product_id)

        # Fetch all products in a single bulk query (reuses products module)
        products_map = {}
        if include_products and all_product_ids:
            products_list = (
                await self.product_service.query_service.get_products_by_ids(
                    product_ids=list(all_product_ids),
                    customer_tier=None,  # No tier-specific pricing for order history
                    include_pricing=False,  # Order already has final prices
                    include_categories=False,
                    include_tags=False,
                    include_inventory=False,
                )
            )
            products_map = {p.id: p.model_dump(mode="json") for p in products_list}

        # Fetch all stores in a single bulk query (reuses stores module)
        stores_map = {}
        if include_stores and all_store_ids:
            async with AsyncSessionLocal() as session:
                stores = await self.store_service.get_stores_by_ids(
                    session, list(all_store_ids)
                )
                # Convert Store models to dicts inside session to avoid lazy loading issues
                # Access all attributes we need while session is active
                stores_map = {
                    s.id: {
                        "id": s.id,
                        "name": s.name,
                        "address": s.address,
                        "latitude": s.latitude,
                        "longitude": s.longitude,
                        "phone": s.phone,
                        "email": s.email,
                        "is_active": s.is_active,
                        "created_at": s.created_at.isoformat()
                        if s.created_at
                        else None,
                        "updated_at": s.updated_at.isoformat()
                        if s.updated_at
                        else None,
                    }
                    for s in stores
                }

        # Fetch all addresses in a single bulk query (reuses users module)
        addresses_map = {}
        if include_addresses and all_address_ids:
            addresses = await self.address_service.get_addresses_by_ids(
                list(all_address_ids)
            )
            addresses_map = {a.id: a.model_dump(mode="json") for a in addresses}

        # Build enriched order schemas
        order_schemas = []
        for order in orders:
            # Filter out delivery product from items
            filtered_items = []
            for item in order.items:
                if item.product_id != DELIVERY_PRODUCT_ODOO_ID:
                    item_dict = {
                        "id": item.id,
                        "order_id": item.order_id,
                        "source_cart_id": item.source_cart_id,
                        "product_id": item.product_id,
                        "store_id": item.store_id,
                        "quantity": item.quantity,
                        "unit_price": float(item.unit_price),
                        "total_price": float(item.total_price),
                        "created_at": item.created_at,
                        "product": products_map.get(item.product_id),  # Attach product
                    }
                    filtered_items.append(OrderItemSchema.model_validate(item_dict))

            # Build order dict with store and address attached
            order_dict = {
                "id": order.id,
                "user_id": order.user_id,
                "store_id": order.store_id,
                "address_id": order.address_id,
                "total_amount": float(order.total_amount),
                "delivery_charge": float(order.delivery_charge),
                "fulfillment_mode": order.fulfillment_mode,
                "delivery_service_level": order.delivery_service_level,
                "platform": order.platform,
                "status": order.status,
                "payment_reference": order.payment_transaction.payment_reference
                if order.payment_transaction
                else None,
                "transaction_id": order.payment_transaction.transaction_id
                if order.payment_transaction
                else None,
                "created_at": order.created_at,
                "updated_at": order.updated_at,
                "items": filtered_items,
                "store": stores_map.get(order.store_id),  # Attach store
                "address": addresses_map.get(order.address_id)
                if order.address_id
                else None,  # Attach address
            }
            order_schemas.append(OrderSchema.model_validate(order_dict))

        return order_schemas

    @handle_service_errors("retrieving orders")
    async def get_all_orders(
        self,
        user_id: Optional[str] = None,
        rider_id: Optional[int] = None,
        cart_ids: Optional[List[int]] = None,
        status: Optional[List[str]] = None,
        include_products: bool = False,
        include_stores: bool = False,
        include_addresses: bool = False,
    ) -> List[OrderSchema]:
        async with AsyncSessionLocal() as session:
            query = (
                select(Order)
                .options(
                    selectinload(Order.items), selectinload(Order.payment_transaction)
                )
                .distinct()
                .order_by(Order.created_at.desc())
            )

            if cart_ids:
                query = query.join(Order.items).filter(
                    OrderItem.source_cart_id.in_(cart_ids)
                )

            if user_id:
                query = query.filter(Order.user_id == user_id)

            if rider_id:
                query = query.filter(Order.rider_id == rider_id)

            if status:
                query = query.filter(Order.status.in_(status))

            result = await session.execute(query)
            orders = list(result.scalars().unique().all())

            # Use enrichment method to populate products, stores, and addresses
            return await self._enrich_orders_with_products_and_stores(
                orders,
                include_products=include_products,
                include_stores=include_stores,
                include_addresses=include_addresses,
            )

    @handle_service_errors("retrieving paginated orders")
    async def get_orders_paginated(
        self,
        page: int = 1,
        limit: int = 20,
        user_id: Optional[str] = None,
        rider_id: Optional[int] = None,
        cart_ids: Optional[List[int]] = None,
        status: Optional[List[str]] = None,
        include_products: bool = False,
        include_stores: bool = False,
        include_addresses: bool = False,
    ) -> Dict[str, Any]:
        offset = (page - 1) * limit
        async with AsyncSessionLocal() as session:
            # Base query creation (similar to get_all_orders but we need count too)
            query = select(Order)

            # Apply Filters
            if cart_ids:
                query = query.join(Order.items).filter(
                    OrderItem.source_cart_id.in_(cart_ids)
                )

            if user_id:
                query = query.filter(Order.user_id == user_id)

            if rider_id:
                query = query.filter(Order.rider_id == rider_id)

            if status:
                query = query.filter(Order.status.in_(status))

            # Count query (efficient count)
            # We clone the query for count before adding eager loads and ordering
            from sqlalchemy import func

            count_query = select(func.count()).select_from(query.subquery())
            total_result = await session.execute(count_query)
            total_count = total_result.scalar() or 0

            # Add eager loads and ordering for data query
            query = (
                query.options(
                    selectinload(Order.items), selectinload(Order.payment_transaction)
                )
                .distinct()
                .order_by(Order.created_at.desc())
                .limit(limit)
                .offset(offset)
            )

            result = await session.execute(query)
            orders = list(result.scalars().unique().all())

            # Enrich
            enriched_orders = await self._enrich_orders_with_products_and_stores(
                orders,
                include_products=include_products,
                include_stores=include_stores,
                include_addresses=include_addresses,
            )

            return {
                "orders": enriched_orders,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total_results": total_count,
                    "page": page,
                },
            }

    @handle_service_errors("retrieving order")
    async def get_order_by_id(
        self,
        order_id: int,
        include_products: bool = True,
        include_stores: bool = True,
        include_addresses: bool = True,
    ) -> OrderSchema | None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Order)
                .options(
                    selectinload(Order.items), selectinload(Order.payment_transaction)
                )
                .filter(Order.id == order_id)
            )
            order = result.scalars().first()
            if not order:
                return None

            # Use enrichment method to populate products, stores, and addresses
            enriched_orders = await self._enrich_orders_with_products_and_stores(
                [order],
                include_products=include_products,
                include_stores=include_stores,
                include_addresses=include_addresses,
            )
            return enriched_orders[0] if enriched_orders else None

    @handle_service_errors("creating order")
    async def create_order(
        self,
        order_data: CreateOrderSchema,
        user_id: str,
        platform: Optional[str] = None,
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
                    platform=platform,
                    delivery_option=order_data.delivery_option,
                    items=order_items_to_create,
                )
                session.add(new_order)
                await session.flush()

                # Re-query with eager loading of items
                result = await session.execute(
                    select(Order)
                    .options(
                        selectinload(Order.items),
                        selectinload(Order.payment_transaction),
                    )
                    .filter(Order.id == new_order.id)
                )
                order_with_items = result.scalar_one()

            # Use existing enrichment method to properly convert to schema
            enriched_orders = await self._enrich_orders_with_products_and_stores(
                [order_with_items],
                include_products=True,
                include_stores=True,
                include_addresses=False,
            )
            return enriched_orders[0]

    @handle_service_errors("updating order status")
    async def update_order_status(
        self,
        order_id: int,
        status_update: UpdateOrderSchema,
        current_user: Optional[Dict] = None,
    ) -> OrderSchema:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                result = await session.execute(
                    select(Order)
                    .options(
                        selectinload(Order.items).selectinload(OrderItem.product),
                        selectinload(Order.store),
                        selectinload(Order.rider),
                    )
                    .filter(Order.id == order_id)
                )
                order = result.scalars().first()

                if not order:
                    raise ResourceNotFoundException(
                        f"Order with ID {order_id} not found."
                    )

                # Get status values as strings for comparison
                current_status = order.status
                new_status = (
                    status_update.status.value
                    if isinstance(status_update.status, OrderStatus)
                    else status_update.status
                )

                # Role-based validation
                if current_user and current_user.get("role") == "rider":
                    # 1. Verify Assignment
                    # We need to fetch the rider profile for this user
                    rider_stmt = select(RiderProfile).where(
                        RiderProfile.user_id == current_user.get("uid")
                    )
                    rider_result = await session.execute(rider_stmt)
                    rider_profile = rider_result.scalar_one_or_none()

                    if not rider_profile or order.rider_id != rider_profile.id:
                        # Use ForbiddenException if available, else ValidationException
                        raise ValidationException(
                            "You can only update status for orders assigned to you."
                        )

                    # 2. Verify Valid Transitions for Riders
                    # Allowed: PACKED -> SHIPPED -> DELIVERED
                    allowed_transitions = {
                        OrderStatus.PACKED.value: [OrderStatus.SHIPPED.value],
                        OrderStatus.SHIPPED.value: [OrderStatus.DELIVERED.value],
                    }

                    allowed_next_statuses = allowed_transitions.get(current_status, [])
                    if new_status not in allowed_next_statuses:
                        raise ValidationException(
                            f"Riders cannot transition order from {current_status} to {new_status}. "
                            f"Allowed transitions: {allowed_transitions}"
                        )

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
                        raise ValidationException("Order must be PACKED to be SHIPPED.")
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
                    if current_status not in [
                        OrderStatus.PACKED.value,
                        OrderStatus.SHIPPED.value,
                    ]:
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
                    elif current_status in [
                        OrderStatus.CONFIRMED.value,
                        OrderStatus.PROCESSING.value,
                        OrderStatus.PACKED.value,
                    ]:
                        # Cannot cancel orders that are confirmed or being prepared
                        raise ValidationException(
                            "Cannot cancel a CONFIRMED, PROCESSING, or PACKED order. Please contact support."
                        )

                order.status = (
                    status_update.status.value
                    if isinstance(status_update.status, OrderStatus)
                    else status_update.status
                )
                # Note: session.begin() context manager auto-commits on exit
                await session.flush()  # Ensure changes are persisted

                # Re-query with eager loading of items
                result = await session.execute(
                    select(Order)
                    .options(
                        selectinload(Order.items),
                        selectinload(Order.payment_transaction),
                    )
                    .filter(Order.id == order.id)
                )
                order_with_items = result.scalar_one()

            # Use existing enrichment method to properly convert to schema
            enriched_orders = await self._enrich_orders_with_products_and_stores(
                [order_with_items],
                include_products=True,
                include_stores=True,
                include_addresses=True,
            )
            return enriched_orders[0]

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

        cart_ids = callback_result.get("cart_ids")
        payment_status = callback_result["status"]

        if not cart_ids:
            return {"status": "error", "message": "Cart IDs not found in callback"}

        if payment_status == "success":
            # Update order statuses to CONFIRMED
            # We need to find the orders associated with these carts
            async with AsyncSessionLocal() as session:
                stmt = (
                    select(Order)
                    .join(Order.items)
                    .where(OrderItem.source_cart_id.in_(cart_ids))
                    .distinct()
                )
                result = await session.execute(stmt)
                orders = result.scalars().all()

            # Update each order status
            # We call update_order_status one by one to trigger side effects (inventory)
            for order in orders:
                if order.status == OrderStatus.PENDING.value:
                    try:
                        await self.update_order_status(
                            order.id, UpdateOrderSchema(status=OrderStatus.CONFIRMED)
                        )
                        self._error_handler.logger.info(
                            f"Order {order.id} confirmed via payment callback"
                        )

                        # Logically, we might want to trigger Odoo sync here or in update_order_status
                        if background_tasks:
                            background_tasks.add_task(
                                self._background_odoo_sync, order.id
                            )

                    except Exception as e:
                        self._error_handler.logger.error(
                            f"Failed to confirm order {order.id} in callback: {e}"
                        )
                        # We don't fail the entire callback if one order fails,
                        # but we should log it.

        return callback_result

    @handle_service_errors("assigning rider to order")
    async def assign_rider(self, order_id: int, rider_id: int) -> OrderSchema:
        """Assign a rider to a PACKED order"""
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # 1. Verify Rider exists
                rider_stmt = select(RiderProfile).where(RiderProfile.id == rider_id)
                rider_result = await session.execute(rider_stmt)
                rider = rider_result.scalar_one_or_none()
                if not rider:
                    raise ResourceNotFoundException(
                        f"Rider with ID {rider_id} not found"
                    )

                # 2. Verify Order exists and is PACKED
                order_stmt = (
                    select(Order)
                    .options(
                        selectinload(Order.items).selectinload(OrderItem.product),
                        selectinload(Order.store),
                        selectinload(Order.payment_transaction),
                        selectinload(Order.rider),
                    )
                    .where(Order.id == order_id)
                )
                order_result = await session.execute(order_stmt)
                order = order_result.scalar_one_or_none()

                if not order:
                    raise ResourceNotFoundException(
                        f"Order with ID {order_id} not found"
                    )

                if order.status != OrderStatus.PACKED.value:
                    raise ValidationException(
                        f"Order must be in PACKED state to assign a rider. Current status: {order.status}"
                    )

                # 3. Assign Rider
                order.rider_id = rider_id
                await session.flush()

                # Re-query to ensure everything is loaded correctly for the return schema
                # This avoids "greenlet_spawn" issues with accessing relationships on a potentially stale object
                order_stmt = (
                    select(Order)
                    .options(
                        selectinload(Order.items).selectinload(OrderItem.product),
                        selectinload(Order.store),
                        selectinload(Order.payment_transaction),
                        selectinload(Order.rider),
                    )
                    .where(Order.id == order_id)
                )
                order_result = await session.execute(order_stmt)
                order = order_result.scalar_one()

            # Enrich
            enriched_orders = await self._enrich_orders_with_products_and_stores(
                [order],
                include_products=True,
                include_stores=True,
                include_addresses=True,
            )
            return enriched_orders[0]

    @handle_service_errors("unassigning rider from order")
    async def unassign_rider(self, order_id: int) -> dict:
        """Remove rider assignment from a PACKED order"""
        async with AsyncSessionLocal() as session:
            async with session.begin():
                # Verify Order exists and is PACKED
                stmt = select(Order).where(Order.id == order_id)
                result = await session.execute(stmt)
                order = result.scalar_one_or_none()

                if not order:
                    raise ResourceNotFoundException(
                        f"Order with ID {order_id} not found"
                    )

                if order.status != OrderStatus.PACKED.value:
                    raise ValidationException(
                        f"Order must be in PACKED state to unassign a rider. Current status: {order.status}"
                    )

                order.rider_id = None
                await session.flush()
        return {"message": "Rider assignment removed successfully"}
