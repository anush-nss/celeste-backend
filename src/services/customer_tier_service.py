from datetime import datetime, timedelta
from typing import List, Optional, Dict
from src.core.firebase import get_firestore_db
from src.models.tier_models import (
    CustomerTierSchema, CreateCustomerTierSchema, UpdateCustomerTierSchema,
    UserTierProgressSchema, UserTierInfoSchema, TierEvaluationSchema,
    TierRequirementsSchema, TierBenefitsSchema
)
from src.shared.constants import Collections, CustomerTier

class CustomerTierService:
    def __init__(self):
        self.db = get_firestore_db()
        self.customer_tiers_collection = self.db.collection(Collections.CUSTOMER_TIERS)
        self.users_collection = self.db.collection(Collections.USERS)
        self.orders_collection = self.db.collection(Collections.ORDERS)
    
    # Customer Tier Management
    async def create_customer_tier(self, tier_data: CreateCustomerTierSchema) -> CustomerTierSchema:
        """Create a new customer tier"""
        doc_ref = self.customer_tiers_collection.document()
        
        tier_dict = tier_data.model_dump()
        tier_dict.update({
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        })
        
        doc_ref.set(tier_dict)
        
        return CustomerTierSchema(**tier_dict, id=doc_ref.id)
    
    async def get_customer_tier_by_id(self, tier_id: str) -> Optional[CustomerTierSchema]:
        """Get a customer tier by ID"""
        doc = self.customer_tiers_collection.document(tier_id).get()
        if doc.exists:
            tier_data = doc.to_dict()
            if tier_data:
                return CustomerTierSchema(**tier_data, id=doc.id)
        return None
    
    async def get_customer_tier_by_code(self, tier_code: CustomerTier) -> Optional[CustomerTierSchema]:
        """Get a customer tier by tier code"""
        docs = self.customer_tiers_collection.where('tier_code', '==', tier_code.value).limit(1).stream()
        doc = next(docs, None)
        if doc:
            tier_data = doc.to_dict()
            if tier_data:
                return CustomerTierSchema(**tier_data, id=doc.id)
        return None
    
    async def get_all_customer_tiers(self, active_only: bool = False) -> List[CustomerTierSchema]:
        """Get all customer tiers, optionally filtered by active status"""
        query = self.customer_tiers_collection.order_by('level')
        if active_only:
            query = query.where('active', '==', True)
        
        docs = query.stream()
        tiers = []
        for doc in docs:
            tier_data = doc.to_dict()
            if tier_data:
                tiers.append(CustomerTierSchema(**tier_data, id=doc.id))
        return tiers
    
    async def update_customer_tier(self, tier_id: str, tier_data: UpdateCustomerTierSchema) -> Optional[CustomerTierSchema]:
        """Update a customer tier"""
        doc_ref = self.customer_tiers_collection.document(tier_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
        
        update_data = tier_data.model_dump(exclude_unset=True)
        update_data['updated_at'] = datetime.now()
        
        doc_ref.update(update_data)
        
        updated_doc = doc_ref.get()
        if updated_doc.exists:
            updated_data = updated_doc.to_dict()
            if updated_data:
                return CustomerTierSchema(**updated_data, id=updated_doc.id)
        return None
    
    async def delete_customer_tier(self, tier_id: str) -> bool:
        """Delete a customer tier"""
        doc_ref = self.customer_tiers_collection.document(tier_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return False
        
        doc_ref.delete()
        return True
    
    # User Tier Evaluation and Management
    async def get_user_statistics(self, user_id: str) -> Dict:
        """Get user statistics for tier evaluation"""
        # Get user data
        user_doc = self.users_collection.document(user_id).get()
        if not user_doc.exists:
            return {}
        
        user_data = user_doc.to_dict()
        if not user_data:
            return {}
        
        # Get order statistics
        total_orders = user_data.get('total_orders', 0)
        lifetime_value = user_data.get('lifetime_value', 0.0)
        
        # Calculate monthly orders (orders in the last 30 days)
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_orders_query = (self.orders_collection
                              .where('user_id', '==', user_id)
                              .where('createdAt', '>=', thirty_days_ago))
        
        recent_orders = list(recent_orders_query.stream())
        monthly_orders = len(recent_orders)
        
        return {
            'total_orders': total_orders,
            'lifetime_value': lifetime_value,
            'monthly_orders': monthly_orders,
            'last_order_at': user_data.get('last_order_at'),
            'created_at': user_data.get('createdAt')
        }
    
    async def evaluate_user_tier(self, user_id: str) -> TierEvaluationSchema:
        """Evaluate what tier a user should be in based on their activity"""
        # Get user statistics
        stats = await self.get_user_statistics(user_id)
        
        # Get current user tier
        user_doc = self.users_collection.document(user_id).get()
        current_tier = CustomerTier.BRONZE  # default
        if user_doc.exists:
            user_data = user_doc.to_dict()
            if user_data:
                current_tier = CustomerTier(user_data.get('customer_tier', CustomerTier.BRONZE.value))
        
        # Get all active tiers ordered by level
        tiers = await self.get_all_customer_tiers(active_only=True)
        
        # Find eligible tiers
        eligible_tiers = []
        for tier in tiers:
            requirements = tier.requirements
            
            # Check if user meets all requirements
            meets_orders = stats.get('total_orders', 0) >= requirements.min_orders
            meets_value = stats.get('lifetime_value', 0.0) >= requirements.min_lifetime_value
            meets_monthly = stats.get('monthly_orders', 0) >= requirements.min_monthly_orders
            
            if meets_orders and meets_value and meets_monthly:
                eligible_tiers.append(tier.tier_code)
        
        # Find the highest eligible tier
        if not eligible_tiers:
            recommended_tier = CustomerTier.BRONZE
        else:
            # Sort eligible tiers by level (highest first)
            eligible_tier_objects = [tier for tier in tiers if tier.tier_code in eligible_tiers]
            eligible_tier_objects.sort(key=lambda x: x.level, reverse=True)
            recommended_tier = eligible_tier_objects[0].tier_code
        
        tier_changed = recommended_tier != current_tier
        
        return TierEvaluationSchema(
            user_id=user_id,
            total_orders=stats.get('total_orders', 0),
            lifetime_value=stats.get('lifetime_value', 0.0),
            monthly_orders=stats.get('monthly_orders', 0),
            current_tier=current_tier,
            eligible_tiers=eligible_tiers,
            recommended_tier=recommended_tier,
            tier_changed=tier_changed
        )
    
    async def update_user_tier(self, user_id: str, new_tier: CustomerTier) -> bool:
        """Update a user's tier"""
        doc_ref = self.users_collection.document(user_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            return False
        
        doc_ref.update({
            'customer_tier': new_tier.value,
            'updated_at': datetime.now()
        })
        
        return True
    
    async def auto_evaluate_and_update_user_tier(self, user_id: str) -> TierEvaluationSchema:
        """Automatically evaluate and update a user's tier"""
        evaluation = await self.evaluate_user_tier(user_id)
        
        if evaluation.tier_changed:
            success = await self.update_user_tier(user_id, evaluation.recommended_tier)
            if not success:
                evaluation.tier_changed = False
        
        return evaluation
    
    async def get_user_tier_progress(self, user_id: str) -> UserTierProgressSchema:
        """Get a user's current tier and progress towards next tier"""
        # Get current user tier
        user_doc = self.users_collection.document(user_id).get()
        if not user_doc.exists:
            raise ValueError(f"User {user_id} not found")
        
        user_data = user_doc.to_dict()
        if not user_data:
            raise ValueError(f"User {user_id} not found")
        current_tier = CustomerTier(user_data.get('customer_tier', CustomerTier.BRONZE.value))
        
        # Get current tier info
        current_tier_info = await self.get_customer_tier_by_code(current_tier)
        if not current_tier_info:
            raise ValueError(f"Tier {current_tier.value} not found")
        
        # Get user statistics
        stats = await self.get_user_statistics(user_id)
        
        # Find next tier
        all_tiers = await self.get_all_customer_tiers(active_only=True)
        all_tiers.sort(key=lambda x: x.level)
        
        next_tier = None
        next_tier_info = None
        
        for tier in all_tiers:
            if tier.level > current_tier_info.level:
                next_tier = tier.tier_code
                next_tier_info = tier
                break
        
        # Calculate progress towards next tier
        progress = {}
        if next_tier_info:
            next_requirements = next_tier_info.requirements
            
            progress = {
                'orders': {
                    'current': stats.get('total_orders', 0),
                    'required': next_requirements.min_orders,
                    'progress_percentage': min(100, (stats.get('total_orders', 0) / next_requirements.min_orders * 100)) if next_requirements.min_orders > 0 else 100
                },
                'lifetime_value': {
                    'current': stats.get('lifetime_value', 0.0),
                    'required': next_requirements.min_lifetime_value,
                    'progress_percentage': min(100, (stats.get('lifetime_value', 0.0) / next_requirements.min_lifetime_value * 100)) if next_requirements.min_lifetime_value > 0 else 100
                },
                'monthly_orders': {
                    'current': stats.get('monthly_orders', 0),
                    'required': next_requirements.min_monthly_orders,
                    'progress_percentage': min(100, (stats.get('monthly_orders', 0) / next_requirements.min_monthly_orders * 100)) if next_requirements.min_monthly_orders > 0 else 100
                }
            }
        
        return UserTierProgressSchema(
            current_tier=current_tier,
            current_tier_name=current_tier_info.name,
            next_tier=next_tier,
            next_tier_name=next_tier_info.name if next_tier_info else None,
            progress=progress,
            benefits=current_tier_info.benefits
        )
    
    async def get_user_tier_info(self, user_id: str) -> UserTierInfoSchema:
        """Get complete tier information for a user"""
        user_doc = self.users_collection.document(user_id).get()
        if not user_doc.exists:
            raise ValueError(f"User {user_id} not found")
        
        user_data = user_doc.to_dict()
        if not user_data:
            raise ValueError(f"User {user_id} not found")
        current_tier = CustomerTier(user_data.get('customer_tier', CustomerTier.BRONZE.value))
        
        # Get tier info and progress
        tier_info = await self.get_customer_tier_by_code(current_tier)
        if not tier_info:
            raise ValueError(f"Tier {current_tier.value} not found")
        
        progress = await self.get_user_tier_progress(user_id)
        stats = await self.get_user_statistics(user_id)
        
        return UserTierInfoSchema(
            user_id=user_id,
            current_tier=current_tier,
            tier_info=tier_info,
            progress=progress,
            statistics=stats
        )
    
    async def initialize_default_tiers(self) -> List[CustomerTierSchema]:
        """Initialize default customer tiers if they don't exist"""
        existing_tiers = await self.get_all_customer_tiers()
        if existing_tiers:
            return existing_tiers
        
        default_tiers = [
            CreateCustomerTierSchema(
                name="Bronze",
                tier_code=CustomerTier.BRONZE,
                level=1,
                requirements=TierRequirementsSchema(
                    min_orders=0,
                    min_lifetime_value=0.0,
                    min_monthly_orders=0
                ),
                benefits=TierBenefitsSchema(
                    price_list_ids=[],
                    delivery_discount=0.0,
                    priority_support=False,
                    early_access=False
                ),
                icon_url=None,
                color="#CD7F32"
            ),
            CreateCustomerTierSchema(
                name="Silver",
                tier_code=CustomerTier.SILVER,
                level=2,
                requirements=TierRequirementsSchema(
                    min_orders=5,
                    min_lifetime_value=100.0,
                    min_monthly_orders=1
                ),
                benefits=TierBenefitsSchema(
                    price_list_ids=[],
                    delivery_discount=5.0,
                    priority_support=False,
                    early_access=False
                ),
                icon_url=None,
                color="#C0C0C0"
            ),
            CreateCustomerTierSchema(
                name="Gold",
                tier_code=CustomerTier.GOLD,
                level=3,
                requirements=TierRequirementsSchema(
                    min_orders=20,
                    min_lifetime_value=500.0,
                    min_monthly_orders=2
                ),
                benefits=TierBenefitsSchema(
                    price_list_ids=[],
                    delivery_discount=10.0,
                    priority_support=True,
                    early_access=False
                ),
                icon_url=None,
                color="#FFD700"
            ),
            CreateCustomerTierSchema(
                name="Platinum",
                tier_code=CustomerTier.PLATINUM,
                level=4,
                requirements=TierRequirementsSchema(
                    min_orders=50,
                    min_lifetime_value=2000.0,
                    min_monthly_orders=5
                ),
                benefits=TierBenefitsSchema(
                    price_list_ids=[],
                    delivery_discount=15.0,
                    priority_support=True,
                    early_access=True
                ),
                icon_url=None,
                color="#E5E4E2"
            )
        ]
        
        created_tiers = []
        for tier_data in default_tiers:
            created_tier = await self.create_customer_tier(tier_data)
            created_tiers.append(created_tier)
        
        return created_tiers