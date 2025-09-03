from typing import Optional, List, Dict, Any, Tuple
from src.core.firebase import get_firestore_db
from src.models.product_models import (
    ProductSchema, CreateProductSchema, UpdateProductSchema, ProductQuerySchema,
    EnhancedProductSchema, PaginatedProductsResponse, PricingInfoSchema
)
from src.shared.constants import CustomerTier

class ProductService:
    def __init__(self):
        self.db = get_firestore_db()
        self.products_collection = self.db.collection('products')

    async def get_all_products(self, query_params: ProductQuerySchema) -> list[ProductSchema]:
        """Legacy method for backward compatibility"""
        products_ref = self.products_collection

        # Apply filters
        if query_params.categoryId:
            products_ref = products_ref.where('categoryId', '==', query_params.categoryId)
        if query_params.minPrice is not None:
            products_ref = products_ref.where('price', '>=', query_params.minPrice)
        if query_params.maxPrice is not None:
            products_ref = products_ref.where('price', '<=', query_params.maxPrice)
        if query_params.isFeatured is not None:
            products_ref = products_ref.where('isFeatured', '==', query_params.isFeatured)

        # Apply pagination
        limit = query_params.limit or 20
        products_ref = products_ref.limit(limit)

        # Handle cursor-based pagination
        if query_params.cursor:
            cursor_doc = self.products_collection.document(query_params.cursor).get()
            if cursor_doc.exists:
                products_ref = products_ref.start_after(cursor_doc)

        docs = products_ref.stream()
        all_products = []
        for doc in docs:
            doc_dict = doc.to_dict()
            if doc_dict:
                all_products.append(ProductSchema(id=doc.id, **doc_dict))

        return all_products

    async def get_products_with_pagination(
        self, 
        query_params: ProductQuerySchema,
        customer_tier: Optional[CustomerTier] = None,
        pricing_service=None
    ) -> PaginatedProductsResponse:
        """
        Enhanced product listing with cursor-based pagination and smart pricing
        """
        products_ref = self.products_collection.order_by('name')  # Consistent ordering for pagination

        # Apply filters
        if query_params.categoryId:
            products_ref = products_ref.where('categoryId', '==', query_params.categoryId)
        if query_params.minPrice is not None:
            products_ref = products_ref.where('price', '>=', query_params.minPrice)
        if query_params.maxPrice is not None:
            products_ref = products_ref.where('price', '<=', query_params.maxPrice)
        if query_params.isFeatured is not None:
            products_ref = products_ref.where('isFeatured', '==', query_params.isFeatured)

        # Apply limit (default 20, max 100)
        limit = min(query_params.limit or 20, 100)
        # Fetch one extra to check if there are more results
        products_ref = products_ref.limit(limit + 1)

        # Handle cursor-based pagination
        cursor_doc = None
        if query_params.cursor:
            cursor_doc = self.products_collection.document(query_params.cursor).get()
            if cursor_doc.exists:
                products_ref = products_ref.start_after(cursor_doc)

        # Execute query
        docs = list(products_ref.stream())
        
        # Check if there are more results
        has_more = len(docs) > limit
        if has_more:
            docs = docs[:-1]  # Remove the extra document

        # Convert to product objects
        products = []
        for doc in docs:
            doc_dict = doc.to_dict()
            if doc_dict:
                products.append({
                    'id': doc.id,
                    'data': doc_dict,
                    'doc_ref': doc
                })

        # Apply pricing if requested and pricing service available
        enhanced_products = []
        if query_params.include_pricing and pricing_service and products:
            # Extract product data for bulk pricing calculation
            product_list = []
            for prod in products:
                product_list.append({
                    'id': prod['id'],
                    'price': prod['data'].get('price', 0),
                    'categoryId': prod['data'].get('categoryId'),
                    **prod['data']
                })
            
            # Calculate bulk pricing
            pricing_results = await pricing_service.calculate_bulk_product_pricing(
                product_list, customer_tier, 1
            )
            
            # Create enhanced product schemas with pricing
            for i, prod in enumerate(products):
                pricing_info = pricing_results[i] if i < len(pricing_results) else None
                
                enhanced_product = EnhancedProductSchema(
                    id=prod['id'],
                    **prod['data'],
                    pricing=PricingInfoSchema(**pricing_info) if pricing_info else None
                )
                enhanced_products.append(enhanced_product)
        else:
            # Create enhanced products without pricing
            for prod in products:
                enhanced_product = EnhancedProductSchema(
                    id=prod['id'],
                    **prod['data']
                )
                enhanced_products.append(enhanced_product)

        # Prepare pagination metadata
        pagination = {
            "current_cursor": query_params.cursor,
            "next_cursor": products[-1]['id'] if products and has_more else None,
            "has_more": has_more,
            "total_returned": len(enhanced_products)
        }

        return PaginatedProductsResponse(
            products=enhanced_products,
            pagination=pagination
        )

    async def get_product_by_id(self, product_id: str) -> ProductSchema | None:
        doc = self.products_collection.document(product_id).get()
        if doc.exists:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                return ProductSchema(id=doc.id, **doc_dict)
        return None

    async def create_product(self, product_data: CreateProductSchema) -> ProductSchema:
        doc_ref = self.products_collection.document()
        product_dict = product_data.model_dump()
        doc_ref.set(product_dict)
        created_product = doc_ref.get()
        created_dict = created_product.to_dict()
        if created_dict:  # Ensure created_dict is not None
            return ProductSchema(id=created_product.id, **created_dict)
        else:
            # Handle the case where the document doesn't exist after creation
            raise Exception("Failed to create product")

    async def update_product(self, product_id: str, product_data: UpdateProductSchema) -> ProductSchema | None:
        doc_ref = self.products_collection.document(product_id)
        if not doc_ref.get().exists:
            return None
        product_dict = product_data.model_dump(exclude_unset=True)
        doc_ref.update(product_dict)
        updated_product = doc_ref.get()
        updated_dict = updated_product.to_dict()
        if updated_dict:  # Ensure updated_dict is not None
            return ProductSchema(id=updated_product.id, **updated_dict)
        return None

    async def delete_product(self, product_id: str) -> bool:
        doc_ref = self.products_collection.document(product_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True
