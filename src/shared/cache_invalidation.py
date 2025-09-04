"""
Centralized cache invalidation for cross-domain dependencies
"""

from typing import Optional
from src.shared.utils import get_logger

logger = get_logger(__name__)


class CacheInvalidationManager:
    """Manages cross-domain cache invalidation"""
    
    def __init__(self):
        self._domain_caches = {}
    
    def register_domain_cache(self, domain: str, cache_instance):
        """Register a domain cache for cross-domain invalidation"""
        self._domain_caches[domain] = cache_instance
        logger.debug(f"Registered cache for domain: {domain}")
    
    def invalidate_pricing_dependencies(self, changed_domain: str, changed_id: Optional[str] = None) -> int:
        """Invalidate pricing caches when dependencies change"""
        total_deleted = 0
        
        # Get pricing cache
        pricing_cache = self._domain_caches.get('pricing')
        if not pricing_cache:
            logger.warning("Pricing cache not registered for cross-domain invalidation")
            return 0
        
        logger.debug(f"Invalidating pricing caches due to {changed_domain} change: {changed_id or 'all'}")
        
        # Invalidate pricing calculations when dependencies change
        if changed_domain in ['tiers', 'categories', 'products', 'price_lists']:
            total_deleted += pricing_cache.invalidate_pricing_cache('pricing')
        
        return total_deleted
    
    def invalidate_cross_domain_dependencies(self, changed_domain: str, changed_id: Optional[str] = None) -> int:
        """Invalidate all cross-domain dependencies"""
        total_deleted = 0
        
        # Domain dependency mapping
        dependency_map = {
            'tiers': ['pricing'],  # Tier changes affect pricing
            'categories': ['pricing'],  # Category changes might affect pricing
            'products': ['pricing'],  # Product changes affect pricing
            'price_lists': ['pricing'],  # Price list changes affect pricing
        }
        
        affected_domains = dependency_map.get(changed_domain, [])
        
        for affected_domain in affected_domains:
            if affected_domain == 'pricing':
                total_deleted += self.invalidate_pricing_dependencies(changed_domain, changed_id)
            # Add more domain-specific invalidations here as needed
        
        return total_deleted


# Global cache invalidation manager
cache_invalidation_manager = CacheInvalidationManager()
