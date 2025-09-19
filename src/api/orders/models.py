from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from src.config.constants import OrderStatus


class OrderItemSchema(BaseModel):
    id: int
    product_id: int
    quantity: int
    price: float

    model_config = ConfigDict(from_attributes=True)


class OrderSchema(BaseModel):
    id: int
    user_id: int
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
