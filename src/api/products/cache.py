"""
Products-specific cache operations
"""

from typing import Optional

from src.config.cache_config import cache_config
from src.shared.cache_invalidation import cache_invalidation_manager
from src.shared.core_cache import core_cache
from src.shared.utils import get_logger

# Register with invalidation manager
from src.config.constants import Collections

logger = get_logger(__name__)


class ProductsCache:
    """Products domain cache operations"""

    def __init__(self):
        self.cache = core_cache
        self.prefix = cache_config.PREFIXES.get("products", "products")

    # Cache key generators
    def get_product_key(self, product_id: str) -> str:
        """Generate cache key for product data"""
        return self.cache.generate_key(self.prefix, product_id)

    def get_delivery_product_key(self) -> str:
        """Generate cache key for the delivery product"""
        return self.cache.generate_key(self.prefix, "delivery_product")

    # Cache operations with domain-specific TTL
    def get_product(self, product_id: str) -> Optional[dict]:
        """Get cached product data"""
        key = self.get_product_key(product_id)
        return self.cache.get(key)

    def set_product(self, product_id: str, product_data: dict) -> bool:
        """Cache product data with configured TTL"""
        key = self.get_product_key(product_id)
        ttl = cache_config.get_ttl("products")
        return self.cache.set(key, product_data, ttl_seconds=ttl)

    def get_delivery_product(self) -> Optional[dict]:
        """Get cached delivery product data"""
        key = self.get_delivery_product_key()
        return self.cache.get(key)

    def set_delivery_product(self, product_data: dict) -> bool:
        """Cache the delivery product with a static TTL"""
        key = self.get_delivery_product_key()
        ttl = cache_config.get_ttl("static")
        return self.cache.set(key, product_data, ttl_seconds=ttl)

    # Cache invalidation methods
    def invalidate_product_cache(self, product_id: Optional[str] = None) -> int:
        """Invalidate cache for specific product or all products"""
        deleted = 0

        if product_id:
            # Invalidate specific product
            product_key = self.get_product_key(product_id)
            if self.cache.delete(product_key):
                deleted += 1

        else:
            # Invalidate all products and related pricing
            deleted += self.cache.delete_pattern(f"{self.prefix}:*")

        if deleted > 0:
            logger.info(
                f"Invalidated {deleted} products cache keys for product: {product_id or 'all'}"
            )

        return deleted


# Global products cache instance
products_cache = ProductsCache()


cache_invalidation_manager.register_domain_cache(Collections.PRODUCTS, products_cache)
