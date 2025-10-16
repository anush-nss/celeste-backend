from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# Enums for validation
class BenefitType(str, Enum):
    ORDER_DISCOUNT = "order_discount"
    DELIVERY_DISCOUNT = "delivery_discount"


class DiscountType(str, Enum):
    FLAT = "flat"
    PERCENTAGE = "percentage"


# Benefit Schema
class BenefitSchema(BaseModel):
    id: Optional[int] = Field(None, examples=[1])
    benefit_type: BenefitType = Field(..., examples=[BenefitType.ORDER_DISCOUNT])
    discount_type: DiscountType = Field(..., examples=[DiscountType.PERCENTAGE])
    discount_value: float = Field(..., examples=[10.0])
    max_discount_amount: Optional[float] = Field(None, examples=[500.0])
    min_order_value: float = Field(0.0, examples=[2000.0])
    min_items: int = Field(0, examples=[3])
    is_active: bool = Field(True)
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


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


# Price List Schemas (Skipping examples for now as they are complex)
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
    id: Optional[int] = Field(None, examples=[2])
    name: str = Field(..., min_length=1, description="Tier name", examples=["Gold"])
    description: Optional[str] = Field(
        None, examples=["Gold tier members get exclusive benefits"]
    )
    sort_order: int = Field(0, examples=[2])
    is_active: bool = Field(True)
    min_total_spent: float = Field(0.0, examples=[50000.0])
    min_orders_count: int = Field(0, examples=[10])
    min_monthly_spent: float = Field(0.0, examples=[10000.0])
    min_monthly_orders: int = Field(0, examples=[2])
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    benefits: List[BenefitSchema] = Field(default_factory=list)
    price_lists: List[PriceListSchema] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class CreateTierSchema(BaseModel):
    name: str = Field(..., min_length=1, description="Tier name", examples=["Platinum"])
    description: Optional[str] = Field(None, examples=["Top-level customer tier"])
    sort_order: int = Field(0, examples=[1])
    is_active: bool = Field(True)
    min_total_spent: float = Field(0.0, examples=[100000.0])
    min_orders_count: int = Field(0, examples=[25])
    min_monthly_spent: float = Field(0.0, examples=[20000.0])
    min_monthly_orders: int = Field(0, examples=[5])
    benefits: List[int] = Field(
        default_factory=list,
        description="List of benefit IDs to associate with this tier",
        examples=[[1, 2]],
    )
    price_lists: List[int] = Field(
        default_factory=list,
        description="List of price list IDs to associate with this tier",
        examples=[[101]],
    )


class UpdateTierSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    min_total_spent: Optional[float] = None
    min_orders_count: Optional[int] = None
    min_monthly_spent: Optional[float] = None
    min_monthly_orders: Optional[int] = None
    benefits: List[int] = Field(
        default_factory=list,
        description="List of benefit IDs to associate with this tier",
    )
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
