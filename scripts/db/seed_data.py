import asyncio
import os
import sys

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.api.tiers.service import TierService
from src.database.connection import engine
from sqlalchemy import text

# Import all models to ensure mappers are configured correctly
from src.database.models.user import User
from src.database.models.address import Address
from src.database.models.cart import Cart
from src.database.models.category import Category
from src.database.models.ecommerce_category import EcommerceCategory
from src.database.models.product import Product, Tag, ProductTag
from src.database.models.store import Store
from src.database.models.store_tag import StoreTag
from src.database.models.tier import Tier
from src.database.models.tier_benefit import Benefit, tier_benefits
from src.database.models.price_list import PriceList
from src.database.models.price_list_line import PriceListLine
from src.database.models.tier_price_list import TierPriceList
from src.database.models.inventory import Inventory
from src.database.models.order import Order, OrderItem
from src.database.models.payment import PaymentTransaction
from src.database.models.payment_token import UserPaymentToken
from src.database.models.webhook_notification import WebhookNotification
from src.database.models.rider import RiderProfile, StoreRider

async def seed_data():
    """Seed initial lookup data for the database."""
    print("Starting database seeding...")
    
    tier_service = TierService()
    
    try:
        # 1. Seed Tiers
        print("Seeding tiers...")
        tiers = await tier_service.initialize_default_tiers()
        print(f"Initialized {len(tiers)} tiers.")
        
        # 2. Ensure Tier ID 1 exists (fallback default)
        # In case initialize_default_tiers() created it with a different ID due to prior deletions
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT id FROM tiers WHERE id = 1"))
            if not result.first():
                print("Warning: Tier ID 1 (default fallback) does not exist even after initialization.")
                # We could force ID 1 here if needed, but initialize_default_tiers should have handled it 
                # if it was the first record.
                
        print("Database seeding completed successfully.")
        
    except Exception as e:
        print(f"Error during seeding: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_data())
