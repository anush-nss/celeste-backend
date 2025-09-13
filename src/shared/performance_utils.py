"""
Performance utilities for database operations and caching.
"""
import asyncio
from typing import List, Dict, Any, Optional, TypeVar, Generic, Callable
from functools import wraps
import time
from sqlalchemy import select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.utils import get_logger

logger = get_logger(__name__)

T = TypeVar('T')

class BatchProcessor(Generic[T]):
    """Utility for processing items in batches to prevent memory issues"""

    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size

    async def process_in_batches(
        self,
        items: List[T],
        processor: Callable[[List[T]], Any]
    ) -> List[Any]:
        """Process items in batches to manage memory usage"""
        results = []
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]
            try:
                batch_result = await processor(batch)
                if isinstance(batch_result, list):
                    results.extend(batch_result)
                else:
                    results.append(batch_result)
            except Exception as e:
                logger.error(f"Error processing batch {i//self.batch_size + 1}: {str(e)}")
                raise
        return results


class QueryOptimizer:
    """Utilities for optimizing database queries"""

    @staticmethod
    def build_eager_loading_query(base_query, relationships: List[str]):
        """Add eager loading to prevent N+1 queries"""
        query = base_query

        # Get the model class from the query
        model_class = base_query.column_descriptions[0]['entity']

        for relationship in relationships:
            if '.' in relationship:
                # Handle nested relationships like 'product_tags.tag'
                # For now, use simple selectinload for the full dotted path
                # This is a simplified approach that works for most cases
                parts = relationship.split('.')
                current_attr = getattr(model_class, parts[0])
                load_option = selectinload(current_attr)

                # For nested relationships, chain them
                current_model = current_attr.property.mapper.class_
                for part in parts[1:]:
                    nested_attr = getattr(current_model, part)
                    load_option = load_option.selectinload(nested_attr)
                    current_model = nested_attr.property.mapper.class_

                query = query.options(load_option)
            else:
                # Simple relationship
                relationship_attr = getattr(model_class, relationship)
                query = query.options(selectinload(relationship_attr))

        return query

    @staticmethod
    async def get_with_cache_check(
        session: AsyncSession,
        cache_key: str,
        query_builder: Callable[[], Any],
        cache_manager: Optional[Any] = None
    ) -> Any:
        """Get data with cache check to reduce database load"""
        if cache_manager:
            cached_result = cache_manager.get(cache_key)
            if cached_result:
                return cached_result

        result = await query_builder()

        if cache_manager and result:
            cache_manager.set(cache_key, result)

        return result


def async_timer(operation_name: str):
    """Decorator to log operation timing for performance monitoring"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                if execution_time > 1.0:  # Log slow operations
                    logger.warning(f"Slow operation {operation_name}: {execution_time:.2f}s")
                else:
                    logger.debug(f"Operation {operation_name}: {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"Failed operation {operation_name} after {execution_time:.3f}s: {str(e)}")
                raise
        return wrapper
    return decorator


class ConnectionPoolOptimizer:
    """Utilities for database connection pool optimization"""

    @staticmethod
    def get_optimal_pool_settings(expected_concurrent_users: int) -> Dict[str, Any]:
        """Calculate optimal connection pool settings based on expected load"""
        # Conservative approach: 2-3 connections per concurrent user
        # with reasonable bounds
        pool_size = min(max(expected_concurrent_users * 2, 10), 50)
        max_overflow = min(pool_size * 2, 100)

        return {
            "pool_size": pool_size,
            "max_overflow": max_overflow,
            "pool_timeout": 30,
            "pool_recycle": 3600,  # 1 hour
            "pool_pre_ping": True,
        }


class PaginationOptimizer:
    """Optimized pagination for large datasets"""

    @staticmethod
    def build_cursor_pagination_query(
        base_query,
        cursor_field: str,
        cursor_value: Optional[Any] = None,
        limit: int = 20,
        ascending: bool = True
    ):
        """Build optimized cursor-based pagination query"""
        query = base_query

        # Get the model class from the query
        model_class = base_query.column_descriptions[0]['entity']
        cursor_column = getattr(model_class, cursor_field)

        if cursor_value is not None:
            if ascending:
                query = query.filter(cursor_column > cursor_value)
            else:
                query = query.filter(cursor_column < cursor_value)

        # Add ordering
        if ascending:
            query = query.order_by(cursor_column.asc())
        else:
            query = query.order_by(cursor_column.desc())

        # Get one extra item to determine if there are more pages
        return query.limit(limit + 1)


class MemoryOptimizer:
    """Utilities for memory management in large data operations"""

    @staticmethod
    async def stream_large_dataset(
        session: AsyncSession,
        query,
        batch_size: int = 1000,
        processor: Optional[Callable] = None
    ):
        """Stream large datasets to prevent memory exhaustion"""
        offset = 0
        while True:
            batch_query = query.offset(offset).limit(batch_size)
            batch_result = await session.execute(batch_query)
            batch_items = batch_result.scalars().all()

            if not batch_items:
                break

            if processor:
                yield await processor(batch_items)
            else:
                yield batch_items

            offset += batch_size

            # Clear session cache to prevent memory buildup
            session.expunge_all()


class CacheWarmer:
    """Utilities for cache warming and preloading"""

    @staticmethod
    async def warm_frequently_accessed_data(cache_manager, data_loaders: Dict[str, Callable]):
        """Pre-warm cache with frequently accessed data"""
        tasks = []
        for cache_key, loader in data_loaders.items():
            async def warm_cache(key: str, load_func: Callable):
                try:
                    data = await load_func()
                    cache_manager.set(key, data)
                    logger.info(f"Warmed cache for {key}")
                except Exception as e:
                    logger.error(f"Failed to warm cache for {key}: {str(e)}")

            tasks.append(warm_cache(cache_key, loader))

        await asyncio.gather(*tasks, return_exceptions=True)


# Performance monitoring utilities
class PerformanceMetrics:
    """Track performance metrics for monitoring and alerting"""

    def __init__(self):
        self.metrics = {}

    def record_operation(self, operation: str, duration: float, success: bool = True):
        """Record operation metrics"""
        if operation not in self.metrics:
            self.metrics[operation] = {
                'total_calls': 0,
                'total_duration': 0,
                'failures': 0,
                'avg_duration': 0,
                'max_duration': 0,
                'min_duration': float('inf')
            }

        metrics = self.metrics[operation]
        metrics['total_calls'] += 1
        metrics['total_duration'] += duration

        if not success:
            metrics['failures'] += 1

        metrics['avg_duration'] = metrics['total_duration'] / metrics['total_calls']
        metrics['max_duration'] = max(metrics['max_duration'], duration)
        metrics['min_duration'] = min(metrics['min_duration'], duration)

    def get_slow_operations(self, threshold_seconds: float = 1.0) -> List[Dict]:
        """Get operations that are performing slowly"""
        return [
            {'operation': op, **data}
            for op, data in self.metrics.items()
            if data['avg_duration'] > threshold_seconds
        ]

    def reset_metrics(self):
        """Reset all metrics"""
        self.metrics.clear()


# Global performance metrics instance
performance_metrics = PerformanceMetrics()