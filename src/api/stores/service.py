from src.shared.database import get_firestore_db
from src.api.stores.models import StoreSchema, CreateStoreSchema, UpdateStoreSchema


class StoreService:
    def __init__(self):
        self.db = get_firestore_db()
        self.stores_collection = self.db.collection("stores")

    async def get_all_stores(self) -> list[StoreSchema]:
        docs = self.stores_collection.stream()
        result = []
        for doc in docs:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                result.append(StoreSchema(id=doc.id, **doc_dict))
        return result

    async def get_store_by_id(self, store_id: str) -> StoreSchema | None:
        doc = self.stores_collection.document(store_id).get()
        if doc.exists:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                return StoreSchema(id=doc.id, **doc_dict)
        return None

    async def create_store(self, store_data: CreateStoreSchema) -> StoreSchema:
        doc_ref = self.stores_collection.document()
        store_dict = store_data.model_dump()
        doc_ref.set(store_dict)
        created_store = doc_ref.get()
        created_dict = created_store.to_dict()
        if created_dict:  # Ensure created_dict is not None
            return StoreSchema(id=created_store.id, **created_dict)
        else:
            # Handle the case where the document doesn't exist after creation
            raise Exception("Failed to create store")

    async def update_store(
        self, store_id: str, store_data: UpdateStoreSchema
    ) -> StoreSchema | None:
        doc_ref = self.stores_collection.document(store_id)
        if not doc_ref.get().exists:
            return None
        store_dict = store_data.model_dump(exclude_unset=True)
        doc_ref.update(store_dict)
        updated_store = doc_ref.get()
        updated_dict = updated_store.to_dict()
        if updated_dict:  # Ensure updated_dict is not None
            return StoreSchema(id=updated_store.id, **updated_dict)
        return None

    async def delete_store(self, store_id: str) -> bool:
        doc_ref = self.stores_collection.document(store_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True
