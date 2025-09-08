from typing import Optional
from src.shared.database import get_async_db, get_async_collection
from src.api.orders.models import OrderSchema, CreateOrderSchema, UpdateOrderSchema
from src.config.constants import OrderStatus


class OrderService:
    def __init__(self):
        pass

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

    async def get_order_by_id(self, order_id: str) -> OrderSchema | None:
        orders_collection = await self.get_orders_collection()
        doc = orders_collection.document(order_id).get()
        if doc.exists:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                return OrderSchema(id=doc.id, **doc_dict)
        return None

    async def create_order(
        self, order_data: CreateOrderSchema, user_id: str
    ) -> OrderSchema:
        orders_collection = await self.get_orders_collection()
        doc_ref = orders_collection.document()
        order_dict = order_data.model_dump()
        order_dict["userId"] = user_id
        doc_ref.set(order_dict)
        created_order = doc_ref.get()
        created_dict = created_order.to_dict()
        if created_dict:  # Ensure created_dict is not None
            return OrderSchema(id=created_order.id, **created_dict)
        else:
            # Handle the case where the document doesn't exist after creation
            raise Exception("Failed to create order")

    async def update_order(
        self, order_id: str, order_data: UpdateOrderSchema
    ) -> OrderSchema | None:
        orders_collection = await self.get_orders_collection()
        doc_ref = orders_collection.document(order_id)
        if not doc_ref.get().exists:
            return None
        order_dict = order_data.model_dump(exclude_unset=True)
        doc_ref.update(order_dict)
        updated_order = doc_ref.get()
        updated_dict = updated_order.to_dict()
        if updated_dict:  # Ensure updated_dict is not None
            return OrderSchema(id=updated_order.id, **updated_dict)
        return None

    async def delete_order(self, order_id: str) -> bool:
        orders_collection = await self.get_orders_collection()
        doc_ref = orders_collection.document(order_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True
