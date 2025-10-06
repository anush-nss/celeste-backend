import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class CacheItem:
    """Cache item with TTL and metadata"""

    data: Any
    created_at: float
    ttl: int
    hits: int = 0


class CacheService:
    """High-performance in-memory cache with TTL and LRU eviction"""

    def __init__(self, max_size: int = 10000):
        self._cache: Dict[str, CacheItem] = {}
        self._access_order: Dict[str, float] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        async with self._lock:
            if key not in self._cache:
                return None

            item = self._cache[key]

            # Check TTL
            if time.time() - item.created_at > item.ttl:
                del self._cache[key]
                if key in self._access_order:
                    del self._access_order[key]
                return None

            # Update access order and hit count
            self._access_order[key] = time.time()
            item.hits += 1

            return item.data

    async def set(self, key: str, data: Any, ttl: int = 300) -> None:
        """Set item in cache with TTL"""
        async with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self._max_size and key not in self._cache:
                await self._evict_lru()

            self._cache[key] = CacheItem(
                data=data, created_at=time.time(), ttl=ttl, hits=0
            )
            self._access_order[key] = time.time()

    async def delete(self, key: str) -> bool:
        """Delete item from cache"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_order:
                    del self._access_order[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all cache items"""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()

    async def _evict_lru(self) -> None:
        """Evict least recently used item"""
        if not self._access_order:
            return

        # Find LRU item
        lru_key = min(self._access_order.items(), key=lambda x: x[1])[0]

        # Remove LRU item
        if lru_key in self._cache:
            del self._cache[lru_key]
        del self._access_order[lru_key]

    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        async with self._lock:
            total_hits = sum(item.hits for item in self._cache.values())
            expired_count = sum(
                1
                for item in self._cache.values()
                if time.time() - item.created_at > item.ttl
            )

            return {
                "total_items": len(self._cache),
                "max_size": self._max_size,
                "total_hits": total_hits,
                "expired_items": expired_count,
                "hit_rate": total_hits / max(len(self._cache), 1),
            }

    def generate_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments"""
        key_data = {"args": args, "kwargs": kwargs}
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()


# Global cache instance
cache_service = CacheService()
