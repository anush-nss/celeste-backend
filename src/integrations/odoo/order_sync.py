"""
Odoo Order Synchronization Service

High-level service for syncing orders and customers to Odoo ERP.
Handles customer creation, order creation, and error recovery.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.config.constants import OdooSyncStatus
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
            async with AsyncSessionLocal() as session:
                order_data = await self._fetch_order_data(session, order_id)

            # Ensure authenticated with Odoo
            if self.odoo._uid is None:
                self.odoo.authenticate()

            # Step 1: Sync customer to Odoo (find or create)
            odoo_customer_id = await self._sync_customer(order_data["user"])

            # Step 2: Create sales order in Odoo (or find existing)
            odoo_order_result = await self._create_sales_order(
                order_data, odoo_customer_id
            )
            odoo_order_id = odoo_order_result["order_id"]
            order_exists = odoo_order_result["already_exists"]
            order_state = odoo_order_result.get("state", "draft")

            # Step 3: Create order lines (skip if order is already confirmed)
            if order_state != "sale":
                await self._create_order_lines(odoo_order_id, order_data["items"])

                # Step 4: Confirm order in Odoo (skip if already confirmed)
                await self._confirm_order(odoo_order_id)
            else:
                self._error_handler.logger.info(
                    f"Order {odoo_order_id} already confirmed in Odoo, skipping line creation and confirmation"
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
        Find or create customer in Odoo

        Args:
            user: User model instance

        Returns:
            Odoo partner ID
        """
        try:
            # Search for existing customer by firebase_uid
            existing_customers = self.odoo.search_read(
                "res.partner",
                [("firebase_uid", "=", user.firebase_uid)],
                fields=["id", "name", "email"],
                limit=1,
            )

            if existing_customers:
                # Customer exists - update customer_rank
                customer_id = existing_customers[0]["id"]
                self._error_handler.logger.info(
                    f"Found existing Odoo customer {customer_id} for user {user.firebase_uid}"
                )

                # Update customer_rank (total_orders + 1 for this new order)
                self.odoo.write(
                    "res.partner",
                    [customer_id],
                    {"customer_rank": user.total_orders + 1},
                )

                return customer_id

            # Customer doesn't exist - create new
            customer_values = {
                "name": user.name,
                "email": user.email or False,
                "phone": user.phone or False,
                "mobile": user.phone or False,  # Use same phone for mobile
                "firebase_uid": user.firebase_uid,
                "customer_rank": 1,  # First order
                "is_company": False,
            }

            # Add address if available
            if user.addresses and len(user.addresses) > 0:
                # Get default address or first address
                default_address = next(
                    (addr for addr in user.addresses if addr.is_default),
                    user.addresses[0],
                )
                customer_values["street"] = default_address.address

            customer_id = self.odoo.create("res.partner", customer_values)

            self._error_handler.logger.info(
                f"Created new Odoo customer {customer_id} for user {user.firebase_uid}"
            )

            return customer_id

        except Exception as e:
            self._error_handler.logger.error(f"Failed to sync customer: {e}")
            raise OdooSyncError(f"Customer sync failed: {e}")

    async def _create_sales_order(
        self, order_data: Dict[str, Any], odoo_customer_id: int
    ) -> Dict[str, Any]:
        """
        Create sales order in Odoo (with duplicate check)

        Args:
            order_data: Dict with order, items, user
            odoo_customer_id: Odoo partner ID

        Returns:
            Dict with:
                - order_id: Odoo sales order ID
                - already_exists: bool
                - state: Order state in Odoo
        """
        try:
            order = order_data["order"]
            client_ref = f"CELESTE-{order.id}"

            # Check for existing order with this client reference
            existing_orders = self.odoo.search_read(
                "sale.order",
                [("client_order_ref", "=", client_ref)],
                fields=["id", "name", "state"],
                limit=1,
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
                }

            # No duplicate found - create new order
            # Format datetime for Odoo (expects 'YYYY-MM-DD HH:MM:SS')
            date_order_str = order.created_at.strftime("%Y-%m-%d %H:%M:%S")

            order_values = {
                "partner_id": odoo_customer_id,
                "date_order": date_order_str,
                "client_order_ref": client_ref,
                "state": "draft",  # Will confirm later
            }

            order_id = self.odoo.create("sale.order", order_values)

            self._error_handler.logger.info(
                f"Created Odoo sales order {order_id} for order {order.id}"
            )

            return {
                "order_id": order_id,
                "already_exists": False,
                "state": "draft",
            }

        except Exception as e:
            self._error_handler.logger.error(f"Failed to create sales order: {e}")
            raise OdooSyncError(f"Sales order creation failed: {e}")

    async def _create_order_lines(
        self, odoo_order_id: int, order_items: List[OrderItem]
    ) -> None:
        """
        Create order lines in Odoo (skip if lines already exist)

        Args:
            odoo_order_id: Odoo sales order ID
            order_items: List of OrderItem instances
        """
        try:
            # Check if order already has lines (to avoid duplicates on retry)
            existing_lines = self.odoo.search_read(
                "sale.order.line",
                [("order_id", "=", odoo_order_id)],
                fields=["id", "product_id"],
                limit=1,
            )

            if existing_lines:
                self._error_handler.logger.info(
                    f"Odoo order {odoo_order_id} already has order lines, skipping line creation"
                )
                return

            self._error_handler.logger.info(
                f"Creating {len(order_items)} order lines for Odoo order {odoo_order_id}"
            )

            lines_created = 0
            lines_skipped = 0

            # We need to get product information to calculate discounts
            async with AsyncSessionLocal() as session:
                from src.database.models.product import Product

                for item in order_items:
                    # Fetch product to get ref and base_price
                    product_query = select(Product).where(Product.id == item.product_id)
                    product_result = await session.execute(product_query)
                    product = product_result.scalar_one_or_none()

                    if not product:
                        self._error_handler.logger.warning(
                            f"Product {item.product_id} not found in database, skipping order line"
                        )
                        lines_skipped += 1
                        continue

                    # Pad ref to 6 digits with leading zeros to match Odoo format
                    # Database: "1646" -> Odoo: "001646"
                    padded_ref = str(product.ref).zfill(6)

                    self._error_handler.logger.info(
                        f"Looking for product in Odoo | Ref: {product.ref} | Padded: {padded_ref} | Name: {product.name}"
                    )

                    # Find product in Odoo by ref (with padding)
                    odoo_products = self.odoo.search_read(
                        "product.product",
                        [("default_code", "=", padded_ref)],
                        fields=["id", "name"],
                        limit=1,
                    )

                    if not odoo_products:
                        self._error_handler.logger.warning(
                            f"Product ref '{product.ref}' (padded: '{padded_ref}') not found in Odoo, skipping order line"
                        )
                        lines_skipped += 1
                        continue

                    odoo_product_id = odoo_products[0]["id"]
                    self._error_handler.logger.info(
                        f"Found Odoo product | ID: {odoo_product_id} | Name: {odoo_products[0]['name']}"
                    )

                    # Calculate discount percentage
                    # base_price is the original price, unit_price is after discount
                    base_price = float(product.base_price)
                    final_price = float(item.unit_price)

                    discount_percent = 0.0
                    if base_price > 0:
                        discount_percent = (
                            (base_price - final_price) / base_price
                        ) * 100
                        discount_percent = max(
                            0.0, min(100.0, discount_percent)
                        )  # Clamp 0-100

                    # Create order line
                    line_values = {
                        "order_id": odoo_order_id,
                        "product_id": odoo_product_id,
                        "product_uom_qty": item.quantity,
                        "price_unit": base_price,  # Original price
                        "discount": discount_percent,  # Discount percentage
                    }

                    self._error_handler.logger.info(
                        f"Creating order line | Product: {product.ref} | "
                        f"Qty: {item.quantity} | Price: {base_price} | "
                        f"Final Price: {final_price} | Discount: {discount_percent:.2f}%"
                    )

                    line_id = self.odoo.create("sale.order.line", line_values)
                    lines_created += 1

                    self._error_handler.logger.info(
                        f"Created order line {line_id} successfully"
                    )

            self._error_handler.logger.info(
                f"Order lines summary | Created: {lines_created} | Skipped: {lines_skipped}"
            )

            if lines_created == 0:
                raise OdooSyncError(
                    "No order lines were created. All products were skipped."
                )

        except OdooSyncError:
            raise
        except Exception as e:
            self._error_handler.logger.error(
                f"Failed to create order lines: {e}", exc_info=True
            )
            raise OdooSyncError(f"Order lines creation failed: {e}")

    async def _confirm_order(self, odoo_order_id: int) -> None:
        """
        Confirm sales order in Odoo (change state to 'sale')

        Args:
            odoo_order_id: Odoo sales order ID
        """
        try:
            # Check current state first to avoid re-confirming
            order_info = self.odoo.search_read(
                "sale.order",
                [("id", "=", odoo_order_id)],
                fields=["state"],
                limit=1,
            )

            if order_info and order_info[0]["state"] == "sale":
                self._error_handler.logger.info(
                    f"Odoo sales order {odoo_order_id} is already confirmed, skipping confirmation"
                )
                return

            # Confirm the order by calling action_confirm method
            self.odoo.execute_kw(
                "sale.order",
                "action_confirm",
                [[odoo_order_id]],
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
