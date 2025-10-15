"""
Pydantic models for the checkout process.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class LocationSchema(BaseModel):
    """Location details for checkout."""

    mode: str = Field(..., examples=["delivery", "pickup"])
    address_id: Optional[int] = None
    store_id: Optional[int] = None
    delivery_service_level: str = Field(
        default="standard", examples=["standard", "premium", "economy"]
    )


class CheckoutRequestSchema(BaseModel):
    """Request body for checkout preview and order creation."""

    cart_ids: List[int] = Field(..., min_length=1)
    split_order: bool = False
    location: LocationSchema


# Define a new base schema without the inventory_status field
class CheckoutItemSchema(BaseModel):
    product_id: int
    product_name: str
    quantity: int
    base_price: float
    final_price: float
    total_price: float
    savings_per_item: float
    total_savings: float
    discount_percentage: float
    applied_discounts: List[dict] = Field(default_factory=list)


class CheckoutCartItemPricingSchema(CheckoutItemSchema):
    """Cart item pricing schema with source cart ID."""

    source_cart_id: int


class StoreFulfillmentResponse(BaseModel):
    """Fulfillment details for a single store."""

    order_id: Optional[int] = None
    store_id: int
    store_name: str
    items: List[CheckoutCartItemPricingSchema]
    subtotal: float
    delivery_cost: float
    total: float


class CheckoutResponse(BaseModel):
    """Response for checkout preview and successful order creation."""

    fulfillable_stores: List[StoreFulfillmentResponse]
    overall_total: float
    unavailable_items: List[dict] = Field(default_factory=list)


class NonSplitErrorResponse(BaseModel):
    """Error response for non-split orders that cannot be fulfilled by a single store."""

    detail: str
    fulfillable_stores: List[StoreFulfillmentResponse]
    overall_total: float
