from src.core.firebase import get_firestore_db
from src.models.product_models import ProductSchema, CreateProductSchema, UpdateProductSchema, ProductQuerySchema

class ProductService:
    def __init__(self):
        self.db = get_firestore_db()
        self.products_collection = self.db.collection('products')

    async def get_all_products(self, query_params: ProductQuerySchema) -> list[ProductSchema]:
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
        if query_params.limit:
            products_ref = products_ref.limit(query_params.limit)
        if query_params.offset:
            # Firestore doesn't have a direct offset, usually done with start_after/start_at
            # For simplicity, we'll just fetch and slice for now. For large datasets, this needs optimization.
            pass

        docs = products_ref.stream()
        all_products = []
        for doc in docs:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                all_products.append(ProductSchema(id=doc.id, **doc_dict))

        if query_params.offset:
            all_products = all_products[query_params.offset:]

        return all_products

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
