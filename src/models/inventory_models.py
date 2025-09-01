from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class InventorySchema(BaseModel):
    id: Optional[str] = None
    productId: str
    storeId: str
    stock: int = Field(..., ge=0)
    lastUpdated: Optional[datetime] = None

class CreateInventorySchema(BaseModel):
    productId: str
    storeId: str
    stock: int = Field(..., ge=0)

class UpdateInventorySchema(BaseModel):
    stock: int = Field(..., ge=0)
