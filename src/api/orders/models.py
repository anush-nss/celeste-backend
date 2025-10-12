from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.config.constants import FulfillmentMode, OrderStatus


class OrderItemSchema(BaseModel):
    id: int
    order_id: int
    source_cart_id: int
    product_id: int
    store_id: int
    quantity: int
    unit_price: float
    total_price: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderSchema(BaseModel):
    id: int
    user_id: str  # Changed from int to str to match Firebase UID
    store_id: int
    address_id: Optional[int] = Field(
        default=None, description="Delivery address ID (for delivery orders)"
    )
    total_amount: float
    delivery_charge: Optional[float] = Field(
        default=0.0, description="Delivery charge for the order"
    )
    fulfillment_mode: FulfillmentMode = Field(
        default=FulfillmentMode.PICKUP,
        description="Order fulfillment mode: pickup, delivery, or far_delivery",
    )
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
