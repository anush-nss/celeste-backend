import asyncio
from typing import Optional, List
from google.cloud.firestore_v1.base_query import FieldFilter
from src.shared.db_client import db_client
from src.config.cache_config import cache_config
from .cache import products_cache
from src.api.products.models import (
    ProductSchema,
    CreateProductSchema,
    UpdateProductSchema,
    ProductQuerySchema,
    EnhancedProductSchema,
    PaginatedProductsResponse,
    PricingInfoSchema,
)
from src.config.constants import Collections


class ProductService:
    """Product service with clean, maintainable code"""    
    def __init__(self):
        self.products_collection = db_client.collection(Collections.PRODUCTS)

    async def get_all_products(
        self, query_params: ProductQuerySchema
    ) -> list[ProductSchema]:
        """Get products with simple filtering and pagination"""
        query = self.products_collection

        # Apply filters
        if query_params.categoryId:
            query = query.where(filter=FieldFilter("categoryId", "==", query_params.categoryId))
        if query_params.minPrice is not None:
            query = query.where(filter=FieldFilter("price", ">=", query_params.minPrice))
        if query_params.maxPrice is not None:
            query = query.where(filter=FieldFilter("price", "<=", query_params.maxPrice))

        # Apply pagination
        limit = min(query_params.limit or 20, 100)
        query = query.limit(limit)

        # Handle cursor-based pagination
        if query_params.cursor:
            cursor_doc = await self.products_collection.document(query_params.cursor).get()
            if cursor_doc.exists:
                query = query.start_after(cursor_doc)

        docs = query.stream()
        products = []
        async for doc in docs:
            doc_dict = doc.to_dict()
            if doc_dict:
                products.append(ProductSchema(id=doc.id, **doc_dict))

        return products

    async def get_products_with_pagination(
        self,
        query_params: ProductQuerySchema,
        customer_tier: Optional[str] = None,
        pricing_service=None,
    ) -> PaginatedProductsResponse:
        """Get products with optional pricing information"""
        # Get base products
        base_products = await self.get_all_products(query_params)
        
        if not base_products:
            return PaginatedProductsResponse(
                products=[], 
                pagination={"current_cursor": None, "next_cursor": None, "has_more": False, "total_returned": 0}
            )
        
        # Batch calculate pricing for all products at once
        enhanced_products = []
        if query_params.include_pricing and pricing_service and customer_tier:
            # Convert to dict format for bulk pricing
            product_data = [
                {
                    "id": p.id,
                    "price": p.price,
                    "categoryId": p.categoryId
                }
                for p in base_products
            ]
            
            # Get pricing for all products in one batch
            pricing_results = await pricing_service.calculate_bulk_product_pricing(
                product_data, customer_tier
            )
            
            # Combine products with pricing
            for i, product in enumerate(base_products):
                enhanced_product = EnhancedProductSchema(**product.model_dump())
                pricing_info = pricing_results[i] if i < len(pricing_results) else None
                if pricing_info:
                    enhanced_product.pricing = PricingInfoSchema(**pricing_info)
                
                # Filter discounted products if requested
                if query_params.only_discounted:
                    if enhanced_product.pricing and enhanced_product.pricing.discount_applied > 0:
                        enhanced_products.append(enhanced_product)
                else:
                    enhanced_products.append(enhanced_product)
        else:
            # No pricing needed, just convert products
            for product in base_products:
                enhanced_products.append(EnhancedProductSchema(**product.model_dump()))
        
        limit = min(query_params.limit or 20, 100)
        
        # Determine if there are more results
        has_more = len(enhanced_products) >= limit
        
        # Get next cursor (last product ID if we have more results)
        next_cursor = None
        if has_more and enhanced_products:
            next_cursor = enhanced_products[-1].id
        
        pagination = {
            "current_cursor": query_params.cursor,
            "next_cursor": next_cursor,
            "has_more": has_more,
            "total_returned": min(len(enhanced_products), limit)
        }
        
        return PaginatedProductsResponse(products=enhanced_products[:limit], pagination=pagination)

    async def get_product_by_id(self, product_id: str) -> ProductSchema | None:
        """Get a single product by ID with caching"""
        # Check cache first
        cached_product = products_cache.get_product(product_id)
        if cached_product is not None:
            return ProductSchema(**cached_product)
        
        # Fallback to database
        doc = await self.products_collection.document(product_id).get()
        if doc.exists:
            doc_dict = doc.to_dict()
            if doc_dict:
                product = ProductSchema(id=doc.id, **doc_dict)
                # Cache with configured TTL
                products_cache.set_product(product_id, product.model_dump())
                return product
        return None

    async def get_product_by_id_with_pricing(
        self, 
        product_id: str, 
        include_pricing: Optional[bool] = True,
        customer_tier: Optional[str] = None,
        pricing_service=None
    ) -> Optional[EnhancedProductSchema]:
        """Get a single product with optional pricing information"""
        product = await self.get_product_by_id(product_id)
        if not product:
            return None
        
        enhanced_product = EnhancedProductSchema(**product.model_dump())
        
        if include_pricing is True and customer_tier and pricing_service:
            pricing_info = await pricing_service.calculate_product_pricing(
                product.id, product.price, product.categoryId, customer_tier
            )
            if pricing_info:
                enhanced_product.pricing = PricingInfoSchema(**pricing_info)
        
        return enhanced_product

    async def create_product(self, product_data: CreateProductSchema) -> ProductSchema:
        """Create a new product"""
        doc_ref = self.products_collection.document()
        product_dict = product_data.model_dump()
        await doc_ref.set(product_dict)
        
        # Cache the new product
        new_product = ProductSchema(id=doc_ref.id, **product_dict)
        products_cache.set_product(doc_ref.id, new_product.model_dump())
        
        return new_product

    async def update_product(
        self, product_id: str, product_data: UpdateProductSchema
    ) -> ProductSchema | None:
        """Update an existing product"""
        doc_ref = self.products_collection.document(product_id)
        if not (await doc_ref.get()).exists:
            return None
        
        update_dict = product_data.model_dump(exclude_unset=True)
        await doc_ref.update(update_dict)
        
        # Selective cache invalidation
        products_cache.invalidate_product_cache(product_id)
        
        updated_doc = await doc_ref.get()
        updated_dict = updated_doc.to_dict()
        if updated_dict:
            return ProductSchema(id=updated_doc.id, **updated_dict)
        return None

    async def delete_product(self, product_id: str) -> bool:
        """Delete a product"""
        doc_ref = self.products_collection.document(product_id)
        if not (await doc_ref.get()).exists:
            return False
        
        # Selective cache invalidation
        products_cache.invalidate_product_cache(product_id)
        
        await doc_ref.delete()
        return True

    async def get_products_by_ids(self, product_ids: List[str]) -> List[ProductSchema]:
        """Get multiple products by their IDs using cache"""
        if not product_ids:
            return []
        
        tasks = [self.get_product_by_id(product_id) for product_id in product_ids]
        results = await asyncio.gather(*tasks)
        
        return [product for product in results if product]