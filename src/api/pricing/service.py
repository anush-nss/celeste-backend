from datetime import datetime
from typing import List, Optional, Dict
from functools import lru_cache
from src.shared.db_client import db_client
from src.api.pricing.models import (
    PriceListSchema,
    CreatePriceListSchema,
    UpdatePriceListSchema,
    PriceListLineSchema,
    CreatePriceListLineSchema,
    UpdatePriceListLineSchema,
)
from src.config.constants import Collections, PriceListType, DiscountType, DEFAULT_FALLBACK_TIER


class PricingService:
    """Pricing service with clean, maintainable code"""
    
    def __init__(self):
        self.price_lists_collection = db_client.collection(Collections.PRICE_LISTS)
        self.price_list_lines_collection = db_client.collection(Collections.PRICE_LIST_LINES)
        self.customer_tiers_collection = db_client.collection(Collections.CUSTOMER_TIERS)

    # Price List Management
    def create_price_list(self, price_list_data: CreatePriceListSchema) -> PriceListSchema:
        """Create a new price list"""
        doc_ref = self.price_lists_collection.document()
        price_list_dict = price_list_data.model_dump()
        price_list_dict.update({
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        })
        doc_ref.set(price_list_dict)
        return PriceListSchema(**price_list_dict, id=doc_ref.id)

    def get_price_list_by_id(self, price_list_id: str) -> Optional[PriceListSchema]:
        """Get a price list by ID"""
        doc = self.price_lists_collection.document(price_list_id).get()
        if doc.exists:
            doc_data = doc.to_dict()
            if doc_data:
                return PriceListSchema(**doc_data, id=doc.id)
        return None

    @lru_cache(maxsize=32)
    def _get_cached_price_lists(self, active_only: bool = False) -> tuple:
        """Get cached price lists - returns tuple for hashability"""
        query = self.price_lists_collection.order_by("priority")
        
        if active_only:
            query = query.where("active", "==", True)

        docs = query.stream()
        price_lists = []
        for doc in docs:
            doc_data = doc.to_dict()
            if doc_data:
                price_lists.append(PriceListSchema(**doc_data, id=doc.id))

        return tuple(price_lists)
    
    def get_all_price_lists(self, active_only: bool = False) -> List[PriceListSchema]:
        """Get all price lists, optionally filtered by active status"""
        return list(self._get_cached_price_lists(active_only))

    def update_price_list(
        self, price_list_id: str, price_list_data: UpdatePriceListSchema
    ) -> Optional[PriceListSchema]:
        """Update a price list"""
        doc_ref = self.price_lists_collection.document(price_list_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        update_data = price_list_data.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.now()
        doc_ref.update(update_data)

        # Clear cache
        self._get_cached_price_lists.cache_clear()

        updated_doc = doc_ref.get()
        if updated_doc.exists:
            updated_data = updated_doc.to_dict()
            if updated_data:
                return PriceListSchema(**updated_data, id=updated_doc.id)
        return None

    def delete_price_list(self, price_list_id: str) -> bool:
        """Delete a price list and its lines"""
        doc_ref = self.price_lists_collection.document(price_list_id)
        doc = doc_ref.get()

        if not doc.exists:
            return False

        # Delete all associated price list lines
        lines_query = self.price_list_lines_collection.where("price_list_id", "==", price_list_id)
        lines_docs = lines_query.stream()

        for line_doc in lines_docs:
            line_doc.reference.delete()

        # Clear caches
        self._get_cached_price_lists.cache_clear()
        self._get_cached_price_list_lines.cache_clear()
        
        # Delete the price list
        doc_ref.delete()
        return True

    # Price List Lines Management
    def create_price_list_line(
        self, price_list_id: str, line_data: CreatePriceListLineSchema
    ) -> PriceListLineSchema:
        """Create a new price list line"""
        line_data.validate_type_fields()

        doc_ref = self.price_list_lines_collection.document()
        line_dict = line_data.model_dump()
        line_dict.update({
            "price_list_id": price_list_id,
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        })
        doc_ref.set(line_dict)
        
        # Clear price list lines cache
        self._get_cached_price_list_lines.cache_clear()

        return PriceListLineSchema(**line_dict, id=doc_ref.id)

    @lru_cache(maxsize=128)
    def _get_cached_price_list_lines(self, price_list_id: str) -> tuple:
        """Get cached price list lines - returns tuple for hashability"""
        docs = self.price_list_lines_collection.where("price_list_id", "==", price_list_id).stream()
        lines = []
        for doc in docs:
            doc_data = doc.to_dict()
            if doc_data:
                lines.append(PriceListLineSchema(**doc_data, id=doc.id))
        return tuple(lines)
    
    def get_price_list_lines(self, price_list_id: str) -> List[PriceListLineSchema]:
        """Get all lines for a price list"""
        return list(self._get_cached_price_list_lines(price_list_id))

    def update_price_list_line(
        self, line_id: str, line_data: UpdatePriceListLineSchema
    ) -> Optional[PriceListLineSchema]:
        """Update a price list line"""
        doc_ref = self.price_list_lines_collection.document(line_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        update_data = line_data.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.now()
        doc_ref.update(update_data)

        updated_doc = doc_ref.get()
        if updated_doc.exists:
            updated_data = updated_doc.to_dict()
            if updated_data:
                return PriceListLineSchema(**updated_data, id=updated_doc.id)
        return None

    def delete_price_list_line(self, line_id: str) -> bool:
        """Delete a price list line"""
        doc_ref = self.price_list_lines_collection.document(line_id)
        doc = doc_ref.get()

        if not doc.exists:
            return False

        doc_ref.delete()
        return True

    # Price Calculation
    def calculate_product_pricing(
        self,
        product_id: Optional[str],
        base_price: float,
        category_id: Optional[str],
        customer_tier: str,
        quantity: int = 1
    ) -> Optional[Dict]:
        """Calculate pricing for a single product"""
        if not customer_tier:
            customer_tier = DEFAULT_FALLBACK_TIER

        # Get active price lists
        active_price_lists = self.get_all_price_lists(active_only=True)
        
        if not active_price_lists:
            return self._create_base_pricing_result(base_price, customer_tier)

        final_price = base_price
        applied_price_lists = []
        best_discount = 0.0

        # Apply discounts from each price list in priority order
        for price_list in active_price_lists:
            # Check if price list is valid (date range)
            if not self._is_price_list_valid(price_list):
                continue

            # Skip if price list has no ID
            if not price_list.id:
                continue

            # Get applicable lines for this product
            applicable_lines = self._get_applicable_lines(
                price_list.id, product_id, category_id, quantity
            )

            # Find best discount from this price list
            for line in applicable_lines:
                discount = self._calculate_discount(base_price, line)
                if discount > best_discount:
                    best_discount = discount
                    final_price = base_price - discount
                    if price_list.name not in applied_price_lists:
                        applied_price_lists.append(price_list.name)

        discount_percentage = (best_discount / base_price * 100) if base_price > 0 else 0

        return {
            "base_price": base_price,
            "final_price": final_price,
            "discount_applied": best_discount,
            "discount_percentage": discount_percentage,
            "applied_price_lists": applied_price_lists,
            "customer_tier": customer_tier
        }

    def calculate_bulk_product_pricing(
        self,
        products: List[Dict],
        customer_tier: str,
        quantity: int = 1,
    ) -> List[Dict]:
        """Calculate pricing for multiple products efficiently"""
        if not products or not customer_tier:
            return [self._create_base_pricing_result(p.get("price", 0.0), customer_tier) for p in products]

        # Get all active price lists once
        active_price_lists = self.get_all_price_lists(active_only=True)
        
        if not active_price_lists:
            return [self._create_base_pricing_result(p.get("price", 0.0), customer_tier) for p in products]

        # Filter valid price lists once
        valid_price_lists = [pl for pl in active_price_lists if self._is_price_list_valid(pl)]
        
        if not valid_price_lists:
            return [self._create_base_pricing_result(p.get("price", 0.0), customer_tier) for p in products]

        # Get all price list lines for all valid price lists at once
        all_price_lines = {}
        for price_list in valid_price_lists:
            if price_list.id:  # Skip if no ID
                lines = self.get_price_list_lines(price_list.id)
                all_price_lines[price_list.id] = lines

        # Calculate pricing for each product using cached data
        results = []
        for product in products:
            base_price = product.get("price", 0.0)
            product_id = product.get("id")
            category_id = product.get("categoryId")
            
            # Skip products without required data
            if not product_id:
                results.append(self._create_base_pricing_result(base_price, customer_tier))
                continue
            
            final_price = base_price
            applied_price_lists = []
            best_discount = 0.0

            # Apply discounts from each price list in priority order
            for price_list in valid_price_lists:
                if not price_list.id:  # Skip if no ID
                    continue
                lines = all_price_lines.get(price_list.id, [])
                
                # Find applicable lines for this product
                for line in lines:
                    if self._line_applies_to_product(line, product_id, category_id, quantity):
                        discount = self._calculate_discount(base_price, line)
                        if discount > best_discount:
                            best_discount = discount
                            final_price = base_price - discount
                            if price_list.name not in applied_price_lists:
                                applied_price_lists.append(price_list.name)

            discount_percentage = (best_discount / base_price * 100) if base_price > 0 else 0

            results.append({
                "base_price": base_price,
                "final_price": final_price,
                "discount_applied": best_discount,
                "discount_percentage": discount_percentage,
                "applied_price_lists": applied_price_lists,
                "customer_tier": customer_tier
            })

        return results

    # Helper methods
    def _is_price_list_valid(self, price_list: PriceListSchema) -> bool:
        """Check if price list is within valid date range"""
        from datetime import timezone
        now = datetime.now(timezone.utc)
        
        # Convert to timezone-aware if needed
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

    def _get_applicable_lines(
        self,
        price_list_id: str,
        product_id: Optional[str],
        category_id: Optional[str],
        quantity: int
    ) -> List[PriceListLineSchema]:
        """Get price list lines that apply to this product"""
        lines = self.get_price_list_lines(price_list_id)
        applicable_lines = []

        for line in lines:
            if self._line_applies_to_product(line, product_id, category_id, quantity):
                applicable_lines.append(line)

        return applicable_lines

    def _line_applies_to_product(
        self,
        line: PriceListLineSchema,
        product_id: Optional[str],
        category_id: Optional[str],
        quantity: int
    ) -> bool:
        """Check if a price list line applies to a product"""
        # Check type-specific conditions
        if line.type == PriceListType.PRODUCT:
            if not product_id or line.product_id != product_id:
                return False
        elif line.type == PriceListType.CATEGORY:
            if not category_id or line.category_id != category_id:
                return False
        # PriceListType.ALL applies to all products

        # Check quantity constraints
        if quantity < line.min_product_qty:
            return False
        
        if line.max_product_qty and quantity > line.max_product_qty:
            return False

        return True

    def _calculate_discount(self, base_price: float, line: PriceListLineSchema) -> float:
        """Calculate discount amount from a price list line"""
        if line.discount_type == DiscountType.PERCENTAGE:
            return base_price * (line.amount / 100)
        elif line.discount_type == DiscountType.FLAT:
            return min(line.amount, base_price)  # Don't exceed base price
        return 0.0

    def _create_base_pricing_result(self, base_price: float, customer_tier: str) -> Dict:
        """Create base pricing result with no discounts"""
        return {
            "base_price": base_price,
            "final_price": base_price,
            "discount_applied": 0.0,
            "discount_percentage": 0.0,
            "applied_price_lists": [],
            "customer_tier": customer_tier
        }