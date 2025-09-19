"""
Centralized cache invalidation manager for all domains
"""

from typing import Optional, Dict, Any, List, Callable
from src.shared.utils import get_logger
from src.config.constants import Collections, CacheScopes
from src.config.cache_config import cache_config

logger = get_logger(__name__)


# Use the constants from config
CacheInvalidationScope = CacheScopes


class CacheInvalidationManager:
    """Centralized manager for all cache invalidation operations"""

    def __init__(self):
        self._domain_caches: Dict[str, Any] = {}
        self._invalidation_hooks: Dict[str, List[Callable]] = {}
        self._dependency_map: Dict[str, List[str]] = {
            # Core domain dependencies
            Collections.CUSTOMER_TIERS: [Collections.PRICE_LISTS, Collections.PRODUCTS],
            Collections.CATEGORIES: [Collections.PRICE_LISTS, Collections.PRODUCTS],
            Collections.PRODUCTS: [Collections.PRICE_LISTS],
            Collections.PRICE_LISTS: [Collections.PRICE_LISTS],  # Price list changes affect pricing cache
            Collections.STORES: [],  # Stores don't affect other domains currently
        }

    def register_domain_cache(self, domain: str, cache_instance):
        """Register a domain cache for centralized invalidation"""
        self._domain_caches[domain] = cache_instance
        logger.debug(f"Registered cache for domain: {domain}")

    def register_invalidation_hook(self, domain: str, hook: Callable):
        """Register custom invalidation hook for domain"""
        if domain not in self._invalidation_hooks:
            self._invalidation_hooks[domain] = []
        self._invalidation_hooks[domain].append(hook)
        logger.debug(f"Registered invalidation hook for domain: {domain}")

    def invalidate_entity(
        self, 
        domain: str, 
        entity_id: Optional[str] = None, 
        scope: CacheInvalidationScope = CacheInvalidationScope.SPECIFIC
    ) -> int:
        """Main entry point for all cache invalidation operations"""
        total_deleted = 0
        
        logger.info(
            f"Starting cache invalidation for domain: {domain}, "
            f"entity: {entity_id or 'all'}, scope: {scope.value}"
        )

        # Step 1: Invalidate the primary domain cache
        total_deleted += self._invalidate_domain_cache(domain, entity_id)
        
        # Step 2: Execute custom hooks for this domain
        total_deleted += self._execute_invalidation_hooks(domain, entity_id)
        
        # Step 3: Handle cross-domain dependencies if needed
        if scope in [CacheInvalidationScope.CROSS_DOMAIN, CacheInvalidationScope.GLOBAL]:
            total_deleted += self._invalidate_dependencies(domain, entity_id)
        
        # Step 4: Global invalidation if requested
        if scope == CacheInvalidationScope.GLOBAL:
            total_deleted += self._invalidate_all_caches()
        
        logger.info(f"Cache invalidation completed. Total keys deleted: {total_deleted}")
        return total_deleted

    def _invalidate_domain_cache(self, domain: str, entity_id: Optional[str] = None) -> int:
        """Invalidate cache for a specific domain"""
        cache_instance = self._domain_caches.get(domain)
        if not cache_instance:
            logger.warning(f"No cache registered for domain: {domain}")
            return 0
        
        deleted = 0
        
        # Use domain-specific invalidation methods
        if domain == Collections.PRODUCTS:
            deleted = cache_instance.invalidate_product_cache(entity_id)
        elif domain == Collections.CATEGORIES:
            deleted = cache_instance.invalidate_category_cache(entity_id)
        elif domain == Collections.PRICE_LISTS:
            if entity_id:
                deleted = cache_instance.invalidate_price_list_cache(entity_id)
            else:
                deleted = cache_instance.invalidate_pricing_cache(cache_config.INVALIDATION_SCOPE_ALL)
        elif domain == Collections.CUSTOMER_TIERS:
            deleted = cache_instance.invalidate_tier_cache(entity_id)
        elif domain == Collections.STORES:
            if entity_id:
                cache_instance.invalidate_store_cache(entity_id)
                deleted = 1
            else:
                cache_instance.invalidate_stores_cache()
                deleted = 1
        else:
            logger.warning(f"No specific invalidation method for domain: {domain}")
            
        return deleted

    def _execute_invalidation_hooks(self, domain: str, entity_id: Optional[str] = None) -> int:
        """Execute custom invalidation hooks for domain"""
        hooks = self._invalidation_hooks.get(domain, [])
        total_deleted = 0
        
        for hook in hooks:
            try:
                result = hook(entity_id)
                if isinstance(result, int):
                    total_deleted += result
            except Exception as e:
                logger.error(f"Error executing invalidation hook for {domain}: {e}")
        
        return total_deleted

    def _invalidate_dependencies(self, changed_domain: str, entity_id: Optional[str] = None) -> int:
        """Invalidate caches that depend on the changed domain"""
        total_deleted = 0
        affected_domains = self._dependency_map.get(changed_domain, [])
        
        logger.debug(
            f"Invalidating dependencies for {changed_domain}: {affected_domains}"
        )
        
        for affected_domain in affected_domains:
            # Recursive invalidation for dependent domains
            total_deleted += self._invalidate_domain_cache(affected_domain)
            
        return total_deleted

    def _invalidate_all_caches(self) -> int:
        """Nuclear option: invalidate all registered caches"""
        total_deleted = 0
        
        logger.warning("Performing global cache invalidation (nuclear option)")
        
        for domain, cache_instance in self._domain_caches.items():
            try:
                total_deleted += self._invalidate_domain_cache(domain)
            except Exception as e:
                logger.error(f"Error during global invalidation of {domain}: {e}")
        
        return total_deleted

    # Convenience methods for common operations
    def invalidate_product(self, product_id: Optional[str] = None) -> int:
        """Convenience method for product invalidation"""
        return self.invalidate_entity(Collections.PRODUCTS, product_id, CacheScopes.CROSS_DOMAIN)
    
    def invalidate_category(self, category_id: Optional[int] = None) -> int:
        """Convenience method for category invalidation"""
        return self.invalidate_entity(Collections.CATEGORIES, str(category_id), CacheScopes.CROSS_DOMAIN)
    
    def invalidate_tier(self, tier_id: Optional[str] = None) -> int:
        """Convenience method for tier invalidation"""
        return self.invalidate_entity(Collections.CUSTOMER_TIERS, tier_id, CacheScopes.CROSS_DOMAIN)
    
    def invalidate_price_list(self, price_list_id: Optional[str] = None) -> int:
        """Convenience method for price list invalidation"""
        return self.invalidate_entity(Collections.PRICE_LISTS, price_list_id, CacheScopes.CROSS_DOMAIN)
    
    def invalidate_store(self, store_id: Optional[str] = None) -> int:
        """Convenience method for store invalidation"""
        return self.invalidate_entity(Collections.STORES, store_id, CacheScopes.SPECIFIC)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about registered caches"""
        stats = {
            "registered_domains": list(self._domain_caches.keys()),
            "dependency_map": self._dependency_map,
            "hooks_registered": {
                domain: len(hooks) for domain, hooks in self._invalidation_hooks.items()
            }
        }
        
        # Get individual cache stats if available
        for domain, cache_instance in self._domain_caches.items():
            if hasattr(cache_instance, 'cache') and hasattr(cache_instance.cache, 'get_cache_stats'):
                stats[f"{domain}_cache_stats"] = cache_instance.cache.get_cache_stats()
        
        return stats

    # Legacy methods for backward compatibility
    def invalidate_pricing_dependencies(
        self, changed_domain: str, changed_id: Optional[str] = None
    ) -> int:
        """Legacy method - use invalidate_entity instead"""
        logger.warning("invalidate_pricing_dependencies is deprecated, use invalidate_entity instead")
        return self._invalidate_dependencies(changed_domain, changed_id)

    def invalidate_cross_domain_dependencies(
        self, changed_domain: str, changed_id: Optional[str] = None
    ) -> int:
        """Legacy method - use invalidate_entity instead"""
        logger.warning("invalidate_cross_domain_dependencies is deprecated, use invalidate_entity instead")
        return self._invalidate_dependencies(changed_domain, changed_id)


# Global cache invalidation manager
cache_invalidation_manager = CacheInvalidationManager()
