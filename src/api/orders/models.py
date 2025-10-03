from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field

from src.config.constants import OrderStatus


class OrderItemSchema(BaseModel):
    id: int
    order_id: int
    source_cart_id: int
    product_id: int
    quantity: int
    unit_price: float
    total_price: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderSchema(BaseModel):
    id: int
    user_id: str  # Changed from int to str to match Firebase UID
    store_id: int
    total_amount: float
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemSchema]

    model_config = ConfigDict(from_attributes=True)


class CreateOrderItemSchema(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)


class CreateOrderSchema(BaseModel):
    store_id: int
    items: List[CreateOrderItemSchema]


class UpdateOrderSchema(BaseModel):
    status: OrderStatus
