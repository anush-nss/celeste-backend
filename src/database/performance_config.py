"""
Database performance configuration and optimization utilities.
"""

import os
from typing import Any, Dict, Optional

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool


class DatabasePerformanceConfig:
    """Centralized database performance configuration"""

    @staticmethod
    def get_connection_pool_config(environment: str = "development") -> Dict[str, Any]:
        """Get optimized connection pool configuration based on environment"""

        if environment == "production":
            return {
                "poolclass": QueuePool,
                "pool_size": int(os.getenv("DB_POOL_SIZE", "20")),
                "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "30")),
                "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
                "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),  # 1 hour
                "pool_pre_ping": True,
                "pool_reset_on_return": "commit",
            }
        elif environment == "staging":
            return {
                "poolclass": QueuePool,
                "pool_size": 15,
                "max_overflow": 20,
                "pool_timeout": 30,
                "pool_recycle": 3600,
                "pool_pre_ping": True,
                "pool_reset_on_return": "commit",
            }
        else:  # development
            return {
                "poolclass": QueuePool,
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30,
                "pool_recycle": -1,  # No recycling in development
                "pool_pre_ping": True,
                "pool_reset_on_return": "commit",
            }

    @staticmethod
    def get_engine_options(environment: str = "development") -> Dict[str, Any]:
        """Get optimized engine options"""
        base_options = {
            "echo": environment == "development",
            "echo_pool": False,
            "future": True,
            "connect_args": {
                "application_name": f"celeste_api_{environment}",
                "connect_timeout": 30,
            },
        }

        if environment == "production":
            base_options["connect_args"].update(
                {
                    "command_timeout": 60,
                    "server_settings": {
                        "jit": "off",  # Disable JIT for faster query compilation
                        "application_name": "celeste_api_prod",
                    },
                }
            )

        return base_options

    @staticmethod
    def setup_engine_events(engine: Engine):
        """Set up engine events for monitoring and optimization"""

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            """Optimize SQLite connections if using SQLite for development"""
            if "sqlite" in str(engine.url):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.close()

        @event.listens_for(engine, "connect")
        def set_postgresql_settings(dbapi_connection, connection_record):
            """Optimize PostgreSQL connections"""
            if "postgresql" in str(engine.url):
                cursor = dbapi_connection.cursor()
                # Set connection-level optimizations
                cursor.execute("SET statement_timeout = '30s'")
                cursor.execute("SET lock_timeout = '10s'")
                cursor.execute("SET idle_in_transaction_session_timeout = '5min'")
                cursor.close()


class QueryOptimizationConfig:
    """Query-level optimization configurations"""

    # Batch sizes for different operations
    BATCH_SIZES = {
        "bulk_insert": 1000,
        "bulk_update": 500,
        "bulk_select": 100,
        "pagination_default": 20,
        "pagination_max": 100,
    }

    # Cache TTL settings (seconds)
    CACHE_TTL = {
        "categories": 3600,  # 1 hour
        "products": 1800,  # 30 minutes
        "price_lists": 1800,  # 30 minutes
        "tiers": 3600,  # 1 hour
        "user_profile": 900,  # 15 minutes
        "stores": 1800,  # 30 minutes
    }

    # Query timeout settings (seconds)
    QUERY_TIMEOUTS = {
        "simple_select": 5,
        "complex_join": 15,
        "bulk_operation": 30,
        "report_query": 60,
    }

    @staticmethod
    def get_eager_loading_strategy(entity_name: str) -> str:
        """Get optimal loading strategy for different entities"""
        strategies = {
            "products": "selectinload",  # Good for one-to-many
            "categories": "selectinload",
            "users": "selectinload",
            "orders": "joinedload",  # Good for many-to-one
            "price_lists": "selectinload",
        }
        return strategies.get(entity_name, "selectinload")


class IndexOptimizationConfig:
    """Database index optimization configurations"""

    # Critical indexes for performance
    PERFORMANCE_INDEXES = {
        "users": [
            ("firebase_uid",),  # Primary lookups
            ("email",),  # Login lookups
            ("tier_id",),  # Tier-based queries
            ("role", "is_delivery"),  # Role filtering
        ],
        "products": [
            ("name",),  # Search queries
            ("brand",),  # Brand filtering
            ("base_price",),  # Price sorting
            ("created_at",),  # Recent products
        ],
        "addresses": [
            ("user_id", "is_default"),  # User's default address
            ("latitude", "longitude"),  # Geo queries
        ],
        "orders": [
            ("userId", "status"),  # User order history
            ("createdAt",),  # Order timeline
            ("status",),  # Status filtering
        ],
        "price_lists": [
            ("is_active", "priority"),  # Active price lists
            ("valid_from", "valid_until"),  # Date range queries
        ],
        "cart": [
            ("user_id", "product_id"),  # Cart operations
        ],
    }

    @staticmethod
    def get_composite_indexes() -> Dict[str, list]:
        """Get composite indexes for complex queries"""
        return {
            "products": [
                ("brand", "base_price", "created_at"),  # Product catalog queries
            ],
            "users": [
                ("role", "tier_id", "total_orders"),  # User analytics
            ],
            "price_list_lines": [
                ("price_list_id", "is_active", "min_quantity"),  # Pricing calculations
            ],
        }


class CacheOptimizationConfig:
    """Caching strategy configuration"""

    # Cache key patterns
    CACHE_KEY_PATTERNS = {
        "user_profile": "user:profile:{user_id}",
        "user_tier": "user:tier:{user_id}",
        "product_details": "product:details:{product_id}",
        "product_pricing": "product:pricing:{product_id}:{tier_id}",
        "category_tree": "categories:tree",
        "active_price_lists": "price_lists:active:{tier_id}",
        "store_locations": "stores:all:{active_only}",
    }

    # Cache invalidation patterns
    INVALIDATION_PATTERNS = {
        "user_update": ["user:profile:{user_id}", "user:tier:{user_id}"],
        "product_update": [
            "product:details:{product_id}",
            "product:pricing:{product_id}:*",
        ],
        "price_list_update": ["price_lists:active:*", "product:pricing:*"],
        "tier_update": ["user:tier:*", "price_lists:active:*"],
    }

    @staticmethod
    def should_cache(operation_type: str, data_size: int) -> bool:
        """Determine if operation result should be cached"""
        cache_rules = {
            "user_profile": data_size < 10000,  # Cache small user profiles
            "product_list": data_size < 100000,  # Cache reasonable product lists
            "category_tree": data_size < 50000,  # Always cache categories
            "price_calculation": True,  # Always cache pricing
        }
        return cache_rules.get(operation_type, data_size < 50000)


class MonitoringConfig:
    """Performance monitoring configuration"""

    # Slow query thresholds (seconds)
    SLOW_QUERY_THRESHOLDS = {
        "select": 1.0,
        "insert": 0.5,
        "update": 0.8,
        "delete": 1.0,
        "bulk_operation": 5.0,
    }

    # Resource utilization alerts
    RESOURCE_ALERTS = {
        "connection_pool_usage": 0.8,  # Alert when 80% of pool is used
        "query_timeout_rate": 0.05,  # Alert when 5% of queries timeout
        "cache_miss_rate": 0.3,  # Alert when cache miss rate > 30%
        "memory_usage": 0.85,  # Alert when memory usage > 85%
    }

    # Performance metrics to track
    METRICS_TO_TRACK = [
        "query_duration",
        "connection_pool_size",
        "cache_hit_ratio",
        "database_connections_active",
        "slow_query_count",
        "error_rate",
        "throughput_per_second",
    ]


# Configuration factory
def get_performance_config(environment: Optional[str] = None) -> Dict[str, Any]:
    """Get complete performance configuration for the given environment"""
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development")

    return {
        "database": {
            "pool": DatabasePerformanceConfig.get_connection_pool_config(environment),
            "engine": DatabasePerformanceConfig.get_engine_options(environment),
        },
        "query": {
            "batch_sizes": QueryOptimizationConfig.BATCH_SIZES,
            "timeouts": QueryOptimizationConfig.QUERY_TIMEOUTS,
            "cache_ttl": QueryOptimizationConfig.CACHE_TTL,
        },
        "indexes": {
            "performance": IndexOptimizationConfig.PERFORMANCE_INDEXES,
            "composite": IndexOptimizationConfig.get_composite_indexes(),
        },
        "cache": {
            "key_patterns": CacheOptimizationConfig.CACHE_KEY_PATTERNS,
            "invalidation": CacheOptimizationConfig.INVALIDATION_PATTERNS,
        },
        "monitoring": {
            "thresholds": MonitoringConfig.SLOW_QUERY_THRESHOLDS,
            "alerts": MonitoringConfig.RESOURCE_ALERTS,
            "metrics": MonitoringConfig.METRICS_TO_TRACK,
        },
    }
