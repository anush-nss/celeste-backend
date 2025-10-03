"""
Tiers-specific cache operations
"""

from typing import List, Optional

from src.config.cache_config import cache_config
from src.shared.cache_invalidation import cache_invalidation_manager
from src.shared.core_cache import core_cache
from src.shared.utils import get_logger
from src.config.constants import Collections

logger = get_logger(__name__)


class TiersCache:
    """Tiers domain cache operations"""

    def __init__(self):
        self.cache = core_cache
        self.prefix = cache_config.PREFIXES.get("customer_tiers", "customer_tiers")

    # Cache key generators
    def get_tier_key(self, tier_id: str) -> str:
        """Generate cache key for tier data"""
        return self.cache.generate_key(self.prefix, tier_id)

    def get_tier_by_code_key(self, tier_code: str) -> str:
        """Generate cache key for tier data by code"""
        return self.cache.generate_key(self.prefix, f"code:{tier_code}")

    def get_all_tiers_key(self) -> str:
        """Generate cache key for all tiers"""
        return self.cache.generate_key(self.prefix, "all")

    def get_default_tier_key(self) -> str:
        """Generate cache key for default tier"""
        return self.cache.generate_key(self.prefix, "default")

    # Cache operations with domain-specific TTL
    def get_tier(self, tier_id: str) -> Optional[dict]:
        """Get cached tier data"""
        key = self.get_tier_key(tier_id)
        return self.cache.get(key)

    def set_tier(self, tier_id: str, tier_data: dict) -> bool:
        """Cache tier data with configured TTL"""
        key = self.get_tier_key(tier_id)
        ttl = cache_config.get_ttl("tiers")  # Use tiers TTL for tiers
        return self.cache.set(key, tier_data, ttl_seconds=ttl)

    def get_tier_by_code(self, tier_code: str) -> Optional[dict]:
        """Get cached tier data by code"""
        key = self.get_tier_by_code_key(tier_code)
        return self.cache.get(key)

    def set_tier_by_code(self, tier_code: str, tier_data: dict) -> bool:
        """Cache tier data by code with configured TTL"""
        key = self.get_tier_by_code_key(tier_code)
        ttl = cache_config.get_ttl("tiers")
        return self.cache.set(key, tier_data, ttl_seconds=ttl)

    def get_all_tiers(self) -> Optional[List]:
        """Get cached all tiers"""
        key = self.get_all_tiers_key()
        return self.cache.get(key)

    def set_all_tiers(self, tiers: List) -> bool:
        """Cache all tiers with configured TTL"""
        key = self.get_all_tiers_key()
        ttl = cache_config.get_ttl("tiers")
        return self.cache.set(key, tiers, ttl_seconds=ttl)

    def get_default_tier(self) -> Optional[str]:
        """Get cached default tier"""
        key = self.get_default_tier_key()
        return self.cache.get(key)

    def set_default_tier(self, tier_code: str) -> bool:
        """Cache default tier with configured TTL"""
        key = self.get_default_tier_key()
        ttl = cache_config.get_ttl("tiers")
        return self.cache.set(key, tier_code, ttl_seconds=ttl)

    # Cache invalidation methods
    def invalidate_tier_cache(
        self, tier_id: Optional[str] = None, tier_code: Optional[str] = None
    ) -> int:
        """Invalidate cache for specific tier or all tiers"""
        deleted = 0

        if tier_id:
            tier_key = self.get_tier_key(tier_id)
            if self.cache.delete(tier_key):
                deleted += 1

        if tier_code:
            tier_by_code_key = self.get_tier_by_code_key(tier_code)
            if self.cache.delete(tier_by_code_key):
                deleted += 1

        if not tier_id and not tier_code:
            # Invalidate all tiers
            deleted += self.cache.delete_pattern(f"{self.prefix}:*")

        if deleted > 0:
            logger.info(
                f"Invalidated {deleted} tiers cache keys for tier: {tier_id or tier_code or 'all'}"
            )

        return deleted


# Global tiers cache instance
tiers_cache = TiersCache()

cache_invalidation_manager.register_domain_cache(
    Collections.CUSTOMER_TIERS, tiers_cache
)
