import asyncio
from datetime import datetime
from typing import List, Optional, Dict
from google.cloud.firestore_v1.base_query import FieldFilter
from src.shared.database import get_async_db, get_async_collection
from src.shared.utils import get_logger
from src.config.cache_config import cache_config
from .cache import pricing_cache
from src.api.pricing.models import (
    PriceListSchema,
    CreatePriceListSchema,
    UpdatePriceListSchema,
    PriceListLineSchema,
    CreatePriceListLineSchema,
    UpdatePriceListLineSchema,
)
from src.config.constants import (
    Collections,
    PriceListType,
    DiscountType,
    DEFAULT_FALLBACK_TIER,
)

logger = get_logger(__name__)


class PricingService:
    """Pricing service with optimized caching and pre-loading"""

    def __init__(self):
        pass

    async def get_price_lists_collection(self):
        return await get_async_collection(Collections.PRICE_LISTS)

    async def get_price_list_lines_collection(self):
        return await get_async_collection(Collections.PRICE_LIST_LINES)

    async def get_customer_tiers_collection(self):
        return await get_async_collection(Collections.CUSTOMER_TIERS)

    async def create_price_list(
        self, price_list_data: CreatePriceListSchema
    ) -> PriceListSchema:
        """Create a new price list"""
        price_lists_collection = await self.get_price_lists_collection()
        doc_ref = price_lists_collection.document()
        price_list_dict = price_list_data.model_dump()
        price_list_dict.update(
            {"created_at": datetime.now(), "updated_at": datetime.now()}
        )
        await doc_ref.set(price_list_dict)

        pricing_cache.invalidate_price_list_cache()

        return PriceListSchema(**price_list_dict, id=doc_ref.id)

    async def get_price_list_by_id(
        self, price_list_id: str
    ) -> Optional[PriceListSchema]:
        """Get a price list by ID"""
        price_lists_collection = await self.get_price_lists_collection()
        doc = await price_lists_collection.document(price_list_id).get()
        if doc.exists:
            doc_data = doc.to_dict()
            if doc_data:
                return PriceListSchema(**doc_data, id=doc.id)
        return None

    async def get_all_price_lists(
        self, active_only: bool = False
    ) -> List[PriceListSchema]:
        """Get all price lists, optionally filtered by active status"""
        cached_lists = pricing_cache.get_price_lists(active_only)
        if cached_lists is not None:
            return cached_lists

        price_lists_collection = await self.get_price_lists_collection()
        query = price_lists_collection.order_by(field_path="priority")
        if active_only:
            query = query.where(filter=FieldFilter("active", "==", True))

        docs = query.stream()
        price_lists = []
        async for doc in docs:
            doc_data = doc.to_dict()
            if doc_data:
                price_lists.append(PriceListSchema(**doc_data, id=doc.id))

        if price_lists:
            pricing_cache.set_price_lists(price_lists, active_only)

        return price_lists

    async def update_price_list(
        self, price_list_id: str, price_list_data: UpdatePriceListSchema
    ) -> Optional[PriceListSchema]:
        """Update a price list"""
        price_lists_collection = await self.get_price_lists_collection()
        doc_ref = price_lists_collection.document(price_list_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return None

        update_data = price_list_data.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.now()
        await doc_ref.update(update_data)

        pricing_cache.invalidate_price_list_cache(price_list_id)

        updated_doc = await doc_ref.get()
        if updated_doc.exists:
            updated_data = updated_doc.to_dict()
            if updated_data:
                return PriceListSchema(**updated_data, id=updated_doc.id)
        return None

    async def delete_price_list(self, price_list_id: str) -> bool:
        """Delete a price list and its lines"""
        price_lists_collection = await self.get_price_lists_collection()
        doc_ref = price_lists_collection.document(price_list_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return False

        price_list_lines_collection = await self.get_price_list_lines_collection()
        lines_query = price_list_lines_collection.where(
            filter=FieldFilter("price_list_id", "==", price_list_id)
        )
        lines_docs = lines_query.stream()

        async for line_doc in lines_docs:
            await line_doc.reference.delete()

        pricing_cache.invalidate_price_list_cache(price_list_id)

        await doc_ref.delete()
        return True

    async def create_price_list_line(
        self, price_list_id: str, line_data: CreatePriceListLineSchema
    ) -> PriceListLineSchema:
        """Create a new price list line"""
        line_data.validate_type_fields()

        price_list_lines_collection = await self.get_price_list_lines_collection()
        doc_ref = price_list_lines_collection.document()
        line_dict = line_data.model_dump()
        line_dict.update(
            {
                "price_list_id": price_list_id,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
            }
        )
        await doc_ref.set(line_dict)

        pricing_cache.invalidate_price_list_cache(price_list_id)

        return PriceListLineSchema(**line_dict, id=doc_ref.id)

    async def get_price_list_lines(
        self, price_list_id: str
    ) -> List[PriceListLineSchema]:
        """Get all lines for a price list"""
        cached_lines = pricing_cache.get_price_list_lines(price_list_id)
        if cached_lines is not None:
            return cached_lines

        price_list_lines_collection = await self.get_price_list_lines_collection()
        docs = price_list_lines_collection.where(
            filter=FieldFilter("price_list_id", "==", price_list_id)
        ).stream()
        lines = []
        async for doc in docs:
            doc_data = doc.to_dict()
            if doc_data:
                lines.append(PriceListLineSchema(**doc_data, id=doc.id))

        if lines:
            pricing_cache.set_price_list_lines(price_list_id, lines)

        return lines

    async def update_price_list_line(
        self, line_id: str, line_data: UpdatePriceListLineSchema
    ) -> Optional[PriceListLineSchema]:
        """Update a price list line"""
        price_list_lines_collection = await self.get_price_list_lines_collection()
        doc_ref = price_list_lines_collection.document(line_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return None

        update_data = line_data.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.now()
        await doc_ref.update(update_data)

        pricing_cache.invalidate_price_list_cache()

        updated_doc = await doc_ref.get()
        if updated_doc.exists:
            updated_data = updated_doc.to_dict()
            if updated_data:
                return PriceListLineSchema(**updated_data, id=updated_doc.id)
        return None

    async def delete_price_list_line(self, line_id: str) -> bool:
        """Delete a price list line"""
        price_list_lines_collection = await self.get_price_list_lines_collection()
        doc_ref = price_list_lines_collection.document(line_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return False

        pricing_cache.invalidate_price_list_cache()

        await doc_ref.delete()
        return True

    async def calculate_product_pricing(
        self,
        product_id: Optional[str],
        base_price: float,
        category_id: Optional[str],
        customer_tier: str,
        quantity: int = 1,
    ) -> Optional[Dict]:
        """Calculate pricing for a single product with caching"""
        if not customer_tier:
            customer_tier = DEFAULT_FALLBACK_TIER

        cached_result = pricing_cache.get_product_pricing(
            product_id or "none", base_price, category_id, customer_tier, quantity
        )
        if cached_result is not None:
            return cached_result

        active_price_lists = await self.get_all_price_lists(active_only=True)

        if not active_price_lists:
            return self.create_base_pricing_result(base_price, customer_tier)

        final_price = base_price
        applied_price_lists = []
        best_discount = 0.0

        for price_list in active_price_lists:
            if not self.is_price_list_valid(price_list):
                continue

            if not price_list.id:
                continue

            applicable_lines = await self.get_applicable_lines(
                price_list.id, product_id, category_id, quantity
            )

            for line in applicable_lines:
                discount = self.calculate_discount(base_price, line)
                if discount > best_discount:
                    best_discount = discount
                    final_price = base_price - discount
                    if price_list.name not in applied_price_lists:
                        applied_price_lists.append(price_list.name)

        discount_percentage = (
            (best_discount / base_price * 100) if base_price > 0 else 0
        )

        result = {
            "base_price": base_price,
            "final_price": final_price,
            "discount_applied": best_discount,
            "discount_percentage": discount_percentage,
            "applied_price_lists": applied_price_lists,
            "customer_tier": customer_tier,
        }

        pricing_cache.set_product_pricing(
            product_id or "none",
            base_price,
            category_id,
            customer_tier,
            result,
            quantity,
        )

        return result

    async def calculate_bulk_product_pricing(
        self,
        products: List[Dict],
        customer_tier: str,
        quantity: int = 1,
    ) -> List[Dict]:
        """Calculate pricing for multiple products efficiently with caching"""
        if not products or not customer_tier:
            return [
                self.create_base_pricing_result(p.get("price", 0.0), customer_tier)
                for p in products
            ]

        product_ids = [p.get("id", "") for p in products if p.get("id")]
        if product_ids:
            cached_result = pricing_cache.get_bulk_pricing(customer_tier, product_ids)
            if cached_result is not None:
                return cached_result

        active_price_lists = await self.get_all_price_lists(active_only=True)

        if not active_price_lists:
            return [
                self.create_base_pricing_result(p.get("price", 0.0), customer_tier)
                for p in products
            ]

        valid_price_lists = [
            pl for pl in active_price_lists if self.is_price_list_valid(pl)
        ]

        if not valid_price_lists:
            return [
                self.create_base_pricing_result(p.get("price", 0.0), customer_tier)
                for p in products
            ]

        price_list_ids = [pl.id for pl in valid_price_lists if pl.id]
        tasks = [self.get_price_list_lines(pl_id) for pl_id in price_list_ids]
        results = await asyncio.gather(*tasks)
        all_price_lines = {
            pl_id: lines for pl_id, lines in zip(price_list_ids, results)
        }

        results = []
        for product in products:
            base_price = product.get("price", 0.0)
            product_id = product.get("id")
            category_id = product.get("categoryId")

            if not product_id:
                results.append(
                    self.create_base_pricing_result(base_price, customer_tier)
                )
                continue

            final_price = base_price
            applied_price_lists = []
            best_discount = 0.0

            for price_list in valid_price_lists:
                if not price_list.id:
                    continue
                lines = all_price_lines.get(price_list.id, [])

                for line in lines:
                    if self.line_applies_to_product(
                        line, product_id, category_id, quantity
                    ):
                        discount = self.calculate_discount(base_price, line)
                        if discount > best_discount:
                            best_discount = discount
                            final_price = base_price - discount
                            if price_list.name not in applied_price_lists:
                                applied_price_lists.append(price_list.name)

            discount_percentage = (
                (best_discount / base_price * 100) if base_price > 0 else 0
            )

            results.append(
                {
                    "base_price": base_price,
                    "final_price": final_price,
                    "discount_applied": best_discount,
                    "discount_percentage": discount_percentage,
                    "applied_price_lists": applied_price_lists,
                    "customer_tier": customer_tier,
                }
            )

        if product_ids and results:
            pricing_cache.set_bulk_pricing(customer_tier, product_ids, results)

        return results

    def is_price_list_valid(self, price_list: PriceListSchema) -> bool:
        """Check if price list is within valid date range"""
        from datetime import timezone

        now = datetime.now(timezone.utc)

        valid_from = price_list.valid_from
        if valid_from and valid_from.tzinfo is None:
            valid_from = valid_from.replace(tzinfo=timezone.utc)

        valid_until = price_list.valid_until
        if valid_until and valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)

        if valid_from and valid_from > now:
            return False

        if valid_until and valid_until < now:
            return False

        return True

    async def get_applicable_lines(
        self,
        price_list_id: str,
        product_id: Optional[str],
        category_id: Optional[str],
        quantity: int,
    ) -> List[PriceListLineSchema]:
        """Get price list lines that apply to this product"""
        lines = await self.get_price_list_lines(price_list_id)
        applicable_lines = []

        for line in lines:
            if self.line_applies_to_product(line, product_id, category_id, quantity):
                applicable_lines.append(line)

        return applicable_lines

    def line_applies_to_product(
        self,
        line: PriceListLineSchema,
        product_id: Optional[str],
        category_id: Optional[str],
        quantity: int,
    ) -> bool:
        """Check if a price list line applies to a product"""
        if line.type == PriceListType.PRODUCT:
            if not product_id or line.product_id != product_id:
                return False
        elif line.type == PriceListType.CATEGORY:
            if not category_id or line.category_id != category_id:
                return False

        if quantity < line.min_product_qty:
            return False

        if line.max_product_qty and quantity > line.max_product_qty:
            return False

        return True

    def calculate_discount(self, base_price: float, line: PriceListLineSchema) -> float:
        """Calculate discount amount from a price list line"""
        if line.discount_type == DiscountType.PERCENTAGE:
            return base_price * (line.amount / 100)
        elif line.discount_type == DiscountType.FLAT:
            return min(line.amount, base_price)
        return 0.0

    def create_base_pricing_result(self, base_price: float, customer_tier: str) -> Dict:
        """Create base pricing result with no discounts"""
        return {
            "base_price": base_price,
            "final_price": base_price,
            "discount_applied": 0.0,
            "discount_percentage": 0.0,
            "applied_price_lists": [],
            "customer_tier": customer_tier,
        }
