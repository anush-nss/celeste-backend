from typing import List, Optional

from src.api.products.cache import products_cache
from src.api.tags.models import CreateTagSchema
from src.api.tags.service import TagService as BaseTagService
from src.config.constants import Collections
from src.database.models.product import Tag
from src.shared.cache_invalidation import cache_invalidation_manager
from src.shared.error_handler import ErrorHandler


class ProductTagService:
    """Handles tag management for products"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.tag_service = BaseTagService(entity_type="product")

    async def create_product_tag(
        self,
        name: str,
        tag_type_suffix: str,
        slug: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Tag:
        """Create a new product tag with specific type (e.g., 'color', 'size')"""
        tag_data = CreateTagSchema(
            tag_type=tag_type_suffix,  # Will become "product_{tag_type_suffix}"
            name=name,
            slug=slug,
            description=description,
        )
        return await self.tag_service.create_tag(tag_data)

    async def create_product_tags(self, tags_data: list[CreateTagSchema]) -> list[Tag]:
        """Create multiple new product tags with specific type (e.g., 'color', 'size')"""
        return await self.tag_service.create_tags(tags_data)

    async def get_product_tags(
        self, is_active: bool = True, tag_type_suffix: Optional[str] = None
    ) -> List[Tag]:
        """Get product tags, optionally filtered by type suffix (e.g., 'color', 'size')"""
        return await self.tag_service.get_tags_by_type(is_active, tag_type_suffix)

    async def assign_tag_to_product(
        self, product_id: int, tag_id: int, value: Optional[str] = None
    ):
        """Assign a tag to a product using shared TagService"""
        await self.tag_service.assign_tag_to_entity(product_id, tag_id, value)

        # Invalidate cache
        products_cache.invalidate_product_cache(str(product_id))
        cache_invalidation_manager.invalidate_entity(
            Collections.PRODUCTS, str(product_id)
        )

    async def remove_tag_from_product(self, product_id: int, tag_id: int) -> bool:
        """Remove a tag from a product using shared TagService"""
        success = await self.tag_service.remove_tag_from_entity(product_id, tag_id)

        if success:
            # Invalidate cache
            products_cache.invalidate_product_cache(str(product_id))
            cache_invalidation_manager.invalidate_entity(
                Collections.PRODUCTS, str(product_id)
            )

        return success
