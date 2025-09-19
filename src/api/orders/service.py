from typing import List, Optional
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from src.database.connection import AsyncSessionLocal
from src.database.models.order import Order, OrderItem
from src.database.models.product import Product
from src.api.orders.models import OrderSchema, CreateOrderSchema, UpdateOrderSchema
from src.api.inventory.service import InventoryService
from src.config.constants import OrderStatus
from src.shared.exceptions import ResourceNotFoundException, ValidationException
from src.shared.error_handler import ErrorHandler, handle_service_errors
from decimal import Decimal


class OrderService:
    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.inventory_service = InventoryService()

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
