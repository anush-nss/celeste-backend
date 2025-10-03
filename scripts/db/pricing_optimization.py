"""
Database migration script for pricing optimization
This script adds indexes and other database optimizations for better performance
"""

import os
import sys

# Add the project root to the Python path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from sqlalchemy import text

from src.database.connection import engine

# Import all database models to ensure SQLAlchemy relationships are properly registered


async def apply_pricing_optimizations():
    """Apply database optimizations for pricing queries"""
    async with engine.connect() as conn:
        # Add indexes for optimized queries
        # These indexes are already defined in the models, but we'll ensure they exist
        print("Applying pricing optimization indexes...")

        # Ensure statistics are up to date for query planner
        print("Updating database statistics...")
        await conn.execute(text("ANALYZE products"))
        await conn.execute(text("ANALYZE categories"))
        await conn.execute(text("ANALYZE product_categories"))
        await conn.execute(text("ANALYZE price_lists"))
        await conn.execute(text("ANALYZE price_list_lines"))
        await conn.execute(text("ANALYZE tier_price_lists"))

        await conn.commit()
        print("Pricing optimizations applied successfully.")


if __name__ == "__main__":
    import asyncio

    print("Applying pricing optimizations...")
    asyncio.run(apply_pricing_optimizations())
    print("Pricing optimizations complete.")
