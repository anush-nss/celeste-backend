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
from sqlalchemy.orm import selectinload

from src.config.constants import OdooSyncStatus, DELIVERY_PRODUCT_ODOO_ID
from src.database.connection import AsyncSessionLocal
from src.database.models.order import Order, OrderItem
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

            # Fetch order data with relationships
            self._error_handler.logger.info(f"[{order_id}] Fetching order data...")
            async with AsyncSessionLocal() as session:
                order_data = await self._fetch_order_data(session, order_id)
            self._error_handler.logger.info(
                f"[{order_id}] Fetched order data successfully."
            )

            # Ensure authenticated with Odoo
            if self.odoo._uid is None:
                self._error_handler.logger.info(
                    f"[{order_id}] Authenticating with Odoo..."
                )
                self.odoo.authenticate()
                self._error_handler.logger.info(
                    f"[{order_id}] Authenticated successfully."
                )

            # Step 1: Sync customer to Odoo (find or create)
            self._error_handler.logger.info(f"[{order_id}] Syncing customer...")
            odoo_customer_id = await self._sync_customer(order_data["user"])
            self._error_handler.logger.info(
                f"[{order_id}] Customer synced successfully. Odoo Customer ID: {odoo_customer_id}"
            )

            # Step 2: Create sales order with all lines in Odoo (or find existing)
            self._error_handler.logger.info(
                f"[{order_id}] Creating sales order with all lines in one call..."
            )
            odoo_order_result = await self._create_sales_order(
                order_data, odoo_customer_id
            )
            odoo_order_id = odoo_order_result["order_id"]
            order_exists = odoo_order_result["already_exists"]
            order_state = odoo_order_result.get("state", "draft")
            lines_created = odoo_order_result.get("lines_created", 0)
            lines_skipped = odoo_order_result.get("lines_skipped", 0)

            if order_exists:
                self._error_handler.logger.info(
                    f"[{order_id}] Sales order found in Odoo. Odoo Order ID: {odoo_order_id}"
                )
            else:
                self._error_handler.logger.info(
                    f"[{order_id}] Sales order created with {lines_created} lines ({lines_skipped} skipped). Odoo Order ID: {odoo_order_id}"
                )

            # Step 3: Confirm order in Odoo (skip if already confirmed)
            if order_state != "sale":
                self._error_handler.logger.info(f"[{order_id}] Confirming order...")
                await self._confirm_order(odoo_order_id)
                self._error_handler.logger.info(
                    f"[{order_id}] Order confirmed successfully."
                )
            else:
                self._error_handler.logger.info(
                    f"Order {odoo_order_id} already confirmed in Odoo, skipping confirmation"
                )

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
        """Fetch order data with all relationships"""
        # Fetch order with items
        order_query = select(Order).where(Order.id == order_id)
        result = await session.execute(order_query)
        order = result.scalar_one_or_none()

        if not order:
            raise OdooSyncError(f"Order {order_id} not found")

        # Fetch order items
        items_query = select(OrderItem).where(OrderItem.order_id == order_id)
        items_result = await session.execute(items_query)
        order_items = items_result.scalars().all()

        # Fetch user with addresses eagerly loaded
        user_query = (
            select(User)
            .options(selectinload(User.addresses))
            .where(User.firebase_uid == order.user_id)
        )
        user_result = await session.execute(user_query)
        user = user_result.scalar_one_or_none()

        if not user:
            raise OdooSyncError(f"User {order.user_id} not found")

        return {
            "order": order,
            "items": order_items,
            "user": user,
        }

    async def _sync_customer(self, user: User) -> int:
        """
        Find or create customer in Odoo, with local caching.

        Args:
            user: User model instance

        Returns:
            Odoo partner ID
        """
        # Step 1: Check for cached Odoo customer ID
        if user.odoo_customer_id:
            self._error_handler.logger.info(
                f"Found cached Odoo customer ID {user.odoo_customer_id} for user {user.firebase_uid}"
            )
            return user.odoo_customer_id

        try:
            # Step 2: Search for existing customer in Odoo by firebase_uid (async)
            self._error_handler.logger.info(
                f"No cached ID found. Searching for Odoo customer for user {user.firebase_uid}"
            )
            loop = asyncio.get_event_loop()
            existing_customers = await loop.run_in_executor(
                self._executor,
                lambda: self.odoo.search_read(
                    "res.partner",
                    [("firebase_uid", "=", user.firebase_uid)],
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
                    "mobile": user.phone or False,
                    "firebase_uid": user.firebase_uid,
                    "customer_rank": 1,
                    "is_company": False,
                }

                if user.addresses and len(user.addresses) > 0:
                    default_address = next(
                        (addr for addr in user.addresses if addr.is_default),
                        user.addresses[0],
                    )
                    customer_values["street"] = default_address.address

                customer_id = await loop.run_in_executor(
                    self._executor,
                    lambda: self.odoo.create("res.partner", customer_values),
                )
                self._error_handler.logger.info(
                    f"Created new Odoo customer {customer_id} for user {user.firebase_uid}"
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
        self, order_data: Dict[str, Any], odoo_customer_id: int
    ) -> Dict[str, Any]:
        """
        Create sales order in Odoo with all order lines in a single call (with duplicate check)

        Args:
            order_data: Dict with order, items, user
            odoo_customer_id: Odoo partner ID

        Returns:
            Dict with:
                - order_id: Odoo sales order ID
                - already_exists: bool
                - state: Order state in Odoo
                - lines_created: Number of lines created
                - lines_skipped: Number of lines skipped
        """
        try:
            order = order_data["order"]
            order_items = order_data["items"]
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
                # Order already exists in Odoo
                existing_order = existing_orders[0]
                order_id = existing_order["id"]
                order_state = existing_order["state"]

                self._error_handler.logger.warning(
                    f"Order already exists in Odoo | "
                    f"Celeste Order ID: {order.id} | "
                    f"Odoo Order ID: {order_id} | "
                    f"Odoo Order Name: {existing_order['name']} | "
                    f"State: {order_state} | "
                    f"Skipping duplicate creation"
                )

                return {
                    "order_id": order_id,
                    "already_exists": True,
                    "state": order_state,
                    "lines_created": 0,
                    "lines_skipped": 0,
                }

            # No duplicate found - prepare order lines first
            self._error_handler.logger.info(
                f"Preparing {len(order_items)} order lines for order {order.id}"
            )

            # Step 1: Fetch all products in a single query
            product_ids = [item.product_id for item in order_items]
            async with AsyncSessionLocal() as session:
                from src.database.models.product import Product

                products_query = select(Product).where(Product.id.in_(product_ids))
                products_result = await session.execute(products_query)
                products = {p.id: p for p in products_result.scalars().all()}

            self._error_handler.logger.info(
                f"Fetched {len(products)} products from database"
            )

            # Step 2: Batch fetch Odoo products by refs
            padded_refs = []
            product_ref_map = {}  # Map padded_ref -> our product

            for item in order_items:
                product = products.get(item.product_id)
                if product:
                    padded_ref = str(product.ref).zfill(6)
                    padded_refs.append(padded_ref)
                    product_ref_map[padded_ref] = product

            # Batch search Odoo products (run in thread pool to avoid blocking)
            odoo_products_list = []
            if padded_refs:
                self._error_handler.logger.info(
                    f"Searching for {len(padded_refs)} products in Odoo (async)"
                )
                loop = asyncio.get_event_loop()
                odoo_products_list = await loop.run_in_executor(
                    self._executor,
                    lambda: self.odoo.search_read(
                        "product.product",
                        [("default_code", "in", padded_refs)],
                        fields=["id", "name", "default_code"],
                    ),
                )

            # Create a map: padded_ref -> odoo_product_id
            odoo_product_map = {p["default_code"]: p["id"] for p in odoo_products_list}

            self._error_handler.logger.info(
                f"Found {len(odoo_product_map)} products in Odoo"
            )

            # Step 3: Build order lines
            order_lines = []
            lines_skipped = 0

            for item in order_items:
                product = products.get(item.product_id)

                if not product:
                    self._error_handler.logger.warning(
                        f"Product {item.product_id} not found in database, skipping order line"
                    )
                    lines_skipped += 1
                    continue

                padded_ref = str(product.ref).zfill(6)
                odoo_product_id = odoo_product_map.get(padded_ref)

                if not odoo_product_id:
                    self._error_handler.logger.warning(
                        f"Product ref '{product.ref}' (padded: '{padded_ref}') not found in Odoo, skipping order line"
                    )
                    lines_skipped += 1
                    continue

                # For the delivery product, the price is dynamic.
                # Set the price_unit directly to the delivery charge and discount to 0.
                if item.product_id == DELIVERY_PRODUCT_ODOO_ID:
                    base_price = float(item.unit_price)
                    final_price = base_price
                    discount_percent = 0.0
                else:
                    # For regular products, calculate discount based on base vs final price.
                    base_price = float(product.base_price)
                    final_price = float(item.unit_price)

                    if base_price > 0:
                        discount_percent = (
                            (base_price - final_price) / base_price
                        ) * 100
                        discount_percent = max(
                            0.0, min(100.0, discount_percent)
                        )  # Clamp 0-100
                    else:
                        discount_percent = 0.0

                # Prepare order line using Odoo's command syntax: (0, 0, {...})
                line_values = {
                    "product_id": odoo_product_id,
                    "product_uom_qty": item.quantity,
                    "price_unit": base_price,  # Use base_price or dynamic price
                    "discount": discount_percent,  # Apply calculated discount
                }

                self._error_handler.logger.info(
                    f"Prepared order line | Product: {product.ref} | "
                    f"Qty: {item.quantity} | Price: {base_price} | "
                    f"Final Price: {final_price} | Discount: {discount_percent:.2f}%"
                )

                # Add to order_lines list using (0, 0, values) command
                order_lines.append((0, 0, line_values))

            lines_created = len(order_lines)

            if lines_created == 0:
                raise OdooSyncError(
                    "No order lines were created. All products were skipped."
                )

            self._error_handler.logger.info(
                f"Order lines summary | Prepared: {lines_created} | Skipped: {lines_skipped}"
            )

            # Create order with all lines in a single call (run in thread pool)
            date_order_str = order.created_at.strftime("%Y-%m-%d %H:%M:%S")

            order_values = {
                "partner_id": odoo_customer_id,
                "date_order": date_order_str,
                "client_order_ref": client_ref,
                "state": "draft",  # Will confirm later
                "order_line": order_lines,  # Include all lines in one call
            }

            self._error_handler.logger.info(
                f"Creating Odoo sales order with {lines_created} lines (async)..."
            )
            loop = asyncio.get_event_loop()
            order_id = await loop.run_in_executor(
                self._executor, lambda: self.odoo.create("sale.order", order_values)
            )

            self._error_handler.logger.info(
                f"Created Odoo sales order {order_id} with {lines_created} lines for order {order.id}"
            )

            return {
                "order_id": order_id,
                "already_exists": False,
                "state": "draft",
                "lines_created": lines_created,
                "lines_skipped": lines_skipped,
            }

        except OdooSyncError:
            raise
        except Exception as e:
            self._error_handler.logger.error(
                f"Failed to create sales order: {e}", exc_info=True
            )
            raise OdooSyncError(f"Sales order creation failed: {e}")

    async def _confirm_order(self, odoo_order_id: int) -> None:
        """
        Confirm sales order in Odoo (change state to 'sale')

        Args:
            odoo_order_id: Odoo sales order ID
        """
        try:
            # Check current state first to avoid re-confirming (async)
            loop = asyncio.get_event_loop()
            order_info = await loop.run_in_executor(
                self._executor,
                lambda: self.odoo.search_read(
                    "sale.order",
                    [("id", "=", odoo_order_id)],
                    fields=["state"],
                    limit=1,
                ),
            )

            if order_info and order_info[0]["state"] == "sale":
                self._error_handler.logger.info(
                    f"Odoo sales order {odoo_order_id} is already confirmed, skipping confirmation"
                )
                return

            # Confirm the order by calling action_confirm method (async)
            await loop.run_in_executor(
                self._executor,
                lambda: self.odoo.execute_kw(
                    "sale.order",
                    "action_confirm",
                    [[odoo_order_id]],
                ),
            )

            self._error_handler.logger.info(
                f"Confirmed Odoo sales order {odoo_order_id}"
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
