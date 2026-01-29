#!/usr/bin/env python3
"""
Script to update user preferences based on recent interactions.

This script identifies users with recent activity and updates their preference
profiles, including their interest vector, category affinities, and brand affinities.
It is designed to be run as a periodic background job.

Usage:
    python scripts/db/update_user_preferences.py
    python scripts.db.update_user_preferences.py --user-id <USER_ID> # Update a specific user
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy.future import select

# Add the project root to the Python path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.api.personalization.service import PersonalizationService
from src.config.constants import INTERACTION_DECAY_DAYS
from src.database.connection import AsyncSessionLocal, engine
from src.database.models.product_interaction import ProductInteraction

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


async def get_active_users():
    """
    Get a list of user IDs with recent interactions.
    """
    async with AsyncSessionLocal() as session:
        cutoff_date = datetime.now(timezone.utc) - timedelta(
            days=INTERACTION_DECAY_DAYS
        )

        query = (
            select(ProductInteraction.user_id)
            .where(ProductInteraction.timestamp >= cutoff_date)
            .distinct()
            .order_by(ProductInteraction.user_id)
        )

        result = await session.execute(query)
        user_ids = [row[0] for row in result.fetchall()]
        return user_ids


async def main(user_id: str | None = None):
    """
    Main function to run the user preferences update process.
    """
    print("=" * 80)
    print("USER PREFERENCES UPDATE SCRIPT")
    print("=" * 80)
    print()

    personalization_service = PersonalizationService()
    results = {"success": 0, "failed": 0, "skipped": 0}

    try:
        if user_id:
            users_to_update = [user_id]
            print(f"Updating preferences for specific user: {user_id}")
        else:
            print("Fetching active users to update...")
            users_to_update = await get_active_users()
            print(f"Found {len(users_to_update)} active users.")

        if not users_to_update:
            print("No active users to update.")
            return

        for i, current_user_id in enumerate(users_to_update):
            print(f"Processing user {i + 1}/{len(users_to_update)}: {current_user_id}")
            success = await personalization_service.update_user_preferences(
                current_user_id
            )
            if success:
                results["success"] += 1
            else:
                # "Skipped" is more accurate than "failed" if the user has too few interactions
                results["skipped"] += 1

        # Display results
        print()
        print("=" * 80)
        print("PREFERENCE UPDATE RESULTS")
        print("=" * 80)
        print(f"✅ Successfully updated: {results['success']} users")
        print(f"⏭️  Skipped (not enough data): {results['skipped']} users")
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
    print("USER PREFERENCES UPDATE COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update user preferences based on recent interactions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--user-id",
        type=str,
        help="Update preferences for a specific user ID.",
    )

    args = parser.parse_args()

    try:
        asyncio.run(main(user_id=args.user_id))
    except KeyboardInterrupt:
        print("\n\n⚠️  User preference update interrupted by user")
        sys.exit(1)
