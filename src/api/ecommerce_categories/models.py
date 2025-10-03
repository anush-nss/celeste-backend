from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EcommerceCategorySchema(BaseModel):
    id: Optional[int] = None
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    image_url: Optional[str] = None
    parent_category_id: Optional[int] = None

    subcategories: Optional[List["EcommerceCategorySchema"]] = None

    model_config = ConfigDict(from_attributes=True)


class CreateEcommerceCategorySchema(BaseModel):
    id: Optional[int] = Field(None, description="Optional manual ID specification")
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    image_url: Optional[str] = None
    parent_category_id: Optional[int] = None


class UpdateEcommerceCategorySchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    parent_category_id: Optional[int] = None
