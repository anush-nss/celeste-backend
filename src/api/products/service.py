from typing import List, Optional

from src.api.products.models import (
    CreateProductSchema,
    EnhancedProductSchema,
    PaginatedProductsResponse,
    ProductQuerySchema,
    ProductSchema,
    UpdateProductSchema,
)
from src.api.products.services import (
    ProductBulkService,
    ProductCoreService,
    ProductInventoryService,
    ProductQueryService,
    ProductTagService,
)
from src.api.tags.models import CreateTagSchema
from src.database.models.product import Tag
from src.shared.error_handler import ErrorHandler


class ProductService:
    """Main product service that orchestrates specialized services"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.core_service = ProductCoreService()
        self.query_service = ProductQueryService()
        self.inventory_service = ProductInventoryService()
        self.tag_service = ProductTagService()
        self.bulk_service = ProductBulkService()

    # Core CRUD operations
    async def get_product_by_id(
        self,
        product_id: int,
        include_categories: bool = True,
        include_tags: bool = True,
        store_id: Optional[int] = None,
    ) -> EnhancedProductSchema | None:
        """Get product by ID with relationships and optional inventory."""
        product = await self.core_service.get_product_by_id(
            product_id, include_categories, include_tags
        )

        if product and store_id:
            product = await self.inventory_service.add_inventory_to_single_product(
                product, store_id
            )

        return product

    async def get_product_by_ref(
        self,
        product_ref: str,
        include_categories: bool = True,
        include_tags: bool = True,
        store_id: Optional[int] = None,
    ) -> EnhancedProductSchema | None:
        """Get product by ref with relationships and optional inventory."""
        product = await self.core_service.get_product_by_ref(
            product_ref, include_categories, include_tags
        )

        if product and store_id:
            product = await self.inventory_service.add_inventory_to_single_product(
                product, store_id
            )

        return product

    async def get_enhanced_product_by_id(
        self,
        product_id: int,
        include_pricing: bool = True,
        include_categories: bool = True,
        include_tags: bool = True,
        include_inventory: bool = True,
        customer_tier: Optional[int] = None,
        store_ids: Optional[List[int]] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        quantity: int = 1,
    ) -> Optional[EnhancedProductSchema]:
        """Get single product using comprehensive SQL query like bulk products endpoint"""

        # Create a query that filters for specific product ID
        query_params = ProductQuerySchema(
            limit=1,
            cursor=None,
            include_pricing=include_pricing,
            include_categories=include_categories,
            include_tags=include_tags,
            include_inventory=include_inventory,
            latitude=latitude,
            longitude=longitude,
            store_id=store_ids,
        )

        # Determine store_ids if inventory requested with location
        effective_store_ids = store_ids
        if include_inventory and not store_ids and latitude and longitude:
            effective_store_ids = await self.inventory_service.get_stores_by_location(
                latitude, longitude
            )

        # Use query service to get product with comprehensive SQL
        # We'll create a custom method for single product retrieval
        product = await self.query_service.get_single_product_by_id(
            product_id, query_params, customer_tier, effective_store_ids, quantity
        )

        return product

    async def get_enhanced_product_by_ref(
        self,
        ref: str,
        include_pricing: bool = True,
        include_categories: bool = True,
        include_tags: bool = True,
        include_inventory: bool = True,
        customer_tier: Optional[int] = None,
        store_ids: Optional[List[int]] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        quantity: int = 1,
    ) -> Optional[EnhancedProductSchema]:
        """Get single product by ref using comprehensive SQL query like bulk products endpoint"""

        # Create a query that filters for specific product ref
        query_params = ProductQuerySchema(
            limit=1,
            cursor=None,
            include_pricing=include_pricing,
            include_categories=include_categories,
            include_tags=include_tags,
            include_inventory=include_inventory,
            latitude=latitude,
            longitude=longitude,
            store_id=store_ids,
        )

        # Determine store_ids if inventory requested with location
        effective_store_ids = store_ids
        if include_inventory and not store_ids and latitude and longitude:
            effective_store_ids = await self.inventory_service.get_stores_by_location(
                latitude, longitude
            )

        # Use query service to get product with comprehensive SQL
        # We'll create a custom method for single product retrieval by ref
        product = await self.query_service.get_single_product_by_ref(
            ref, query_params, customer_tier, effective_store_ids, quantity
        )

        return product

    async def create_product(self, product_data: CreateProductSchema) -> ProductSchema:
        """Create a new product with categories and tags"""
        return await self.core_service.create_product(product_data)

    async def update_product(
        self, product_id: int, product_data: UpdateProductSchema
    ) -> ProductSchema | None:
        """Update an existing product"""
        return await self.core_service.update_product(product_id, product_data)

    async def delete_product(self, product_id: int) -> bool:
        """Delete a product"""
        return await self.core_service.delete_product(product_id)

    # Bulk operations
    async def create_products(
        self, products_data: list[CreateProductSchema]
    ) -> list[ProductSchema]:
        """Create multiple new products with validation and optimization"""
        return await self.bulk_service.create_products(products_data)

    # Query operations with pricing and inventory integration

    async def get_products_with_criteria(
        self,
        query_params: ProductQuerySchema,
        customer_tier: Optional[int] = None,
        store_ids: Optional[List[int]] = None,
    ) -> PaginatedProductsResponse:
        """Product query with comprehensive criteria and caching"""

        # Determine store_ids if inventory requested with location
        effective_store_ids = store_ids
        if (
            query_params.include_inventory
            and not store_ids
            and query_params.latitude
            and query_params.longitude
        ):
            effective_store_ids = await self.inventory_service.get_stores_by_location(
                query_params.latitude, query_params.longitude
            )

        # Single comprehensive query with all data
        return await self.query_service.get_products_with_criteria(
            query_params, customer_tier, effective_store_ids
        )

    # Tag management methods - delegated to ProductTagService
    async def create_product_tag(
        self,
        name: str,
        tag_type_suffix: str,
        slug: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Tag:
        """Create a new product tag with specific type (e.g., 'color', 'size')"""
        return await self.tag_service.create_product_tag(
            name, tag_type_suffix, slug, description
        )

    async def create_product_tags(self, tags_data: list[CreateTagSchema]) -> list[Tag]:
        """Create multiple new product tags with specific type (e.g., 'color', 'size')"""
        return await self.tag_service.create_product_tags(tags_data)

    async def get_product_tags(
        self, is_active: bool = True, tag_type_suffix: Optional[str] = None
    ) -> List[Tag]:
        """Get product tags, optionally filtered by type suffix (e.g., 'color', 'size')"""
        return await self.tag_service.get_product_tags(is_active, tag_type_suffix)

    async def assign_tag_to_product(
        self, product_id: int, tag_id: int, value: Optional[str] = None
    ):
        """Assign a tag to a product using shared TagService"""
        await self.tag_service.assign_tag_to_product(product_id, tag_id, value)

    async def remove_tag_from_product(self, product_id: int, tag_id: int) -> bool:
        """Remove a tag from a product using shared TagService"""
        return await self.tag_service.remove_tag_from_product(product_id, tag_id)

    async def get_recent_products(
        self,
        user_id: str,
        limit: int = 20,
        customer_tier: Optional[int] = None,
        include_pricing: bool = True,
        include_categories: bool = False,
        include_tags: bool = False,
        include_inventory: bool = False,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> List[EnhancedProductSchema]:
        """Get recently bought products for a user from ordered carts"""

        # Determine store_ids if inventory requested with location
        store_ids = None
        if include_inventory and latitude and longitude:
            store_ids = await self.inventory_service.get_stores_by_location(
                latitude, longitude
            )

        # Get recent products using query service
        return await self.query_service.get_recent_products_for_user(
            user_id=user_id,
            limit=limit,
            customer_tier=customer_tier,
            store_ids=store_ids,
            include_pricing=include_pricing,
            include_categories=include_categories,
            include_tags=include_tags,
            include_inventory=include_inventory,
        )
