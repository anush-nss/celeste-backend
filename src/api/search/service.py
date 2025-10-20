import asyncio
import logging
from datetime import datetime
from typing import List, Optional

import numpy as np
from pgvector.sqlalchemy import Vector
from sentence_transformers import SentenceTransformer
from sqlalchemy import and_, desc, func, or_, text
from sqlalchemy.future import select

from src.api.products.models import EnhancedProductSchema
from src.api.products.service import ProductService
from src.config.constants import (
    MIN_SEARCH_COUNT_FOR_SUGGESTION,
    MIN_SUCCESS_RATE_FOR_SUGGESTION,
    SEARCH_DROPDOWN_LIMIT,
    SEARCH_FULL_DEFAULT_LIMIT,
    SEARCH_HYBRID_WEIGHT_SEMANTIC,
    SEARCH_HYBRID_WEIGHT_TFIDF,
    SEARCH_MIN_QUERY_LENGTH,
    SENTENCE_TRANSFORMER_MODEL,
    InteractionType,
    SearchMode,
)
from src.database.connection import AsyncSessionLocal
from src.database.models.product import Product
from src.database.models.product_interaction import ProductInteraction
from src.database.models.product_vector import ProductVector
from src.database.models.search_interaction import SearchInteraction
from src.database.models.search_suggestion import SearchSuggestion
from src.shared.error_handler import ErrorHandler


class SearchService:
    """
    Service for product search functionality.

    Implements hybrid search combining:
    - Semantic search (sentence transformers + vector similarity)
    - Keyword search (PostgreSQL full-text search)
    - Search tracking and analytics
    - Search suggestions
    """

    _instance: Optional['SearchService'] = None
    _model_loaded: bool = False

    def __new__(cls):
        """Singleton pattern to ensure only one instance with shared model"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if not hasattr(self, '_initialized'):
            self._error_handler = ErrorHandler(__name__)
            self._model: Optional[SentenceTransformer] = None
            self.product_service = ProductService()
            self.logger = logging.getLogger(__name__)
            self._initialized = True

    def _load_model(self):
        """Lazy load the sentence transformer model with memory optimization"""
        if self._model is None:
            self.logger.info(
                f"Loading sentence transformer model: {SENTENCE_TRANSFORMER_MODEL}"
            )
            # Load from local cache (pre-downloaded during container build)
            # local_files_only=True prevents any internet access to HuggingFace Hub
            self._model = SentenceTransformer(
                SENTENCE_TRANSFORMER_MODEL,
                device='cpu',  # Force CPU for consistency
                cache_folder=None,  # Use default cache
                local_files_only=True  # CRITICAL: Never contact HuggingFace API
            )
            SearchService._model_loaded = True
            self.logger.info("Model loaded successfully from local cache")
        return self._model

    def warmup(self):
        """
        Warm up the search service by pre-loading the model.
        Call this at application startup to avoid cold start delays.
        """
        if not SearchService._model_loaded:
            self.logger.info("Warming up search service...")
            self._load_model()
            # Test encode to ensure model is fully initialized
            self._model.encode("warmup query", convert_to_numpy=True)
            self.logger.info("Search service warmup complete!")
        else:
            self.logger.info("Search service already warmed up")

    async def search_products(
        self,
        query: str,
        mode: SearchMode = SearchMode.FULL,
        limit: Optional[int] = None,
        user_id: Optional[str] = None,
        customer_tier: Optional[int] = None,
        include_pricing: bool = True,
        include_categories: bool = False,
        include_tags: bool = False,
        include_inventory: bool = True,
        category_ids: Optional[List[int]] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        store_ids: Optional[List[int]] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> dict:
        """
        Search products using hybrid semantic + keyword search.

        Args:
            query: Search query string
            mode: 'dropdown' or 'full'
            limit: Max results to return
            user_id: Firebase UID (for tracking)
            customer_tier: User's tier for pricing
            include_pricing: Include pricing info
            include_categories: Include category info
            include_tags: Include tag info
            include_inventory: Include inventory info
            category_ids: Filter by categories
            min_price: Minimum price filter
            max_price: Maximum price filter
            store_ids: Store IDs for inventory
            latitude: User latitude for inventory
            longitude: User longitude for inventory

        Returns:
            dict with products and metadata
        """
        # Validate query
        query = query.strip()
        if len(query) < SEARCH_MIN_QUERY_LENGTH:
            return {
                "products": [],
                "suggestions": [],
                "total_results": 0,
                "search_metadata": {
                    "query": query,
                    "error": f"Query too short (minimum {SEARCH_MIN_QUERY_LENGTH} characters)",
                },
            }

        # Set default limit based on mode
        if limit is None:
            limit = (
                SEARCH_DROPDOWN_LIMIT
                if mode == SearchMode.DROPDOWN
                else SEARCH_FULL_DEFAULT_LIMIT
            )

        # Perform search
        start_time = datetime.now()

        if mode == SearchMode.DROPDOWN:
            # Dropdown mode: fast suggestions + top products
            result = await self._search_dropdown(
                query=query,
                limit=limit,
                user_id=user_id,
                customer_tier=customer_tier,
            )
        else:
            # Full search mode: comprehensive results
            result = await self._search_full(
                query=query,
                limit=limit,
                user_id=user_id,
                customer_tier=customer_tier,
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

        # Calculate search time
        search_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Track search interaction (async, don't wait)
        if user_id:
            asyncio.create_task(
                self._track_search_interaction(
                    user_id=user_id,
                    query=query,
                    mode=mode.value,
                    results_count=len(result.get("products", [])),
                    extra_data={
                        "search_time_ms": search_time_ms,
                        "filters": {
                            "category_ids": category_ids,
                            "min_price": min_price,
                            "max_price": max_price,
                        },
                    },
                )
            )

        # Add metadata
        result["search_metadata"] = {
            "query": query,
            "search_time_ms": round(search_time_ms, 2),
            "mode": mode.value,
        }

        return result

    async def _search_dropdown(
        self,
        query: str,
        limit: int,
        user_id: Optional[str] = None,
        customer_tier: Optional[int] = None,
    ) -> dict:
        """
        Fast dropdown search - suggestions + top products.

        Returns:
            dict with suggestions and products
        """
        # Get search suggestions
        suggestions = await self._get_search_suggestions(query, limit=3)

        # Get top matching products (lightweight)
        products = await self._search_hybrid(
            query=query,
            limit=limit,
            include_pricing=True,
            include_categories=False,
            include_tags=False,
            include_inventory=False,
            customer_tier=customer_tier,
        )

        # Convert to lightweight format for dropdown
        lightweight_products = [
            {
                "id": p.id,
                "name": p.name,
                "ref": p.ref,
                "image_url": p.image_urls[0] if p.image_urls else None,
                "base_price": float(p.base_price),
                "final_price": (
                    float(p.pricing.final_price)
                    if p.pricing
                    else float(p.base_price)
                ),
            }
            for p in products
        ]

        return {
            "suggestions": suggestions,
            "products": lightweight_products,
            "total_results": len(lightweight_products),
        }

    async def _search_full(
        self,
        query: str,
        limit: int,
        user_id: Optional[str] = None,
        customer_tier: Optional[int] = None,
        include_pricing: bool = True,
        include_categories: bool = False,
        include_tags: bool = False,
        include_inventory: bool = True,
        category_ids: Optional[List[int]] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        store_ids: Optional[List[int]] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> dict:
        """
        Full search with all filters and complete product data.

        Returns:
            dict with products and metadata
        """
        # Perform hybrid search
        products = await self._search_hybrid(
            query=query,
            limit=limit,
            include_pricing=include_pricing,
            include_categories=include_categories,
            include_tags=include_tags,
            include_inventory=include_inventory,
            customer_tier=customer_tier,
            category_ids=category_ids,
            min_price=min_price,
            max_price=max_price,
            store_ids=store_ids,
            latitude=latitude,
            longitude=longitude,
        )

        # Convert Pydantic models to dicts for JSON serialization
        # mode='json' handles datetime, Decimal, and other special types
        serialized_products = [p.model_dump(mode='json') for p in products]

        return {
            "products": serialized_products,
            "total_results": len(serialized_products),
        }

    async def _search_hybrid(
        self,
        query: str,
        limit: int,
        include_pricing: bool = True,
        include_categories: bool = False,
        include_tags: bool = False,
        include_inventory: bool = False,
        customer_tier: Optional[int] = None,
        category_ids: Optional[List[int]] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        store_ids: Optional[List[int]] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> List[EnhancedProductSchema]:
        """
        Hybrid search combining semantic similarity and keyword matching.

        Uses pgvector for fast cosine similarity search.
        """
        try:
            # Generate query embedding
            model = self._load_model()
            query_embedding = model.encode(query, convert_to_numpy=True)

            async with AsyncSessionLocal() as session:
                # Build hybrid search query
                # Using pgvector's cosine distance operator (<=>)
                # Note: Using CAST() instead of :: to avoid conflict with named parameters
                search_query = """
                WITH ranked_products AS (
                    SELECT
                        pv.product_id,
                        pv.vector_embedding <=> CAST(:query_vector AS vector) AS distance,
                        1 - (pv.vector_embedding <=> CAST(:query_vector AS vector)) AS similarity,
                        ts_rank(
                            to_tsvector('english', pv.text_content),
                            plainto_tsquery('english', :query)
                        ) AS keyword_rank
                    FROM product_vectors pv
                    WHERE pv.text_content IS NOT NULL
                )
                SELECT
                    p.id,
                    rp.similarity,
                    rp.keyword_rank,
                    (:semantic_weight * rp.similarity + :keyword_weight * rp.keyword_rank) AS combined_score
                FROM ranked_products rp
                JOIN products p ON p.id = rp.product_id
                WHERE rp.similarity > 0.1  -- Minimum similarity threshold
                   OR rp.keyword_rank > 0  -- Or has keyword match
                ORDER BY combined_score DESC
                LIMIT :search_limit
                """

                result = await session.execute(
                    text(search_query),
                    {
                        "query_vector": str(query_embedding.tolist()),  # Convert to string for CAST
                        "query": query,
                        "semantic_weight": SEARCH_HYBRID_WEIGHT_SEMANTIC,
                        "keyword_weight": SEARCH_HYBRID_WEIGHT_TFIDF,
                        "search_limit": limit * 2,  # Get more for filtering
                    },
                )
                rows = result.fetchall()

                if not rows:
                    return []

                # Extract product IDs
                product_ids = [row.id for row in rows]

                # Get full product data using existing ProductQueryService
                products = await self.product_service.query_service.get_products_by_ids(
                    product_ids=product_ids,
                    customer_tier=customer_tier,
                    store_ids=store_ids,
                    is_nearby_store=True,
                    include_pricing=include_pricing,
                    include_categories=include_categories,
                    include_tags=include_tags,
                    include_inventory=include_inventory,
                    latitude=latitude,
                    longitude=longitude,
                )

                # Apply additional filters
                if category_ids:
                    products = [
                        p
                        for p in products
                        if any(
                            cat.get("id") in category_ids
                            for cat in (p.categories or [])
                        )
                    ]

                if min_price is not None:
                    products = [
                        p
                        for p in products
                        if float(p.base_price) >= min_price
                    ]

                if max_price is not None:
                    products = [
                        p
                        for p in products
                        if float(p.base_price) <= max_price
                    ]

                # Maintain search ranking order
                product_order_map = {pid: idx for idx, pid in enumerate(product_ids)}
                products.sort(
                    key=lambda p: product_order_map.get(p.id, len(product_ids))
                )

                # Return up to limit
                return products[:limit]

        except Exception as e:
            self.logger.error(f"Error in hybrid search: {e}", exc_info=True)
            return []

    async def _get_search_suggestions(
        self, query: str, limit: int = 5
    ) -> List[dict]:
        """
        Get search suggestions based on query.

        Returns popular/trending queries that match the input.
        """
        try:
            async with AsyncSessionLocal() as session:
                # Search for matching suggestions
                search_query = (
                    select(SearchSuggestion)
                    .where(
                        and_(
                            SearchSuggestion.query.ilike(f"%{query}%"),
                            SearchSuggestion.search_count
                            >= MIN_SEARCH_COUNT_FOR_SUGGESTION,
                            SearchSuggestion.success_rate
                            >= MIN_SUCCESS_RATE_FOR_SUGGESTION,
                        )
                    )
                    .order_by(
                        desc(SearchSuggestion.is_trending),
                        desc(SearchSuggestion.search_count),
                    )
                    .limit(limit)
                )

                result = await session.execute(search_query)
                suggestions = result.scalars().all()

                return [
                    {
                        "query": s.query,
                        "type": "trending" if s.is_trending else "popular",
                        "search_count": s.search_count,
                    }
                    for s in suggestions
                ]

        except Exception as e:
            self.logger.error(f"Error getting search suggestions: {e}")
            return []

    async def _track_search_interaction(
        self,
        user_id: str,
        query: str,
        mode: str,
        results_count: int,
        extra_data: Optional[dict] = None,
    ):
        """
        Track search interaction for analytics and personalization.

        Args:
            user_id: Firebase UID
            query: Search query
            mode: Search mode (dropdown/full)
            results_count: Number of results returned
            extra_data: Additional context
        """
        try:
            async with AsyncSessionLocal() as session:
                interaction = SearchInteraction(
                    user_id=user_id,
                    query=query,
                    mode=mode,
                    results_count=results_count,
                    timestamp=datetime.now(),
                    extra_data=extra_data,
                )
                session.add(interaction)
                await session.commit()

                self.logger.debug(f"Tracked search: {query} for user {user_id}")

        except Exception as e:
            self.logger.error(f"Error tracking search interaction: {e}")

    async def track_search_click(
        self, user_id: str, query: str, product_id: int
    ) -> bool:
        """
        Track when a user clicks a product from search results.

        Args:
            user_id: Firebase UID
            query: Original search query
            product_id: Product that was clicked

        Returns:
            True if tracked successfully
        """
        try:
            async with AsyncSessionLocal() as session:
                # Update the most recent search interaction for this user/query
                search_query = (
                    select(SearchInteraction)
                    .where(
                        and_(
                            SearchInteraction.user_id == user_id,
                            SearchInteraction.query == query,
                        )
                    )
                    .order_by(desc(SearchInteraction.timestamp))
                    .limit(1)
                )

                result = await session.execute(search_query)
                interaction = result.scalars().first()

                if interaction:
                    # Add clicked product ID
                    if interaction.clicked_product_ids is None:
                        interaction.clicked_product_ids = []
                    if product_id not in interaction.clicked_product_ids:
                        clicked_ids = list(interaction.clicked_product_ids)
                        clicked_ids.append(product_id)
                        interaction.clicked_product_ids = clicked_ids

                    await session.commit()

                # Also create product interaction
                from src.config.constants import INTERACTION_SCORES

                product_interaction = ProductInteraction(
                    user_id=user_id,
                    product_id=product_id,
                    interaction_type=InteractionType.SEARCH_CLICK.value,
                    interaction_score=INTERACTION_SCORES[InteractionType.SEARCH_CLICK],
                    timestamp=datetime.now(),
                    extra_data={"search_query": query},
                )
                session.add(product_interaction)
                await session.commit()

                self.logger.debug(
                    f"Tracked search click: product {product_id} from query '{query}'"
                )
                return True

        except Exception as e:
            self.logger.error(f"Error tracking search click: {e}")
            return False
