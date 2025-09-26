from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl, ConfigDict # Added ConfigDict


class CategoryQuerySchema(BaseModel):
    """Schema for category query parameters"""
    include_subcategories: Optional[bool] = Field(
        default=True,
        description="Whether to include subcategories in the response"
    )
    
    model_config = ConfigDict(from_attributes=True)


class CategorySchema(BaseModel):
    id: Optional[int] = None # Changed to int
    name: str = Field(..., min_length=1)
    sort_order: int # Changed from order
    description: Optional[str] = None
    image_url: Optional[str] = None # Changed from imageUrl and HttpUrl
    parent_category_id: Optional[int] = None # Changed from parentCategoryId and str

    subcategories: Optional[List["CategorySchema"]] = None # Added for nested representation

    model_config = ConfigDict(from_attributes=True) # Added for ORM mode


class CreateCategorySchema(BaseModel):
    id: Optional[int] = Field(None, description="Optional manual ID specification")
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    image_url: Optional[str] = None # Changed from imageUrl
    parent_category_id: Optional[int] = None # Changed from parentCategoryId
    sort_order: int # Changed from order


class UpdateCategorySchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None # Changed from imageUrl
    parent_category_id: Optional[int] = None # Changed from parentCategoryId
    sort_order: Optional[int] = None # Changed from order