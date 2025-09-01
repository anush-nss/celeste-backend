from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl

class ProductSchema(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    unit: str
    categoryId: str
    imageUrl: Optional[HttpUrl] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

class CreateProductSchema(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    unit: str
    categoryId: str
    imageUrl: Optional[HttpUrl] = None

class UpdateProductSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    unit: Optional[str] = None
    categoryId: Optional[str] = None
    imageUrl: Optional[HttpUrl] = None

class ProductQuerySchema(BaseModel):
    limit: Optional[int] = None
    offset: Optional[int] = None
    includeDiscounts: Optional[bool] = None
    categoryId: Optional[str] = None
    minPrice: Optional[float] = None
    maxPrice: Optional[float] = None
    isFeatured: Optional[bool] = None
