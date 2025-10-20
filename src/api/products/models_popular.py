from typing import List, Optional

from pydantic import BaseModel, Field

from src.config.constants import (
    POPULARITY_DEFAULT_LIMIT,
    POPULARITY_MAX_LIMIT,
    POPULARITY_MIN_INTERACTIONS,
    PopularityMode,
)


class PopularityMetricsSchema(BaseModel):
    """Popularity metrics for a product"""

    view_count: int = Field(..., description="Number of views")
    cart_add_count: int = Field(..., description="Number of times added to cart")
    order_count: int = Field(..., description="Number of times ordered")
    search_count: int = Field(..., description="Number of search clicks")
    popularity_score: float = Field(..., description="Overall popularity score")
    trending_score: float = Field(..., description="Trending score (time-decayed)")
    last_interaction: Optional[str] = Field(
        None, description="Last interaction timestamp (ISO format)"
    )


class PopularProductsQuerySchema(BaseModel):
    """Query parameters for popular products endpoint"""

    mode: PopularityMode = Field(
        default=PopularityMode.TRENDING,
        description="Popularity ranking mode",
    )
    limit: int = Field(
        default=POPULARITY_DEFAULT_LIMIT,
        ge=1,
        le=POPULARITY_MAX_LIMIT,
        description=f"Maximum number of products (1-{POPULARITY_MAX_LIMIT})",
    )
    time_window_days: Optional[int] = Field(
        None,
        ge=1,
        le=365,
        description="Limit to products popular in last N days (1-365)",
    )
    category_ids: Optional[List[int]] = Field(
        None, description="Filter by category IDs"
    )
    min_interactions: int = Field(
        default=POPULARITY_MIN_INTERACTIONS,
        ge=1,
        description="Minimum interactions required",
    )
    include_pricing: bool = Field(
        default=True, description="Include pricing information"
    )
    include_categories: bool = Field(
        default=False, description="Include category information"
    )
    include_tags: bool = Field(default=False, description="Include tag information")
    include_inventory: bool = Field(
        default=True, description="Include inventory information"
    )
    include_popularity_metrics: bool = Field(
        default=True, description="Include popularity metrics in response"
    )
    # Store/location filters (for inventory)
    store_ids: Optional[List[int]] = Field(
        None, description="Store IDs for inventory lookup"
    )
    latitude: Optional[float] = Field(
        None, ge=-90, le=90, description="Latitude for nearby stores"
    )
    longitude: Optional[float] = Field(
        None, ge=-180, le=180, description="Longitude for nearby stores"
    )


class PopularProductSchema(BaseModel):
    """
    Product with popularity metrics.
    Extends base product schema with popularity data.
    """

    # Core product fields (same as EnhancedProductSchema)
    id: int
    name: str
    ref: Optional[str] = None
    description: Optional[str] = None
    base_price: float
    brand: Optional[str] = None
    image_urls: List[str] = []

    # Optional fields based on include flags
    pricing: Optional[dict] = None
    categories: Optional[List[dict]] = None
    tags: Optional[List[dict]] = None
    inventory: Optional[List[dict]] = None

    # Popularity metrics (if include_popularity_metrics=True)
    popularity_metrics: Optional[PopularityMetricsSchema] = None


class PopularProductsResponseSchema(BaseModel):
    """Response for popular products endpoint"""

    products: List[dict] = Field(default_factory=list, description="Popular products")
    total_results: int = Field(..., description="Total number of products returned")
    mode: str = Field(..., description="Popularity mode used")
    time_window_days: Optional[int] = Field(
        None, description="Time window applied (days)"
    )
    filters_applied: dict = Field(
        default_factory=dict, description="Filters that were applied"
    )
