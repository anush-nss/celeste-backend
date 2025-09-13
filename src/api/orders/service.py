from typing import Optional
from src.shared.database import get_async_db, get_async_collection
from src.api.orders.models import OrderSchema, CreateOrderSchema, UpdateOrderSchema
from src.config.constants import OrderStatus
from src.shared.exceptions import ResourceNotFoundException, ValidationException, ConflictException
from src.shared.error_handler import ErrorHandler, handle_service_errors
from src.shared.performance_utils import async_timer


class OrderService:
    def __init__(self):
        self._error_handler = ErrorHandler(__name__)

    async def get_orders_collection(self):
        return await get_async_collection("orders")

    async def get_all_orders(self, user_id: Optional[str] = None) -> list[OrderSchema]:
        orders_ref = await self.get_orders_collection()
        if user_id:
            orders_ref = orders_ref.where("userId", "==", user_id)
        docs = orders_ref.stream()
        result = []
        for doc in docs:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                result.append(OrderSchema(id=doc.id, **doc_dict))
        return result

    @handle_service_errors("retrieving order by ID")
    @async_timer("get_order_by_id")
    async def get_order_by_id(self, order_id: str) -> OrderSchema | None:
        if not order_id or not order_id.strip():
            raise ValidationException(detail="Valid order ID is required")

        orders_collection = await self.get_orders_collection()
        doc = orders_collection.document(order_id.strip()).get()
        if doc.exists:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                return OrderSchema(id=doc.id, **doc_dict)
        return None

    @handle_service_errors("creating order")
    @async_timer("create_order")
    async def create_order(
        self, order_data: CreateOrderSchema, user_id: str
    ) -> OrderSchema:
        if not user_id or not user_id.strip():
            raise ValidationException(detail="Valid user ID is required")

        if not order_data.items or len(order_data.items) == 0:
            raise ValidationException(detail="Order must contain at least one item")

        if order_data.totalAmount <= 0:
            raise ValidationException(detail="Order total amount must be positive")

        # Validate order items
        for item in order_data.items:
            if not item.productId or not item.productId.strip():
                raise ValidationException(detail="All items must have valid product IDs")
            if item.quantity <= 0:
                raise ValidationException(detail="All items must have positive quantities")
            if item.price < 0:
                raise ValidationException(detail="Item prices cannot be negative")

        orders_collection = await self.get_orders_collection()
        doc_ref = orders_collection.document()
        order_dict = order_data.model_dump()
        order_dict["userId"] = user_id.strip()

        try:
            doc_ref.set(order_dict)
            created_order = doc_ref.get()
            created_dict = created_order.to_dict()
            if created_dict:  # Ensure created_dict is not None
                return OrderSchema(id=created_order.id, **created_dict)
            else:
                raise ValidationException(detail="Failed to create order - document not found after creation")
        except Exception as e:
            self._error_handler.logger.error(f"Failed to create order for user {user_id}: {str(e)}")
            raise ValidationException(detail="Failed to create order due to database error")

    @handle_service_errors("updating order")
    @async_timer("update_order")
    async def update_order(
        self, order_id: str, order_data: UpdateOrderSchema
    ) -> OrderSchema | None:
        if not order_id or not order_id.strip():
            raise ValidationException(detail="Valid order ID is required")

        orders_collection = await self.get_orders_collection()
        doc_ref = orders_collection.document(order_id.strip())

        doc = doc_ref.get()
        if not doc.exists:
            raise ResourceNotFoundException(detail=f"Order with ID {order_id} not found")

        order_dict = order_data.model_dump(exclude_unset=True)
        if not order_dict:  # No fields to update
            raise ValidationException(detail="At least one field must be provided for update")

        try:
            doc_ref.update(order_dict)
            updated_order = doc_ref.get()
            updated_dict = updated_order.to_dict()
            if updated_dict:  # Ensure updated_dict is not None
                return OrderSchema(id=updated_order.id, **updated_dict)
            return None
        except Exception as e:
            self._error_handler.logger.error(f"Failed to update order {order_id}: {str(e)}")
            raise ValidationException(detail="Failed to update order due to database error")

    async def delete_order(self, order_id: str) -> bool:
        orders_collection = await self.get_orders_collection()
        doc_ref = orders_collection.document(order_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True
