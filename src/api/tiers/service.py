from datetime import datetime, timedelta
from typing import List, Optional, Dict
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, desc

from src.database.connection import AsyncSessionLocal
from src.database.models.tier import Tier
from src.database.models.tier_benefit import TierBenefit
from src.database.models.price_list import PriceList
from src.database.models.price_list_line import PriceListLine
from src.database.models.tier_price_list import TierPriceList
from src.database.models.user import User
from src.shared.utils import get_logger
from src.api.tiers.models import (
    TierSchema,
    CreateTierSchema,
    UpdateTierSchema,
    TierBenefitSchema,
    CreateTierBenefitSchema,
    PriceListSchema,
    PriceListLineSchema,
    UserTierProgressSchema,
    UserTierInfoSchema,
    TierEvaluationSchema,
)
from src.shared.exceptions import ResourceNotFoundException
from .cache import tiers_cache


class TierService:
    def __init__(self):
        self.logger = get_logger(__name__)

    async def create_tier(self, tier_data: CreateTierSchema) -> TierSchema:
        """Create a new tier with benefits"""
        async with AsyncSessionLocal() as session:
            # Create the tier
            new_tier = Tier(
                name=tier_data.name,
                description=tier_data.description,
                sort_order=tier_data.sort_order,
                is_active=tier_data.is_active,
                min_total_spent=tier_data.min_total_spent,
                min_orders_count=tier_data.min_orders_count,
                min_monthly_spent=tier_data.min_monthly_spent,
                min_monthly_orders=tier_data.min_monthly_orders,
            )
            session.add(new_tier)
            await session.flush()  # Get the ID

            # Create benefits if provided
            for benefit_data in tier_data.benefits:
                benefit = TierBenefit(
                    tier_id=new_tier.id,
                    benefit_type=benefit_data.benefit_type.value,
                    discount_type=benefit_data.discount_type.value if benefit_data.discount_type else None,
                    discount_value=benefit_data.discount_value,
                    max_discount_amount=benefit_data.max_discount_amount,
                    min_order_amount=benefit_data.min_order_amount,
                    is_active=benefit_data.is_active,
                )
                session.add(benefit)

            await session.commit()
            await session.refresh(new_tier)

            tiers_cache.invalidate_tier_cache()

            return await self._tier_to_schema(new_tier)

    async def get_tier_by_id(self, tier_id: int) -> Optional[TierSchema]:
        """Get a tier by ID"""
        cached_tier = tiers_cache.get_tier(str(tier_id))
        if cached_tier:
            return TierSchema(**cached_tier)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tier).options(selectinload(Tier.benefits)).where(Tier.id == tier_id)
            )
            tier = result.scalars().first()
            if tier:
                tier_schema = await self._tier_to_schema(tier)
                tiers_cache.set_tier(str(tier_id), tier_schema.model_dump())
                return tier_schema
            return None

    async def get_tier_by_name(self, name: str) -> Optional[TierSchema]:
        """Get a tier by name"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tier).options(selectinload(Tier.benefits)).where(Tier.name == name)
            )
            tier = result.scalars().first()
            if tier:
                return await self._tier_to_schema(tier)
            return None

    async def get_all_tiers(self, active_only: bool = False) -> List[TierSchema]:
        """Get all tiers"""
        cached_tiers = tiers_cache.get_all_tiers()
        if cached_tiers and not active_only: # Simplified cache check
            return [TierSchema(**t) for t in cached_tiers]

        async with AsyncSessionLocal() as session:
            query = select(Tier).options(selectinload(Tier.benefits)).order_by(Tier.sort_order)
            if active_only:
                query = query.where(Tier.is_active == True)
            
            result = await session.execute(query)
            tiers = result.scalars().all()
            
            tier_schemas = [await self._tier_to_schema(tier) for tier in tiers]
            if not active_only:
                tiers_cache.set_all_tiers([t.model_dump() for t in tier_schemas])
            return tier_schemas

    async def update_tier(self, tier_id: int, tier_data: UpdateTierSchema) -> Optional[TierSchema]:
        """Update a tier"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Tier).where(Tier.id == tier_id))
            tier = result.scalars().first()
            
            if not tier:
                return None
            
            update_data = tier_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(tier, key, value)
            
            await session.commit()
            await session.refresh(tier)

            tiers_cache.invalidate_tier_cache(tier_id=str(tier_id))
            
            return await self._tier_to_schema(tier)

    async def _tier_to_schema(self, tier: Tier) -> TierSchema:
        """Convert SQLAlchemy Tier model to Pydantic schema"""
        from src.shared.sqlalchemy_utils import safe_model_validate, safe_model_validate_list
        
        tier_schema = safe_model_validate(TierSchema, tier)
        
        # Handle benefits relationship if loaded
        if hasattr(tier, 'benefits') and tier.benefits:
            tier_schema.benefits = safe_model_validate_list(TierBenefitSchema, tier.benefits)
        
        return tier_schema

    async def delete_tier(self, tier_id: int) -> bool:
        """Delete a tier"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Tier).where(Tier.id == tier_id))
            tier = result.scalars().first()
            
            if not tier:
                return False
            
            await session.delete(tier)
            await session.commit()
            tiers_cache.invalidate_tier_cache(tier_id=str(tier_id))
            return True

    async def get_default_tier(self) -> int:
        """Get the default tier (Bronze tier with lowest sort_order)"""
        cached_tier_id = tiers_cache.get_default_tier()
        if cached_tier_id:
            return int(cached_tier_id)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tier).where(Tier.is_active == True).order_by(Tier.sort_order).limit(1)
            )
            tier = result.scalars().first()
            tier_id = tier.id if tier else 1  # Default to tier ID 1 (Bronze)
            tiers_cache.set_default_tier(str(tier_id))
            return tier_id

    async def get_user_tier_id(self, user_id: str) -> Optional[int]:
        """Get a user's current tier ID"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User.tier_id).where(User.firebase_uid == user_id))
            tier_id = result.scalars().first()
            return tier_id

    async def update_user_tier(self, user_id: str, new_tier_id: int) -> bool:
        """Update a user's tier"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.firebase_uid == user_id))
            user = result.scalars().first()
            
            if not user:
                return False
            
            user.tier_id = new_tier_id
            await session.commit()
            return True

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

    async def get_user_tier_progress(self, user_id: str) -> UserTierProgressSchema:
        current_tier_id = await self.get_user_tier_id(user_id) or await self.get_default_tier()
        current_tier = await self.get_tier_by_id(current_tier_id)
        if not current_tier:
            raise ValueError("Current tier not found")

        if current_tier.id is None:
            raise ValueError("Current tier has no ID")

        all_tiers = await self.get_all_tiers(active_only=True)
        next_tier = next((t for t in all_tiers if t.sort_order > current_tier.sort_order), None)

        stats = await self.get_user_statistics(user_id)
        progress = {}
        if next_tier:
            progress = {
                "total_spent": {
                    "current": stats.get("lifetime_value", 0.0),
                    "required": next_tier.min_total_spent,
                    "progress": (stats.get("lifetime_value", 0.0) / next_tier.min_total_spent) * 100
                    if next_tier.min_total_spent > 0
                    else 100,
                },
                "total_orders": {
                    "current": stats.get("total_orders", 0),
                    "required": next_tier.min_orders_count,
                    "progress": (stats.get("total_orders", 0) / next_tier.min_orders_count) * 100
                    if next_tier.min_orders_count > 0
                    else 100,
                },
            }

        return UserTierProgressSchema(
            current_tier_id=current_tier.id,
            current_tier_name=current_tier.name,
            next_tier_id=next_tier.id if next_tier else None,
            next_tier_name=next_tier.name if next_tier else None,
            progress=progress,
            benefits=current_tier.benefits,
        )

    async def get_user_tier_info(self, user_id: str) -> UserTierInfoSchema:
        current_tier_id = await self.get_user_tier_id(user_id) or await self.get_default_tier()
        tier_info = await self.get_tier_by_id(current_tier_id)
        if not tier_info:
            raise ValueError("Tier information not found")

        progress = await self.get_user_tier_progress(user_id)
        statistics = await self.get_user_statistics(user_id)

        return UserTierInfoSchema(
            user_id=user_id,
            current_tier_id=current_tier_id,
            tier_info=tier_info,
            progress=progress,
            statistics=statistics,
        )

    async def evaluate_user_tier(self, user_id: str) -> TierEvaluationSchema:
        """Evaluate what tier a user should be in based on their activity"""
        stats = await self.get_user_statistics(user_id)
        current_tier_id = await self.get_user_tier_id(user_id) or await self.get_default_tier()
        tiers = await self.get_all_tiers(active_only=True)

        eligible_tier_ids = []
        for tier in tiers:
            if tier.id is not None and (
                stats.get("total_orders", 0) >= tier.min_orders_count
                and stats.get("lifetime_value", 0.0) >= tier.min_total_spent
            ):
                eligible_tier_ids.append(tier.id)

        recommended_tier_id: int = await self.get_default_tier()
        if eligible_tier_ids:
            eligible_tiers = [t for t in tiers if t.id in eligible_tier_ids]
            if eligible_tiers:
                eligible_tiers.sort(key=lambda x: x.sort_order, reverse=True)
                highest_tier = eligible_tiers[0]
                if highest_tier.id is not None:
                    recommended_tier_id = highest_tier.id

        return TierEvaluationSchema(
            user_id=user_id,
            total_orders=stats.get("total_orders", 0),
            lifetime_value=stats.get("lifetime_value", 0.0),
            monthly_orders=0,  # Not tracking monthly orders anymore
            current_tier_id=current_tier_id,
            eligible_tier_ids=eligible_tier_ids,
            recommended_tier_id=recommended_tier_id,
            tier_changed=recommended_tier_id != current_tier_id,
        )

    async def auto_evaluate_and_update_user_tier(self, user_id: str) -> TierEvaluationSchema:
        """Automatically evaluate and update a user's tier"""
        evaluation = await self.evaluate_user_tier(user_id)

        if evaluation.tier_changed:
            success = await self.update_user_tier(user_id, evaluation.recommended_tier_id)
            if not success:
                evaluation.tier_changed = False

        return evaluation

    async def initialize_default_tiers(self) -> List[TierSchema]:
        """Initialize default tiers if they don't exist"""
        existing_tiers = await self.get_all_tiers()
        if existing_tiers:
            return existing_tiers

        from src.api.tiers.models import CreateTierBenefitSchema, BenefitType, DiscountType

        default_tiers_data = [
            CreateTierSchema(
                name="Bronze",
                description="Default tier",
                sort_order=1,
                min_total_spent=0.0,
                min_orders_count=0,
                benefits=[]
            ),
            CreateTierSchema(
                name="Silver", 
                description="Premium tier",
                sort_order=2,
                min_total_spent=500.0,
                min_orders_count=5,
                benefits=[
                    CreateTierBenefitSchema(
                        benefit_type=BenefitType.DELIVERY_DISCOUNT,
                        discount_type=DiscountType.PERCENTAGE,
                        discount_value=10.0,
                        max_discount_amount=50.0
                    ),
                    CreateTierBenefitSchema(
                        benefit_type=BenefitType.FREE_SHIPPING,
                        min_order_amount=200.0
                    )
                ]
            ),
            CreateTierSchema(
                name="Gold",
                description="VIP tier", 
                sort_order=3,
                min_total_spent=2000.0,
                min_orders_count=20,
                benefits=[
                    CreateTierBenefitSchema(
                        benefit_type=BenefitType.DELIVERY_DISCOUNT,
                        discount_type=DiscountType.PERCENTAGE,
                        discount_value=15.0,
                        max_discount_amount=100.0
                    ),
                    CreateTierBenefitSchema(
                        benefit_type=BenefitType.ORDER_DISCOUNT,
                        discount_type=DiscountType.PERCENTAGE,
                        discount_value=5.0,
                        max_discount_amount=200.0,
                        min_order_amount=100.0
                    ),
                    CreateTierBenefitSchema(
                        benefit_type=BenefitType.FREE_SHIPPING,
                        min_order_amount=100.0
                    )
                ]
            )
        ]

        created_tiers = []
        for tier_data in default_tiers_data:
            created_tier = await self.create_tier(tier_data)
            created_tiers.append(created_tier)

        return created_tiers
