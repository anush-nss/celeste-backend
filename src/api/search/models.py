from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from src.config.constants import (
    SEARCH_DROPDOWN_LIMIT,
    SEARCH_FULL_DEFAULT_LIMIT,
    SEARCH_FULL_MAX_LIMIT,
    SEARCH_MAX_QUERY_LENGTH,
    SEARCH_MIN_QUERY_LENGTH,
    SearchMode,
)


class SearchSuggestionSchema(BaseModel):
    """Search suggestion for autocomplete"""

    query: str = Field(..., description="Suggested search query")
    type: str = Field(..., description="Suggestion type: trending or popular")
    search_count: Optional[int] = Field(
        None, description="Number of times this query was searched"
    )


class DropdownProductSchema(BaseModel):
    """Lightweight product schema for dropdown results"""

    id: int
    name: str
    ref: Optional[str] = None
    image_url: Optional[str] = None
    base_price: float
    final_price: float


class SearchMetadataSchema(BaseModel):
    """Metadata about the search operation"""

    query: str = Field(..., description="The search query")
    search_time_ms: float = Field(..., description="Search execution time in milliseconds")
    mode: str = Field(..., description="Search mode: dropdown or full")
    method: Optional[str] = Field(None, description="Search method used: hybrid, semantic, keyword")
    filters_applied: Optional[dict] = Field(None, description="Filters that were applied")
    error: Optional[str] = Field(None, description="Error message if search failed")


class SearchDropdownResponse(BaseModel):
    """Response for dropdown search mode"""

    suggestions: List[SearchSuggestionSchema] = Field(
        default_factory=list, description="Search query suggestions"
    )
    products: List[DropdownProductSchema] = Field(
        default_factory=list, description="Top matching products"
    )
    total_results: int = Field(..., description="Total number of products returned")
    search_metadata: SearchMetadataSchema


class SearchFullResponse(BaseModel):
    """Response for full search mode"""

    products: List[dict] = Field(
        default_factory=list, description="Full product details"
    )
    total_results: int = Field(..., description="Total number of products returned")
    search_metadata: SearchMetadataSchema


class SearchQuerySchema(BaseModel):
    """Search query parameters"""

    q: str = Field(
        ...,
        min_length=SEARCH_MIN_QUERY_LENGTH,
        max_length=SEARCH_MAX_QUERY_LENGTH,
        description="Search query string",
    )
    mode: SearchMode = Field(
        default=SearchMode.FULL, description="Search mode: dropdown or full"
    )
    limit: Optional[int] = Field(
        None,
        ge=1,
        le=SEARCH_FULL_MAX_LIMIT,
        description=f"Maximum results (default: {SEARCH_FULL_DEFAULT_LIMIT} for full, {SEARCH_DROPDOWN_LIMIT} for dropdown)",
    )
    include_pricing: bool = Field(default=True, description="Include pricing information")
    include_categories: bool = Field(default=False, description="Include category information")
    include_tags: bool = Field(default=False, description="Include tag information")
    include_inventory: bool = Field(default=True, description="Include inventory information")
    category_ids: Optional[List[int]] = Field(None, description="Filter by category IDs")
    min_price: Optional[float] = Field(None, ge=0, description="Minimum price filter")
    max_price: Optional[float] = Field(None, ge=0, description="Maximum price filter")
    latitude: Optional[float] = Field(
        None, ge=-90, le=90, description="User latitude for inventory lookup"
    )
    longitude: Optional[float] = Field(
        None, ge=-180, le=180, description="User longitude for inventory lookup"
    )

    @field_validator("max_price")
    @classmethod
    def validate_price_range(cls, v, info):
        """Ensure max_price is greater than min_price if both provided"""
        if v is not None and info.data.get("min_price") is not None:
            if v < info.data["min_price"]:
                raise ValueError("max_price must be greater than min_price")
        return v


class SearchClickSchema(BaseModel):
    """Track search result click"""

    query: str = Field(..., description="Original search query")
    product_id: int = Field(..., description="Product ID that was clicked")


class SearchClickResponse(BaseModel):
    """Response after tracking search click"""

    success: bool
    message: str
