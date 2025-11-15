import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.future import select

from src.config.constants import INTERACTION_SCORES, InteractionType
from src.database.connection import AsyncSessionLocal
from src.database.models.product_interaction import ProductInteraction
from src.shared.error_handler import ErrorHandler


class InteractionService:
    """
    Service for tracking user interactions with products.

    Handles:
    - Recording all types of interactions (view, cart, order, etc.)
    - Automatic popularity score updates
    - Automatic user preference updates
    - Interaction deduplication (prevent spam)
    """

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.logger = logging.getLogger(__name__)

    async def track_interaction(
        self,
        user_id: str,
        product_id: int,
        interaction_type: InteractionType,
        extra_data: Optional[dict] = None,
        auto_update_popularity: bool = True,
        auto_update_preferences: bool = False,
    ) -> bool:
        """
        Track a user interaction with a product.

        Args:
            user_id: Firebase UID
            product_id: Product ID
            interaction_type: Type of interaction
            extra_data: Additional context (order_id, search_query, etc.)
            auto_update_popularity: Trigger popularity update in background
            auto_update_preferences: Trigger preference update in background

        Returns:
            True if tracked successfully
        """
        try:
            async with AsyncSessionLocal() as session:
                # Get interaction score
                interaction_score = INTERACTION_SCORES.get(interaction_type, 1.0)

                # Create interaction record
                interaction = ProductInteraction(
                    user_id=user_id,
                    product_id=product_id,
                    interaction_type=interaction_type.value,
                    interaction_score=interaction_score,
                    timestamp=datetime.now(),
                    extra_data=extra_data or {},
                )

                session.add(interaction)
                await session.commit()

                self.logger.debug(
                    f"Tracked {interaction_type.value} interaction: user={user_id}, product={product_id}"
                )

                # Trigger background updates if requested
                if auto_update_popularity:
                    asyncio.create_task(self._update_popularity_async(product_id))

                if auto_update_preferences:
                    asyncio.create_task(self._update_preferences_async(user_id))

                return True

        except Exception as e:
            self.logger.error(
                f"Error tracking interaction: {e}",
                exc_info=True,
            )
            return False

    async def track_cart_add(
        self,
        user_id: str,
        product_id: int,
        quantity: int = 1,
        auto_update: bool = True,
    ) -> bool:
        """
        Track when user adds product to cart.

        Args:
            user_id: Firebase UID
            product_id: Product ID
            quantity: Quantity added
            auto_update: Auto-update popularity

        Returns:
            True if tracked successfully
        """
        return await self.track_interaction(
            user_id=user_id,
            product_id=product_id,
            interaction_type=InteractionType.CART_ADD,
            extra_data={"quantity": quantity},
            auto_update_popularity=auto_update,
            auto_update_preferences=False,  # Wait for order
        )

    async def track_wishlist_add(
        self,
        user_id: str,
        product_id: int,
        auto_update: bool = True,
    ) -> bool:
        """
        Track when user adds product to wishlist.

        Args:
            user_id: Firebase UID
            product_id: Product ID
            auto_update: Auto-update popularity

        Returns:
            True if tracked successfully
        """
        return await self.track_interaction(
            user_id=user_id,
            product_id=product_id,
            interaction_type=InteractionType.WISHLIST_ADD,
            auto_update_popularity=auto_update,
            auto_update_preferences=False,
        )

    async def track_order(
        self,
        user_id: str,
        product_id: int,
        order_id: int,
        quantity: int = 1,
        price: Optional[float] = None,
        auto_update: bool = True,
    ) -> bool:
        """
        Track when user orders a product.

        This is the highest-value interaction.

        Args:
            user_id: Firebase UID
            product_id: Product ID
            order_id: Order ID
            quantity: Quantity ordered
            price: Price paid
            auto_update: Auto-update popularity and preferences

        Returns:
            True if tracked successfully
        """
        return await self.track_interaction(
            user_id=user_id,
            product_id=product_id,
            interaction_type=InteractionType.ORDER,
            extra_data={
                "order_id": order_id,
                "quantity": quantity,
                "price": price,
            },
            auto_update_popularity=auto_update,
            auto_update_preferences=auto_update,  # Update preferences after order
        )

    async def track_view(
        self,
        user_id: str,
        product_id: int,
        auto_update: bool = False,  # Views don't auto-update by default
    ) -> bool:
        """
        Track when user views a product.

        Note: Views are low-signal, so we don't auto-update by default.

        Args:
            user_id: Firebase UID
            product_id: Product ID
            auto_update: Auto-update popularity (False by default)

        Returns:
            True if tracked successfully
        """
        return await self.track_interaction(
            user_id=user_id,
            product_id=product_id,
            interaction_type=InteractionType.VIEW,
            auto_update_popularity=auto_update,
            auto_update_preferences=False,
        )

    async def track_bulk_orders(
        self,
        user_id: str,
        order_id: int,
        products: list,  # List of (product_id, quantity, price)
        auto_update: bool = True,
    ) -> dict:
        """
        Track multiple products in a single order.

        Args:
            user_id: Firebase UID
            order_id: Order ID
            products: List of (product_id, quantity, price) tuples
            auto_update: Auto-update popularity and preferences

        Returns:
            Dict with success/failure counts
        """
        results = {"success": 0, "failed": 0}

        for product_id, quantity, price in products:
            success = await self.track_order(
                user_id=user_id,
                product_id=product_id,
                order_id=order_id,
                quantity=quantity,
                price=price,
                auto_update=False,  # Don't trigger for each item
            )

            if success:
                results["success"] += 1
            else:
                results["failed"] += 1

        # Trigger single update for user preferences after all items
        if auto_update and results["success"] > 0:
            asyncio.create_task(self._update_preferences_async(user_id))

        self.logger.info(
            f"Tracked bulk order {order_id}: {results['success']} products"
        )
        return results

    async def get_user_interaction_count(
        self, user_id: str, interaction_type: Optional[InteractionType] = None
    ) -> int:
        """
        Get total interaction count for a user.

        Args:
            user_id: Firebase UID
            interaction_type: Optional filter by type

        Returns:
            Count of interactions
        """
        try:
            async with AsyncSessionLocal() as session:
                query = select(ProductInteraction).where(
                    ProductInteraction.user_id == user_id
                )

                if interaction_type:
                    query = query.where(
                        ProductInteraction.interaction_type == interaction_type.value
                    )

                from sqlalchemy import func

                result = await session.execute(
                    select(func.count()).select_from(query.subquery())
                )
                count = result.scalar()

                return count or 0

        except Exception as e:
            self.logger.error(f"Error getting interaction count: {e}", exc_info=True)
            return 0

    async def get_user_recently_ordered_products(
        self, user_id: str, days: int = 30
    ) -> list:
        """
        Get products user recently ordered.

        Used to de-prioritize in personalization.

        Args:
            user_id: Firebase UID
            days: Look back period in days

        Returns:
            List of product IDs
        """
        try:
            from datetime import timedelta

            async with AsyncSessionLocal() as session:
                cutoff_date = datetime.now() - timedelta(days=days)

                query = (
                    select(ProductInteraction.product_id)
                    .where(
                        ProductInteraction.user_id == user_id,
                        ProductInteraction.interaction_type
                        == InteractionType.ORDER.value,
                        ProductInteraction.timestamp >= cutoff_date,
                    )
                    .distinct()
                )

                result = await session.execute(query)
                product_ids = [row[0] for row in result.fetchall()]

                return product_ids

        except Exception as e:
            self.logger.error(
                f"Error getting recently ordered products: {e}", exc_info=True
            )
            return []

    async def _update_popularity_async(self, product_id: int):
        """
        Background task to update product popularity.

        Args:
            product_id: Product ID
        """
        try:
            from src.api.products.services.popularity_service import PopularityService

            popularity_service = PopularityService()
            await popularity_service.update_product_popularity(product_id)

        except Exception as e:
            self.logger.error(
                f"Error in background popularity update: {e}", exc_info=True
            )

    async def _update_preferences_async(self, user_id: str):
        """
        Background task to update user preferences.

        Args:
            user_id: Firebase UID
        """
        try:
            from src.api.personalization.service import PersonalizationService

            personalization_service = PersonalizationService()
            await personalization_service.update_user_preferences(user_id)

        except Exception as e:
            self.logger.error(
                f"Error in background preference update: {e}", exc_info=True
            )

    async def deduplicate_recent_interaction(
        self,
        user_id: str,
        product_id: int,
        interaction_type: InteractionType,
        within_minutes: int = 5,
    ) -> bool:
        """
        Check if user has same interaction with product recently.

        Prevents spam/double-tracking.

        Args:
            user_id: Firebase UID
            product_id: Product ID
            interaction_type: Type of interaction
            within_minutes: Time window to check

        Returns:
            True if duplicate found (should skip tracking)
        """
        try:
            from datetime import timedelta

            async with AsyncSessionLocal() as session:
                cutoff_time = datetime.now() - timedelta(minutes=within_minutes)

                query = select(ProductInteraction).where(
                    ProductInteraction.user_id == user_id,
                    ProductInteraction.product_id == product_id,
                    ProductInteraction.interaction_type == interaction_type.value,
                    ProductInteraction.timestamp >= cutoff_time,
                )

                result = await session.execute(query)
                existing = result.scalars().first()

                return existing is not None

        except Exception as e:
            self.logger.error(
                f"Error checking duplicate interaction: {e}", exc_info=True
            )
            return False
