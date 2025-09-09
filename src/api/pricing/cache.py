"""
Pricing-specific cache operations
"""

from typing import List, Dict, Optional
from src.shared.core_cache import core_cache
from src.config.cache_config import cache_config
from src.shared.utils import get_logger
import hashlib

logger = get_logger(__name__)


class PricingCache:
    """Pricing domain cache operations"""

    def __init__(self):
        self.cache = core_cache
        self.prefix = cache_config.PREFIXES.get("price_lists", "pricing")

    # Cache key generators
    def get_product_pricing_key(
        self,
        product_id: str,
        base_price: float,
        category_id: Optional[str],
        customer_tier: str,
        quantity: int = 1,
    ) -> str:
        """Generate cache key for individual product pricing"""
        return self.cache.generate_key(
            f"{self.prefix}_product",
            product_id,
            base_price,
            category_id or "none",
            customer_tier,
            quantity,
        )

    def get_bulk_pricing_key(self, customer_tier: str, product_ids: List[str]) -> str:
        """Generate cache key for bulk pricing"""
        product_hash = hashlib.md5(":".join(sorted(product_ids)).encode()).hexdigest()
        return self.cache.generate_key(
            f"{self.prefix}_bulk", customer_tier, product_hash
        )

    def get_price_lists_key(self, active_only: bool = False) -> str:
        """Generate cache key for price lists"""
        return self.cache.generate_key(
            f"{self.prefix}_lists", "active" if active_only else cache_config.INVALIDATION_SCOPE_ALL
        )

    def get_price_list_lines_key(self, price_list_id: str) -> str:
        """Generate cache key for price list lines"""
        return self.cache.generate_key(f"{self.prefix}_lines", price_list_id)

    # Cache operations with domain-specific TTL
    def get_product_pricing(
        self,
        product_id: str,
        base_price: float,
        category_id: Optional[str],
        customer_tier: str,
        quantity: int = 1,
    ) -> Optional[Dict]:
        """Get cached product pricing"""
        key = self.get_product_pricing_key(
            product_id, base_price, category_id, customer_tier, quantity
        )
        return self.cache.get(key)

    def set_product_pricing(
        self,
        product_id: str,
        base_price: float,
        category_id: Optional[str],
        customer_tier: str,
        pricing_data: Dict,
        quantity: int = 1,
    ) -> bool:
        """Cache product pricing with configured TTL"""
        key = self.get_product_pricing_key(
            product_id, base_price, category_id, customer_tier, quantity
        )
        ttl = cache_config.get_ttl("product_pricing")
        return self.cache.set(key, pricing_data, ttl_seconds=ttl)

    def get_bulk_pricing(
        self, customer_tier: str, product_ids: List[str]
    ) -> Optional[List[Dict]]:
        """Get cached bulk pricing"""
        key = self.get_bulk_pricing_key(customer_tier, product_ids)
        return self.cache.get(key)

    def set_bulk_pricing(
        self, customer_tier: str, product_ids: List[str], pricing_data: List[Dict]
    ) -> bool:
        """Cache bulk pricing with configured TTL"""
        key = self.get_bulk_pricing_key(customer_tier, product_ids)
        ttl = cache_config.get_ttl("bulk_pricing")
        return self.cache.set(key, pricing_data, ttl_seconds=ttl)

    def get_price_lists(self, active_only: bool = False) -> Optional[List]:
        """Get cached price lists"""
        key = self.get_price_lists_key(active_only)
        return self.cache.get(key)

    def set_price_lists(self, price_lists: List, active_only: bool = False) -> bool:
        """Cache price lists with configured TTL"""
        key = self.get_price_lists_key(active_only)
        ttl = cache_config.get_ttl("price_lists")
        return self.cache.set(key, price_lists, ttl_seconds=ttl)

    def get_price_list_lines(self, price_list_id: str) -> Optional[List]:
        """Get cached price list lines"""
        key = self.get_price_list_lines_key(price_list_id)
        return self.cache.get(key)

    def set_price_list_lines(self, price_list_id: str, lines: List) -> bool:
        """Cache price list lines with configured TTL"""
        key = self.get_price_list_lines_key(price_list_id)
        ttl = cache_config.get_ttl("price_list_lines")
        return self.cache.set(key, lines, ttl_seconds=ttl)

    # Cache invalidation methods
    def invalidate_pricing_cache(self, scope: str = None) -> int:
        """Invalidate pricing-related caches with selective scope"""
        # Default scope if not provided
        if scope is None:
            scope = self.prefix
            
        patterns = {
            cache_config.INVALIDATION_SCOPE_ALL: [
                f"{self.prefix}_product:*",
                f"{self.prefix}_bulk:*",
                f"{self.prefix}_lists:*",
                f"{self.prefix}_lines:*",
            ],
            self.prefix: [f"{self.prefix}_product:*", f"{self.prefix}_bulk:*"],
            "price_lists": [f"{self.prefix}_lists:*"],
            "price_list_lines": [f"{self.prefix}_lines:*"],
        }

        deleted = 0
        for pattern in patterns.get(scope, []):
            deleted += self.cache.delete_pattern(pattern)

        if deleted > 0:
            logger.info(f"Invalidated {deleted} pricing cache keys for scope: {scope}")

        return deleted

    def invalidate_price_list_cache(self, price_list_id: Optional[str] = None) -> int:
        """Invalidate cache for specific price list or all price lists"""
        deleted = 0

        if price_list_id:
            # Invalidate specific price list lines
            lines_pattern = f"{self.prefix}_lines:{price_list_id}*"
            deleted += self.cache.delete_pattern(lines_pattern)
        else:
            # Invalidate all price list related caches
            deleted += self.cache.delete_pattern(f"{self.prefix}_lists:*")
            deleted += self.cache.delete_pattern(f"{self.prefix}_lines:*")

        # Always invalidate pricing calculations when price lists change
        deleted += self.cache.delete_pattern(f"{self.prefix}_product:*")
        deleted += self.cache.delete_pattern(f"{self.prefix}_bulk:*")

        if deleted > 0:
            logger.info(
                f"Invalidated {deleted} pricing cache keys for price list: {price_list_id or 'all'}"
            )

        return deleted


# Global pricing cache instance
pricing_cache = PricingCache()

# Register with invalidation manager
from src.shared.cache_invalidation import cache_invalidation_manager
from src.config.constants import Collections

cache_invalidation_manager.register_domain_cache(Collections.PRICE_LISTS, pricing_cache)
