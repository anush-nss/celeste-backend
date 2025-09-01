from typing import Optional
from pydantic import BaseModel, Field, HttpUrl

class CategorySchema(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    imageUrl: Optional[HttpUrl] = None
    parentCategoryId: Optional[str] = None

class CreateCategorySchema(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    imageUrl: Optional[HttpUrl] = None
    parentCategoryId: Optional[str] = None

class UpdateCategorySchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    imageUrl: Optional[HttpUrl] = None
    parentCategoryId: Optional[str] = None
