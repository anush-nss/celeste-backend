import threading
import time
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass
from functools import wraps
import logging

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for a request"""
    endpoint: str
    duration_ms: float
    query_count: int
    cache_hits: int
    cache_misses: int
    memory_usage_mb: Optional[float] = None
    status_code: int = 200


class PerformanceMonitor:
    """Monitor and track performance metrics"""

    def __init__(self):
        self.metrics: Dict[str, list] = {}
        self.active_requests: Dict[str, dict] = {}

    def start_request(self, request_id: str, endpoint: str) -> None:
        """Start monitoring a request"""
        self.active_requests[request_id] = {
            "endpoint": endpoint,
            "start_time": time.time(),
            "query_count": 0,
            "cache_hits": 0,
            "cache_misses": 0
        }

    def end_request(self, request_id: str, status_code: int = 200) -> Optional[PerformanceMetrics]:
        """End monitoring and record metrics"""
        if request_id not in self.active_requests:
            return None

        request_data = self.active_requests.pop(request_id)
        duration_ms = (time.time() - request_data["start_time"]) * 1000

        metrics = PerformanceMetrics(
            endpoint=request_data["endpoint"],
            duration_ms=duration_ms,
            query_count=request_data["query_count"],
            cache_hits=request_data["cache_hits"],
            cache_misses=request_data["cache_misses"],
            status_code=status_code
        )

        # Store metrics for analysis
        endpoint = request_data["endpoint"]
        if endpoint not in self.metrics:
            self.metrics[endpoint] = []
        self.metrics[endpoint].append(metrics)

        # Keep only last 1000 metrics per endpoint
        if len(self.metrics[endpoint]) > 1000:
            self.metrics[endpoint] = self.metrics[endpoint][-1000:]

        # Log slow requests
        if duration_ms > 1000:  # > 1 second
            logger.warning(f"Slow request: {endpoint} took {duration_ms:.2f}ms")

        return metrics

    def record_query(self, request_id: str) -> None:
        """Record a database query"""
        if request_id in self.active_requests:
            self.active_requests[request_id]["query_count"] += 1

    def record_cache_hit(self, request_id: str) -> None:
        """Record a cache hit"""
        if request_id in self.active_requests:
            self.active_requests[request_id]["cache_hits"] += 1

    def record_cache_miss(self, request_id: str) -> None:
        """Record a cache miss"""
        if request_id in self.active_requests:
            self.active_requests[request_id]["cache_misses"] += 1

    def get_endpoint_stats(self, endpoint: str) -> Dict[str, Any]:
        """Get statistics for an endpoint"""
        if endpoint not in self.metrics or not self.metrics[endpoint]:
            return {"error": "No data available"}

        metrics_list = self.metrics[endpoint]
        durations = [m.duration_ms for m in metrics_list]
        query_counts = [m.query_count for m in metrics_list]

        return {
            "endpoint": endpoint,
            "total_requests": len(metrics_list),
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "p95_duration_ms": sorted(durations)[int(0.95 * len(durations))],
            "avg_queries_per_request": sum(query_counts) / len(query_counts),
            "total_cache_hits": sum(m.cache_hits for m in metrics_list),
            "total_cache_misses": sum(m.cache_misses for m in metrics_list),
            "cache_hit_ratio": sum(m.cache_hits for m in metrics_list) / max(sum(m.cache_hits + m.cache_misses for m in metrics_list), 1),
            "error_rate": sum(1 for m in metrics_list if m.status_code >= 400) / len(metrics_list)
        }

    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all endpoints"""
        return {
            endpoint: self.get_endpoint_stats(endpoint)
            for endpoint in self.metrics.keys()
        }


# Global performance monitor
performance_monitor = PerformanceMonitor()


def monitor_performance(endpoint_name: Optional[str] = None):
    """Decorator to monitor function performance"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            endpoint = endpoint_name or f"{func.__module__}.{func.__name__}"
            request_id = f"{endpoint}_{time.time()}_{id(asyncio.current_task())}"

            performance_monitor.start_request(request_id, endpoint)
            try:
                result = await func(*args, **kwargs)
                performance_monitor.end_request(request_id, 200)
                return result
            except Exception as e:
                performance_monitor.end_request(request_id, 500)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            endpoint = endpoint_name or f"{func.__module__}.{func.__name__}"
            request_id = f"{endpoint}_{time.time()}_{id(threading.current_thread())}"

            performance_monitor.start_request(request_id, endpoint)
            try:
                result = func(*args, **kwargs)
                performance_monitor.end_request(request_id, 200)
                return result
            except Exception as e:
                performance_monitor.end_request(request_id, 500)
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


def log_performance_summary():
    """Log performance summary for all endpoints"""
    stats = performance_monitor.get_all_stats()
    for endpoint, data in stats.items():
        if "error" not in data:
            logger.info(
                f"Performance Summary - {endpoint}: "
                f"avg={data['avg_duration_ms']:.2f}ms, "
                f"p95={data['p95_duration_ms']:.2f}ms, "
                f"queries={data['avg_queries_per_request']:.1f}, "
                f"cache_hit_ratio={data['cache_hit_ratio']:.2%}"
            )


# Add performance monitoring to critical functions
def track_query():
    """Context manager to track database queries"""
    class QueryTracker:
        def __init__(self):
            self.request_id = None

        def __enter__(self):
            # Try to get current request ID from context
            try:
                task = asyncio.current_task()
                if task:
                    self.request_id = f"query_{id(task)}"
                    performance_monitor.record_query(self.request_id)
            except:
                pass
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    return QueryTracker()