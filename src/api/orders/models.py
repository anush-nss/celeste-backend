from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from src.config.constants import FulfillmentMode, OrderStatus, Platform


class OrderItemSchema(BaseModel):
    id: int = Field(..., examples=[101])
    order_id: int = Field(..., examples=[1])
    source_cart_id: int = Field(..., examples=[2])
    product_id: int = Field(..., examples=[6288])
    store_id: int = Field(..., examples=[1])
    quantity: int = Field(..., examples=[2])
    unit_price: float = Field(..., examples=[1150.0])
    total_price: float = Field(..., examples=[2300.0])
    created_at: datetime
    product: Optional[Dict[str, Any]] = Field(
        default=None, description="Full product details (if populated)"
    )

    model_config = ConfigDict(from_attributes=True)


class OrderSchema(BaseModel):
    id: int = Field(..., examples=[1])
    payment_reference: Optional[str] = Field(
        None, description="Payment reference for this order"
    )
    transaction_id: Optional[str] = Field(
        None, description="External transaction ID from payment gateway"
    )
    user_id: str = Field(..., examples=["TZKU3C493fY2JH9Ftnsdpz5occN2"])
    store_id: int = Field(..., examples=[1])
    address_id: Optional[int] = Field(
        default=None,
        description="Delivery address ID (for delivery orders)",
        examples=[1],
    )
    total_amount: float = Field(..., examples=[2600.0])
    delivery_charge: Optional[float] = Field(
        default=0.0, description="Delivery charge for the order", examples=[300.0]
    )
    fulfillment_mode: FulfillmentMode = Field(
        default=FulfillmentMode.PICKUP,
        description="Order fulfillment mode: pickup, delivery, or far_delivery",
        examples=[FulfillmentMode.DELIVERY.value],
    )
    delivery_service_level: Optional[str] = Field(
        default="standard",
        description="Requested delivery service level (e.g., standard, priority, premium)",
        examples=["standard"],
    )
    platform: Optional[Platform] = Field(
        default=None,
        description="Platform from which the order originated (e.g., 'mobile', 'web')",
        examples=["web"],
    )
    status: OrderStatus = Field(..., examples=[OrderStatus.PENDING.value])
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemSchema]
    store: Optional[Dict[str, Any]] = Field(
        default=None, description="Full store details (if populated)"
    )
    address: Optional[Dict[str, Any]] = Field(
        default=None, description="Full delivery address details (if populated)"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "user_id": "TZKU3C493fY2JH9Ftnsdpz5occN2",
                    "store_id": 1,
                    "address_id": 1,
                    "total_amount": 2600.0,
                    "delivery_charge": 300.0,
                    "fulfillment_mode": "delivery",
                    "delivery_service_level": "standard",
                    "platform": "web",
                    "status": "pending",
                    "created_at": "2025-10-15T10:00:00Z",
                    "updated_at": "2025-10-15T10:00:00Z",
                    "items": [
                        {
                            "id": 101,
                            "order_id": 1,
                            "source_cart_id": 2,
                            "product_id": 6288,
                            "store_id": 1,
                            "quantity": 2,
                            "unit_price": 1150.0,
                            "total_price": 2300.0,
                            "created_at": "2025-10-15T10:00:00Z",
                        }
                    ],
                }
            ]
        },
    )


class CreateOrderItemSchema(BaseModel):
    product_id: int = Field(..., examples=[6288])
    quantity: int = Field(..., examples=[3])


class CreateOrderSchema(BaseModel):
    store_id: int = Field(..., examples=[1])
    items: List[CreateOrderItemSchema]
    platform: Optional[Platform] = Field(
        default=None,
        description="Platform from which the order originated (e.g., 'mobile', 'web')",
        examples=["web"],
    )


class UpdateOrderSchema(BaseModel):
    status: OrderStatus = Field(..., examples=[OrderStatus.CONFIRMED.value])


class PaymentCallbackSchema(BaseModel):
    payment_reference: str
    amount: float
    status_code: str
    transaction_id: str
    signature: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "payment_reference": "some-uuid-string",
                    "amount": 10650.0,
                    "status_code": "2",
                    "transaction_id": "txn_12345",
                    "signature": "some-signature-string",
                }
            ]
        }
    )


class PaginatedOrdersResponse(BaseModel):
    orders: List[OrderSchema]
    pagination: Dict[str, Any] = Field(
        ...,
        description="Pagination metadata",
        examples=[
            {
                "limit": 20,
                "offset": 0,
                "total_results": 100,
            }
        ],
    )
