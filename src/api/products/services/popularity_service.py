import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import desc, text
from sqlalchemy.future import select

from src.config.constants import (
    INTERACTION_SCORES,
    POPULARITY_MIN_INTERACTIONS,
    POPULARITY_TIME_DECAY_HOURS,
    TRENDING_RECENT_DAYS,
    InteractionType,
    PopularityMode,
)
from src.database.connection import AsyncSessionLocal
from src.database.models.product_interaction import ProductInteraction
from src.database.models.product_popularity import ProductPopularity
from src.shared.error_handler import ErrorHandler


class PopularityService:
    """
    Service for managing product popularity and trending products.

    Handles:
    - Popularity score calculation (view, cart, order weighted scores)
    - Trending score calculation (time-decayed recent activity)
    - Popular products retrieval with multiple ranking modes
    - Background popularity score updates
    """

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.logger = logging.getLogger(__name__)

    async def get_popular_products(
        self,
        mode: PopularityMode = PopularityMode.TRENDING,
        limit: int = 20,
        time_window_days: Optional[int] = None,
        category_ids: Optional[List[int]] = None,
        min_interactions: int = POPULARITY_MIN_INTERACTIONS,
    ) -> List[int]:
        """
        Get popular product IDs based on various ranking modes.

        Args:
            mode: Ranking mode (trending, most_viewed, most_ordered, etc.)
            limit: Maximum number of products to return
            time_window_days: Limit to products popular in last N days
            category_ids: Filter by category IDs
            min_interactions: Minimum interactions required to be considered

        Returns:
            List of product IDs sorted by popularity
        """
        try:
            async with AsyncSessionLocal() as session:
                # Base query
                query = select(ProductPopularity.product_id)

                # Apply minimum interactions filter
                if mode == PopularityMode.TRENDING:
                    query = query.where(ProductPopularity.trending_score > 0).order_by(
                        desc(ProductPopularity.trending_score)
                    )
                elif mode == PopularityMode.MOST_VIEWED:
                    query = query.where(
                        ProductPopularity.view_count >= min_interactions
                    ).order_by(desc(ProductPopularity.view_count))
                elif mode == PopularityMode.MOST_CARTED:
                    query = query.where(
                        ProductPopularity.cart_add_count >= min_interactions
                    ).order_by(desc(ProductPopularity.cart_add_count))
                elif mode == PopularityMode.MOST_ORDERED:
                    query = query.where(
                        ProductPopularity.order_count >= min_interactions
                    ).order_by(desc(ProductPopularity.order_count))
                elif mode == PopularityMode.MOST_SEARCHED:
                    query = query.where(
                        ProductPopularity.search_count >= min_interactions
                    ).order_by(desc(ProductPopularity.search_count))
                else:  # OVERALL
                    query = query.where(
                        ProductPopularity.popularity_score > 0
                    ).order_by(desc(ProductPopularity.popularity_score))

                # Apply time window filter if specified
                if time_window_days:
                    cutoff_date = datetime.now(timezone.utc) - timedelta(
                        days=time_window_days
                    )
                    query = query.where(
                        ProductPopularity.last_interaction >= cutoff_date
                    )

                # Apply category filter using join (if needed)
                # For now, we'll get all products and filter in product service layer

                # Limit results
                query = query.limit(limit)

                result = await session.execute(query)
                product_ids = [row[0] for row in result.fetchall()]

                self.logger.debug(
                    f"Retrieved {len(product_ids)} popular products (mode: {mode.value})"
                )
                return product_ids

        except Exception as e:
            self.logger.error(f"Error getting popular products: {e}", exc_info=True)
            return []

    async def update_product_popularity(self, product_id: int) -> bool:
        """
        Update popularity metrics for a single product.

        Args:
            product_id: Product ID to update

        Returns:
            True if successful
        """
        try:
            async with AsyncSessionLocal() as session:
                # Get interaction counts
                counts_query = text("""
                    SELECT
                        COUNT(*) FILTER (WHERE interaction_type = :view) as view_count,
                        COUNT(*) FILTER (WHERE interaction_type = :cart) as cart_count,
                        COUNT(*) FILTER (WHERE interaction_type = :order) as order_count,
                        COUNT(*) FILTER (WHERE interaction_type = :search) as search_count,
                        MAX(timestamp) as last_interaction
                    FROM product_interactions
                    WHERE product_id = :product_id
                """)

                result = await session.execute(
                    counts_query,
                    {
                        "product_id": product_id,
                        "view": InteractionType.VIEW.value,
                        "cart": InteractionType.CART_ADD.value,
                        "order": InteractionType.ORDER.value,
                        "search": InteractionType.SEARCH_CLICK.value,
                    },
                )
                row = result.fetchone()

                if not row:
                    return False

                view_count = row.view_count or 0
                cart_count = row.cart_count or 0
                order_count = row.order_count or 0
                search_count = row.search_count or 0
                last_interaction = row.last_interaction or datetime.now(timezone.utc)

                # Calculate overall popularity score
                popularity_score = (
                    view_count * INTERACTION_SCORES[InteractionType.VIEW]
                    + cart_count * INTERACTION_SCORES[InteractionType.CART_ADD]
                    + order_count * INTERACTION_SCORES[InteractionType.ORDER]
                    + search_count * INTERACTION_SCORES[InteractionType.SEARCH_CLICK]
                )

                # Calculate trending score (time-decayed recent activity)
                trending_score = await self._calculate_trending_score(
                    product_id, session
                )

                # Update or create popularity record
                existing = await session.execute(
                    select(ProductPopularity).where(
                        ProductPopularity.product_id == product_id
                    )
                )
                popularity = existing.scalars().first()

                if popularity:
                    popularity.view_count = view_count
                    popularity.cart_add_count = cart_count
                    popularity.order_count = order_count
                    popularity.search_count = search_count
                    popularity.popularity_score = popularity_score
                    popularity.trending_score = trending_score
                    popularity.last_interaction = last_interaction
                    popularity.last_updated = datetime.now(timezone.utc)
                else:
                    popularity = ProductPopularity(
                        product_id=product_id,
                        view_count=view_count,
                        cart_add_count=cart_count,
                        order_count=order_count,
                        search_count=search_count,
                        popularity_score=popularity_score,
                        trending_score=trending_score,
                        last_interaction=last_interaction,
                    )
                    session.add(popularity)

                await session.commit()
                self.logger.debug(
                    f"Updated popularity for product {product_id}: score={popularity_score:.2f}, trending={trending_score:.2f}"
                )
                return True

        except Exception as e:
            self.logger.error(
                f"Error updating popularity for product {product_id}: {e}",
                exc_info=True,
            )
            return False

    async def _calculate_trending_score(self, product_id: int, session) -> float:
        """
        Calculate trending score with exponential time decay.

        Recent interactions are weighted more heavily.
        Uses exponential decay: score = interaction_weight * exp(-hours_ago / decay_constant)

        Args:
            product_id: Product ID
            session: Database session

        Returns:
            Trending score (higher = more trending)
        """
        try:
            # Get recent interactions (last N days)
            cutoff_date = datetime.now(timezone.utc) - timedelta(
                days=TRENDING_RECENT_DAYS
            )

            interactions_query = select(
                ProductInteraction.interaction_type,
                ProductInteraction.timestamp,
            ).where(
                ProductInteraction.product_id == product_id,
                ProductInteraction.timestamp >= cutoff_date,
            )

            result = await session.execute(interactions_query)
            interactions = result.fetchall()

            if not interactions:
                return 0.0

            trending_score = 0.0
            now = datetime.now(timezone.utc)

            for interaction_type, timestamp in interactions:
                # Time decay: more recent = higher score
                hours_ago = (now - timestamp).total_seconds() / 3600
                time_decay = pow(
                    0.5, hours_ago / POPULARITY_TIME_DECAY_HOURS
                )  # Half-life decay

                # Weight by interaction type
                interaction_weight = INTERACTION_SCORES.get(
                    InteractionType(interaction_type), 1.0
                )

                trending_score += interaction_weight * time_decay

            return round(trending_score, 2)

        except Exception as e:
            self.logger.error(
                f"Error calculating trending score for product {product_id}: {e}",
                exc_info=True,
            )
            return 0.0

    async def update_all_popularity_scores(self) -> dict:
        """
        Update popularity scores for all products with interactions.

        This is meant to be run as a background task.

        Returns:
            dict with success/failure counts
        """
        self.logger.info("Starting popularity score update for all products")
        results = {"success": 0, "failed": 0}

        try:
            async with AsyncSessionLocal() as session:
                # Get all products with interactions
                products_query = (
                    select(ProductInteraction.product_id)
                    .distinct()
                    .order_by(ProductInteraction.product_id)
                )

                result = await session.execute(products_query)
                product_ids = [row[0] for row in result.fetchall()]

                self.logger.info(f"Updating popularity for {len(product_ids)} products")

                # Update each product
                for product_id in product_ids:
                    success = await self.update_product_popularity(product_id)
                    if success:
                        results["success"] += 1
                    else:
                        results["failed"] += 1

                    # Log progress every 100 products
                    if (results["success"] + results["failed"]) % 100 == 0:
                        self.logger.info(
                            f"Progress: {results['success'] + results['failed']}/{len(product_ids)} products"
                        )

        except Exception as e:
            self.logger.error(f"Error in bulk popularity update: {e}", exc_info=True)

        self.logger.info(
            f"Popularity update complete: {results['success']} success, {results['failed']} failed"
        )
        return results

    async def get_popularity_metrics(self, product_id: int) -> Optional[dict]:
        """
        Get popularity metrics for a specific product.

        Args:
            product_id: Product ID

        Returns:
            dict with popularity metrics or None if not found
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(ProductPopularity).where(
                        ProductPopularity.product_id == product_id
                    )
                )
                popularity = result.scalars().first()

                if not popularity:
                    return None

                return {
                    "view_count": popularity.view_count,
                    "cart_add_count": popularity.cart_add_count,
                    "order_count": popularity.order_count,
                    "search_count": popularity.search_count,
                    "popularity_score": float(popularity.popularity_score),
                    "trending_score": float(popularity.trending_score),
                    "last_interaction": popularity.last_interaction.isoformat()
                    if popularity.last_interaction
                    else None,
                }

        except Exception as e:
            self.logger.error(
                f"Error getting popularity metrics for product {product_id}: {e}",
                exc_info=True,
            )
            return None
