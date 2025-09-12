from typing import Optional, List
from src.shared.core_cache import core_cache
from src.config.cache_config import cache_config
from src.shared.utils import get_logger
from src.shared.cache_invalidation import cache_invalidation_manager
from src.api.categories.models import CategorySchema # Import CategorySchema

logger = get_logger(__name__)


class CategoriesCache:
    """Categories domain cache operations"""

    def __init__(self):
        self.cache = core_cache
        self.prefix = cache_config.PREFIXES.get("categories", "categories")

    # Cache key generators
    def get_category_key(self, category_id: int) -> str: # Changed type to int
        """Generate cache key for category data"""
        return self.cache.generate_key(self.prefix, str(category_id)) # Convert to str

    def get_all_categories_key(self) -> str:
        """Generate cache key for all categories"""
        return self.cache.generate_key(self.prefix, "all")

    # Cache operations with domain-specific TTL
    def get_category(self, category_id: int) -> Optional[dict]: # Changed type to int
        """Get cached category data"""
        key = self.get_category_key(category_id)
        return self.cache.get(key)

    def set_category(self, category_id: int, category_data: dict) -> bool: # Changed type to int
        """Cache category data with configured TTL"""
        key = self.get_category_key(category_id)
        ttl = cache_config.get_ttl("categories")
        return self.cache.set(key, category_data, ttl_seconds=ttl)

    def get_all_categories(self) -> Optional[List[dict]]: # Changed return type hint
        """Get cached all categories"""
        key = self.get_all_categories_key()
        return self.cache.get(key)

    def set_all_categories(self, categories: List[dict]) -> bool: # Changed type hint
        """Cache all categories with configured TTL"""
        key = self.get_all_categories_key()
        ttl = cache_config.get_ttl("categories")
        return self.cache.set(key, categories, ttl_seconds=ttl)

    # Cache invalidation methods
    def invalidate_category_cache(self, category_id: Optional[int] = None) -> int: # Changed type to int
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


        if deleted > 0:
            logger.info(
                f"Invalidated {deleted} categories cache keys for category: {category_id or 'all'}"
            )

        return deleted


# Global categories cache instance
categories_cache = CategoriesCache()

# Register with invalidation manager
from src.config.constants import Collections
cache_invalidation_manager.register_domain_cache(Collections.CATEGORIES, categories_cache)