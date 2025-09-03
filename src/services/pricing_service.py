from datetime import datetime
from typing import List, Optional, Dict, Any
from src.core.firebase import get_firestore_db
from src.models.pricing_models import (
    PriceListSchema, CreatePriceListSchema, UpdatePriceListSchema,
    PriceListLineSchema, CreatePriceListLineSchema, UpdatePriceListLineSchema,
    PriceCalculationRequest, PriceCalculationResponse,
    BulkPriceCalculationRequest, BulkPriceCalculationResponse
)
from src.shared.constants import Collections, PriceListType, DiscountType, CustomerTier

class PricingService:
    def __init__(self):
        self.db = get_firestore_db()
        self.price_lists_collection = self.db.collection(Collections.PRICE_LISTS)
        self.price_list_lines_collection = self.db.collection(Collections.PRICE_LIST_LINES)
        self.products_collection = self.db.collection(Collections.PRODUCTS)
        self.customer_tiers_collection = self.db.collection(Collections.CUSTOMER_TIERS)
    
    # Price List Management
    async def create_price_list(self, price_list_data: CreatePriceListSchema) -> PriceListSchema:
        """Create a new price list"""
        doc_ref = self.price_lists_collection.document()
        
        price_list_dict = price_list_data.model_dump()
        price_list_dict.update({
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        })
        
        doc_ref.set(price_list_dict)
        
        return PriceListSchema(**price_list_dict, id=doc_ref.id)
    
    async def get_price_list_by_id(self, price_list_id: str) -> Optional[PriceListSchema]:
        """Get a price list by ID"""
        doc = self.price_lists_collection.document(price_list_id).get()
        if doc.exists:
            doc_data = doc.to_dict()
            if doc_data:
                return PriceListSchema(**doc_data, id=doc.id)
        return None
    
    async def get_all_price_lists(self, active_only: bool = False) -> List[PriceListSchema]:
        """Get all price lists, optionally filtered by active status"""
        query = self.price_lists_collection.order_by('priority')
        if active_only:
            query = query.where('active', '==', True)
        
        docs = query.stream()
        price_lists = []
        for doc in docs:
            doc_data = doc.to_dict()
            if doc_data:
                price_lists.append(PriceListSchema(**doc_data, id=doc.id))
        return price_lists
    
    async def update_price_list(self, price_list_id: str, price_list_data: UpdatePriceListSchema) -> Optional[PriceListSchema]:
        """Update a price list"""
        doc_ref = self.price_lists_collection.document(price_list_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
        
        update_data = price_list_data.model_dump(exclude_unset=True)
        update_data['updated_at'] = datetime.now()
        
        doc_ref.update(update_data)
        
        updated_doc = doc_ref.get()
        if updated_doc.exists:
            updated_data = updated_doc.to_dict()
            if updated_data:
                return PriceListSchema(**updated_data, id=updated_doc.id)
        return None
    
    async def delete_price_list(self, price_list_id: str) -> bool:
        """Delete a price list and its lines"""
        doc_ref = self.price_lists_collection.document(price_list_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return False
        
        # Delete all associated price list lines
        lines_query = self.price_list_lines_collection.where('price_list_id', '==', price_list_id)
        lines_docs = lines_query.stream()
        
        for line_doc in lines_docs:
            line_doc.reference.delete()
        
        # Delete the price list
        doc_ref.delete()
        return True
    
    # Price List Lines Management
    async def create_price_list_line(self, price_list_id: str, line_data: CreatePriceListLineSchema) -> PriceListLineSchema:
        """Create a new price list line"""
        # Validate the line data
        line_data.validate_type_fields()
        
        doc_ref = self.price_list_lines_collection.document()
        
        line_dict = line_data.model_dump()
        line_dict.update({
            'price_list_id': price_list_id,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        })
        
        doc_ref.set(line_dict)
        
        return PriceListLineSchema(**line_dict, id=doc_ref.id)
    
    async def get_price_list_lines(self, price_list_id: str) -> List[PriceListLineSchema]:
        """Get all lines for a price list"""
        docs = self.price_list_lines_collection.where('price_list_id', '==', price_list_id).stream()
        lines = []
        for doc in docs:
            doc_data = doc.to_dict()
            if doc_data:
                lines.append(PriceListLineSchema(**doc_data, id=doc.id))
        return lines
    
    async def update_price_list_line(self, line_id: str, line_data: UpdatePriceListLineSchema) -> Optional[PriceListLineSchema]:
        """Update a price list line"""
        doc_ref = self.price_list_lines_collection.document(line_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
        
        update_data = line_data.model_dump(exclude_unset=True)
        update_data['updated_at'] = datetime.now()
        
        doc_ref.update(update_data)
        
        updated_doc = doc_ref.get()
        if updated_doc.exists:
            updated_data = updated_doc.to_dict()
            if updated_data:
                return PriceListLineSchema(**updated_data, id=updated_doc.id)
        return None
    
    async def delete_price_list_line(self, line_id: str) -> bool:
        """Delete a price list line"""
        doc_ref = self.price_list_lines_collection.document(line_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return False
        
        doc_ref.delete()
        return True
    
    # Price Calculation
    async def get_product_base_price(self, product_id: str) -> float:
        """Get the base price of a product"""
        doc = self.products_collection.document(product_id).get()
        if doc.exists:
            product_data = doc.to_dict()
            if product_data:
                return product_data.get('price', 0.0)
        return 0.0
    
    async def get_tier_price_lists(self, customer_tier: CustomerTier) -> List[str]:
        """Get price list IDs associated with a customer tier"""
        # Get customer tier document
        tier_docs = self.customer_tiers_collection.where('tier_code', '==', customer_tier.value).limit(1).stream()
        tier_doc = next(tier_docs, None)
        
        if tier_doc:
            tier_data = tier_doc.to_dict()
            if tier_data:
                benefits = tier_data.get('benefits', {})
                if benefits:
                    return benefits.get('price_list_ids', [])
        
        return []
    
    async def get_global_price_lists(self) -> List[str]:
        """Get global price lists (those not assigned to specific tiers)"""
        # For now, we'll consider price lists with type 'ALL' as global
        # This can be enhanced with a specific 'is_global' field in the future
        now = datetime.now()
        
        query = self.price_lists_collection.where('active', '==', True).where('valid_from', '<=', now)
        docs = query.stream()
        
        global_lists = []
        for doc in docs:
            data = doc.to_dict()
            if not data:
                continue
                
            valid_until = data.get('valid_until')
            
            # Check if price list is still valid
            if valid_until is None or valid_until >= now:
                # Check if this price list has 'ALL' type lines (making it global)
                lines_query = self.price_list_lines_collection.where('price_list_id', '==', doc.id).where('type', '==', PriceListType.ALL.value).limit(1)
                lines_docs = list(lines_query.stream())
                
                if lines_docs:
                    global_lists.append(doc.id)
        
        return global_lists
    
    async def get_applicable_price_lines(self, price_list_id: str, product_id: str, category_ids: List[str], quantity: int) -> List[PriceListLineSchema]:
        """Get applicable price list lines for a product"""
        lines = []
        
        # Get product-specific lines
        product_lines_query = (self.price_list_lines_collection
                              .where('price_list_id', '==', price_list_id)
                              .where('type', '==', PriceListType.PRODUCT.value)
                              .where('product_id', '==', product_id)
                              .where('min_product_qty', '<=', quantity))
        
        for doc in product_lines_query.stream():
            line_data = doc.to_dict()
            if line_data:
                max_qty = line_data.get('max_product_qty')
                if max_qty is None or quantity <= max_qty:
                    lines.append(PriceListLineSchema(**line_data, id=doc.id))
        
        # Get category-specific lines
        for category_id in category_ids:
            category_lines_query = (self.price_list_lines_collection
                                   .where('price_list_id', '==', price_list_id)
                                   .where('type', '==', PriceListType.CATEGORY.value)
                                   .where('category_id', '==', category_id)
                                   .where('min_product_qty', '<=', quantity))
            
            for doc in category_lines_query.stream():
                line_data = doc.to_dict()
                if line_data:
                    max_qty = line_data.get('max_product_qty')
                    if max_qty is None or quantity <= max_qty:
                        lines.append(PriceListLineSchema(**line_data, id=doc.id))
        
        # Get global lines (type='all')
        global_lines_query = (self.price_list_lines_collection
                              .where('price_list_id', '==', price_list_id)
                              .where('type', '==', PriceListType.ALL.value)
                              .where('min_product_qty', '<=', quantity))
        
        for doc in global_lines_query.stream():
            line_data = doc.to_dict()
            if line_data:
                max_qty = line_data.get('max_product_qty')
                if max_qty is None or quantity <= max_qty:
                    lines.append(PriceListLineSchema(**line_data, id=doc.id))
        
        return lines
    
    def apply_discount(self, base_price: float, price_line: PriceListLineSchema) -> float:
        """Apply a discount from a price list line"""
        if price_line.discount_type == DiscountType.PERCENTAGE:
            discount_amount = base_price * (price_line.amount / 100)
            return max(0, base_price - discount_amount)
        elif price_line.discount_type == DiscountType.FLAT:
            return max(0, base_price - price_line.amount)
        return base_price
    
    async def calculate_price(self, product_id: str, customer_tier: Optional[CustomerTier] = None, quantity: int = 1) -> PriceCalculationResponse:
        """Calculate price for a product considering customer tier and quantity"""
        base_price = await self.get_product_base_price(product_id)
        
        # If no tier provided, return base price
        if not customer_tier:
            return PriceCalculationResponse(
                product_id=product_id,
                base_price=base_price,
                final_price=base_price,
                discount_applied=0.0,
                discount_percentage=0.0,
                customer_tier=None,
                quantity=quantity,
                applied_price_lists=[]
            )
        
        # Get product details for category information
        product_doc = self.products_collection.document(product_id).get()
        category_ids = []
        if product_doc.exists:
            product_data = product_doc.to_dict()
            if product_data:
                category_ids = product_data.get('category_ids', [])
        
        # Get applicable price lists
        tier_price_lists = await self.get_tier_price_lists(customer_tier)
        global_price_lists = await self.get_global_price_lists()
        
        all_price_list_ids = tier_price_lists + global_price_lists
        
        # Get all price lists and sort by priority
        price_lists = []
        for price_list_id in all_price_list_ids:
            price_list = await self.get_price_list_by_id(price_list_id)
            if price_list and price_list.active:
                now = datetime.now()
                if price_list.valid_from <= now and (price_list.valid_until is None or price_list.valid_until >= now):
                    price_lists.append(price_list)
        
        # Sort by priority (lower number = higher priority)
        price_lists.sort(key=lambda x: x.priority)
        
        # Apply discounts from applicable price lists
        final_price = base_price
        applied_price_lists = []
        
        for price_list in price_lists:
            applicable_lines = await self.get_applicable_price_lines(
                price_list.id, product_id, category_ids, quantity
            )
            
            # Apply the best discount from this price list
            best_price = final_price
            for line in applicable_lines:
                discounted_price = self.apply_discount(final_price, line)
                if discounted_price < best_price:
                    best_price = discounted_price
            
            if best_price < final_price:
                final_price = best_price
                applied_price_lists.append(price_list.name)
        
        discount_applied = base_price - final_price
        discount_percentage = (discount_applied / base_price * 100) if base_price > 0 else 0
        
        return PriceCalculationResponse(
            product_id=product_id,
            base_price=base_price,
            final_price=final_price,
            discount_applied=discount_applied,
            discount_percentage=discount_percentage,
            customer_tier=customer_tier.value if customer_tier else None,
            quantity=quantity,
            applied_price_lists=applied_price_lists
        )
    
    async def calculate_bulk_prices(self, request: BulkPriceCalculationRequest) -> BulkPriceCalculationResponse:
        """Calculate prices for multiple products"""
        results = []
        total_base_price = 0.0
        total_final_price = 0.0
        
        for item in request.items:
            calculation = await self.calculate_price(
                item.product_id, 
                CustomerTier(item.customer_tier) if item.customer_tier else None, 
                item.quantity
            )
            results.append(calculation)
            total_base_price += calculation.base_price * calculation.quantity
            total_final_price += calculation.final_price * calculation.quantity
        
        total_savings = total_base_price - total_final_price
        
        return BulkPriceCalculationResponse(
            items=results,
            total_base_price=total_base_price,
            total_final_price=total_final_price,
            total_savings=total_savings
        )