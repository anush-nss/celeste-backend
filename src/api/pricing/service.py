from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List, Optional, Dict
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, desc

from src.database.connection import AsyncSessionLocal
# Import all models to ensure relationships are properly registered
import src.database.models
from src.database.models.price_list import PriceList
from src.database.models.price_list_line import PriceListLine
from src.database.models.tier_price_list import TierPriceList
from src.database.models.tier import Tier
from src.database.models.product import Product
from src.database.models.category import Category

from src.shared.utils import get_logger
from src.api.pricing.models import (
    PriceListSchema,
    CreatePriceListSchema,
    UpdatePriceListSchema,
    PriceListLineSchema,
    CreatePriceListLineSchema,
    UpdatePriceListLineSchema,
    ProductPricingSchema,
    TierPriceListAssignmentSchema,
    DiscountType,
)
from src.shared.exceptions import ResourceNotFoundException

logger = get_logger(__name__)


class PricingService:
    """PostgreSQL-based pricing service"""

    def __init__(self):
        self.logger = logger

    # Price List Management
    async def create_price_list(self, price_list_data: CreatePriceListSchema) -> PriceListSchema:
        """Create a new price list"""
        async with AsyncSessionLocal() as session:
            new_price_list = PriceList(
                name=price_list_data.name,
                description=price_list_data.description,
                priority=price_list_data.priority,
                valid_from=price_list_data.valid_from or datetime.now(),
                valid_until=price_list_data.valid_until,
                is_active=price_list_data.is_active,
            )
            session.add(new_price_list)
            await session.commit()
            await session.refresh(new_price_list)
            
            return await self._price_list_to_schema(new_price_list)

    async def get_price_list_by_id(self, price_list_id: int) -> Optional[PriceListSchema]:
        """Get a price list by ID"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(PriceList).options(selectinload(PriceList.lines)).where(PriceList.id == price_list_id)
            )
            price_list = result.scalars().first()
            if price_list:
                return await self._price_list_to_schema(price_list)
            return None

    async def get_all_price_lists(self, active_only: bool = False) -> List[PriceListSchema]:
        """Get all price lists"""
        async with AsyncSessionLocal() as session:
            query = select(PriceList).options(selectinload(PriceList.lines)).order_by(PriceList.priority.desc())
            if active_only:
                query = query.where(PriceList.is_active == True)
            
            result = await session.execute(query)
            price_lists = result.scalars().all()
            
            return [await self._price_list_to_schema(pl) for pl in price_lists]

    async def update_price_list(self, price_list_id: int, price_list_data: UpdatePriceListSchema) -> Optional[PriceListSchema]:
        """Update a price list"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(PriceList).where(PriceList.id == price_list_id))
            price_list = result.scalars().first()
            
            if not price_list:
                return None
            
            update_data = price_list_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(price_list, key, value)
            
            await session.commit()
            await session.refresh(price_list)
            
            return await self._price_list_to_schema(price_list)

    async def delete_price_list(self, price_list_id: int) -> bool:
        """Delete a price list"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(PriceList).where(PriceList.id == price_list_id))
            price_list = result.scalars().first()
            
            if not price_list:
                return False
            
            await session.delete(price_list)
            await session.commit()
            return True

    # Price List Line Management  
    async def add_price_list_line(self, price_list_id: int, line_data: CreatePriceListLineSchema) -> PriceListLineSchema:
        """Add a line to a price list"""
        async with AsyncSessionLocal() as session:
            new_line = PriceListLine(
                price_list_id=price_list_id,
                product_id=line_data.product_id,
                category_id=line_data.category_id,
                discount_type=line_data.discount_type.value,
                discount_value=line_data.discount_value,
                max_discount_amount=line_data.max_discount_amount,
                min_quantity=line_data.min_quantity,
                min_order_amount=line_data.min_order_amount,
                is_active=line_data.is_active,
            )
            session.add(new_line)
            await session.commit()
            await session.refresh(new_line)
            
            return await self._price_list_line_to_schema(new_line)

    async def get_price_list_lines(self, price_list_id: int) -> List[PriceListLineSchema]:
        """Get all lines for a price list"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(PriceListLine).where(PriceListLine.price_list_id == price_list_id)
            )
            lines = result.scalars().all()
            
            return [await self._price_list_line_to_schema(line) for line in lines]

    async def update_price_list_line(self, line_id: int, line_data: UpdatePriceListLineSchema) -> Optional[PriceListLineSchema]:
        """Update a price list line"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(PriceListLine).where(PriceListLine.id == line_id))
            line = result.scalars().first()
            
            if not line:
                return None
            
            update_data = line_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                if key == "discount_type" and value:
                    setattr(line, key, value.value)
                else:
                    setattr(line, key, value)
            
            await session.commit()
            await session.refresh(line)
            
            return await self._price_list_line_to_schema(line)

    async def delete_price_list_line(self, line_id: int) -> bool:
        """Delete a price list line"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(PriceListLine).where(PriceListLine.id == line_id))
            line = result.scalars().first()
            
            if not line:
                return False
            
            await session.delete(line)
            await session.commit()
            return True

    # Tier Price List Association Management
    async def assign_price_list_to_tier(self, tier_id: int, price_list_id: int) -> bool:
        """Assign a price list to a tier"""
        async with AsyncSessionLocal() as session:
            # Check if association already exists
            existing = await session.execute(
                select(TierPriceList).where(
                    and_(TierPriceList.tier_id == tier_id, TierPriceList.price_list_id == price_list_id)
                )
            )
            if existing.scalars().first():
                return True  # Already exists
            
            association = TierPriceList(tier_id=tier_id, price_list_id=price_list_id)
            session.add(association)
            await session.commit()
            return True

    async def remove_price_list_from_tier(self, tier_id: int, price_list_id: int) -> bool:
        """Remove a price list from a tier"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(TierPriceList).where(
                    and_(TierPriceList.tier_id == tier_id, TierPriceList.price_list_id == price_list_id)
                )
            )
            association = result.scalars().first()
            
            if not association:
                return False
            
            await session.delete(association)
            await session.commit()
            return True

    async def get_tier_price_lists(self, tier_id: int) -> List[PriceListSchema]:
        """Get all price lists for a tier"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(TierPriceList)
                .options(selectinload(TierPriceList.price_list))
                .where(TierPriceList.tier_id == tier_id)
            )
            tier_price_lists = result.scalars().all()
            
            price_lists = [tpl.price_list for tpl in tier_price_lists if tpl.price_list and tpl.price_list.is_active]
            price_lists.sort(key=lambda pl: pl.priority, reverse=True)

            return [await self._price_list_to_schema(pl) for pl in price_lists]

    # Pricing Calculation Methods
    async def calculate_product_price(self, user_tier_id: Optional[int], product_id: int, product_category_ids: List[int], quantity: int = 1) -> ProductPricingSchema:
        """Calculate the final price for a product based on user tier and quantity"""
        async with AsyncSessionLocal() as session:
            # Get product base price
            product_result = await session.execute(select(Product).where(Product.id == product_id))
            product = product_result.scalars().first()
            
            if not product:
                raise ResourceNotFoundException(detail=f"Product with ID {product_id} not found")
            
            base_price = product.base_price
            final_price = base_price
            applied_discounts = []
            
            if user_tier_id:
                # Get applicable price lists for the user's tier
                tier_price_lists = await self.get_tier_price_lists(user_tier_id)
                
                for price_list in tier_price_lists:
                    # Check if price list is valid (date range)
                    now = datetime.now(timezone.utc)
                    if price_list.valid_from and now < price_list.valid_from:
                        continue
                    if price_list.valid_until and now > price_list.valid_until:
                        continue
                    
                    # Find applicable lines for this product
                    lines_result = await session.execute(
                        select(PriceListLine)
                        .where(PriceListLine.price_list_id == price_list.id)
                        .where(PriceListLine.is_active == True)
                        .where(
                            or_(
                                PriceListLine.product_id == product_id,
                                PriceListLine.category_id.in_(product_category_ids), # Specific categories of the product
                                and_(PriceListLine.product_id.is_(None), PriceListLine.category_id.is_(None))
                            )
                        )
                        .where(PriceListLine.min_quantity <= quantity)
                        .order_by(PriceListLine.product_id.desc().nullslast())  # Product-specific first
                    )
                    
                    lines = lines_result.scalars().all()
                    
                    for line in lines:
                        discount_applied = self._apply_discount(base_price, line, quantity)
                        if discount_applied < final_price:
                            final_price = discount_applied
                            applied_discounts.append({
                                "price_list_id": price_list.id,
                                "price_list_name": price_list.name,
                                "line_id": line.id,
                                "discount_type": line.discount_type,
                                "discount_value": float(line.discount_value),
                                "original_price": float(base_price),
                                "discounted_price": float(round(discount_applied, 2)),
                                "savings": float(round(base_price - discount_applied, 2))
                            })
                            break  # Use first applicable discount from this price list
            
            return ProductPricingSchema(
                product_id=product_id,
                quantity=quantity,
                base_price=float(base_price),
                final_price=float(round(final_price, 2)),
                total_price=float(round(final_price * quantity, 2)),
                savings=float(round((base_price - final_price) * quantity, 2)),
                applied_discounts=applied_discounts
            )

    def _apply_discount(self, base_price: Decimal, line: PriceListLine, quantity: int) -> Decimal:
        """Apply a discount from a price list line"""
        if line.discount_type == "percentage":
            discount_amount = base_price * (line.discount_value / 100)
            if line.max_discount_amount:
                discount_amount = min(discount_amount, line.max_discount_amount)
            return base_price - discount_amount
        
        elif line.discount_type == "flat":
            return max(Decimal(0), base_price - line.discount_value)
        
        elif line.discount_type == "fixed_price":
            return line.discount_value
        
        return base_price

    async def calculate_bulk_product_pricing(self, product_data: List[Dict[str, Any]], user_tier_id: Optional[int]) -> List[ProductPricingSchema]:
        """Calculate pricing for multiple products"""
        
        results = []
        for p_data in product_data:
            product_id = int(p_data["id"])
            quantity = p_data.get("quantity", 1)
            product_category_ids = p_data.get("category_ids", [])
            try:
                pricing = await self.calculate_product_price(user_tier_id, product_id, product_category_ids, quantity)
                results.append(pricing)
            except ResourceNotFoundException:
                # Skip products that don't exist
                continue
        
        return results

    # Helper methods
    async def _price_list_to_schema(self, price_list: PriceList) -> PriceListSchema:
        """Convert SQLAlchemy PriceList model to Pydantic schema"""
        from src.shared.sqlalchemy_utils import safe_model_validate
        return safe_model_validate(PriceListSchema, price_list)

    async def _price_list_line_to_schema(self, line: PriceListLine) -> PriceListLineSchema:
        """Convert SQLAlchemy PriceListLine model to Pydantic schema"""
        from src.shared.sqlalchemy_utils import safe_model_validate
        return safe_model_validate(PriceListLineSchema, line)