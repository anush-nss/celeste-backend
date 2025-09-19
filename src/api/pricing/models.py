from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum

# Use enums directly in models since we're not using the old constants
class DiscountType(str, Enum):
    PERCENTAGE = "percentage"
    FLAT = "flat" 
    FIXED_PRICE = "fixed_price"


class PriceListSchema(BaseModel):
    id: Optional[int] = None
    name: str = Field(..., min_length=1, description="Price list name")
    description: Optional[str] = None
    priority: int = Field(default=0, description="Priority order (higher = more priority)")
    valid_from: datetime = Field(..., description="When this price list becomes valid")
    valid_until: Optional[datetime] = Field(None, description="When this price list expires")
    is_active: bool = Field(default=True, description="Whether this price list is active")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CreatePriceListSchema(BaseModel):
    name: str = Field(..., min_length=1, description="Price list name")
    description: Optional[str] = None
    priority: int = Field(default=0, description="Priority order")
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: bool = Field(default=True, description="Whether this price list is active")


class UpdatePriceListSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    priority: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: Optional[bool] = None


class PriceListLineSchema(BaseModel):
    id: Optional[int] = None
    price_list_id: Optional[int] = None
    product_id: Optional[int] = Field(None, description="Specific product (null = all products)")
    category_id: Optional[int] = Field(None, description="Product category (null = all categories)")
    discount_type: DiscountType = Field(..., description="Type of discount")
    discount_value: float = Field(..., ge=0, description="Discount amount or percentage")
    max_discount_amount: Optional[float] = Field(None, description="Maximum discount cap for percentage discounts")
    min_quantity: int = Field(default=1, ge=1, description="Minimum quantity required")
    min_order_amount: Optional[float] = Field(None, description="Minimum order amount required")
    is_active: bool = Field(default=True, description="Whether this line is active")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CreatePriceListLineSchema(BaseModel):
    product_id: Optional[int] = Field(None, description="Specific product ID")
    category_id: Optional[int] = Field(None, description="Category ID")
    discount_type: DiscountType = Field(..., description="Type of discount")
    discount_value: float = Field(..., ge=0, description="Discount amount or percentage")
    max_discount_amount: Optional[float] = None
    min_quantity: int = Field(default=1, ge=1)
    min_order_amount: Optional[float] = None
    is_active: bool = Field(default=True)


class UpdatePriceListLineSchema(BaseModel):
    product_id: Optional[int] = None
    category_id: Optional[int] = None
    discount_type: Optional[DiscountType] = None
    discount_value: Optional[float] = Field(None, ge=0)
    max_discount_amount: Optional[float] = None
    min_quantity: Optional[int] = Field(None, ge=1)
    min_order_amount: Optional[float] = None
    is_active: Optional[bool] = None


class ProductPricingSchema(BaseModel):
    """Schema for individual product pricing calculation result"""
    product_id: int
    quantity: int
    base_price: float
    final_price: float
    total_price: float
    savings: float
    applied_discounts: List[dict] = Field(default_factory=list)


class TierPriceListAssignmentSchema(BaseModel):
    """Schema for assigning price lists to tiers"""
    tier_id: int
    price_list_id: int
