import asyncio
import argparse
from src.database.base import Base
from src.database.connection import engine
from src.database.models.user import User  # Import User model to ensure it's registered with Base.metadata
from src.database.models.address import Address  # Added import
from src.database.models.cart import Cart  # Added import
from src.database.models.category import Category  # Added import
from src.database.models.product import Product, Tag, ProductTag  # Added product models
from src.database.models.associations import product_categories  # Import association table
from src.database.models.tier import Tier
from src.database.models.tier_benefit import Benefit, tier_benefits
from src.database.models.price_list import PriceList
from src.database.models.price_list_line import PriceListLine
from src.database.models.tier_price_list import TierPriceList

async def init_db(drop_tables: bool = False):
    async with engine.begin() as conn:
        if drop_tables:
            print("Dropping all tables...")
            await conn.run_sync(Base.metadata.drop_all)
            print("Tables dropped.")
        print("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize the database.")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop all existing tables before creating new ones."
    )
    args = parser.parse_args()

    asyncio.run(init_db(drop_tables=args.drop))
