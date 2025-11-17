from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from src.config.constants import PromotionType


class PromotionBase(BaseModel):
    is_active: Optional[bool] = Field(
        default=True, description="Whether the promotion is currently active."
    )
    promotion_type: PromotionType
    priority: Optional[int] = Field(
        default=1,
        description="Higher value means higher priority for random selection.",
        gt=0,
    )
    start_date: datetime
    end_date: datetime
    product_ids: Optional[List[int]] = Field(default=None)
    category_ids: Optional[List[int]] = Field(default=None)
    image_urls_web: Optional[List[str]] = Field(default=None)
    image_urls_mobile: Optional[List[str]] = Field(default=None)


class CreatePromotionSchema(PromotionBase):
    pass


class UpdatePromotionSchema(BaseModel):
    is_active: Optional[bool] = None
    promotion_type: Optional[PromotionType] = None
    priority: Optional[int] = Field(default=None, gt=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    product_ids: Optional[List[int]] = None
    category_ids: Optional[List[int]] = None
    image_urls_web: Optional[List[str]] = None
    image_urls_mobile: Optional[List[str]] = None


class PromotionSchema(PromotionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
