from src.shared.database import get_firestore_db
from src.api.categories.models import (
    CategorySchema,
    CreateCategorySchema,
    UpdateCategorySchema,
)


class CategoryService:
    def __init__(self):
        self.db = get_firestore_db()
        self.categories_collection = self.db.collection("categories")

    async def get_all_categories(self) -> list[CategorySchema]:
        docs = self.categories_collection.stream()
        result = []
        for doc in docs:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                result.append(CategorySchema(id=doc.id, **doc_dict))
        return result

    async def get_category_by_id(self, category_id: str) -> CategorySchema | None:
        doc = self.categories_collection.document(category_id).get()
        if doc.exists:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                return CategorySchema(id=doc.id, **doc_dict)
        return None

    async def create_category(
        self, category_data: CreateCategorySchema
    ) -> CategorySchema:
        doc_ref = self.categories_collection.document()
        doc_ref.set(category_data.model_dump())
        created_category = doc_ref.get()
        created_dict = created_category.to_dict()
        if created_dict:  # Ensure created_dict is not None
            return CategorySchema(id=created_category.id, **created_dict)
        else:
            # Handle the case where the document doesn't exist after creation
            raise Exception("Failed to create category")

    async def update_category(
        self, category_id: str, category_data: UpdateCategorySchema
    ) -> CategorySchema | None:
        doc_ref = self.categories_collection.document(category_id)
        if not doc_ref.get().exists:
            return None
        doc_ref.update(category_data.model_dump(exclude_unset=True))
        updated_category = doc_ref.get()
        updated_dict = updated_category.to_dict()
        if updated_dict:  # Ensure updated_dict is not None
            return CategorySchema(id=updated_category.id, **updated_dict)
        return None

    async def delete_category(self, category_id: str) -> bool:
        doc_ref = self.categories_collection.document(category_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True
