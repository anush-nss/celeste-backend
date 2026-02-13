import gc
import json
import logging
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.future import select

from src.config.constants import (
    NEXT_DAY_DELIVERY_ONLY_TAG_ID,
    SEARCH_TFIDF_MAX_FEATURES,
    SEARCH_VECTOR_DIM,
)
from src.database.connection import AsyncSessionLocal
from src.database.models.product import Product
from src.database.models.product_vector import ProductVector
from src.shared.error_handler import ErrorHandler


class VectorService:
    """
    Service for product search vector placeholders.
    (Vector search disabled for Vercel deployment)
    """

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.logger = logging.getLogger(__name__)

    def _load_model(self):
        return None

    def _unload_model(self):
        pass

    def _get_tfidf_vectorizer(self):
        return None

    async def _build_product_text(self, product_id: int, session) -> Optional[str]:
        return None

    async def vectorize_product(self, product_id: int, version: int = 1) -> bool:
        """Disabled for Vercel deployment"""
        return True

    async def vectorize_products_batch(
        self,
        product_ids: List[int],
        version: int = 1,
        batch_size: int = 8,
    ) -> dict:
        """Disabled for Vercel deployment"""
        return {"success": len(product_ids), "failed": 0, "skipped": 0}

    async def vectorize_all_products(
        self, version: int = 1, only_missing: bool = False
    ) -> dict:
        """Disabled for Vercel deployment"""
        return {"success": 0, "failed": 0, "skipped": 0}

    async def update_product_vector(self, product_id: int) -> bool:
        """
        Update vector for a product (e.g., when product is updated).

        Args:
            product_id: Product ID to update

        Returns:
            True if successful
        """
        return await self.vectorize_product(product_id)

    async def delete_product_vector(self, product_id: int) -> bool:
        """
        Delete vector for a product.

        Args:
            product_id: Product ID

        Returns:
            True if successful
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(ProductVector).where(ProductVector.product_id == product_id)
                )
                vector = result.scalars().first()

                if vector:
                    await session.delete(vector)
                    await session.commit()
                    self.logger.info(f"Deleted vector for product {product_id}")
                    return True
                else:
                    self.logger.warning(f"No vector found for product {product_id}")
                    return False

        except Exception as e:
            self.logger.error(f"Error deleting vector for product {product_id}: {e}")
            return False

    async def find_similar_products(
        self,
        product_id: int,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> List[tuple]:
        """Disabled for Vercel deployment"""
        return []
