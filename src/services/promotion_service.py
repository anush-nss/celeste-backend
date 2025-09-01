from src.core.firebase import get_firestore_db
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class PromotionSchema(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    imageUrl: Optional[str] = None
    validFrom: datetime
    validTo: datetime
    isActive: bool = True

class PromotionService:
    def __init__(self):
        self.db = get_firestore_db()
        self.promotions_collection = self.db.collection('promotions')

    async def get_all_promotions(self) -> list[PromotionSchema]:
        docs = self.promotions_collection.where('isActive', '==', True).stream()
        result = []
        for doc in docs:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                result.append(PromotionSchema(id=doc.id, **doc_dict))
        return result

    async def get_promotion_by_id(self, promotion_id: str) -> PromotionSchema | None:
        doc = self.promotions_collection.document(promotion_id).get()
        if doc.exists:
            doc_dict = doc.to_dict()
            if doc_dict:  # Ensure doc_dict is not None
                return PromotionSchema(id=doc.id, **doc_dict)
        return None
