import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from google.cloud.firestore_v1.base_query import FieldFilter
from src.shared.db_client import db_client
from src.shared.utils import get_logger
from src.config.cache_config import cache_config
from .cache import tiers_cache
from src.api.tiers.models import (
    CustomerTierSchema,
    CreateCustomerTierSchema,
    UpdateCustomerTierSchema,
    UserTierProgressSchema,
    UserTierInfoSchema,
    TierEvaluationSchema,
    TierRequirementsSchema,
    TierBenefitsSchema,
)
from src.config.constants import Collections, DEFAULT_FALLBACK_TIER


class TierService:
    def __init__(self):
        self.customer_tiers_collection = db_client.collection(Collections.CUSTOMER_TIERS)
        self.users_collection = db_client.collection(Collections.USERS)
        self.orders_collection = db_client.collection(Collections.ORDERS)
        self.logger = get_logger(__name__)

    async def create_customer_tier(
        self, tier_data: CreateCustomerTierSchema
    ) -> CustomerTierSchema:
        """Create a new customer tier"""
        doc_ref = self.customer_tiers_collection.document()

        tier_dict = tier_data.model_dump()
        tier_dict.update({"created_at": datetime.now(), "updated_at": datetime.now()})

        await doc_ref.set(tier_dict)
        
        new_tier = CustomerTierSchema(**tier_dict, id=doc_ref.id)
        tiers_cache.set_tier(doc_ref.id, new_tier.model_dump())
        tiers_cache.set_tier_by_code(new_tier.tier_code, new_tier.model_dump())
        
        tiers_cache.invalidate_tier_cache()

        return new_tier

    async def get_customer_tier_by_id(
        self, tier_id: str
    ) -> Optional[CustomerTierSchema]:
        """Get a customer tier by ID"""
        cached_tier = tiers_cache.get_tier(tier_id)
        if cached_tier:
            return CustomerTierSchema(**cached_tier)

        doc = await self.customer_tiers_collection.document(tier_id).get()
        if doc.exists:
            tier_data = doc.to_dict()
            if tier_data:
                tier = CustomerTierSchema(**tier_data, id=doc.id)
                tiers_cache.set_tier(tier_id, tier.model_dump())
                return tier
        return None

    async def get_customer_tier_by_code(
        self, tier_code: str
    ) -> Optional[CustomerTierSchema]:
        """Get a customer tier by tier code with caching"""
        cached_tier = tiers_cache.get_tier_by_code(tier_code)
        if cached_tier:
            return CustomerTierSchema(**cached_tier)

        try:
            docs = (
                self.customer_tiers_collection.where(filter=FieldFilter("tier_code", "==", tier_code))
                .limit(1)
                .stream()
            )
            async for doc in docs:
                tier_data = doc.to_dict()
                if tier_data:
                    tier = CustomerTierSchema(**tier_data, id=doc.id)
                    tiers_cache.set_tier_by_code(tier_code, tier.model_dump())
                    return tier
        except Exception as e:
            self.logger.error(f"Error in get_customer_tier_by_code: {e}")
        
        return None

    async def get_all_customer_tiers(
        self, active_only: bool = False
    ) -> List[CustomerTierSchema]:
        """Get all customer tiers with caching"""
        cached_tiers = tiers_cache.get_all_tiers()
        if cached_tiers:
            if active_only:
                return [CustomerTierSchema(**t) for t in cached_tiers if t.get("active")]
            return [CustomerTierSchema(**t) for t in cached_tiers]

        try:
            query = self.customer_tiers_collection
            if active_only:
                query = query.where(filter=FieldFilter("active", "==", True))
            docs = query.stream()
            tiers = []
            async for doc in docs:
                tier_data = doc.to_dict()
                if tier_data:
                    tiers.append(CustomerTierSchema(**tier_data, id=doc.id))

            tiers.sort(key=lambda x: x.level)
            
            tiers_cache.set_all_tiers([t.model_dump() for t in tiers])

            if active_only:
                return [tier for tier in tiers if tier.active]
            
            return tiers

        except Exception as e:
            self.logger.error(f"Error in get_all_customer_tiers: {e}")
            return []

    async def update_customer_tier(
        self, tier_id: str, tier_data: UpdateCustomerTierSchema
    ) -> Optional[CustomerTierSchema]:
        """Update a customer tier"""
        doc_ref = self.customer_tiers_collection.document(tier_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return None

        update_data = tier_data.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.now()

        await doc_ref.update(update_data)

        updated_doc = await doc_ref.get()
        if updated_doc.exists:
            updated_data = updated_doc.to_dict()
            if updated_data:
                updated_tier = CustomerTierSchema(**updated_data, id=updated_doc.id)
                tiers_cache.invalidate_tier_cache(tier_id=tier_id, tier_code=updated_tier.tier_code)
                return updated_tier
        return None

    async def delete_customer_tier(self, tier_id: str) -> bool:
        """Delete a customer tier"""
        doc_ref = self.customer_tiers_collection.document(tier_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return False
        
        tier_data = doc.to_dict()
        if not tier_data:
            return False

        await doc_ref.delete()
        tiers_cache.invalidate_tier_cache(tier_id=tier_id, tier_code=tier_data.get("tier_code"))
        return True

    async def get_default_tier(self) -> str:
        """Get the default tier with caching"""
        cached_tier_code = tiers_cache.get_default_tier()
        if cached_tier_code:
            return cached_tier_code

        try:
            docs = (
                self.customer_tiers_collection.where(filter=FieldFilter("is_default", "==", True))
                .where(filter=FieldFilter("active", "==", True))
                .limit(1)
                .stream()
            )
            async for doc in docs:
                tier_data = doc.to_dict()
                if tier_data:
                    tier_code = tier_data.get("tier_code", DEFAULT_FALLBACK_TIER)
                    tiers_cache.set_default_tier(tier_code)
                    return tier_code
        except Exception as e:
            self.logger.error(f"Error in get_default_tier: {e}")

        return DEFAULT_FALLBACK_TIER

    async def get_user_tier(self, user_id: str) -> Optional[str]:
        """Get a user's current tier"""
        user_doc = await self.users_collection.document(user_id).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            if user_data and user_data.get("customer_tier"):
                return user_data["customer_tier"]
        return None

    async def update_user_tier(self, user_id: str, new_tier: str) -> bool:
        """Update a user's tier"""
        doc_ref = self.users_collection.document(user_id)
        doc = await doc_ref.get()

        if not doc.exists:
            return False

        await doc_ref.update({"customer_tier": new_tier, "updated_at": datetime.now()})
        return True

    async def get_user_statistics(self, user_id: str) -> Dict:
        """Get user statistics for tier evaluation"""
        user_doc = await self.users_collection.document(user_id).get()
        if not user_doc.exists:
            return {}

        user_data = user_doc.to_dict()
        if not user_data:
            return {}

        total_orders = user_data.get("total_orders", 0)
        lifetime_value = user_data.get("lifetime_value", 0.0)

        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_orders_query = self.orders_collection.where(
            filter=FieldFilter("user_id", "==", user_id)
        ).where(filter=FieldFilter("createdAt", ">=", thirty_days_ago))

        recent_orders = [doc async for doc in recent_orders_query.stream()]
        monthly_orders = len(recent_orders)

        return {
            "total_orders": total_orders,
            "lifetime_value": lifetime_value,
            "monthly_orders": monthly_orders,
            "last_order_at": user_data.get("last_order_at"),
            "created_at": user_data.get("createdAt"),
        }

    async def evaluate_user_tier(self, user_id: str) -> TierEvaluationSchema:
        """Evaluate what tier a user should be in based on their activity"""
        stats = await self.get_user_statistics(user_id)
        current_tier_code = await self.get_user_tier(user_id) or await self.get_default_tier()
        tiers = await self.get_all_customer_tiers(active_only=True)

        eligible_tiers = []
        for tier in tiers:
            requirements = tier.requirements
            if (
                stats.get("total_orders", 0) >= requirements.min_orders and
                stats.get("lifetime_value", 0.0) >= requirements.min_lifetime_value and
                stats.get("monthly_orders", 0) >= requirements.min_monthly_orders
            ):
                eligible_tiers.append(tier.tier_code)

        recommended_tier = DEFAULT_FALLBACK_TIER
        if eligible_tiers:
            eligible_tier_objects = [tier for tier in tiers if tier.tier_code in eligible_tiers]
            eligible_tier_objects.sort(key=lambda x: x.level, reverse=True)
            recommended_tier = eligible_tier_objects[0].tier_code

        return TierEvaluationSchema(
            user_id=user_id,
            total_orders=stats.get("total_orders", 0),
            lifetime_value=stats.get("lifetime_value", 0.0),
            monthly_orders=stats.get("monthly_orders", 0),
            current_tier=current_tier_code,
            eligible_tiers=eligible_tiers,
            recommended_tier=recommended_tier,
            tier_changed=recommended_tier != current_tier_code,
        )

    async def auto_evaluate_and_update_user_tier(
        self, user_id: str
    ) -> TierEvaluationSchema:
        """Automatically evaluate and update a user's tier"""
        evaluation = await self.evaluate_user_tier(user_id)

        if evaluation.tier_changed:
            success = await self.update_user_tier(user_id, evaluation.recommended_tier)
            if not success:
                evaluation.tier_changed = False

        return evaluation

    async def get_user_tier_progress(self, user_id: str) -> UserTierProgressSchema:
        """Get a user's current tier and progress towards next tier"""
        current_tier_code = await self.get_user_tier(user_id)
        if not current_tier_code:
            raise ValueError(f"User {user_id} not found")

        current_tier_info = await self.get_customer_tier_by_code(current_tier_code)
        if not current_tier_info:
            raise ValueError(f"Tier {current_tier_code} not found")

        stats = await self.get_user_statistics(user_id)
        all_tiers = await self.get_all_customer_tiers(active_only=True)

        next_tier_info = None
        for tier in all_tiers:
            if tier.level > current_tier_info.level:
                next_tier_info = tier
                break

        progress = {}
        if next_tier_info:
            next_requirements = next_tier_info.requirements
            progress = {
                "orders": {
                    "current": stats.get("total_orders", 0),
                    "required": next_requirements.min_orders,
                    "progress_percentage": (
                        min(100, (stats.get("total_orders", 0) / next_requirements.min_orders * 100))
                        if next_requirements.min_orders > 0 else 100
                    ),
                },
                "lifetime_value": {
                    "current": stats.get("lifetime_value", 0.0),
                    "required": next_requirements.min_lifetime_value,
                    "progress_percentage": (
                        min(100, (stats.get("lifetime_value", 0.0) / next_requirements.min_lifetime_value * 100))
                        if next_requirements.min_lifetime_value > 0 else 100
                    ),
                },
                "monthly_orders": {
                    "current": stats.get("monthly_orders", 0),
                    "required": next_requirements.min_monthly_orders,
                    "progress_percentage": (
                        min(100, (stats.get("monthly_orders", 0) / next_requirements.min_monthly_orders * 100))
                        if next_requirements.min_monthly_orders > 0 else 100
                    ),
                },
            }

        return UserTierProgressSchema(
            current_tier=current_tier_code,
            current_tier_name=current_tier_info.name,
            next_tier=next_tier_info.tier_code if next_tier_info else None,
            next_tier_name=next_tier_info.name if next_tier_info else None,
            progress=progress,
            benefits=current_tier_info.benefits,
        )

    async def get_user_tier_info(self, user_id: str) -> UserTierInfoSchema:
        """Get complete tier information for a user"""
        current_tier_code = await self.get_user_tier(user_id)
        if not current_tier_code:
            raise ValueError(f"User {user_id} not found")

        tier_info = await self.get_customer_tier_by_code(current_tier_code)
        if not tier_info:
            raise ValueError(f"Tier {current_tier_code} not found")

        progress = await self.get_user_tier_progress(user_id)
        stats = await self.get_user_statistics(user_id)

        return UserTierInfoSchema(
            user_id=user_id,
            current_tier=current_tier_code,
            tier_info=tier_info,
            progress=progress,
            statistics=stats,
        )

    async def initialize_default_tiers(self) -> List[CustomerTierSchema]:
        """Initialize default customer tiers if they don't exist"""
        existing_tiers = await self.get_all_customer_tiers()
        if existing_tiers:
            return existing_tiers

        default_tiers_data = [
            {
                "name": "Bronze", "tier_code": "BRONZE", "level": 1,
                "requirements": {"min_orders": 0, "min_lifetime_value": 0.0, "min_monthly_orders": 0},
                "benefits": {"price_list_ids": [], "delivery_discount": 0.0, "priority_support": False, "early_access": False},
                "icon_url": None, "color": "#CD7F32", "is_default": True,
            },
            {
                "name": "Silver", "tier_code": "SILVER", "level": 2,
                "requirements": {"min_orders": 5, "min_lifetime_value": 100.0, "min_monthly_orders": 1},
                "benefits": {"price_list_ids": [], "delivery_discount": 5.0, "priority_support": False, "early_access": False},
                "icon_url": None, "color": "#C0C0C0",
            },
            {
                "name": "Gold", "tier_code": "GOLD", "level": 3,
                "requirements": {"min_orders": 20, "min_lifetime_value": 500.0, "min_monthly_orders": 2},
                "benefits": {"price_list_ids": [], "delivery_discount": 10.0, "priority_support": True, "early_access": False},
                "icon_url": None, "color": "#FFD700",
            },
            {
                "name": "Platinum", "tier_code": "PLATINUM", "level": 4,
                "requirements": {"min_orders": 50, "min_lifetime_value": 2000.0, "min_monthly_orders": 5},
                "benefits": {"price_list_ids": [], "delivery_discount": 15.0, "priority_support": True, "early_access": True},
                "icon_url": None, "color": "#E5E4E2",
            },
        ]

        tasks = [self.create_customer_tier(CreateCustomerTierSchema(**data)) for data in default_tiers_data]
        created_tiers = await asyncio.gather(*tasks)

        return created_tiers
