import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, desc, delete

from src.database.connection import AsyncSessionLocal
# Import all models to ensure relationships are properly registered
import src.database.models
from src.database.models.tier import Tier
from src.database.models.tier_benefit import Benefit
from src.database.models.price_list import PriceList
from src.database.models.price_list_line import PriceListLine
from src.database.models.tier_price_list import TierPriceList
from src.database.models.user import User
from src.shared.utils import get_logger
from src.api.tiers.models import (
    TierSchema,
    CreateTierSchema,
    UpdateTierSchema,
    BenefitSchema,
    CreateBenefitSchema,
    UpdateBenefitSchema,
    PriceListSchema,
    PriceListLineSchema,
    UserTierProgressSchema,
    UserTierInfoSchema,
    TierEvaluationSchema,
)
from src.shared.exceptions import ResourceNotFoundException, ValidationException, ConflictException
from src.shared.error_handler import ErrorHandler, handle_service_errors
from src.shared.performance_utils import async_timer, BatchProcessor
from sqlalchemy.exc import IntegrityError


class TierService:
    def __init__(self):
        self.logger = get_logger(__name__)
        self._error_handler = ErrorHandler(__name__)
        self._batch_processor = BatchProcessor(batch_size=50)

    @handle_service_errors("creating tier")
    @async_timer("create_tier")
    async def create_tier(self, tier_data: CreateTierSchema) -> TierSchema:
        """Create a new tier with benefits"""
        if not tier_data.name or not tier_data.name.strip():
            raise ValidationException(detail="Tier name is required")

        if tier_data.min_total_spent < 0:
            raise ValidationException(detail="Minimum total spent cannot be negative")

        if tier_data.min_orders_count < 0:
            raise ValidationException(detail="Minimum orders count cannot be negative")

        async with AsyncSessionLocal() as session:
            # Check for duplicate name
            existing = await session.execute(
                select(Tier).filter(Tier.name == tier_data.name.strip())
            )
            if existing.scalars().first():
                raise ConflictException(detail=f"Tier with name '{tier_data.name}' already exists")

            # Create the tier
            new_tier = Tier(
                name=tier_data.name.strip(),
                description=tier_data.description.strip() if tier_data.description else None,
                sort_order=tier_data.sort_order,
                is_active=tier_data.is_active,
                min_total_spent=tier_data.min_total_spent,
                min_orders_count=tier_data.min_orders_count,
                min_monthly_spent=tier_data.min_monthly_spent,
                min_monthly_orders=tier_data.min_monthly_orders,
            )
            session.add(new_tier)
            await session.flush()  # Get the ID

            # Associate existing benefits if provided
            if tier_data.benefits:
                for benefit_id in tier_data.benefits:
                    # Ensure benefit exists before creating association
                    existing_benefit = await session.execute(
                        select(Benefit).where(Benefit.id == benefit_id)
                    )
                    if existing_benefit.scalars().first():
                        from src.database.models.tier_benefit import tier_benefits
                        await session.execute(
                            tier_benefits.insert().values(tier_id=new_tier.id, benefit_id=benefit_id)
                        )

            # Associate existing price lists if provided
            for price_list_id in tier_data.price_lists:
                # Create TierPriceList association
                tier_price_list = TierPriceList(
                    tier_id=new_tier.id,
                    price_list_id=price_list_id
                )
                session.add(tier_price_list)

            await session.commit()
            
            # Load the tier with relationships
            result = await session.execute(
                select(Tier).options(
                    selectinload(Tier.benefits),
                    selectinload(Tier.price_lists).selectinload(TierPriceList.price_list)
                ).where(Tier.id == new_tier.id)
            )
            tier_with_relations = result.scalars().first()

            return await self._tier_to_schema(tier_with_relations)

    async def get_tier_by_id(self, tier_id: int) -> Optional[TierSchema]:
        """Get a tier by ID"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tier).options(
                    selectinload(Tier.benefits),
                    selectinload(Tier.price_lists).selectinload(TierPriceList.price_list)
                ).where(Tier.id == tier_id)
            )
            tier = result.scalars().first()
            if tier:
                return await self._tier_to_schema(tier)
            return None

    async def get_tier_by_name(self, name: str) -> Optional[TierSchema]:
        """Get a tier by name"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tier).options(
                    selectinload(Tier.benefits),
                    selectinload(Tier.price_lists).selectinload(TierPriceList.price_list)
                ).where(Tier.name == name)
            )
            tier = result.scalars().first()
            if tier:
                return await self._tier_to_schema(tier)
            return None

    @handle_service_errors("retrieving all tiers")
    @async_timer("get_all_tiers")
    async def get_all_tiers(self, active_only: bool = False) -> List[TierSchema]:
        """Get all tiers with optimized loading"""
        async with AsyncSessionLocal() as session:
            query = select(Tier).options(
                selectinload(Tier.benefits),
                selectinload(Tier.price_lists).selectinload(TierPriceList.price_list)
            ).order_by(Tier.sort_order)
            if active_only:
                query = query.where(Tier.is_active == True)

            result = await session.execute(query)
            tiers = result.scalars().unique().all()  # Use unique() for selectinload

            # Process in batches if many tiers
            if len(tiers) > 20:
                return await self._batch_processor.process_in_batches(
                    list(tiers),
                    lambda batch: [self._tier_to_schema(tier) for tier in batch]
                )
            else:
                return [await self._tier_to_schema(tier) for tier in tiers]

    async def update_tier(self, tier_id: int, tier_data: UpdateTierSchema) -> Optional[TierSchema]:
        """Update a tier"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tier)
                .options(selectinload(Tier.benefits), selectinload(Tier.price_lists))
                .where(Tier.id == tier_id)
            )
            tier = result.scalars().first()
            
            if not tier:
                return None
            
            update_data = tier_data.model_dump(exclude_unset=True)

            # Handle benefits and price_lists separately
            new_benefit_ids = update_data.pop('benefits', None)
            new_price_list_ids = update_data.pop('price_lists', None)

            for key, value in update_data.items():
                setattr(tier, key, value)

            if new_benefit_ids is not None:
                from src.database.models.tier_benefit import tier_benefits
                # Clear existing benefits and add new ones
                await session.execute(delete(tier_benefits).where(tier_benefits.c.tier_id == tier_id))
                for benefit_id in new_benefit_ids:
                    benefit = await session.get(Benefit, benefit_id)
                    if benefit:
                        await session.execute(
                            tier_benefits.insert().values(tier_id=tier_id, benefit_id=benefit_id)
                        )

            if new_price_list_ids is not None:
                # Clear existing price lists and add new ones
                await session.execute(delete(TierPriceList).where(TierPriceList.tier_id == tier_id))
                for price_list_id in new_price_list_ids:
                    price_list = await session.get(PriceList, price_list_id)
                    if price_list:
                        new_association = TierPriceList(tier_id=tier_id, price_list_id=price_list_id)
                        session.add(new_association)
            
            await session.commit()
            
            # Load the tier with relationships
            result = await session.execute(
                select(Tier).options(
                    selectinload(Tier.benefits),
                    selectinload(Tier.price_lists).selectinload(TierPriceList.price_list)
                ).where(Tier.id == tier_id)
            )
            tier_with_relations = result.scalars().first()

            return await self._tier_to_schema(tier_with_relations)

    async def _tier_to_schema(self, tier: Tier) -> TierSchema:
        """Convert SQLAlchemy Tier model to Pydantic schema"""
        from src.shared.sqlalchemy_utils import sqlalchemy_to_dict, safe_model_validate_list
        
        # Convert to dict but handle relationships properly
        tier_dict = sqlalchemy_to_dict(tier)
        
        # Ensure relationship fields have proper default values
        if 'benefits' not in tier_dict or tier_dict['benefits'] is None:
            tier_dict['benefits'] = []
        elif isinstance(tier_dict['benefits'], list):
            # Convert benefits to proper schema
            tier_dict['benefits'] = safe_model_validate_list(BenefitSchema, tier.benefits)
            
        if 'price_lists' not in tier_dict or tier_dict['price_lists'] is None:
            tier_dict['price_lists'] = []
        elif hasattr(tier, 'price_lists') and tier.price_lists is not None:
            # Convert price_lists to proper schema
            tier_dict['price_lists'] = safe_model_validate_list(PriceListSchema, [tpl.price_list for tpl in tier.price_lists])
        
        return TierSchema.model_validate(tier_dict)

    async def delete_tier(self, tier_id: int) -> bool:
        """Delete a tier"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Tier).where(Tier.id == tier_id))
            tier = result.scalars().first()
            
            if not tier:
                return False
            
            await session.delete(tier)
            await session.commit()
            return True

    async def get_default_tier(self) -> Optional[int]:
        """Get the default tier (Bronze tier with lowest sort_order)"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tier).where(Tier.is_active == True).order_by(Tier.sort_order).limit(1)
            )
            tier = result.scalars().first()
            return tier.id if tier else None  # Return None if no tiers exist

    async def get_user_tier_id(self, user_id: str) -> Optional[int]:
        """Get a user's current tier ID"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User.tier_id).where(User.firebase_uid == user_id))
            tier_id = result.scalars().first()
            return tier_id

    async def update_user_tier(self, user_id: str, new_tier_id: int) -> bool:
        """Update a user's tier"""
        async with AsyncSessionLocal() as session:
            try:
                # Check if user exists
                user_result = await session.execute(select(User).where(User.firebase_uid == user_id))
                user = user_result.scalars().first()

                if not user:
                    raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")

                # Check if tier exists
                tier_result = await session.execute(select(Tier).where(Tier.id == new_tier_id))
                tier = tier_result.scalars().first()

                if not tier:
                    raise ResourceNotFoundException(detail=f"Tier with ID {new_tier_id} not found")

                user.tier_id = new_tier_id
                await session.commit()
                return True

            except IntegrityError as e:
                await session.rollback()
                # This shouldn't happen now that we check existence first, but just in case
                error_detail = str(e.orig)
                if "tier_id" in error_detail and "is not present" in error_detail:
                    raise ResourceNotFoundException(detail=f"Tier with ID {new_tier_id} not found")
                else:
                    raise

    async def get_user_statistics(self, user_id: str) -> Dict:
        """Get user statistics for tier evaluation"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.firebase_uid == user_id)
            )
            user = result.scalars().first()
            
            if not user:
                return {}
            
            return {
                "total_orders": user.total_orders or 0,
                "lifetime_value": user.lifetime_value or 0.0,
                "last_order_at": user.last_order_at,
                "created_at": user.created_at,
            }

    @handle_service_errors("evaluating user tier")
    @async_timer("evaluate_user_tier")
    async def evaluate_user_tier(self, user_id: str) -> TierEvaluationSchema:
        """Evaluate what tier a user should be in based on their activity"""
        if not user_id or not user_id.strip():
            raise ValidationException(detail="Valid user ID is required")

        # Batch these operations for performance
        stats, current_tier_id, tiers = await asyncio.gather(
            self.get_user_statistics(user_id.strip()),
            self.get_user_tier_id(user_id.strip()),
            self.get_all_tiers(active_only=True)
        )

        if current_tier_id is None:
            current_tier_id = await self.get_default_tier()

        eligible_tier_ids = []
        for tier in tiers:
            if tier.id is not None and (
                stats.get("total_orders", 0) >= tier.min_orders_count
                and stats.get("lifetime_value", 0.0) >= tier.min_total_spent
            ):
                eligible_tier_ids.append(tier.id)

        recommended_tier_id = await self.get_default_tier()
        if eligible_tier_ids:
            eligible_tiers = [t for t in tiers if t.id in eligible_tier_ids]
            if eligible_tiers:
                eligible_tiers.sort(key=lambda x: x.sort_order, reverse=True)
                highest_tier = eligible_tiers[0]
                if highest_tier.id is not None:
                    recommended_tier_id = highest_tier.id

        # Handle case where no tiers exist at all
        if current_tier_id is None and recommended_tier_id is None:
            # If no tiers exist, create default response
            return TierEvaluationSchema(
                user_id=user_id,
                total_orders=stats.get("total_orders", 0),
                lifetime_value=stats.get("lifetime_value", 0.0),
                monthly_orders=0,
                current_tier_id=0,  # Use 0 to indicate no tier
                eligible_tier_ids=[],
                recommended_tier_id=0,  # Use 0 to indicate no tier
                tier_changed=False,
            )

        return TierEvaluationSchema(
            user_id=user_id,
            total_orders=stats.get("total_orders", 0),
            lifetime_value=stats.get("lifetime_value", 0.0),
            monthly_orders=0,  # Not tracking monthly orders anymore
            current_tier_id=current_tier_id or 0,
            eligible_tier_ids=eligible_tier_ids,
            recommended_tier_id=recommended_tier_id or 0,
            tier_changed=(recommended_tier_id or 0) != (current_tier_id or 0),
        )

    async def auto_evaluate_and_update_user_tier(self, user_id: str) -> TierEvaluationSchema:
        """Automatically evaluate and update a user's tier"""
        evaluation = await self.evaluate_user_tier(user_id)

        if evaluation.tier_changed:
            success = await self.update_user_tier(user_id, evaluation.recommended_tier_id)
            if not success:
                evaluation.tier_changed = False

        return evaluation

    async def get_user_tier_info(self, user_id: str) -> UserTierInfoSchema:
        """Get complete tier information for a user"""
        current_tier_id = await self.get_user_tier_id(user_id)
        if current_tier_id is None:
            raise ValidationException(detail=f"User {user_id} not found or has no tier assigned")

        tier_info = await self.get_tier_by_id(current_tier_id)
        if not tier_info:
            raise ValidationException(detail=f"Tier with ID {current_tier_id} not found")

        progress = await self.get_user_tier_progress(user_id)
        stats = await self.get_user_statistics(user_id)

        return UserTierInfoSchema(
            user_id=user_id,
            current_tier_id=current_tier_id,
            tier_info=tier_info,
            progress=progress,
            statistics=stats,
        )

    async def get_user_tier_progress(self, user_id: str) -> UserTierProgressSchema:
        """Get a user's current tier and progress towards next tier"""
        current_tier_id = await self.get_user_tier_id(user_id)
        if current_tier_id is None:
            raise ValidationException(detail=f"User {user_id} not found or has no tier assigned")

        current_tier_info = await self.get_tier_by_id(current_tier_id)
        if not current_tier_info:
            raise ValidationException(detail=f"Tier with ID {current_tier_id} not found")

        stats = await self.get_user_statistics(user_id)
        all_tiers = await self.get_all_tiers(active_only=True)

        # Find next tier (higher sort_order)
        next_tier_info = None
        for tier in sorted(all_tiers, key=lambda x: x.sort_order):
            if tier.sort_order > current_tier_info.sort_order:
                next_tier_info = tier
                break

        progress = {}
        if next_tier_info:
            progress = {
                "orders": {
                    "current": stats.get("total_orders", 0),
                    "required": next_tier_info.min_orders_count,
                    "progress_percentage": (
                        min(100, (stats.get("total_orders", 0) / next_tier_info.min_orders_count * 100))
                        if next_tier_info.min_orders_count > 0 else 100
                    )
                },
                "spending": {
                    "current": stats.get("lifetime_value", 0),
                    "required": next_tier_info.min_total_spent,
                    "progress_percentage": (
                        min(100, (stats.get("lifetime_value", 0) / next_tier_info.min_total_spent * 100))
                        if next_tier_info.min_total_spent > 0 else 100
                    )
                }
            }

        return UserTierProgressSchema(
            current_tier_id=current_tier_id,
            current_tier_name=current_tier_info.name,
            next_tier_id=next_tier_info.id if next_tier_info else None,
            next_tier_name=next_tier_info.name if next_tier_info else None,
            progress=progress,
            benefits=current_tier_info.benefits,
        )

    async def initialize_default_tiers(self) -> List[TierSchema]:
        """Initialize default tiers if they don't exist"""
        existing_tiers = await self.get_all_tiers()
        if existing_tiers:
            return existing_tiers

        from src.api.tiers.models import CreateBenefitSchema, BenefitType, DiscountType

        default_tiers_data = [
            CreateTierSchema(
                name="Bronze",
                description="Default tier for new customers",
                sort_order=1,
                min_total_spent=0.0,
                min_orders_count=0,
                benefits=[]
            ),
            CreateTierSchema(
                name="Silver", 
                description="Premium tier for valued customers",
                sort_order=2,
                min_total_spent=500.0,
                min_orders_count=5,
                benefits=[]
            ),
            CreateTierSchema(
                name="Gold",
                description="VIP tier for our best customers", 
                sort_order=3,
                min_total_spent=2000.0,
                min_orders_count=20,
                benefits=[]
            )
        ]

        created_tiers = []
        for tier_data in default_tiers_data:
            created_tier = await self.create_tier(tier_data)
            created_tiers.append(created_tier)

        return created_tiers

    # Benefit CRUD methods
    async def create_benefit(self, benefit_data: CreateBenefitSchema) -> BenefitSchema:
        """Create a new benefit"""
        async with AsyncSessionLocal() as session:
            new_benefit = Benefit(
                benefit_type=benefit_data.benefit_type.value,
                discount_type=benefit_data.discount_type.value,
                discount_value=benefit_data.discount_value,
                max_discount_amount=benefit_data.max_discount_amount,
                min_order_value=benefit_data.min_order_value,
                min_items=benefit_data.min_items,
                is_active=benefit_data.is_active,
            )
            session.add(new_benefit)
            await session.commit()
            await session.refresh(new_benefit)

            from src.shared.sqlalchemy_utils import sqlalchemy_to_dict
            benefit_dict = sqlalchemy_to_dict(new_benefit)
            return BenefitSchema.model_validate(benefit_dict)

    async def get_benefit_by_id(self, benefit_id: int) -> Optional[BenefitSchema]:
        """Get a benefit by ID"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Benefit).where(Benefit.id == benefit_id))
            benefit = result.scalars().first()
            if benefit:
                from src.shared.sqlalchemy_utils import sqlalchemy_to_dict
                benefit_dict = sqlalchemy_to_dict(benefit)
                return BenefitSchema.model_validate(benefit_dict)
            return None

    async def get_all_benefits(self, active_only: bool = False) -> List[BenefitSchema]:
        """Get all benefits"""
        async with AsyncSessionLocal() as session:
            query = select(Benefit).order_by(Benefit.id)
            if active_only:
                query = query.where(Benefit.is_active == True)
            
            result = await session.execute(query)
            benefits = result.scalars().all()
            
            from src.shared.sqlalchemy_utils import sqlalchemy_to_dict
            return [BenefitSchema.model_validate(sqlalchemy_to_dict(benefit)) for benefit in benefits]

    async def update_benefit(self, benefit_id: int, benefit_data: UpdateBenefitSchema) -> Optional[BenefitSchema]:
        """Update a benefit"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Benefit).where(Benefit.id == benefit_id))
            benefit = result.scalars().first()
            
            if not benefit:
                return None
            
            update_data = benefit_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                if key in ['benefit_type', 'discount_type'] and value is not None:
                    setattr(benefit, key, value.value if hasattr(value, 'value') else value)
                else:
                    setattr(benefit, key, value)
            
            await session.commit()
            await session.refresh(benefit)
            
            from src.shared.sqlalchemy_utils import sqlalchemy_to_dict
            benefit_dict = sqlalchemy_to_dict(benefit)
            return BenefitSchema.model_validate(benefit_dict)

    async def delete_benefit(self, benefit_id: int) -> bool:
        """Delete a benefit"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Benefit).where(Benefit.id == benefit_id))
            benefit = result.scalars().first()
            
            if not benefit:
                return False
            
            await session.delete(benefit)
            await session.commit()
            return True

    async def associate_benefit_to_tier(self, tier_id: int, benefit_id: int) -> bool:
        """Associate a benefit with a tier"""
        async with AsyncSessionLocal() as session:
            # Check if tier exists
            tier_result = await session.execute(select(Tier).where(Tier.id == tier_id))
            tier = tier_result.scalars().first()
            if not tier:
                raise ResourceNotFoundException(detail=f"Tier with ID {tier_id} not found")

            # Check if benefit exists
            benefit_result = await session.execute(select(Benefit).where(Benefit.id == benefit_id))
            benefit = benefit_result.scalars().first()
            if not benefit:
                raise ResourceNotFoundException(detail=f"Benefit with ID {benefit_id} not found")

            # Check if association already exists using a direct query
            from src.database.models.tier_benefit import tier_benefits
            association_result = await session.execute(
                select(tier_benefits).where(
                    tier_benefits.c.tier_id == tier_id,
                    tier_benefits.c.benefit_id == benefit_id
                )
            )
            association = association_result.first()
            
            if not association:
                # Create the association
                await session.execute(
                    tier_benefits.insert().values(tier_id=tier_id, benefit_id=benefit_id)
                )
                await session.commit()
                return True  # Newly created
            else:
                # Already exists
                raise ConflictException(detail="Benefit already associated with tier")

    async def remove_benefit_from_tier(self, tier_id: int, benefit_id: int) -> bool:
        """Remove a benefit from a tier"""
        async with AsyncSessionLocal() as session:
            # Check if tier exists
            tier_result = await session.execute(select(Tier).where(Tier.id == tier_id))
            tier = tier_result.scalars().first()
            if not tier:
                return False

            # Check if benefit exists
            benefit_result = await session.execute(select(Benefit).where(Benefit.id == benefit_id))
            benefit = benefit_result.scalars().first()
            if not benefit:
                return False

            # Check if association exists using a direct query
            from src.database.models.tier_benefit import tier_benefits
            association_result = await session.execute(
                select(tier_benefits).where(
                    tier_benefits.c.tier_id == tier_id,
                    tier_benefits.c.benefit_id == benefit_id
                )
            )
            association = association_result.first()
            
            if association:
                # Remove the association
                await session.execute(
                    tier_benefits.delete().where(
                        tier_benefits.c.tier_id == tier_id,
                        tier_benefits.c.benefit_id == benefit_id
                    )
                )
                await session.commit()
                return True

            return False

    async def get_tier_benefits(self, tier_id: int) -> List[BenefitSchema]:
        """Get all benefits for a specific tier"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tier).options(selectinload(Tier.benefits)).where(Tier.id == tier_id)
            )
            tier = result.scalars().first()
            if not tier:
                return []

            from src.shared.sqlalchemy_utils import sqlalchemy_to_dict
            return [BenefitSchema.model_validate(sqlalchemy_to_dict(benefit)) for benefit in tier.benefits]