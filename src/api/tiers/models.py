from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# Enums for validation
class BenefitType(str, Enum):
    ORDER_DISCOUNT = "order_discount"
    DELIVERY_DISCOUNT = "delivery_discount"


class DiscountType(str, Enum):
    FLAT = "flat"
    PERCENTAGE = "percentage"


# Benefit Schema (now a separate entity with many-to-many relationship to tiers)
class BenefitSchema(BaseModel):
    id: Optional[int] = None
    benefit_type: BenefitType  # order_discount or delivery_discount
    discount_type: DiscountType  # flat or percentage
    discount_value: float  # required
    max_discount_amount: Optional[float] = None  # used for percentage discounts
    min_order_value: float = 0.0  # minimum order value required
    min_items: int = 0  # minimum items required
    is_active: bool = True
    created_at: Optional[datetime] = None


class CreateBenefitSchema(BaseModel):
    benefit_type: BenefitType
    discount_type: DiscountType
    discount_value: float
    max_discount_amount: Optional[float] = None
    min_order_value: float = 0.0
    min_items: int = 0
    is_active: bool = True


class UpdateBenefitSchema(BaseModel):
    benefit_type: Optional[BenefitType] = None
    discount_type: Optional[DiscountType] = None
    discount_value: Optional[float] = None
    max_discount_amount: Optional[float] = None
    min_order_value: Optional[float] = None
    min_items: Optional[int] = None
    is_active: Optional[bool] = None


# Price List Schemas
class PriceListSchema(BaseModel):
    id: Optional[int] = None
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    priority: int = 0
    valid_from: datetime
    valid_until: Optional[datetime] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PriceListLineSchema(BaseModel):
    id: Optional[int] = None
    price_list_id: Optional[int] = None
    product_id: Optional[int] = None
    category_id: Optional[int] = None
    discount_type: DiscountType
    discount_value: float
    max_discount_amount: Optional[float] = None
    min_quantity: int = 1
    min_order_amount: Optional[float] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# Updated Tier Schema
class TierSchema(BaseModel):
    id: Optional[int] = None
    name: str = Field(..., min_length=1, description="Tier name")
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True

    # Requirements
    min_total_spent: float = 0.0
    min_orders_count: int = 0
    min_monthly_spent: float = 0.0
    min_monthly_orders: int = 0

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Related data
    benefits: List[BenefitSchema] = Field(default_factory=list)
    price_lists: List[PriceListSchema] = Field(default_factory=list)


class CreateTierSchema(BaseModel):
    name: str = Field(..., min_length=1, description="Tier name")
    description: Optional[str] = None
    sort_order: int = 0
    is_active: bool = True

    # Requirements
    min_total_spent: float = 0.0
    min_orders_count: int = 0
    min_monthly_spent: float = 0.0
    min_monthly_orders: int = 0

    # Benefit IDs to associate with the tier
    benefits: List[int] = Field(
        default_factory=list,
        description="List of benefit IDs to associate with this tier",
    )
    # Price list IDs to associate with the tier
    price_lists: List[int] = Field(
        default_factory=list,
        description="List of price list IDs to associate with this tier",
    )


class UpdateTierSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None

    # Requirements
    min_total_spent: Optional[float] = None
    min_orders_count: Optional[int] = None
    min_monthly_spent: Optional[float] = None
    min_monthly_orders: Optional[int] = None

    # Benefit IDs to associate with the tier
    benefits: List[int] = Field(
        default_factory=list,
        description="List of benefit IDs to associate with this tier",
    )
    # Price list IDs to associate with the tier
    price_lists: List[int] = Field(
        default_factory=list,
        description="List of price list IDs to associate with this tier",
    )


# User tier progress and evaluation schemas
class UserTierProgressSchema(BaseModel):
    current_tier_id: int
    current_tier_name: str
    next_tier_id: Optional[int] = None
    next_tier_name: Optional[str] = None
    progress: dict = Field(..., description="Progress towards next tier")
    benefits: List[BenefitSchema] = Field(..., description="Current tier benefits")


class UserTierInfoSchema(BaseModel):
    user_id: str
    current_tier_id: int
    tier_info: TierSchema
    progress: UserTierProgressSchema
    statistics: dict = Field(..., description="User statistics for tier calculation")


class TierEvaluationSchema(BaseModel):
    user_id: str
    total_orders: int
    lifetime_value: float
    monthly_orders: int
    current_tier_id: int
    eligible_tier_ids: List[int]
    recommended_tier_id: int
    tier_changed: bool = False
