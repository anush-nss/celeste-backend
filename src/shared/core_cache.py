"""
Core cache client with basic caching functionality
"""

import hashlib
import threading
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List
from src.shared.utils import get_logger
from src.config.cache_config import cache_config

logger = get_logger(__name__)


class CacheEntry:
    """Cache entry with expiration time"""
    def __init__(self, value: Any, ttl_seconds: Optional[int] = None):
        self.value = value
        ttl = ttl_seconds or cache_config.DEFAULT_TTL
        self.expires_at = datetime.now() + timedelta(seconds=ttl)
    
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at


class CoreCacheClient:
    """Core cache client with basic operations"""
    
    def __init__(self):
        # In-memory cache storage
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._last_cleanup = datetime.now()
        self._cleanup_interval = timedelta(minutes=cache_config.CLEANUP_INTERVAL_MINUTES)
        
        # Redis configuration
        self.redis_client = None
        self.use_redis = cache_config.USE_REDIS
        
        logger.info("Core cache client initialized with in-memory storage")
    
    def _cleanup_if_needed(self):
        """Clean up expired entries periodically"""
        if not self.use_redis:  # Only needed for in-memory
            now = datetime.now()
            if now - self._last_cleanup > self._cleanup_interval:
                expired_keys = [
                    key for key, entry in self._cache.items() 
                    if entry.is_expired()
                ]
                
                for key in expired_keys:
                    del self._cache[key]
                
                if expired_keys:
                    logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
                
                self._last_cleanup = now
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if self.use_redis and self.redis_client:
            # Redis implementation (for future)
            try:
                import pickle
                data = self.redis_client.get(key)
                return pickle.loads(data) if data else None
            except Exception as e:
                logger.error(f"Redis get error: {e}")
                return None
        else:
            # In-memory implementation
            with self._lock:
                self._cleanup_if_needed()
                
                if key in self._cache:
                    entry = self._cache[key]
                    if entry.is_expired():
                        del self._cache[key]
                        return None
                    return entry.value
                return None
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        """Set value in cache with TTL"""
        if self.use_redis and self.redis_client:
            # Redis implementation (for future)
            try:
                import pickle
                data = pickle.dumps(value)
                ttl = ttl_seconds or cache_config.DEFAULT_TTL
                return self.redis_client.setex(key, ttl, data)
            except Exception as e:
                logger.error(f"Redis set error: {e}")
                return False
        else:
            # In-memory implementation
            with self._lock:
                ttl = ttl_seconds or cache_config.DEFAULT_TTL
                self._cache[key] = CacheEntry(value, ttl)
                return True
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if self.use_redis and self.redis_client:
            # Redis implementation (for future)
            try:
                return bool(self.redis_client.delete(key))
            except Exception as e:
                logger.error(f"Redis delete error: {e}")
                return False
        else:
            # In-memory implementation
            with self._lock:
                if key in self._cache:
                    del self._cache[key]
                    return True
                return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern"""
        if self.use_redis and self.redis_client:
            # Redis implementation (for future)
            try:
                keys_list = list(self.redis_client.keys(pattern))
                if keys_list:
                    return self.redis_client.delete(*keys_list)
                return 0
            except Exception as e:
                logger.error(f"Redis delete pattern error: {e}")
                return 0
        else:
            # In-memory implementation
            with self._lock:
                deleted = 0
                keys_to_delete = []
                
                for key in self._cache.keys():
                    if self._match_pattern(key, pattern):
                        keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    del self._cache[key]
                    deleted += 1
                
                return deleted
    
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """Simple pattern matching for in-memory cache"""
        if pattern.endswith('*'):
            return key.startswith(pattern[:-1])
        return key == pattern
    
    def generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key with consistent hashing"""
        key_parts = [prefix] + [str(arg) for arg in args]
        if kwargs:
            sorted_kwargs = sorted(kwargs.items())
            key_parts.extend(f"{k}={v}" for k, v in sorted_kwargs)
        
        key_data = ":".join(key_parts)
        
        # Hash long keys to keep them manageable
        if len(key_data) > 200:
            key_hash = hashlib.md5(key_data.encode()).hexdigest()
            return f"{prefix}:hash:{key_hash}"
        
        return key_data
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if self.use_redis and self.redis_client:
            try:
                info = self.redis_client.info()
                return {
                    "backend": "redis",
                    "used_memory": info.get("used_memory_human", "unknown"),
                    "connected_clients": info.get("connected_clients", 0),
                    "keyspace_hits": info.get("keyspace_hits", 0),
                    "keyspace_misses": info.get("keyspace_misses", 0)
                }
            except Exception:
                return {"backend": "redis", "status": "error"}
        else:
            # In-memory stats
            with self._lock:
                total_keys = len(self._cache)
                expired_keys = sum(1 for entry in self._cache.values() if entry.is_expired())
                
                # Count by prefix
                prefix_counts = {}
                for key in self._cache.keys():
                    prefix = key.split(':', 1)[0] if ':' in key else key
                    prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
                
                return {
                    "backend": "in_memory",
                    "total_keys": total_keys,
                    "active_keys": total_keys - expired_keys,
                    "expired_keys": expired_keys,
                    "prefix_breakdown": prefix_counts
                }


# Global core cache client instance
core_cache = CoreCacheClient()