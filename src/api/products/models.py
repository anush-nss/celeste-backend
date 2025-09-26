from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


# New PostgreSQL schemas
class ProductTagSchema(BaseModel):
    id: int
    tag_type: str                     # 'dietary', 'analytics', etc.
    name: str
    slug: str
    description: Optional[str] = None
    value: Optional[str] = None       # from product_tags table

    model_config = ConfigDict(from_attributes=True)


class ProductSchema(BaseModel):
    id: Optional[int] = None
    ref: Optional[str] = Field(None, min_length=1, max_length=100, description="External reference/SKU")
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    brand: Optional[str] = Field(None, min_length=1)
    base_price: float = Field(..., ge=0)
    unit_measure: str
    image_urls: List[str] = []        # First image is primary
    ecommerce_category_id: Optional[int] = None
    ecommerce_subcategory_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Relationships (loaded when needed)
    categories: Optional[List[Dict[str, Any]]] = None  # Will be CategorySchema when imported
    product_tags: Optional[List[Dict[str, Any]]] = None  # Raw product_tags data
    
    model_config = ConfigDict(from_attributes=True)
    
    @property
    def primary_image_url(self) -> Optional[str]:
        """Get the primary (first) image URL"""
        return self.image_urls[0] if self.image_urls else None


class CreateProductSchema(BaseModel):
    id: Optional[int] = Field(None, description="Optional manual ID specification")
    ref: Optional[str] = Field(None, min_length=1, max_length=100, description="External reference/SKU")
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    brand: Optional[str] = Field(None, min_length=1)
    base_price: float = Field(..., ge=0)
    unit_measure: str
    image_urls: List[str] = []
    ecommerce_category_id: Optional[int] = None
    ecommerce_subcategory_id: Optional[int] = None
    category_ids: List[int] = []      # IDs of categories to assign
    tag_ids: List[int] = []           # IDs of tags to assign


class UpdateProductSchema(BaseModel):
    ref: Optional[str] = Field(None, min_length=1, max_length=100, description="External reference/SKU")
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    brand: Optional[str] = Field(None, min_length=1)
    base_price: Optional[float] = Field(None, ge=0)
    unit_measure: Optional[str] = None
    image_urls: Optional[List[str]] = None
    ecommerce_category_id: Optional[int] = None
    ecommerce_subcategory_id: Optional[int] = None
    category_ids: Optional[List[int]] = None
    tag_ids: Optional[List[int]] = None


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
    """Inventory information for a specific store"""

    store_id: int = Field(..., description="Store ID")
    in_stock: bool = Field(..., description="Whether product is in stock")
    quantity_available: int = Field(..., description="Available quantity")
    quantity_on_hold: int = Field(..., description="Quantity on hold")
    quantity_reserved: int = Field(..., description="Reserved quantity")


class EnhancedProductSchema(BaseModel):
    """Enhanced product schema with pricing and inventory information"""

    id: Optional[int] = None
    ref: Optional[str] = Field(None, min_length=1, max_length=100, description="External reference/SKU")
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    brand: Optional[str] = Field(None, min_length=1)
    base_price: float = Field(..., ge=0, description="Base price of the product")
    unit_measure: str
    image_urls: List[str] = []        # First image is primary
    ecommerce_category_id: Optional[int] = None
    ecommerce_subcategory_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Relationships
    categories: Optional[List[Dict[str, Any]]] = None
    product_tags: Optional[List[Dict[str, Any]]] = None

    # Enhanced fields
    pricing: Optional[PricingInfoSchema] = Field(
        None, description="Pricing information with applied discounts"
    )
    inventory: Optional[List[InventoryInfoSchema]] = Field(
        None, description="Inventory information for multiple stores"
    )
    
    model_config = ConfigDict(from_attributes=True)


class ProductQuerySchema(BaseModel):
    limit: Optional[int] = Field(
        default=20, le=100, description="Number of products to return (max 100)"
    )
    cursor: Optional[int] = Field(
        None, description="Cursor for pagination (product ID to start from)"
    )
    store_id: Optional[List[int]] = Field(
        None, description="Store IDs for multi-store inventory data"
    )
    include_pricing: Optional[bool] = Field(
        default=True, description="Whether to include pricing calculations"
    )
    include_inventory: Optional[bool] = Field(
        default=True, description="Whether to include inventory information (requires store_id)"
    )
    include_categories: Optional[bool] = Field(
        default=False, description="Whether to include category information"
    )
    include_tags: Optional[bool] = Field(
        default=False, description="Whether to include tag information"
    )
    category_ids: Optional[List[int]] = None
    tags: Optional[List[str]] = None           # Filter by tags with flexible syntax
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    only_discounted: Optional[bool] = Field(
        default=False, description="Return only products with discounts applied"
    )
    # Location-based store finding parameters
    latitude: Optional[float] = Field(
        None, ge=-90, le=90, description="User latitude for location-based store finding"
    )
    longitude: Optional[float] = Field(
        None, ge=-180, le=180, description="User longitude for location-based store finding"
    )


class PaginatedProductsResponse(BaseModel):
    """Response model for paginated product listings"""

    products: List[EnhancedProductSchema]
    pagination: Dict[str, Any] = Field(
        ...,
        description="Pagination metadata",
        examples=[
            {
                "current_cursor": 123,
                "next_cursor": 456,
                "has_more": True,
                "total_returned": 20,
            }
        ],
    )
