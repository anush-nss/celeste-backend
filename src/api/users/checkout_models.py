"""
Pydantic models for the checkout process.
"""

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# Define a new base schema without the inventory_status field
class CheckoutItemSchema(BaseModel):
    product_id: int = Field(..., examples=[6288])
    product_name: str = Field(
        ..., examples=["Matic Front Load Detergent Liquid 1L - Surf Excel"]
    )
    quantity: int = Field(..., examples=[2])
    base_price: float = Field(..., examples=[1150.0])
    final_price: float = Field(..., examples=[1150.0])
    total_price: float = Field(..., examples=[2300.0])
    savings_per_item: float = Field(..., examples=[0.0])
    total_savings: float = Field(..., examples=[0.0])
    discount_percentage: float = Field(..., examples=[0.0])
    applied_discounts: List[dict] = Field(default_factory=list, examples=[[]])


class CheckoutCartItemPricingSchema(CheckoutItemSchema):
    """Cart item pricing schema with source cart ID."""

    source_cart_id: int = Field(..., examples=[2])


class LocationSchema(BaseModel):
    """Location details for checkout."""

    mode: str = Field(..., examples=["delivery", "pickup", "far_delivery"])
    address_id: Optional[int] = Field(None, examples=[1])
    store_id: Optional[int] = Field(None, examples=[4])
    delivery_service_level: str = Field(
        default="standard", examples=["standard", "premium", "priority"]
    )


class CheckoutRequestSchema(BaseModel):
    """Request body for checkout preview and order creation."""

    cart_ids: List[int] = Field(..., min_length=1, examples=[[1, 2]])
    split_order: bool = Field(
        False,
        description="Whether to allow splitting the order across multiple stores.",
    )
    location: LocationSchema

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "cart_ids": [1, 2],
                    "split_order": True,
                    "location": {
                        "mode": "delivery",
                        "address_id": 1,
                        "delivery_service_level": "premium",
                    },
                }
            ]
        }
    )


class StoreFulfillmentResponse(BaseModel):
    """Fulfillment details for a single store."""

    order_id: Optional[int] = Field(None, examples=[101])
    store_id: int = Field(..., examples=[1])
    store_name: str = Field(..., examples=["Celeste Daily - Colombo 06"])
    items: List[CheckoutCartItemPricingSchema]
    subtotal: float = Field(..., examples=[10350.0])
    delivery_cost: float = Field(..., examples=[300.0])
    total: float = Field(..., examples=[10650.0])


class CheckoutResponse(BaseModel):
    """Response for checkout preview and successful order creation."""

    fulfillment_mode: str = Field(..., examples=["far_delivery"])
    fulfillable_stores: List[StoreFulfillmentResponse]
    overall_total: float = Field(..., examples=[10650.0])
    unavailable_items: List[dict] = Field(default_factory=list, examples=[[]])

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "fulfillment_mode": "far_delivery",
                    "fulfillable_stores": [
                        {
                            "order_id": 101,
                            "store_id": 1,
                            "store_name": "Celeste Daily - Colombo 06",
                            "items": [
                                {
                                    "product_id": 6288,
                                    "product_name": "Matic Front Load Detergent Liquid 1L - Surf Excel",
                                    "quantity": 9,
                                    "base_price": 1150.0,
                                    "final_price": 1150.0,
                                    "total_price": 10350.0,
                                    "savings_per_item": 0.0,
                                    "total_savings": 0.0,
                                    "discount_percentage": 0.0,
                                    "applied_discounts": [],
                                    "source_cart_id": 2,
                                }
                            ],
                            "subtotal": 10350.0,
                            "delivery_cost": 300.0,
                            "total": 10650.0,
                        }
                    ],
                    "overall_total": 10650.0,
                    "unavailable_items": [
                        {"product_id": 6285, "quantity": 59, "cart_id": 2}
                    ],
                }
            ]
        }
    )


class NonSplitErrorResponse(BaseModel):
    """Error response for non-split orders that cannot be fulfilled by a single store."""

    detail: str = Field(
        ...,
        examples=[
            "No single store can fulfill the entire order. Please review the options below or allow the order to be split."
        ],
    )
    fulfillment_mode: str = Field(..., examples=["delivery"])
    fulfillable_stores: List[StoreFulfillmentResponse]
    overall_total: float = Field(..., examples=[21300.0])
