from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class CategoryQuerySchema(BaseModel):
    """Schema for category query parameters"""

    include_subcategories: Optional[bool] = Field(
        default=True, description="Whether to include subcategories in the response"
    )
    parent_only: Optional[bool] = Field(
        default=False,
        description="Get only parent categories (categories without a parent)",
    )
    parent_id: Optional[int] = Field(
        default=None, description="Get subcategories of a specific parent category ID"
    )
    subcategories_only: Optional[bool] = Field(
        default=False,
        description="Get only subcategories (categories that have a parent)",
    )

    model_config = ConfigDict(from_attributes=True)


class CategorySchema(BaseModel):
    id: Optional[int] = Field(None, examples=[10])
    name: str = Field(..., min_length=1, examples=["Beverages"])
    sort_order: int = Field(..., examples=[1])
    description: Optional[str] = Field(None, examples=["Soft drinks, juices, and more"])
    image_url: Optional[str] = Field(
        None, examples=["https://example.com/images/beverages.png"]
    )
    parent_category_id: Optional[int] = Field(None, examples=[1])
    subcategories: Optional[List["CategorySchema"]] = Field(None)

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 10,
                    "name": "Beverages",
                    "sort_order": 1,
                    "description": "Soft drinks, juices, and more",
                    "image_url": "https://example.com/images/beverages.png",
                    "parent_category_id": 1,
                    "subcategories": [],
                }
            ]
        },
    )


class CreateCategorySchema(BaseModel):
    id: Optional[int] = Field(
        None, description="Optional manual ID specification", examples=[11]
    )
    name: str = Field(..., min_length=1, examples=["Snacks"])
    description: Optional[str] = Field(
        None, examples=["Chips, cookies, and other snacks"]
    )
    image_url: Optional[str] = Field(
        None, examples=["https://example.com/images/snacks.png"]
    )
    parent_category_id: Optional[int] = Field(None, examples=[1])
    sort_order: int = Field(..., examples=[2])


class UpdateCategorySchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    parent_category_id: Optional[int] = None
    sort_order: Optional[int] = None
