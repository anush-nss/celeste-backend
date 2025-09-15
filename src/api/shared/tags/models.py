from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime


class TagSchema(BaseModel):
    id: int
    tag_type: str
    name: str
    slug: str
    description: Optional[str] = None
    is_active: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateTagSchema(BaseModel):
    tag_type: str = Field(..., min_length=1, max_length=50, description="Type of tag (product, store, etc.)")
    name: str = Field(..., min_length=1, max_length=100, description="Display name of the tag")
    slug: Optional[str] = Field(None, min_length=1, max_length=100, description="URL-friendly identifier")
    description: Optional[str] = Field(None, max_length=1000, description="Optional description")


class UpdateTagSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Display name")
    description: Optional[str] = Field(None, max_length=1000, description="Description")
    is_active: Optional[bool] = None


class EntityTagSchema(BaseModel):
    """Base schema for entity-tag associations (product_tags, store_tags, etc.)"""
    id: int
    tag_type: str
    name: str
    slug: str
    description: Optional[str] = None
    value: Optional[str] = Field(None, description="Additional tag value from association table")

    model_config = {"from_attributes": True}