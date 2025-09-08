"""
Categories-specific cache operations
"""

from typing import Optional, List
from src.shared.core_cache import core_cache
from src.config.cache_config import cache_config
from src.shared.utils import get_logger
from src.shared.cache_invalidation import cache_invalidation_manager

logger = get_logger(__name__)


class CategoriesCache:
    """Categories domain cache operations"""

    def __init__(self):
        self.cache = core_cache
        self.prefix = "categories"

    # Cache key generators
    def get_category_key(self, category_id: str) -> str:
        """Generate cache key for category data"""
        return self.cache.generate_key(self.prefix, category_id)

    def get_all_categories_key(self) -> str:
        """Generate cache key for all categories"""
        return self.cache.generate_key(self.prefix, "all")

    # Cache operations with domain-specific TTL
    def get_category(self, category_id: str) -> Optional[dict]:
        """Get cached category data"""
        key = self.get_category_key(category_id)
        return self.cache.get(key)

    def set_category(self, category_id: str, category_data: dict) -> bool:
        """Cache category data with configured TTL"""
        key = self.get_category_key(category_id)
        ttl = cache_config.get_ttl("categories")
        return self.cache.set(key, category_data, ttl_seconds=ttl)

    def get_all_categories(self) -> Optional[List]:
        """Get cached all categories"""
        key = self.get_all_categories_key()
        return self.cache.get(key)

    def set_all_categories(self, categories: List) -> bool:
        """Cache all categories with configured TTL"""
        key = self.get_all_categories_key()
        ttl = cache_config.get_ttl("categories")
        return self.cache.set(key, categories, ttl_seconds=ttl)

    # Cache invalidation methods
    def invalidate_category_cache(self, category_id: Optional[str] = None) -> int:
        """Invalidate cache for specific category or all categories"""
        deleted = 0

        if category_id:
            # Invalidate specific category
            category_key = self.get_category_key(category_id)
            if self.cache.delete(category_key):
                deleted += 1
        else:
            # Invalidate all categories
            deleted += self.cache.delete_pattern(f"{self.prefix}:*")

        # Categories might affect pricing, so invalidate cross-domain dependencies
        if category_id:
            deleted += cache_invalidation_manager.invalidate_cross_domain_dependencies(
                "categories", category_id
            )

        if deleted > 0:
            logger.info(
                f"Invalidated {deleted} categories cache keys for category: {category_id or 'all'}"
            )

        return deleted


# Global categories cache instance
categories_cache = CategoriesCache()

# Register with invalidation manager
cache_invalidation_manager.register_domain_cache("categories", categories_cache)
