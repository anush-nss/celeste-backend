"""
Cache configuration settings
Centralized cache TTL values and settings for consistent caching across the application
"""

import os
from typing import Dict, Any


class CacheConfig:
    """Cache configuration with environment variable overrides"""

    # Default TTL values in seconds
    DEFAULT_TTL = int(os.getenv("CACHE_DEFAULT_TTL", "300"))  # 5 minutes

    # Domain-specific TTL values
    PRODUCT_PRICING_TTL = int(
        os.getenv("CACHE_PRODUCT_PRICING_TTL", "300")
    )  # 5 minutes
    BULK_PRICING_TTL = int(os.getenv("CACHE_BULK_PRICING_TTL", "300"))  # 5 minutes
    PRICE_LISTS_TTL = int(os.getenv("CACHE_PRICE_LISTS_TTL", "600"))  # 10 minutes
    PRICE_LIST_LINES_TTL = int(
        os.getenv("CACHE_PRICE_LIST_LINES_TTL", "600")
    )  # 10 minutes
    PRODUCT_DATA_TTL = int(os.getenv("CACHE_PRODUCT_DATA_TTL", "600"))  # 10 minutes
    USER_DATA_TTL = int(os.getenv("CACHE_USER_DATA_TTL", "900"))  # 15 minutes
    CATEGORY_DATA_TTL = int(os.getenv("CACHE_CATEGORY_DATA_TTL", "1800"))  # 30 minutes

    # Cache cleanup and maintenance
    CLEANUP_INTERVAL_MINUTES = int(
        os.getenv("CACHE_CLEANUP_INTERVAL", "5")
    )  # 5 minutes
    MAX_CACHE_SIZE_MB = int(os.getenv("CACHE_MAX_SIZE_MB", "100"))  # 100 MB limit

    # LRU Cache sizes
    LRU_PRICE_LISTS_SIZE = int(os.getenv("LRU_PRICE_LISTS_SIZE", "32"))
    LRU_PRICE_LIST_LINES_SIZE = int(os.getenv("LRU_PRICE_LIST_LINES_SIZE", "128"))
    LRU_PRODUCTS_SIZE = int(os.getenv("LRU_PRODUCTS_SIZE", "256"))
    LRU_USERS_SIZE = int(os.getenv("LRU_USERS_SIZE", "128"))
    LRU_CATEGORIES_SIZE = int(os.getenv("LRU_CATEGORIES_SIZE", "64"))
    LRU_TIERS_SIZE = int(os.getenv("LRU_TIERS_SIZE", "32"))
    LRU_DEFAULT_SIZE = int(os.getenv("LRU_DEFAULT_SIZE", "64"))

    # Cache prefixes for organization
    PREFIXES = {
        "bulk_pricing": "bulk_pricing",
        "product_pricing": "product_pricing",
        "price_lists": "price_lists",
        "price_list_lines": "price_list_lines",
        "products": "products",
        "users": "users",
        "categories": "categories",
        "orders": "orders",
        "inventory": "inventory",
        "customer_tiers": "customer_tiers",
    }
    
    # Cache invalidation scope constants
    INVALIDATION_SCOPE_ALL = "all"

    @classmethod
    def get_ttl(cls, cache_type: str) -> int:
        """Get TTL for specific cache type"""
        ttl_mapping = {
            "product_pricing": cls.PRODUCT_PRICING_TTL,
            "bulk_pricing": cls.BULK_PRICING_TTL,
            "price_lists": cls.PRICE_LISTS_TTL,
            "price_list_lines": cls.PRICE_LIST_LINES_TTL,
            "products": cls.PRODUCT_DATA_TTL,
            "users": cls.USER_DATA_TTL,
            "categories": cls.CATEGORY_DATA_TTL,
            "default": cls.DEFAULT_TTL,
        }
        return ttl_mapping.get(cache_type, cls.DEFAULT_TTL)

    @classmethod
    def get_lru_size(cls, cache_type: str) -> int:
        """Get LRU cache size for specific cache type"""
        size_mapping = {
            "price_lists": cls.LRU_PRICE_LISTS_SIZE,
            "price_list_lines": cls.LRU_PRICE_LIST_LINES_SIZE,
            "products": cls.LRU_PRODUCTS_SIZE,
            "users": cls.LRU_USERS_SIZE,
            "categories": cls.LRU_CATEGORIES_SIZE,
            "customer_tiers": cls.LRU_TIERS_SIZE,
        }
        return size_mapping.get(cache_type, cls.LRU_DEFAULT_SIZE)

    @classmethod
    def get_all_settings(cls) -> Dict[str, Any]:
        """Get all cache settings for debugging/monitoring"""
        return {
            "ttl_settings": {
                "default": cls.DEFAULT_TTL,
                "product_pricing": cls.PRODUCT_PRICING_TTL,
                "bulk_pricing": cls.BULK_PRICING_TTL,
                "price_lists": cls.PRICE_LISTS_TTL,
                "price_list_lines": cls.PRICE_LIST_LINES_TTL,
                "product_data": cls.PRODUCT_DATA_TTL,
                "user_data": cls.USER_DATA_TTL,
                "category_data": cls.CATEGORY_DATA_TTL,
            },
            "lru_sizes": {
                "price_lists": cls.LRU_PRICE_LISTS_SIZE,
                "price_list_lines": cls.LRU_PRICE_LIST_LINES_SIZE,
                "products": cls.LRU_PRODUCTS_SIZE,
                "users": cls.LRU_USERS_SIZE,
            },
            "maintenance": {
                "cleanup_interval_minutes": cls.CLEANUP_INTERVAL_MINUTES,
                "max_cache_size_mb": cls.MAX_CACHE_SIZE_MB,
            },
        }


# Global cache config instance
cache_config = CacheConfig()
