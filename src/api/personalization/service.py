import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy import desc
from sqlalchemy.future import select

from src.config.constants import (
    INTERACTION_DECAY_DAYS,
    MAX_USER_INTERACTIONS,
    PERSONALIZATION_CATEGORY_WEIGHT,
    PERSONALIZATION_MIN_INTERACTIONS,
    PERSONALIZATION_SEARCH_WEIGHT,
    SEARCH_VECTOR_DIM,
)
from src.database.connection import AsyncSessionLocal
from src.database.models.product_interaction import ProductInteraction
from src.database.models.product_vector import ProductVector
from src.database.models.search_interaction import SearchInteraction
from src.database.models.user_preference import UserPreference
from src.shared.error_handler import ErrorHandler


class PersonalizationService:
    """
    Service for personalized product recommendations.

    Handles:
    - User preference tracking and aggregation
    - Interest vector calculation from interaction history
    - Category and brand affinity scoring
    - Search keyword extraction
    - Personalized product ranking
    - Diversity filtering to prevent filter bubble
    """

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.logger = logging.getLogger(__name__)

    async def get_user_preferences(self, user_id: str) -> Optional[UserPreference]:
        """
        Get user preferences, creating if not exists.

        Args:
            user_id: Firebase UID

        Returns:
            UserPreference object or None
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(UserPreference).where(UserPreference.user_id == user_id)
                )
                preferences = result.scalars().first()

                if not preferences:
                    # Create new preferences
                    preferences = UserPreference(
                        user_id=user_id,
                        interest_vector=None,
                        category_scores={},
                        brand_scores={},
                        search_keywords={},
                        total_interactions=0,
                    )
                    session.add(preferences)
                    await session.commit()
                    await session.refresh(preferences)

                return preferences

        except Exception as e:
            self.logger.error(
                f"Error getting user preferences for {user_id}: {e}", exc_info=True
            )
            return None

    async def update_user_preferences(self, user_id: str) -> bool:
        """
        Update user preferences based on interaction history.

        Aggregates:
        - Interest vector (average of interacted product vectors)
        - Category affinity scores
        - Brand affinity scores
        - Search keywords

        Args:
            user_id: Firebase UID

        Returns:
            True if successful
        """
        try:
            async with AsyncSessionLocal() as session:
                # Get recent interactions (last 100, within decay period)
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=INTERACTION_DECAY_DAYS)

                interactions_query = (
                    select(
                        ProductInteraction.product_id,
                        ProductInteraction.interaction_type,
                        ProductInteraction.interaction_score,
                        ProductInteraction.timestamp,
                    )
                    .where(
                        ProductInteraction.user_id == user_id,
                        ProductInteraction.timestamp >= cutoff_date,
                    )
                    .order_by(desc(ProductInteraction.timestamp))
                    .limit(MAX_USER_INTERACTIONS)
                )

                result = await session.execute(interactions_query)
                interactions = list(result.fetchall())

                if len(interactions) < PERSONALIZATION_MIN_INTERACTIONS:
                    self.logger.debug(
                        f"User {user_id} has {len(interactions)} interactions (min: {PERSONALIZATION_MIN_INTERACTIONS})"
                    )
                    return False

                # Calculate interest vector (weighted average of product vectors)
                interest_vector = await self._calculate_interest_vector(
                    interactions, session
                )

                # Calculate category scores
                category_scores = await self._calculate_category_scores(
                    interactions, session
                )

                # Calculate brand scores
                brand_scores = await self._calculate_brand_scores(interactions, session)

                # Extract search keywords
                search_keywords = await self._extract_search_keywords(user_id, session)

                # Update user preferences
                prefs_result = await session.execute(
                    select(UserPreference).where(UserPreference.user_id == user_id)
                )
                preferences = prefs_result.scalars().first()

                if preferences:
                    preferences.interest_vector = interest_vector  # type: ignore[assignment]
                    preferences.category_scores = category_scores
                    preferences.brand_scores = brand_scores
                    preferences.search_keywords = search_keywords
                    preferences.total_interactions = len(interactions)
                    preferences.last_updated = datetime.now(timezone.utc)
                else:
                    preferences = UserPreference(
                        user_id=user_id,
                        interest_vector=interest_vector,  # type: ignore[arg-type]
                        category_scores=category_scores,
                        brand_scores=brand_scores,
                        search_keywords=search_keywords,
                        total_interactions=len(interactions),
                    )
                    session.add(preferences)

                await session.commit()
                self.logger.debug(
                    f"Updated preferences for user {user_id}: {len(interactions)} interactions"
                )
                return True

        except Exception as e:
            self.logger.error(
                f"Error updating user preferences for {user_id}: {e}", exc_info=True
            )
            return False

    async def _calculate_interest_vector(
        self, interactions: List, session
    ) -> Optional[List[float]]:
        """
        Calculate user interest vector as weighted average of product vectors.

        Args:
            interactions: List of (product_id, type, score, timestamp)
            session: Database session

        Returns:
            Interest vector (384 dimensions) or None
        """
        try:
            # Get product vectors for interacted products
            product_ids = [interaction.product_id for interaction in interactions]

            vectors_query = select(
                ProductVector.product_id, ProductVector.vector_embedding
            ).where(ProductVector.product_id.in_(product_ids))

            result = await session.execute(vectors_query)
            product_vectors = {row.product_id: row.vector_embedding for row in result}

            if not product_vectors:
                return None

            # Calculate weighted average
            weighted_sum = np.zeros(SEARCH_VECTOR_DIM)
            total_weight = 0.0

            for interaction in interactions:
                if interaction.product_id in product_vectors:
                    vector = np.array(product_vectors[interaction.product_id])
                    weight = interaction.interaction_score

                    # Apply time decay
                    days_ago = (datetime.now(timezone.utc) - interaction.timestamp).days
                    if days_ago > 0:
                        time_decay = pow(0.9, days_ago / 7)  # Decay over weeks
                        weight *= time_decay

                    weighted_sum += vector * weight
                    total_weight += weight

            if total_weight > 0:
                interest_vector = (weighted_sum / total_weight).tolist()
                return interest_vector
            else:
                return None

        except Exception as e:
            self.logger.error(f"Error calculating interest vector: {e}", exc_info=True)
            return None

    async def _calculate_category_scores(
        self, interactions: List, session
    ) -> Dict[int, float]:
        """
        Calculate category affinity scores from interactions.

        Args:
            interactions: List of interactions
            session: Database session

        Returns:
            Dict mapping category_id to affinity score
        """
        try:
            from sqlalchemy import text

            # Get categories for interacted products
            product_ids = [interaction.product_id for interaction in interactions]

            categories_query = text("""
                SELECT pc.category_id, pi.interaction_score
                FROM product_categories pc
                JOIN product_interactions pi ON pc.product_id = pi.product_id
                WHERE pi.product_id = ANY(:product_ids)
            """)

            result = await session.execute(
                categories_query, {"product_ids": product_ids}
            )
            rows = result.fetchall()

            category_scores = {}
            for row in rows:
                category_id = row.category_id
                score = row.interaction_score or 0

                if category_id in category_scores:
                    category_scores[category_id] += score
                else:
                    category_scores[category_id] = score

            # Normalize scores
            if category_scores:
                max_score = max(category_scores.values())
                if max_score > 0:
                    category_scores = {
                        cat_id: score / max_score
                        for cat_id, score in category_scores.items()
                    }

            return category_scores

        except Exception as e:
            self.logger.error(f"Error calculating category scores: {e}", exc_info=True)
            return {}

    async def _calculate_brand_scores(
        self, interactions: List, session
    ) -> Dict[str, float]:
        """
        Calculate brand affinity scores from interactions.

        Args:
            interactions: List of interactions
            session: Database session

        Returns:
            Dict mapping brand name to affinity score
        """
        try:
            from sqlalchemy import text

            product_ids = [interaction.product_id for interaction in interactions]

            brands_query = text("""
                SELECT p.brand, pi.interaction_score
                FROM products p
                JOIN product_interactions pi ON p.id = pi.product_id
                WHERE pi.product_id = ANY(:product_ids) AND p.brand IS NOT NULL
            """)

            result = await session.execute(brands_query, {"product_ids": product_ids})
            rows = result.fetchall()

            brand_scores = {}
            for row in rows:
                brand = row.brand
                score = row.interaction_score or 0

                if brand in brand_scores:
                    brand_scores[brand] += score
                else:
                    brand_scores[brand] = score

            # Normalize scores
            if brand_scores:
                max_score = max(brand_scores.values())
                if max_score > 0:
                    brand_scores = {
                        brand: score / max_score
                        for brand, score in brand_scores.items()
                    }

            return brand_scores

        except Exception as e:
            self.logger.error(f"Error calculating brand scores: {e}", exc_info=True)
            return {}

    async def _extract_search_keywords(self, user_id: str, session) -> Dict[str, int]:
        """
        Extract frequently searched keywords for user.

        Args:
            user_id: Firebase UID
            session: Database session

        Returns:
            Dict mapping keyword to frequency
        """
        try:
            # Get recent search queries
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=INTERACTION_DECAY_DAYS)

            searches_query = (
                select(SearchInteraction.query)
                .where(
                    SearchInteraction.user_id == user_id,
                    SearchInteraction.timestamp >= cutoff_date,
                )
                .order_by(desc(SearchInteraction.timestamp))
                .limit(50)
            )

            result = await session.execute(searches_query)
            queries = [row.query for row in result]

            # Extract keywords (simple tokenization)
            keywords = {}
            for query in queries:
                words = query.lower().split()
                for word in words:
                    if len(word) > 2:  # Skip very short words
                        keywords[word] = keywords.get(word, 0) + 1

            # Keep top 20 keywords
            if keywords:
                sorted_keywords = sorted(
                    keywords.items(), key=lambda x: x[1], reverse=True
                )
                keywords = dict(sorted_keywords[:20])

            return keywords

        except Exception as e:
            self.logger.error(f"Error extracting search keywords: {e}", exc_info=True)
            return {}

    async def calculate_personalization_scores(
        self, user_id: str, product_ids: List[int]
    ) -> Dict[int, float]:
        """
        Calculate personalization scores for products based on user preferences.

        Combines:
        - Vector similarity with user interest vector
        - Category affinity
        - Brand affinity
        - Search keyword matching

        Args:
            user_id: Firebase UID
            product_ids: List of product IDs to score

        Returns:
            Dict mapping product_id to personalization score (0-1)
        """
        try:
            async with AsyncSessionLocal() as session:
                # Get user preferences
                prefs_result = await session.execute(
                    select(UserPreference).where(UserPreference.user_id == user_id)
                )
                preferences = prefs_result.scalars().first()

                if (
                    not preferences
                    or preferences.total_interactions < PERSONALIZATION_MIN_INTERACTIONS
                ):
                    # Not enough data for personalization
                    return {}

                # Get product data
                from sqlalchemy import text

                products_query = text("""
                    SELECT
                        p.id,
                        p.brand,
                        pv.vector_embedding,
                        pv.text_content,
                        ARRAY_AGG(DISTINCT pc.category_id) as category_ids
                    FROM products p
                    LEFT JOIN product_vectors pv ON p.id = pv.product_id
                    LEFT JOIN product_categories pc ON p.id = pc.product_id
                    WHERE p.id = ANY(:product_ids)
                    GROUP BY p.id, p.brand, pv.vector_embedding, pv.text_content
                """)

                result = await session.execute(
                    products_query, {"product_ids": product_ids}
                )
                products = result.fetchall()

                scores = {}
                user_vector = (
                    np.array(preferences.interest_vector)
                    if preferences.interest_vector
                    else None
                )

                for product in products:
                    score = 0.0
                    components = 0

                    # 1. Vector similarity (semantic)
                    if user_vector is not None and product.vector_embedding:
                        product_vector = np.array(product.vector_embedding)
                        # Cosine similarity
                        similarity = np.dot(user_vector, product_vector) / (
                            np.linalg.norm(user_vector) * np.linalg.norm(product_vector)
                        )
                        score += max(0, similarity)  # Clamp to 0-1
                        components += 1

                    # 2. Category affinity
                    if preferences.category_scores and product.category_ids:
                        category_score = sum(
                            preferences.category_scores.get(cat_id, 0)
                            for cat_id in product.category_ids
                            if cat_id is not None
                        ) / max(len(product.category_ids), 1)
                        score += category_score * PERSONALIZATION_CATEGORY_WEIGHT
                        components += 1

                    # 3. Brand affinity
                    if preferences.brand_scores and product.brand:
                        brand_score = preferences.brand_scores.get(product.brand, 0)
                        score += brand_score * 0.5  # Brand weight
                        components += 1

                    # 4. Search keyword matching
                    if preferences.search_keywords and product.text_content:
                        text_lower = product.text_content.lower()
                        keyword_matches = sum(
                            freq
                            for keyword, freq in preferences.search_keywords.items()
                            if keyword in text_lower
                        )
                        if keyword_matches > 0:
                            keyword_score = min(1.0, keyword_matches / 10)  # Normalize
                            score += keyword_score * PERSONALIZATION_SEARCH_WEIGHT
                            components += 1

                    # Average score across components
                    if components > 0:
                        scores[product.id] = score / components
                    else:
                        scores[product.id] = 0.0

                return scores

        except Exception as e:
            self.logger.error(
                f"Error calculating personalization scores: {e}", exc_info=True
            )
            return {}

    def apply_diversity_filter(
        self, products: List, personalization_scores: Dict[int, float]
    ) -> List:
        """
        Apply diversity filtering to prevent filter bubble.

        Ensures variety by:
        - Limiting consecutive products from same category
        - Mixing high and medium personalization scores
        - Preserving some serendipity

        Args:
            products: List of product objects
            personalization_scores: Dict of product_id -> score

        Returns:
            Reordered list of products with diversity
        """
        try:
            if not products or not personalization_scores:
                return products

            # Sort by personalization score
            scored_products = [
                (p, personalization_scores.get(p.id, 0)) for p in products
            ]
            scored_products.sort(key=lambda x: x[1], reverse=True)

            # Apply diversity
            diverse_products = []
            recent_categories = []
            max_category_consecutive = 2

            for product, score in scored_products:
                # Get product categories
                product_categories = (
                    [cat.get("id") for cat in product.categories]
                    if hasattr(product, "categories") and product.categories
                    else []
                )

                # Check diversity
                if product_categories:
                    # Check if too many consecutive from same category
                    recent_match = any(
                        cat in recent_categories for cat in product_categories
                    )

                    if (
                        recent_match
                        and len(recent_categories) >= max_category_consecutive
                    ):
                        # Skip for now (might add later for completeness)
                        continue

                diverse_products.append(product)

                # Update recent categories
                if product_categories:
                    recent_categories = (product_categories + recent_categories)[
                        :max_category_consecutive
                    ]

            # Add remaining products at end (for completeness)
            added_ids = {p.id for p in diverse_products}
            for product, _ in scored_products:
                if product.id not in added_ids:
                    diverse_products.append(product)

            return diverse_products

        except Exception as e:
            self.logger.error(f"Error applying diversity filter: {e}", exc_info=True)
            return products
