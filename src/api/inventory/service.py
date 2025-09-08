from typing import Optional
from src.shared.database import get_async_db, get_async_collection
from src.api.inventory.models import (
    InventorySchema,
    CreateInventorySchema,
    UpdateInventorySchema,
)


class InventoryService:
    def __init__(self):
        pass

    async def get_inventory_collection(self):
        return await get_async_collection("inventory")

    async def get_all_inventory(
        self, product_id: Optional[str] = None, store_id: Optional[str] = None
    ) -> list[InventorySchema]:
        inventory_collection = await self.get_inventory_collection()
        inventory_ref = inventory_collection
        if product_id is not None:
            inventory_ref = inventory_ref.where("productId", "==", product_id)
        if store_id is not None:
            inventory_ref = inventory_ref.where("storeId", "==", store_id)
        docs = inventory_ref.stream()
        result = []
        for doc in docs:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                result.append(InventorySchema(id=doc.id, **doc_dict))
        return result

    async def get_inventory_by_id(self, inventory_id: str) -> InventorySchema | None:
        inventory_collection = await self.get_inventory_collection()
        doc = inventory_collection.document(inventory_id).get()
        if doc.exists:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                return InventorySchema(id=doc.id, **doc_dict)
        return None

    async def create_inventory(
        self, inventory_data: CreateInventorySchema
    ) -> InventorySchema:
        inventory_collection = await self.get_inventory_collection()
        doc_ref = inventory_collection.document()
        inventory_dict = inventory_data.model_dump()
        doc_ref.set(inventory_dict)
        created_inventory = doc_ref.get()
        created_dict = created_inventory.to_dict()
        if created_dict:  # Ensure created_dict is not None
            return InventorySchema(id=created_inventory.id, **created_dict)
        else:
            # Handle the case where the document doesn't exist after creation
            raise Exception("Failed to create inventory item")

    async def update_inventory(
        self, inventory_id: str, inventory_data: UpdateInventorySchema
    ) -> InventorySchema | None:
        inventory_collection = await self.get_inventory_collection()
        doc_ref = inventory_collection.document(inventory_id)
        if not doc_ref.get().exists:
            return None
        inventory_dict = inventory_data.model_dump(exclude_unset=True)
        if "productId" in inventory_dict:
            del inventory_dict["productId"]
        if "storeId" in inventory_dict:
            del inventory_dict["storeId"]
        if "stock" in inventory_dict:
            del inventory_dict["stock"]
        doc_ref.update(inventory_dict)
        updated_inventory = doc_ref.get()
        updated_dict = updated_inventory.to_dict()
        if updated_dict:  # Ensure updated_dict is not None
            return InventorySchema(id=updated_inventory.id, **updated_dict)
        return None

    async def delete_inventory(self, inventory_id: str) -> bool:
        inventory_collection = await self.get_inventory_collection()
        doc_ref = inventory_collection.document(inventory_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True
