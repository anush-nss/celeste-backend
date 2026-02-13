"""
Odoo Order Synchronization Service

High-level service for syncing orders and customers to Odoo ERP.
Handles customer creation, order creation, and error recovery.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.config.constants import (
    OdooSyncStatus,
    DELIVERY_PRODUCT_ODOO_ID,
    ODOO_AGGREGATOR_SELECTION,
    ODOO_SALESPERSON_ID,
)
from src.database.connection import AsyncSessionLocal
from src.database.models.order import Order
from src.database.models.user import User
from src.integrations.odoo.exceptions import (
    OdooAuthenticationError,
    OdooConnectionError,
    OdooSyncError,
)
from src.integrations.odoo.service import OdooService
from src.shared.error_handler import ErrorHandler


class OdooOrderSync:
    """
    High-level service for synchronizing orders to Odoo

    Handles:
    - Customer sync (find or create)
    - Order creation with proper pricing and discounts
    - Order line creation
    - Error handling and retry logic
    """

    def __init__(self):
        self.odoo = OdooService()
        self._error_handler = ErrorHandler(__name__)
        # Thread pool for blocking Odoo RPC calls
        self._executor = ThreadPoolExecutor(max_workers=4)

    @retry(
        retry=retry_if_exception_type((OdooConnectionError, OdooAuthenticationError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def sync_order_to_odoo(self, order_id: int) -> Dict[str, Any]:
        """
        Sync a confirmed order to Odoo

        Args:
            order_id: Our internal order ID

        Returns:
            Dict with sync results:
                - success: bool
                - odoo_order_id: int | None
                - odoo_customer_id: int | None
                - error: str | None
        """
        try:
            self._error_handler.logger.info(f"Starting Odoo sync for order {order_id}")

            # Local imports to avoid circular dependency
            from src.api.orders.service import OrderService
            from src.api.users.service import UserService

            order_service = OrderService()
            user_service = UserService()

            # Step 1: Fetch enriched order data using existing service (Efficiency #1)
            self._error_handler.logger.info(
                f"[{order_id}] Fetching enriched order data..."
            )
            order_schema = await order_service.get_order_by_id(
                order_id,
                include_products=True,
                include_stores=True,
                include_addresses=True,
            )

            if not order_schema:
                raise OdooSyncError(f"Order {order_id} not found")

            # Early exit if already synced (Efficiency & Idempotency)
            if order_schema.odoo_sync_status == OdooSyncStatus.SYNCED:
                self._error_handler.logger.info(
                    f"Order {order_id} already successfully synced to Odoo. Skipping."
                )
                return {
                    "success": True,
                    "odoo_order_id": order_schema.odoo_order_id,
                    "odoo_customer_id": order_schema.odoo_customer_id,
                    "error": None,
                }

            # Fetch user with address for customer sync
            user_schema = await user_service.get_user_by_id(
                order_schema.user_id, include_addresses=True
            )

            if not user_schema:
                raise OdooSyncError(f"User {order_schema.user_id} not found")

            # Ensure authenticated with Odoo
            if self.odoo._uid is None:
                self.odoo.authenticate()

            # Step 2: Sync customer to Odoo (find or create)
            # Removed proactive verification (Efficiency #3)
            odoo_customer_id = await self._sync_customer(user_schema)

            # Step 3: Create sales order with all lines in Odoo
            try:
                odoo_order_result = await self._create_sales_order(
                    order_schema, odoo_customer_id
                )
            except OdooSyncError as e:
                # Reactive Recovery (Efficiency #3): If partner doesn't exist, recreate and retry
                error_str = str(e)
                if "res.partner" in error_str and (
                    "Record does not exist" in error_str or "deleted" in error_str
                ):
                    self._error_handler.logger.warning(
                        f"Odoo customer {odoo_customer_id} not found. Re-syncing and retrying..."
                    )
                    # Force re-sync by passing something that triggers create/search
                    odoo_customer_id = await self._sync_customer(
                        user_schema, force_resync=True
                    )
                    odoo_order_result = await self._create_sales_order(
                        order_schema, odoo_customer_id
                    )
                else:
                    raise

            odoo_order_id = odoo_order_result["order_id"]
            order_exists = odoo_order_result["already_exists"]
            order_state = odoo_order_result.get("state", "draft")

            # Step 4: Confirm order in Odoo
            # Optimized flow: Only skip if we definitively know it's already 'received' (Efficiency #4)
            if order_state != "received":
                await self._mark_order_received(odoo_order_id)

            # Step 5: Update our order record
            await self._update_order_sync_status(
                order_id,
                status=OdooSyncStatus.SYNCED,
                odoo_order_id=odoo_order_id,
                odoo_customer_id=odoo_customer_id,
                error=None,
            )

            self._error_handler.logger.info(
                f"Successfully synced order {order_id} to Odoo | "
                f"Odoo Order ID: {odoo_order_id} | "
                f"Odoo Customer ID: {odoo_customer_id} | "
                f"{'Re-synced existing order' if order_exists else 'Created new order'}"
            )

            return {
                "success": True,
                "odoo_order_id": odoo_order_id,
                "odoo_customer_id": odoo_customer_id,
                "error": None,
            }

        except (OdooConnectionError, OdooAuthenticationError) as e:
            # Network/connection errors - can retry
            error_msg = f"Connection error: {str(e)}"
            self._error_handler.logger.error(
                f"Odoo sync failed for order {order_id}: {error_msg}"
            )

            await self._update_order_sync_status(
                order_id, status=OdooSyncStatus.FAILED, error=error_msg
            )

            return {
                "success": False,
                "odoo_order_id": None,
                "odoo_customer_id": None,
                "error": error_msg,
            }

        except Exception as e:
            # Other errors - may need investigation
            error_msg = f"Sync error: {str(e)}"
            self._error_handler.logger.error(
                f"Odoo sync failed for order {order_id}: {error_msg}", exc_info=True
            )

            await self._update_order_sync_status(
                order_id, status=OdooSyncStatus.FAILED, error=error_msg
            )

            return {
                "success": False,
                "odoo_order_id": None,
                "odoo_customer_id": None,
                "error": error_msg,
            }

    async def _fetch_order_data(self, session, order_id: int) -> Dict[str, Any]:
        """Obsolete - replaced by OrderService.get_order_by_id"""
        return {}

    async def _sync_customer(self, user: Any, force_resync: bool = False) -> int:
        """
        Find or create customer in Odoo, with local caching.
        Optimized: Removed proactive verification.

        Args:
            user: User schema or model
            force_resync: Ignore cache and re-sync from Odoo

        Returns:
            Odoo partner ID
        """
        loop = asyncio.get_event_loop()

        # Step 1: Check for cached Odoo customer ID
        if user.odoo_customer_id and not force_resync:
            return user.odoo_customer_id

        try:
            # Step 2: Search for existing customer in Odoo by firebase_uuid
            self._error_handler.logger.info(
                f"Searching for Odoo customer for user {user.firebase_uid}"
            )
            existing_customers = await loop.run_in_executor(
                self._executor,
                lambda: self.odoo.search_read(
                    "res.partner",
                    [("firebase_uuid", "=", user.firebase_uid)],
                    fields=["id", "name", "email"],
                    limit=1,
                ),
            )

            if existing_customers:
                customer_id = existing_customers[0]["id"]
                self._error_handler.logger.info(
                    f"Found existing Odoo customer {customer_id} for user {user.firebase_uid}"
                )
            else:
                # Step 3: Create new customer if not found (async)
                self._error_handler.logger.info(
                    f"Odoo customer not found. Creating new one for user {user.firebase_uid}"
                )
                customer_values = {
                    "name": user.name,
                    "email": user.email or False,
                    "phone": user.phone or False,
                    "firebase_uuid": user.firebase_uid,
                    "customer_rank": 1,
                    "is_company": False,
                }

                if hasattr(user, "addresses") and user.addresses:
                    default_address = next(
                        (
                            addr
                            for addr in user.addresses
                            if getattr(addr, "is_default", False)
                        ),
                        user.addresses[0],
                    )
                    customer_values["street"] = default_address.address

                customer_id = await loop.run_in_executor(
                    self._executor,
                    lambda: self.odoo.create("res.partner", customer_values),
                )

            # Step 4: Cache the Odoo customer ID in our local database
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    user_to_update = await session.get(User, user.firebase_uid)
                    if user_to_update:
                        user_to_update.odoo_customer_id = customer_id
                        await session.flush()

            return customer_id

        except Exception as e:
            self._error_handler.logger.error(f"Failed to sync customer: {e}")
            raise OdooSyncError(f"Customer sync failed: {e}")

    async def _create_sales_order(
        self, order: Any, odoo_customer_id: int
    ) -> Dict[str, Any]:
        """
        Create sales order in Odoo with all order lines in a single call (with duplicate check)
        Optimized: Reuses data already fetched in Step 1.

        Args:
            order: OrderSchema object
            odoo_customer_id: Odoo partner ID
        """
        try:
            client_ref = f"CELESTE-{order.id}"

            # Check for existing order with this client reference (async)
            loop = asyncio.get_event_loop()
            existing_orders = await loop.run_in_executor(
                self._executor,
                lambda: self.odoo.search_read(
                    "sale.order",
                    [("client_order_ref", "=", client_ref)],
                    fields=["id", "name", "state"],
                    limit=1,
                ),
            )

            if existing_orders:
                existing_order = existing_orders[0]
                return {
                    "order_id": existing_order["id"],
                    "already_exists": True,
                    "state": existing_order["state"],
                }

            # Prepare order lines using data already in the schema
            order_lines = []
            lines_skipped = 0

            # Map to store products we found in Odoo
            padded_refs = [
                str(item.product.ref).zfill(6)
                for item in order.items
                if item.product and item.product.ref
            ]

            odoo_products_list = []
            if padded_refs:
                odoo_products_list = await loop.run_in_executor(
                    self._executor,
                    lambda: self.odoo.search_read(
                        "product.product",
                        [("default_code", "in", padded_refs)],
                        fields=["id", "name", "default_code"],
                    ),
                )
            odoo_product_map = {p["default_code"]: p["id"] for p in odoo_products_list}

            for item in order.items:
                if not item.product:
                    lines_skipped += 1
                    continue

                padded_ref = str(item.product.ref).zfill(6)
                odoo_product_id = odoo_product_map.get(padded_ref)

                if not odoo_product_id:
                    lines_skipped += 1
                    continue

                base_price = float(item.product.base_price)
                final_price = float(item.unit_price)

                if base_price > 0:
                    discount_percent = ((base_price - final_price) / base_price) * 100
                    discount_percent = max(0.0, min(100.0, discount_percent))
                else:
                    discount_percent = 0.0

                order_lines.append(
                    (
                        0,
                        0,
                        {
                            "product_id": odoo_product_id,
                            "product_uom_qty": item.quantity,
                            "price_unit": base_price,
                            "discount": discount_percent,
                        },
                    )
                )

            # Add delivery charge
            if order.delivery_charge > 0:
                order_lines.append(
                    (
                        0,
                        0,
                        {
                            "product_id": DELIVERY_PRODUCT_ODOO_ID,
                            "product_uom_qty": 1,
                            "price_unit": float(order.delivery_charge),
                            "discount": 0.0,
                        },
                    )
                )

            if not order_lines:
                raise OdooSyncError("No valid order lines found for Odoo sync")

            date_order_str = order.created_at.strftime("%Y-%m-%d %H:%M:%S")

            order_values = {
                "partner_id": odoo_customer_id,
                "date_order": date_order_str,
                "client_order_ref": client_ref,
                "state": "draft",
                "order_line": order_lines,
                "aggregator_selection": ODOO_AGGREGATOR_SELECTION,
                "user_id": ODOO_SALESPERSON_ID,
            }

            if order.store and order.store.odoo_warehouse_id:
                order_values["warehouse_id"] = order.store.odoo_warehouse_id

            order_id = await loop.run_in_executor(
                self._executor, lambda: self.odoo.create("sale.order", order_values)
            )

            return {
                "order_id": order_id,
                "already_exists": False,
                "state": "draft",
            }

        except Exception as e:
            # Let OdooSyncError bubble up naturally
            if isinstance(e, OdooSyncError):
                raise e
            self._error_handler.logger.error(
                f"Failed to create sales order: {e}", exc_info=True
            )
            raise OdooSyncError(f"Sales order creation failed: {e}")

    async def _mark_order_received(self, odoo_order_id: int) -> None:
        """
        Confirm sales order in Odoo (change state to 'received')
        Optimized: Direct confirmation call.

        Args:
            odoo_order_id: Odoo sales order ID
        """
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self._executor,
                lambda: self.odoo.execute_kw(
                    "sale.order",
                    "action_mark_order_received",
                    [[odoo_order_id]],
                ),
            )
            self._error_handler.logger.info(
                f"Confirmed Odoo sales order {odoo_order_id} to received state"
            )
        except Exception as e:
            self._error_handler.logger.error(
                f"Failed to confirm order {odoo_order_id}: {e}"
            )
            raise OdooSyncError(f"Order confirmation failed: {e}")

    async def _update_order_sync_status(
        self,
        order_id: int,
        status: OdooSyncStatus,
        odoo_order_id: Optional[int] = None,
        odoo_customer_id: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update order Odoo sync status"""
        async with AsyncSessionLocal() as session:
            async with session.begin():
                order_query = select(Order).where(Order.id == order_id)
                result = await session.execute(order_query)
                order = result.scalar_one_or_none()

                if order:
                    order.odoo_sync_status = status
                    order.odoo_last_retry_at = datetime.now(timezone.utc)

                    if status == OdooSyncStatus.SYNCED:
                        order.odoo_order_id = odoo_order_id
                        order.odoo_customer_id = odoo_customer_id
                        order.odoo_synced_at = datetime.now(timezone.utc)
                        order.odoo_sync_error = None
                    elif status == OdooSyncStatus.FAILED:
                        order.odoo_sync_error = (
                            error[:1000] if error else None
                        )  # Limit error length

                    await session.flush()
