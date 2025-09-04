from functools import lru_cache
from src.shared.db_client import db_client
from src.api.categories.models import (
    CategorySchema,
    CreateCategorySchema,
    UpdateCategorySchema,
)
from src.config.constants import Collections


class CategoryService:
    """Category service with caching for improved performance"""
    
    def __init__(self):
        self.categories_collection = db_client.collection(Collections.CATEGORIES)

    @lru_cache(maxsize=64)
    def _get_cached_categories(self) -> tuple:
        """Get cached categories - returns tuple for hashability"""
        docs = self.categories_collection.order_by("order").stream()
        categories = []
        for doc in docs:
            doc_dict = doc.to_dict()
            if doc_dict:
                categories.append(CategorySchema(id=doc.id, **doc_dict))
        return tuple(categories)

    def get_all_categories(self) -> list[CategorySchema]:
        """Get all categories with caching"""
        return list(self._get_cached_categories())

    @lru_cache(maxsize=128)
    def _get_cached_category_by_id(self, category_id: str) -> CategorySchema | None:
        """Get cached category by ID"""
        doc = self.categories_collection.document(category_id).get()
        if doc.exists:
            doc_dict = doc.to_dict()
            if doc_dict:
                return CategorySchema(id=doc.id, **doc_dict)
        return None

    def get_category_by_id(self, category_id: str) -> CategorySchema | None:
        """Get category by ID with caching"""
        return self._get_cached_category_by_id(category_id)

    def create_category(self, category_data: CreateCategorySchema) -> CategorySchema:
        """Create a new category"""
        doc_ref = self.categories_collection.document()
        category_dict = category_data.model_dump()
        doc_ref.set(category_dict)
        
        # Clear caches
        self._get_cached_categories.cache_clear()
        
        return CategorySchema(id=doc_ref.id, **category_dict)

    def update_category(
        self, category_id: str, category_data: UpdateCategorySchema
    ) -> CategorySchema | None:
        """Update an existing category"""
        doc_ref = self.categories_collection.document(category_id)
        if not doc_ref.get().exists:
            return None
        
        update_dict = category_data.model_dump(exclude_unset=True)
        doc_ref.update(update_dict)
        
        # Clear caches
        self._get_cached_categories.cache_clear()
        self._get_cached_category_by_id.cache_clear()
        
        updated_doc = doc_ref.get()
        updated_dict = updated_doc.to_dict()
        if updated_dict:
            return CategorySchema(id=updated_doc.id, **updated_dict)
        return None

    def delete_category(self, category_id: str) -> bool:
        """Delete a category"""
        doc_ref = self.categories_collection.document(category_id)
        if not doc_ref.get().exists:
            return False
        
        # Clear caches
        self._get_cached_categories.cache_clear()
        self._get_cached_category_by_id.cache_clear()
        
        doc_ref.delete()
        return True

    def get_categories_by_ids(self, category_ids: list[str]) -> list[CategorySchema]:
        """Get multiple categories by their IDs efficiently"""
        if not category_ids:
            return []
        
        categories = []
        for category_id in category_ids:
            category = self.get_category_by_id(category_id)
            if category:
                categories.append(category)
        
        return categories