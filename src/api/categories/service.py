import asyncio
from src.shared.database import get_async_db, get_async_collection
from src.config.cache_config import cache_config
from .cache import categories_cache
from src.api.categories.models import (
    CategorySchema,
    CreateCategorySchema,
    UpdateCategorySchema,
)
from src.config.constants import Collections


class CategoryService:
    """Category service with caching for improved performance"""
    
    def __init__(self):
        pass

    async def get_categories_collection(self):
        return await get_async_collection(Collections.CATEGORIES)

    async def get_all_categories(self) -> list[CategorySchema]:
        """Get all categories with caching"""
        cached_categories = categories_cache.get_all_categories()
        if cached_categories is not None:
            return [CategorySchema(**c) for c in cached_categories]
        
        categories_collection = await self.get_categories_collection()
        docs = categories_collection.order_by(field_path="order").stream()
        categories = []
        async for doc in docs:
            doc_dict = doc.to_dict()
            if doc_dict:
                categories.append(CategorySchema(id=doc.id, **doc_dict))
        
        if categories:
            categories_cache.set_all_categories([c.model_dump() for c in categories])
        
        return categories

    async def get_category_by_id(self, category_id: str) -> CategorySchema | None:
        """Get category by ID with caching"""
        cached_category = categories_cache.get_category(category_id)
        if cached_category is not None:
            return CategorySchema(**cached_category)
        
        categories_collection = await self.get_categories_collection()
        doc = await categories_collection.document(category_id).get()
        if doc.exists:
            doc_dict = doc.to_dict()
            if doc_dict:
                category = CategorySchema(id=doc.id, **doc_dict)
                categories_cache.set_category(category_id, category.model_dump())
                return category
        return None

    async def create_category(self, category_data: CreateCategorySchema) -> CategorySchema:
        """Create a new category"""
        categories_collection = await self.get_categories_collection()
        doc_ref = categories_collection.document()
        category_dict = category_data.model_dump()
        await doc_ref.set(category_dict)
        
        new_category = CategorySchema(id=doc_ref.id, **category_dict)
        categories_cache.set_category(doc_ref.id, new_category.model_dump())
        
        categories_cache.invalidate_category_cache()
        
        return new_category

    async def update_category(
        self, category_id: str, category_data: UpdateCategorySchema
    ) -> CategorySchema | None:
        """Update an existing category"""
        categories_collection = await self.get_categories_collection()
        doc_ref = categories_collection.document(category_id)
        if not (await doc_ref.get()).exists:
            return None
        
        update_dict = category_data.model_dump(exclude_unset=True)
        await doc_ref.update(update_dict)
        
        categories_cache.invalidate_category_cache(category_id)
        
        updated_doc = await doc_ref.get()
        updated_dict = updated_doc.to_dict()
        if updated_dict:
            return CategorySchema(id=updated_doc.id, **updated_dict)
        return None

    async def delete_category(self, category_id: str) -> bool:
        """Delete a category"""
        categories_collection = await self.get_categories_collection()
        doc_ref = categories_collection.document(category_id)
        if not (await doc_ref.get()).exists:
            return False
        
        categories_cache.invalidate_category_cache(category_id)
        
        await doc_ref.delete()
        return True

    async def get_categories_by_ids(self, category_ids: list[str]) -> list[CategorySchema]:
        """Get multiple categories by their IDs efficiently"""
        if not category_ids:
            return []
        
        tasks = [self.get_category_by_id(category_id) for category_id in category_ids]
        results = await asyncio.gather(*tasks)
        
        return [category for category in results if category]
