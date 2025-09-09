"""
Stores caching module for improved performance
"""

from typing import Optional, List, Dict, Any
from src.shared.core_cache import core_cache
from src.config.constants import (
    DEFAULT_STORES_LIMIT,
)


class StoresCache:
    """Cache manager for stores data (excluding location-based searches)"""

    def __init__(self):
        self.cache = core_cache
        self.cache_ttl = 300  # 5 minutes

    # Store-specific cache keys
    def _get_all_stores_key(self) -> str:
        return "stores:all"

    def _get_store_key(self, store_id: str) -> str:
        return f"stores:store:{store_id}"

    def _get_active_stores_key(self) -> str:
        return "stores:active"

    # Cache operations for all stores
    def get_all_stores(
        self, active_only: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """Get cached stores data"""
        cache_key = (
            self._get_active_stores_key() if active_only else self._get_all_stores_key()
        )
        return self.cache.get(cache_key)

    def set_all_stores(
        self, stores: List[Dict[str, Any]], active_only: bool = False
    ) -> None:
        """Cache stores data"""
        cache_key = (
            self._get_active_stores_key() if active_only else self._get_all_stores_key()
        )
        self.cache.set(cache_key, stores, ttl_seconds=self.cache_ttl)

    # Cache operations for individual stores
    def get_store(self, store_id: str) -> Optional[Dict[str, Any]]:
        """Get cached individual store"""
        return self.cache.get(self._get_store_key(store_id))

    def set_store(self, store_id: str, store_data: Dict[str, Any]) -> None:
        """Cache individual store"""
        self.cache.set(
            self._get_store_key(store_id), store_data, ttl_seconds=self.cache_ttl
        )

    def delete_store(self, store_id: str) -> None:
        """Remove store from cache"""
        self.cache.delete(self._get_store_key(store_id))

    # Cache invalidation
    def invalidate_stores_cache(self) -> None:
        """Invalidate all stores cache when data changes"""
        # Clear all stores caches
        self.cache.delete(self._get_all_stores_key())
        self.cache.delete(self._get_active_stores_key())

    def invalidate_store_cache(self, store_id: str) -> None:
        """Invalidate specific store cache"""
        self.delete_store(store_id)
        # Also invalidate general caches as they might contain this store
        self.invalidate_stores_cache()


# Global cache instance
stores_cache = StoresCache()