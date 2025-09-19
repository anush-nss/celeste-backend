from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class InventorySchema(BaseModel):
    id: int
    product_id: int
    store_id: int
    quantity_available: int
    quantity_reserved: int
    quantity_on_hold: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateInventorySchema(BaseModel):
    product_id: int
    store_id: int
    quantity_available: int = Field(..., ge=0)
    quantity_reserved: int = Field(0, ge=0)
    quantity_on_hold: int = Field(0, ge=0)


class UpdateInventorySchema(BaseModel):
    quantity_available: Optional[int] = Field(None, ge=0)
    quantity_reserved: Optional[int] = Field(None, ge=0)
    quantity_on_hold: Optional[int] = Field(None, ge=0)


class AdjustInventorySchema(BaseModel):
    product_id: int
    store_id: int
    available_change: int = 0
    on_hold_change: int = 0
    reserved_change: int = 0
