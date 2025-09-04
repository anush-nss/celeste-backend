from datetime import datetime
from typing import Optional, List, Dict, Any
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


class PricingInfoSchema(BaseModel):
    base_price: float = Field(..., description="Original product base price")
    final_price: float = Field(..., description="Final price after discounts")
    discount_applied: float = Field(
        default=0, description="Total discount amount applied"
    )
    discount_percentage: float = Field(
        default=0, description="Discount percentage applied"
    )
    applied_price_lists: List[str] = Field(
        default=[], description="IDs of price lists that contributed to the discount"
    )


class InventoryInfoSchema(BaseModel):
    """Future inventory information placeholder"""

    in_stock: Optional[bool] = Field(None, description="Whether product is in stock")
    quantity_available: Optional[int] = Field(None, description="Available quantity")
    reserved_quantity: Optional[int] = Field(None, description="Reserved quantity")
    reorder_level: Optional[int] = Field(
        None, description="Minimum stock level for reordering"
    )


class EnhancedProductSchema(BaseModel):
    """Enhanced product schema with pricing and inventory information"""

    id: Optional[str] = None
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    price: float = Field(..., ge=0, description="Base price of the product")
    unit: str
    categoryId: str
    imageUrl: Optional[HttpUrl] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    # Enhanced fields
    pricing: Optional[PricingInfoSchema] = Field(
        None, description="Pricing information with applied discounts"
    )
    inventory: Optional[InventoryInfoSchema] = Field(
        None, description="Inventory information (future expansion)"
    )


class ProductQuerySchema(BaseModel):
    limit: Optional[int] = Field(
        default=20, le=100, description="Number of products to return (max 100)"
    )
    cursor: Optional[str] = Field(
        None, description="Cursor for pagination (product ID to start from)"
    )
    include_pricing: Optional[bool] = Field(
        default=True, description="Whether to include pricing calculations"
    )
    categoryId: Optional[str] = None
    minPrice: Optional[float] = None
    maxPrice: Optional[float] = None
    only_discounted: Optional[bool] = Field(
        default=False, description="Return only products with discounts applied"
    )


class PaginatedProductsResponse(BaseModel):
    """Response model for paginated product listings"""

    products: List[EnhancedProductSchema]
    pagination: Dict[str, Any] = Field(
        ...,
        description="Pagination metadata",
        examples=[
            {
                "current_cursor": "product_id_123",
                "next_cursor": "product_id_456",
                "has_more": True,
                "total_returned": 20,
            }
        ],
    )
