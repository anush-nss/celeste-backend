#!/usr/bin/env python3
"""
Script to retry failed Odoo order synchronizations.

This script finds all orders with an 'odoo_sync_status' of 'failed' and
attempts to sync them to Odoo again. It can be run for all failed orders
or for a specific order ID.

Usage:
    # Retry all failed Odoo syncs
    python scripts/db/retry_failed_odoo_syncs.py

    # Retry a specific order
    python scripts/db/retry_failed_odoo_syncs.py --order-id 123
"""

import argparse
import asyncio
import os
import sys
from typing import List, Optional

from sqlalchemy import select

# Add the project root to the Python path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.config.constants import OdooSyncStatus
from src.database.connection import AsyncSessionLocal, engine
from src.database.models.order import Order

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
from src.database.models.payment import PaymentTransaction
from src.database.models.payment_token import UserPaymentToken
from src.database.models.webhook_notification import WebhookNotification
from src.database.models.rider import RiderProfile, StoreRider

from src.integrations.odoo.order_sync import OdooOrderSync


async def get_orders_to_retry(order_id: Optional[int] = None) -> List[int]:
    """
    Get a list of order IDs to retry.

    Args:
        order_id: If provided, returns a list containing only this ID.
                  Otherwise, fetches all orders with a 'failed' sync status.

    Returns:
        A list of order IDs.
    """
    if order_id:
        return [order_id]

    async with AsyncSessionLocal() as session:
        query = select(Order.id).where(Order.odoo_sync_status == OdooSyncStatus.FAILED)
        result = await session.execute(query)
        order_ids = [row[0] for row in result.fetchall()]
        return order_ids


async def main(order_id: Optional[int] = None):
    """
    Main function to run the Odoo sync retry process.

    Args:
        order_id: A specific order ID to retry.
    """
    print("=" * 80)
    print("RETRY FAILED ODOO ORDER SYNCS SCRIPT")
    print("=" * 80)
    print()

    results = {"success": 0, "failed": 0}
    odoo_sync = OdooOrderSync()

    try:
        orders_to_retry = await get_orders_to_retry(order_id)

        if not orders_to_retry:
            print("✅ No failed Odoo syncs found to retry.")
            return

        print(f"Found {len(orders_to_retry)} orders to retry.")
        print()

        for i, current_order_id in enumerate(orders_to_retry):
            print(
                f"--> Processing order {i + 1}/{len(orders_to_retry)} (ID: {current_order_id})..."
            )
            try:
                sync_result = await odoo_sync.sync_order_to_odoo(current_order_id)
                if sync_result.get("success"):
                    print(f"    ✅ Successfully synced order {current_order_id}")
                    results["success"] += 1
                else:
                    print(
                        f"    ❌ Failed to sync order {current_order_id}. Reason: {sync_result.get('error')}"
                    )
                    results["failed"] += 1
            except Exception as e:
                print(
                    f"    ❌ An unexpected error occurred while syncing order {current_order_id}: {e}"
                )
                results["failed"] += 1
            print("-" * 40)

        # Display final results
        print()
        print("=" * 80)
        print("SYNC RETRY RESULTS")
        print("=" * 80)
        print(f"✅ Successfully synced: {results['success']} orders")
        print(f"❌ Failed to sync:      {results['failed']} orders")
        print()

    except Exception as e:
        print(f"❌ An unexpected error occurred during the script execution: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    finally:
        # Properly dispose of the engine to close all connections
        await engine.dispose()

    print("=" * 80)
    print("ODOO SYNC RETRY COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Retry failed Odoo order synchronizations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Retry all orders with a 'failed' sync status
  python scripts/db/retry_failed_odoo_syncs.py

  # Retry only a specific order by its ID
  python scripts/db/retry_failed_odoo_syncs.py --order-id 123
        """,
    )

    parser.add_argument(
        "--order-id",
        type=int,
        help="A specific order ID to retry, ignoring all others.",
    )

    args = parser.parse_args()

    try:
        asyncio.run(main(order_id=args.order_id))
    except KeyboardInterrupt:
        print("\n\n⚠️  Odoo sync retry interrupted by user")
        sys.exit(1)
