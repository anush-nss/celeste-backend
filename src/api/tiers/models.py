from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from src.config.constants import CustomerTier


class TierRequirementsSchema(BaseModel):
    min_orders: int = Field(
        default=0, ge=0, description="Minimum number of orders required"
    )
    min_lifetime_value: float = Field(
        default=0.0, ge=0, description="Minimum lifetime value required"
    )
    min_monthly_orders: int = Field(
        default=0, ge=0, description="Minimum monthly orders required"
    )


class TierBenefitsSchema(BaseModel):
    price_list_ids: List[str] = Field(
        default_factory=list, description="Price list IDs available to this tier"
    )
    delivery_discount: float = Field(
        default=0.0, ge=0, le=100, description="Delivery discount percentage"
    )
    priority_support: bool = Field(
        default=False, description="Whether tier gets priority support"
    )
    early_access: bool = Field(
        default=False, description="Whether tier gets early access to products"
    )


class CustomerTierSchema(BaseModel):
    id: Optional[str] = None
    name: str = Field(
        ..., min_length=1, description="Tier name (e.g., 'Gold', 'Platinum')"
    )
    tier_code: CustomerTier = Field(..., description="Tier code")
    level: int = Field(
        ..., ge=1, description="Tier level (higher number = better tier)"
    )
    requirements: TierRequirementsSchema = Field(
        ..., description="Requirements to achieve this tier"
    )
    benefits: TierBenefitsSchema = Field(..., description="Benefits of this tier")
    icon_url: Optional[str] = Field(None, description="URL to tier icon")
    color: str = Field(default="#888888", description="Tier color (hex code)")
    active: bool = Field(default=True, description="Whether this tier is active")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CreateCustomerTierSchema(BaseModel):
    name: str = Field(..., min_length=1, description="Tier name")
    tier_code: CustomerTier = Field(..., description="Tier code")
    level: int = Field(..., ge=1, description="Tier level")
    requirements: TierRequirementsSchema = Field(
        ..., description="Requirements to achieve this tier"
    )
    benefits: TierBenefitsSchema = Field(..., description="Benefits of this tier")
    icon_url: Optional[str] = Field(None, description="URL to tier icon")
    color: str = Field(default="#888888", description="Tier color")
    active: bool = Field(default=True, description="Whether this tier is active")


class UpdateCustomerTierSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, description="Tier name")
    level: Optional[int] = Field(None, ge=1, description="Tier level")
    requirements: Optional[TierRequirementsSchema] = Field(
        None, description="Requirements to achieve this tier"
    )
    benefits: Optional[TierBenefitsSchema] = Field(
        None, description="Benefits of this tier"
    )
    icon_url: Optional[str] = Field(None, description="URL to tier icon")
    color: Optional[str] = Field(None, description="Tier color")
    active: Optional[bool] = Field(None, description="Whether this tier is active")


class UserTierProgressSchema(BaseModel):
    current_tier: CustomerTier
    current_tier_name: str
    next_tier: Optional[CustomerTier] = None
    next_tier_name: Optional[str] = None
    progress: dict = Field(..., description="Progress towards next tier")
    benefits: TierBenefitsSchema = Field(..., description="Current tier benefits")


class UserTierInfoSchema(BaseModel):
    user_id: str
    current_tier: CustomerTier
    tier_info: CustomerTierSchema
    progress: UserTierProgressSchema
    statistics: dict = Field(..., description="User statistics for tier calculation")


class TierEvaluationSchema(BaseModel):
    user_id: str
    total_orders: int
    lifetime_value: float
    monthly_orders: int
    current_tier: CustomerTier
    eligible_tiers: List[CustomerTier]
    recommended_tier: CustomerTier
    tier_changed: bool = False
