from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from src.config.constants import PriceListType, DiscountType


class PriceListSchema(BaseModel):
    id: Optional[str] = None
    name: str = Field(
        ...,
        min_length=1,
        description="Price list name (e.g., 'VIP Discount', 'Bulk Pricing')",
    )
    priority: int = Field(
        ..., ge=1, description="Priority order (1 = highest priority)"
    )
    active: bool = Field(default=True, description="Whether this price list is active")
    valid_from: datetime = Field(..., description="When this price list becomes valid")
    valid_until: Optional[datetime] = Field(
        None, description="When this price list expires (null = never expires)"
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CreatePriceListSchema(BaseModel):
    name: str = Field(..., min_length=1, description="Price list name")
    priority: int = Field(
        ..., ge=1, description="Priority order (1 = highest priority)"
    )
    active: bool = Field(default=True, description="Whether this price list is active")
    valid_from: datetime = Field(..., description="When this price list becomes valid")
    valid_until: Optional[datetime] = Field(
        None, description="When this price list expires"
    )


class UpdatePriceListSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, description="Price list name")
    priority: Optional[int] = Field(None, ge=1, description="Priority order")
    active: Optional[bool] = Field(
        None, description="Whether this price list is active"
    )
    valid_from: Optional[datetime] = Field(
        None, description="When this price list becomes valid"
    )
    valid_until: Optional[datetime] = Field(
        None, description="When this price list expires"
    )


class PriceListLineSchema(BaseModel):
    id: Optional[str] = None
    price_list_id: str = Field(..., description="Reference to price list")
    type: PriceListType = Field(..., description="Type of price list line")
    product_id: Optional[str] = Field(
        None, description="Product ID (required if type='product')"
    )
    category_id: Optional[str] = Field(
        None, description="Category ID (required if type='category')"
    )
    discount_type: DiscountType = Field(..., description="Discount type")
    amount: float = Field(
        ..., ge=0, description="Discount amount (percentage or flat amount)"
    )
    min_product_qty: int = Field(
        default=1, ge=1, description="Minimum quantity required"
    )
    max_product_qty: Optional[int] = Field(
        None, ge=1, description="Maximum quantity allowed (null = no limit)"
    )
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CreatePriceListLineSchema(BaseModel):
    type: PriceListType = Field(..., description="Type of price list line")
    product_id: Optional[str] = Field(
        None, description="Product ID (required if type='product')"
    )
    category_id: Optional[str] = Field(
        None, description="Category ID (required if type='category')"
    )
    discount_type: DiscountType = Field(..., description="Discount type")
    amount: float = Field(..., ge=0, description="Discount amount")
    min_product_qty: int = Field(
        default=1, ge=1, description="Minimum quantity required"
    )
    max_product_qty: Optional[int] = Field(
        None, ge=1, description="Maximum quantity allowed"
    )

    def validate_type_fields(self):
        """Validate that required fields are provided based on type"""
        if self.type == PriceListType.PRODUCT and not self.product_id:
            raise ValueError("product_id is required when type is 'product'")
        if self.type == PriceListType.CATEGORY and not self.category_id:
            raise ValueError("category_id is required when type is 'category'")
        if self.type == PriceListType.ALL and (self.product_id or self.category_id):
            raise ValueError(
                "product_id and category_id must be null when type is 'all'"
            )


class UpdatePriceListLineSchema(BaseModel):
    type: Optional[PriceListType] = Field(None, description="Type of price list line")
    product_id: Optional[str] = Field(None, description="Product ID")
    category_id: Optional[str] = Field(None, description="Category ID")
    discount_type: Optional[DiscountType] = Field(None, description="Discount type")
    amount: Optional[float] = Field(None, ge=0, description="Discount amount")
    min_product_qty: Optional[int] = Field(
        None, ge=1, description="Minimum quantity required"
    )
    max_product_qty: Optional[int] = Field(
        None, ge=1, description="Maximum quantity allowed"
    )
