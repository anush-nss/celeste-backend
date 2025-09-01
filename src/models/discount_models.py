from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from src.shared.constants import DiscountType

class DiscountSchema(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    type: DiscountType
    value: float = Field(..., ge=0)
    validFrom: datetime
    validTo: datetime
    applicableProducts: Optional[List[str]] = None
    applicableCategories: Optional[List[str]] = None

class CreateDiscountSchema(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    type: DiscountType
    value: float = Field(..., ge=0)
    validFrom: datetime
    validTo: datetime
    applicableProducts: Optional[List[str]] = None
    applicableCategories: Optional[List[str]] = None

class UpdateDiscountSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    type: Optional[DiscountType] = None
    value: Optional[float] = Field(None, ge=0)
    validFrom: Optional[datetime] = None
    validTo: Optional[datetime] = None
    applicableProducts: Optional[List[str]] = None
    applicableCategories: Optional[List[str]] = None

class DiscountQuerySchema(BaseModel):
    availableOnly: Optional[bool] = None
    populateReferences: Optional[bool] = None
