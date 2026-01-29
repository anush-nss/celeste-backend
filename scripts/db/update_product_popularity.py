#!/usr/bin/env python3
"""
Script to update popularity scores for all products.

This script calculates and updates popularity metrics (overall score, trending score)
for all products that have recorded interactions. It is designed to be run as a
periodic background job to keep popularity data fresh.

Usage:
    python scripts/db/update_product_popularity.py
"""

import argparse
import asyncio
import os
import sys

# Add the project root to the Python path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.api.products.services.popularity_service import PopularityService
from src.database.connection import engine

# Import all database models to ensure SQLAlchemy relationships are properly registered
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


async def main():
    """
    Main function to run the product popularity update process.
    """
    print("=" * 80)
    print("PRODUCT POPULARITY UPDATE SCRIPT")
    print("=" * 80)
    print()

    popularity_service = PopularityService()

    try:
        # Update popularity scores for all products
        results = await popularity_service.update_all_popularity_scores()

        # Display results
        print()
        print("=" * 80)
        print("POPULARITY UPDATE RESULTS")
        print("=" * 80)
        print(f"✅ Successfully updated: {results['success']} products")
        print(f"❌ Failed to update:    {results['failed']} products")
        print()

        total = results["success"] + results["failed"]
        if total > 0:
            success_rate = (results["success"] / total) * 100
            print(f"Success rate: {success_rate:.1f}%")
        print()

    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    finally:
        # Properly dispose of the engine to close all connections
        await engine.dispose()

    print("=" * 80)
    print("POPULARITY UPDATE COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update popularity scores for all products.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script connects to the database, finds all products with interactions,
and recalculates their popularity and trending scores.

It's recommended to run this script as a scheduled job (e.g., daily) to
ensure product popularity rankings are always up-to-date.
        """,
    )

    # No arguments needed for this script yet, but parser is here for future extension
    args = parser.parse_args()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Popularity update interrupted by user")
        sys.exit(1)
