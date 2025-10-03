import argparse
import asyncio
import os
import sys

# Add the project root to the Python path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.database.base import Base
from src.database.connection import engine
from src.database.models.user import (
    User,
)  # Import User model to ensure it's registered with Base.metadata
from src.database.models.address import Address  # Added import
from src.database.models.cart import Cart  # Added import
from src.database.models.category import Category  # Added import
from src.database.models.ecommerce_category import (
    EcommerceCategory,
)  # Added ecommerce category model
from src.database.models.product import Product, Tag, ProductTag  # Added product models
from src.database.models.associations import (
    product_categories,
)  # Import association table
from src.database.models.store import Store  # Added store model
from src.database.models.store_tag import StoreTag  # Added store tag model
from src.database.models.tier import Tier
from src.database.models.tier_benefit import Benefit, tier_benefits
from src.database.models.price_list import PriceList
from src.database.models.price_list_line import PriceListLine
from src.database.models.tier_price_list import TierPriceList
from src.database.models.inventory import Inventory
from src.database.models.order import Order, OrderItem

# Avoid unused import issues
_ = (
    User,
    Address,
    Cart,
    Category,
    EcommerceCategory,
    Product,
    Tag,
    ProductTag,
    product_categories,
    Store,
    StoreTag,
    Tier,
    Benefit,
    tier_benefits,
    PriceList,
    PriceListLine,
    TierPriceList,
    Inventory,
    Order,
    OrderItem,
)


async def init_db(drop_tables: bool = False):
    async with engine.begin() as conn:
        if drop_tables:
            print("Dropping all tables...")
            await conn.run_sync(Base.metadata.drop_all)
            print("Tables dropped.")
        print("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created.")


async def apply_pricing_optimizations():
    """Apply database optimizations for pricing queries"""
    try:
        from scripts.db.pricing_optimization import (
            apply_pricing_optimizations as pricing_opt_func,
        )

        print("Applying pricing optimizations...")
        await pricing_opt_func()
        print("Pricing optimizations applied successfully.")
    except Exception as e:
        print(f"Warning: Could not apply pricing optimizations: {e}")
        print("This is not critical for database initialization.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize the database.")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop all existing tables before creating new ones.",
    )
    args = parser.parse_args()

    asyncio.run(init_db(drop_tables=args.drop))

    # Apply pricing optimizations
    asyncio.run(apply_pricing_optimizations())
    print("Database initialization complete.")
