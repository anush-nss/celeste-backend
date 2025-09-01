from src.core.firebase import get_firestore_db
from src.models.discount_models import DiscountSchema, CreateDiscountSchema, UpdateDiscountSchema, DiscountQuerySchema
from datetime import datetime

class DiscountService:
    def __init__(self):
        self.db = get_firestore_db()
        self.discounts_collection = self.db.collection('discounts')

    async def get_all_discounts(self, query_params: DiscountQuerySchema) -> list[DiscountSchema]:
        discounts_ref = self.discounts_collection

        if query_params.availableOnly:
            now = datetime.now()
            discounts_ref = discounts_ref.where('validFrom', '<=', now).where('validTo', '>=', now)

        docs = discounts_ref.stream()
        discounts = []
        for doc in docs:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                discounts.append(DiscountSchema(id=doc.id, **doc_dict))

        # TODO: Implement populateReferences logic if needed (fetching product/category details)

        return discounts

    async def get_discount_by_id(self, discount_id: str) -> DiscountSchema | None:
        doc = self.discounts_collection.document(discount_id).get()
        if doc.exists:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                return DiscountSchema(id=doc.id, **doc_dict)
        return None

    async def create_discount(self, discount_data: CreateDiscountSchema) -> DiscountSchema:
        doc_ref = self.discounts_collection.document()
        doc_ref.set(discount_data.model_dump())
        created_discount = doc_ref.get()
        created_dict = created_discount.to_dict()
        if created_dict:  # Ensure created_dict is not None
            return DiscountSchema(id=created_discount.id, **created_dict)
        else:
            # Handle the case where the document doesn't exist after creation
            raise Exception("Failed to create discount")

    async def update_discount(self, discount_id: str, discount_data: UpdateDiscountSchema) -> DiscountSchema | None:
        doc_ref = self.discounts_collection.document(discount_id)
        if not doc_ref.get().exists:
            return None
        doc_ref.update(discount_data.model_dump(exclude_unset=True))
        updated_discount = doc_ref.get()
        updated_dict = updated_discount.to_dict()
        if updated_dict:  # Ensure updated_dict is not None
            return DiscountSchema(id=updated_discount.id, **updated_dict)
        return None

    async def delete_discount(self, discount_id: str) -> bool:
        doc_ref = self.discounts_collection.document(discount_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True
