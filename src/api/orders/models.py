from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from src.config.constants import OrderStatus


class OrderItemSchema(BaseModel):
    productId: str
    name: str
    price: float = Field(..., ge=0)
    quantity: int = Field(..., gt=0)


class OrderSchema(BaseModel):
    id: Optional[str] = None
    userId: str
    items: List[OrderItemSchema]
    totalAmount: float = Field(..., ge=0)
    discountApplied: Optional[str] = None
    promotionApplied: Optional[str] = None
    status: OrderStatus
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class CreateOrderSchema(BaseModel):
    items: List[OrderItemSchema]
    totalAmount: float = Field(..., ge=0)
    discountApplied: Optional[str] = None
    promotionApplied: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING


class UpdateOrderSchema(BaseModel):
    status: OrderStatus
