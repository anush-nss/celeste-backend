from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List, Optional, Dict
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, desc, text
from sqlalchemy.exc import IntegrityError

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
from src.shared.exceptions import ResourceNotFoundException, ValidationException, ConflictException
from src.shared.error_handler import ErrorHandler, handle_service_errors

logger = get_logger(__name__)


class PricingService:
    """PostgreSQL-based pricing service"""

    def __init__(self):
        self.logger = logger
        self._error_handler = ErrorHandler(__name__)

    # Price List Management
    @handle_service_errors("creating price list")
    async def create_price_list(self, price_list_data: CreatePriceListSchema) -> PriceListSchema:
        """Create a new price list"""
        if not price_list_data.name or not price_list_data.name.strip():
            raise ValidationException(detail="Price list name is required")

        if price_list_data.priority < 0:
            raise ValidationException(detail="Priority cannot be negative")

        async with AsyncSessionLocal() as session:
            # Check for duplicate name
            existing = await session.execute(
                select(PriceList).filter(PriceList.name == price_list_data.name.strip())
            )
            if existing.scalars().first():
                raise ConflictException(detail=f"Price list with name '{price_list_data.name}' already exists")

            new_price_list = PriceList(
                name=price_list_data.name.strip(),
                description=price_list_data.description.strip() if price_list_data.description else None,
                priority=price_list_data.priority,
                valid_from=price_list_data.valid_from or datetime.now(timezone.utc),
                valid_until=price_list_data.valid_until,
                is_active=price_list_data.is_active,
            )
            session.add(new_price_list)
            await session.commit()
            await session.refresh(new_price_list)

            return await self._price_list_to_schema(new_price_list)

    @handle_service_errors("retrieving price list by ID")
    async def get_price_list_by_id(self, price_list_id: int) -> Optional[PriceListSchema]:
        """Get a price list by ID"""
        if price_list_id <= 0:
            raise ValidationException(detail="Price list ID must be a positive integer")

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

    async def create_price_lists(self, price_lists_data: list[CreatePriceListSchema]) -> list[PriceListSchema]:
        """Create multiple new price lists with validation and optimization"""
        if not price_lists_data:
            raise ValidationException(detail="Price list cannot be empty")

        async with AsyncSessionLocal() as session:
            new_price_lists = []
            for price_list_data in price_lists_data:
                if not price_list_data.name or not price_list_data.name.strip():
                    raise ValidationException(detail="Price list name is required")

                if price_list_data.priority < 0:
                    raise ValidationException(detail="Priority cannot be negative")

                # Check for duplicate name
                existing = await session.execute(
                    select(PriceList).filter(PriceList.name == price_list_data.name.strip())
                )
                if existing.scalars().first():
                    raise ConflictException(detail=f"Price list with name '{price_list_data.name}' already exists")

                new_price_list = PriceList(
                    name=price_list_data.name.strip(),
                    description=price_list_data.description.strip() if price_list_data.description else None,
                    priority=price_list_data.priority,
                    valid_from=price_list_data.valid_from or datetime.now(timezone.utc),
                    valid_until=price_list_data.valid_until,
                    is_active=price_list_data.is_active,
                )
                new_price_lists.append(new_price_list)
            
            session.add_all(new_price_lists)
            await session.commit()

            for pl in new_price_lists:
                await session.refresh(pl)

            return [await self._price_list_to_schema(pl) for pl in new_price_lists]

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

    async def add_price_list_lines(self, price_list_id: int, lines_data: list[CreatePriceListLineSchema]) -> list[PriceListLineSchema]:
        """Add multiple lines to a price list"""
        async with AsyncSessionLocal() as session:
            new_lines = []
            for line_data in lines_data:
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
                new_lines.append(new_line)
            
            session.add_all(new_lines)
            await session.commit()

            for line in new_lines:
                await session.refresh(line)

            return [await self._price_list_line_to_schema(line) for line in new_lines]

    # Tier Price List Association Management
    async def assign_price_list_to_tier(self, tier_id: int, price_list_id: int) -> bool:
        """Assign a price list to a tier"""
        async with AsyncSessionLocal() as session:
            try:
                # Check if tier exists
                tier_result = await session.execute(
                    select(Tier).where(Tier.id == tier_id)
                )
                if not tier_result.scalars().first():
                    raise ResourceNotFoundException(detail=f"Tier with ID {tier_id} not found")

                # Check if price list exists
                price_list_result = await session.execute(
                    select(PriceList).where(PriceList.id == price_list_id)
                )
                if not price_list_result.scalars().first():
                    raise ResourceNotFoundException(detail=f"Price list with ID {price_list_id} not found")

                # Check if association already exists
                existing = await session.execute(
                    select(TierPriceList).where(
                        and_(TierPriceList.tier_id == tier_id, TierPriceList.price_list_id == price_list_id)
                    )
                )
                if existing.scalars().first():
                    from src.shared.exceptions import ConflictException
                    raise ConflictException(detail=f"Price list {price_list_id} is already assigned to tier {tier_id}")

                association = TierPriceList(tier_id=tier_id, price_list_id=price_list_id)
                session.add(association)
                await session.commit()
                return True

            except IntegrityError as e:
                await session.rollback()
                # This shouldn't happen now that we check existence first, but just in case
                error_detail = str(e.orig)
                if "tier_id" in error_detail and "is not present" in error_detail:
                    raise ResourceNotFoundException(detail=f"Tier with ID {tier_id} not found")
                elif "price_list_id" in error_detail and "is not present" in error_detail:
                    raise ResourceNotFoundException(detail=f"Price list with ID {price_list_id} not found")
                else:
                    raise

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
    @handle_service_errors("calculating product price")
    async def calculate_product_price(self, user_tier_id: Optional[int], product_id: int, product_category_ids: List[int], quantity: int = 1) -> ProductPricingSchema:
        """Calculate the final price for a product based on user tier and quantity"""
        if product_id <= 0:
            raise ValidationException(detail="Product ID must be a positive integer")

        if quantity <= 0 or quantity > 1000:
            raise ValidationException(detail="Quantity must be between 1 and 1000")

        if user_tier_id is not None and user_tier_id <= 0:
            raise ValidationException(detail="User tier ID must be a positive integer")

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
                # Get applicable price lists for the user's tier in a single query
                tier_price_lists_result = await session.execute(
                    select(TierPriceList)
                    .options(selectinload(TierPriceList.price_list))
                    .where(TierPriceList.tier_id == user_tier_id)
                )
                tier_price_list_associations = tier_price_lists_result.scalars().all()
                
                # Filter active price lists and sort by priority
                active_price_lists = [
                    tpl.price_list for tpl in tier_price_list_associations 
                    if tpl.price_list and tpl.price_list.is_active
                ]
                active_price_lists.sort(key=lambda pl: pl.priority, reverse=True)
                
                # Get all price list IDs for efficient querying
                price_list_ids = [pl.id for pl in active_price_lists]
                
                if price_list_ids:
                    # Check which price lists are currently valid
                    now = datetime.now(timezone.utc)
                    valid_price_lists = [
                        pl for pl in active_price_lists
                        if (not pl.valid_from or now >= pl.valid_from) and 
                           (not pl.valid_until or now <= pl.valid_until)
                    ]
                    
                    if valid_price_lists:
                        # Get all applicable price list lines in a single query
                        lines_query = (
                            select(PriceListLine)
                            .where(PriceListLine.price_list_id.in_([pl.id for pl in valid_price_lists]))
                            .where(PriceListLine.is_active == True)
                            .where(PriceListLine.min_quantity <= quantity)
                        )
                        
                        # Add conditions for product/category matching
                        line_conditions = [
                            PriceListLine.product_id == product_id,
                            PriceListLine.category_id.in_(product_category_ids) if product_category_ids else None,
                            and_(PriceListLine.product_id.is_(None), PriceListLine.category_id.is_(None))
                        ]
                        # Filter out None conditions
                        line_conditions = [cond for cond in line_conditions if cond is not None]
                        lines_query = lines_query.where(or_(*line_conditions))
                        
                        lines_query = lines_query.order_by(
                            PriceListLine.price_list_id,
                            PriceListLine.product_id.desc().nullslast()
                        )
                        
                        lines_result = await session.execute(lines_query)
                        all_lines = lines_result.scalars().all()
                        
                        # Group lines by price list for efficient processing
                        lines_by_price_list = {}
                        for line in all_lines:
                            if line.price_list_id not in lines_by_price_list:
                                lines_by_price_list[line.price_list_id] = []
                            lines_by_price_list[line.price_list_id].append(line)
                        
                        # Process each price list in priority order
                        for price_list in valid_price_lists:
                            if price_list.id in lines_by_price_list:
                                lines = lines_by_price_list[price_list.id]
                                # Process lines for this price list
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
            # Prevent division by zero
            if line.discount_value == 0:
                return base_price
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
        """Calculate pricing for multiple products using comprehensive SQL query"""
        if not user_tier_id:
            # If no tier, return base pricing for all products
            return [
                ProductPricingSchema(
                    product_id=int(p_data["id"]),
                    quantity=p_data.get("quantity", 1),
                    base_price=float(p_data["price"]),
                    final_price=float(p_data["price"]),
                    total_price=float(p_data["price"]) * p_data.get("quantity", 1),
                    savings=0.0,
                    applied_discounts=[]
                )
                for p_data in product_data
            ]
        
        product_ids = [int(p_data["id"]) for p_data in product_data]
        if not product_ids:
            return []

        async with AsyncSessionLocal() as session:
            # Optimized bulk pricing query
            pricing_query = """
                WITH active_price_lists AS (
                    SELECT 
                        pl.id as price_list_id,
                        pl.name as price_list_name,
                        pl.priority,
                        tpl.tier_id
                    FROM price_lists pl
                    JOIN tier_price_lists tpl ON pl.id = tpl.price_list_id
                    WHERE pl.is_active = true
                      AND tpl.tier_id = :tier_id
                      AND (pl.valid_from IS NULL OR pl.valid_from <= NOW())
                      AND (pl.valid_until IS NULL OR pl.valid_until >= NOW())
                ),
                applicable_price_list_lines AS (
                    SELECT
                        pll.*,
                        apl.priority as price_list_priority,
                        apl.price_list_name
                    FROM price_list_lines pll
                    JOIN active_price_lists apl ON pll.price_list_id = apl.price_list_id
                    WHERE pll.is_active = true
                      AND pll.min_quantity = 1
                      AND (
                          pll.product_id = ANY(:product_ids) OR
                          (pll.product_id IS NULL AND pll.category_id IN (
                              SELECT pc.category_id
                              FROM product_categories pc
                              WHERE pc.product_id = ANY(:product_ids)
                          )) OR
                          (pll.product_id IS NULL AND pll.category_id IS NULL)
                      )
                ),
                ranked_pricing AS (
                    SELECT 
                        p.id as product_id,
                        p.base_price,
                        apll.price_list_id,
                        apll.price_list_name,
                        apll.discount_type,
                        apll.discount_value,
                        apll.max_discount_amount,
                        CASE 
                            WHEN apll.discount_type = 'percentage' THEN
                                GREATEST(
                                    0,
                                    p.base_price - (
                                        LEAST(
                                            p.base_price * (apll.discount_value / 100),
                                            COALESCE(apll.max_discount_amount, p.base_price * (apll.discount_value / 100))
                                        )
                                    )
                                )
                            WHEN apll.discount_type = 'flat' THEN
                                GREATEST(0, p.base_price - apll.discount_value)
                            WHEN apll.discount_type = 'fixed_price' THEN
                                apll.discount_value
                            ELSE p.base_price
                        END as calculated_final_price,
                        ROW_NUMBER() OVER (
                            PARTITION BY p.id 
                            ORDER BY 
                                apll.price_list_priority DESC,
                                CASE 
                                    WHEN apll.product_id IS NOT NULL THEN 1
                                    WHEN apll.category_id IS NOT NULL THEN 2
                                    ELSE 3
                                END,
                                apll.id
                        ) as pricing_rank
                    FROM products p
                    LEFT JOIN applicable_price_list_lines apll ON (
                        apll.product_id = p.id OR
                        (apll.product_id IS NULL AND apll.category_id IN (
                            SELECT pc.category_id 
                            FROM product_categories pc 
                            WHERE pc.product_id = p.id
                        )) OR
                        (apll.product_id IS NULL AND apll.category_id IS NULL)
                    )
                    WHERE p.id = ANY(:product_ids)
                ),
                best_pricing AS (
                    SELECT 
                        product_id,
                        base_price,
                        calculated_final_price as final_price,
                        (base_price - calculated_final_price) as savings,
                        discount_type,
                        discount_value,
                        max_discount_amount,
                        price_list_id,
                        price_list_name
                    FROM ranked_pricing
                    WHERE pricing_rank = 1
                )
                SELECT 
                    bp.product_id,
                    bp.final_price,
                    bp.savings,
                    bp.discount_type,
                    bp.discount_value,
                    bp.max_discount_amount,
                    bp.price_list_id,
                    bp.price_list_name,
                    bp.base_price
                FROM best_pricing bp
                WHERE bp.product_id = ANY(:product_ids)
            """
            
            pricing_result = await session.execute(
                text(pricing_query),
                {
                    "tier_id": user_tier_id,
                    "product_ids": product_ids
                }
            )
            pricing_rows = pricing_result.fetchall()
            
            # Create a dictionary for quick lookup
            pricing_dict = {}
            for row in pricing_rows:
                pricing_dict[row.product_id] = row
            
            # Build results
            results = []
            for p_data in product_data:
                product_id = int(p_data["id"])
                quantity = p_data.get("quantity", 1)
                base_price = float(p_data["price"])
                
                if product_id in pricing_dict:
                    pricing_row = pricing_dict[product_id]
                    final_price = float(pricing_row.final_price)
                    savings = float(pricing_row.savings)
                    applied_discounts = [{
                        "price_list_id": pricing_row.price_list_id,
                        "price_list_name": pricing_row.price_list_name,
                        "line_id": None,
                        "discount_type": pricing_row.discount_type,
                        "discount_value": float(pricing_row.discount_value) if pricing_row.discount_value else 0.0,
                        "original_price": base_price,
                        "discounted_price": final_price,
                        "savings": savings
                    }] if pricing_row.price_list_name else []
                else:
                    final_price = base_price
                    savings = 0.0
                    applied_discounts = []
                
                results.append(ProductPricingSchema(
                    product_id=product_id,
                    quantity=quantity,
                    base_price=base_price,
                    final_price=final_price,
                    total_price=final_price * quantity,
                    savings=savings * quantity,
                    applied_discounts=applied_discounts
                ))
            
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