from typing import Annotated, List, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.auth.models import DecodedToken
from src.api.search.models import (
    SearchClickResponse,
    SearchClickSchema,
    SearchDropdownResponse,
    SearchFullResponse,
    SearchQuerySchema,
)
from src.api.search.service import SearchService
from src.config.constants import (
    SEARCH_DROPDOWN_LIMIT,
    SEARCH_FULL_DEFAULT_LIMIT,
    SEARCH_FULL_MAX_LIMIT,
    SearchMode,
)
from src.dependencies.auth import get_current_user, get_optional_user
from src.dependencies.tiers import get_user_tier
from src.shared.responses import success_response

search_router = APIRouter(prefix="/products/search", tags=["Search"])
search_service = SearchService()


@search_router.get(
    "",
    summary="Search products with as-you-type support",
    response_model=Union[SearchDropdownResponse, SearchFullResponse],
)
async def search_products(
    q: str = Query(
        ...,
        min_length=2,
        max_length=200,
        description="Search query (minimum 2 characters)",
    ),
    mode: SearchMode = Query(
        default=SearchMode.FULL,
        description="Search mode: 'dropdown' for as-you-type suggestions, 'full' for complete results",
    ),
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=SEARCH_FULL_MAX_LIMIT,
        description=f"Maximum results (default: {SEARCH_FULL_DEFAULT_LIMIT} for full, {SEARCH_DROPDOWN_LIMIT} for dropdown)",
    ),
    include_pricing: bool = Query(True, description="Include pricing information"),
    include_categories: bool = Query(False, description="Include category information"),
    include_tags: bool = Query(False, description="Include tag information"),
    include_inventory: bool = Query(True, description="Include inventory information"),
    category_ids: Optional[List[int]] = Query(None, description="Filter by category IDs"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price filter"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price filter"),
    latitude: Optional[float] = Query(
        None, ge=-90, le=90, description="User latitude for inventory lookup"
    ),
    longitude: Optional[float] = Query(
        None, ge=-180, le=180, description="User longitude for inventory lookup"
    ),
    current_user: Annotated[Optional[DecodedToken], Depends(get_optional_user)] = None,
    user_tier: Optional[int] = Depends(get_user_tier),
):
    """
    **Search products using hybrid semantic + keyword search.**

    ## Modes

    ### Dropdown Mode (`mode=dropdown`)
    - Fast as-you-type search for autocomplete
    - Returns search suggestions + top 5 products
    - Lightweight product data (id, name, image, price)
    - Optimized for real-time typing experience

    ### Full Mode (`mode=full`)
    - Comprehensive search results
    - Complete product data with pricing, categories, inventory
    - Supports all filters (price range, categories, etc.)
    - Default for main search page

    ## Search Algorithm

    Uses **hybrid search** combining:
    - **Semantic similarity** (70%): Understanding query intent using AI embeddings
    - **Keyword matching** (30%): Traditional full-text search

    ## Features

    - ✅ Real-time as-you-type suggestions
    - ✅ Search history and popular queries
    - ✅ Typo-tolerant semantic search
    - ✅ Category and price filtering
    - ✅ Location-based inventory
    - ✅ Tier-based pricing
    - ✅ Search analytics (for logged-in users)

    ## Examples

    ```
    # Dropdown search (as-you-type)
    GET /products/search?q=org&mode=dropdown

    # Full search with filters
    GET /products/search?q=organic+milk&mode=full&category_ids=1,2&min_price=5

    # Search with location for inventory
    GET /products/search?q=coffee&latitude=6.9271&longitude=79.8612
    ```
    """
    # Get user ID if authenticated
    user_id = current_user.uid if current_user else None

    # Get store IDs from location if provided
    store_ids = None
    if include_inventory and latitude and longitude:
        from src.api.stores.service import StoreService

        store_service = StoreService()
        store_ids, _ = await store_service.get_store_ids_by_location(latitude, longitude)

    # Perform search
    result = await search_service.search_products(
        query=q,
        mode=mode,
        limit=limit,
        user_id=user_id,
        customer_tier=user_tier,
        include_pricing=include_pricing,
        include_categories=include_categories,
        include_tags=include_tags,
        include_inventory=include_inventory,
        category_ids=category_ids,
        min_price=min_price,
        max_price=max_price,
        store_ids=store_ids,
        latitude=latitude,
        longitude=longitude,
    )

    return success_response(result)


@search_router.post(
    "/click",
    summary="Track search result click",
    response_model=SearchClickResponse,
    status_code=status.HTTP_200_OK,
)
async def track_search_click(
    click_data: SearchClickSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    """
    **Track when a user clicks a product from search results.**

    This endpoint helps improve:
    - Search result ranking
    - Personalized recommendations
    - Popular product identification
    - Search suggestion quality

    Call this endpoint when:
    - User clicks a product in search results
    - User selects a product from dropdown search

    **Requires authentication.**

    ## Request Body

    ```json
    {
        "query": "organic milk",
        "product_id": 123
    }
    ```

    ## Response

    ```json
    {
        "success": true,
        "data": {
            "success": true,
            "message": "Search click tracked successfully"
        }
    }
    ```
    """
    success = await search_service.track_search_click(
        user_id=current_user.uid,
        query=click_data.query,
        product_id=click_data.product_id,
    )

    if success:
        return success_response(
            {
                "success": True,
                "message": "Search click tracked successfully",
            }
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track search click",
        )
