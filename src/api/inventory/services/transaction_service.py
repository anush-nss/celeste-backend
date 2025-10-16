from sqlalchemy import tuple_
from sqlalchemy.future import select

from src.api.inventory.models import (
    AdjustInventorySchema,
    InventorySchema,
)
from src.config.constants import DELIVERY_PRODUCT_ODOO_ID
from src.database.models.inventory import Inventory
from src.shared.error_handler import ErrorHandler, handle_service_errors
from src.shared.exceptions import ResourceNotFoundException, ValidationException


class InventoryTransactionService:
    """Handles inventory stock transactions (holds, reservations, fulfillment)"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)

    @handle_service_errors("adjusting stock")
    async def adjust_inventory_stock(
        self, adjustment_data: AdjustInventorySchema, session
    ) -> InventorySchema:
        """Atomically adjust stock, hold, or reserved quantities."""
        # Lock the specific inventory row for the duration of the transaction
        result = await session.execute(
            select(Inventory)
            .filter_by(
                product_id=adjustment_data.product_id, store_id=adjustment_data.store_id
            )
            .with_for_update()
        )
        inventory = result.scalars().first()

        if not inventory:
            raise ResourceNotFoundException(
                f"Inventory for product {adjustment_data.product_id} at store {adjustment_data.store_id} not found."
            )

        # Calculate proposed changes
        new_available = inventory.quantity_available + adjustment_data.available_change
        new_on_hold = inventory.quantity_on_hold + adjustment_data.on_hold_change
        new_reserved = inventory.quantity_reserved + adjustment_data.reserved_change
        new_safety_stock = inventory.safety_stock + adjustment_data.safety_stock_change

        # Validate that no quantity goes below zero
        if new_available < 0:
            raise ValidationException("Insufficient stock for this operation.")
        if new_on_hold < 0:
            raise ValidationException("Cannot release more items than are on hold.")
        if new_reserved < 0:
            raise ValidationException("Cannot release more items than are reserved.")
        if new_safety_stock < 0:
            raise ValidationException("Safety stock cannot go below zero.")

        # Apply changes
        inventory.quantity_available = new_available
        inventory.quantity_on_hold = new_on_hold
        inventory.quantity_reserved = new_reserved
        inventory.safety_stock = new_safety_stock

        # Note: session.commit() should be handled by the caller
        # Don't refresh here - it would undo changes before commit!
        return InventorySchema.model_validate(inventory)

    async def place_hold(
        self, product_id: int, store_id: int, quantity: int, session
    ) -> InventorySchema:
        """Place a hold on inventory for an order."""
        if quantity <= 0:
            raise ValidationException("Quantity must be positive.")

        adjustment = AdjustInventorySchema(
            product_id=product_id,
            store_id=store_id,
            available_change=-quantity,
            on_hold_change=quantity,
            safety_stock_change=0,
        )
        return await self.adjust_inventory_stock(adjustment, session)

    async def release_hold(
        self, product_id: int, store_id: int, quantity: int, session
    ) -> InventorySchema:
        """Release a hold on inventory (e.g., order cancelled)."""
        if quantity <= 0:
            raise ValidationException("Quantity must be positive.")

        adjustment = AdjustInventorySchema(
            product_id=product_id,
            store_id=store_id,
            available_change=quantity,
            on_hold_change=-quantity,
            safety_stock_change=0,
        )
        return await self.adjust_inventory_stock(adjustment, session)

    async def confirm_reservation(
        self, product_id: int, store_id: int, quantity: int, session
    ) -> InventorySchema:
        """Convert a hold to a reservation (e.g., payment confirmed)."""
        if quantity <= 0:
            raise ValidationException("Quantity must be positive.")

        adjustment = AdjustInventorySchema(
            product_id=product_id,
            store_id=store_id,
            on_hold_change=-quantity,
            reserved_change=quantity,
            safety_stock_change=0,
        )
        return await self.adjust_inventory_stock(adjustment, session)

    async def fulfill_order(
        self, product_id: int, store_id: int, quantity: int, session
    ) -> InventorySchema:
        """Fulfill an order by removing reserved stock."""
        if quantity <= 0:
            raise ValidationException("Quantity must be positive.")

        adjustment = AdjustInventorySchema(
            product_id=product_id,
            store_id=store_id,
            reserved_change=-quantity,
            safety_stock_change=0,
        )
        return await self.adjust_inventory_stock(adjustment, session)

    async def place_holds_bulk(
        self, holds: list[dict], session
    ) -> list[InventorySchema]:
        """
        Place multiple inventory holds in a single optimized operation.

        Args:
            holds: List of dicts with keys: product_id, store_id, quantity
            session: Database session

        Returns:
            List of updated inventory records

        This method locks all required inventory rows in deterministic order
        to prevent deadlocks, validates all holds, then applies all updates.
        """
        if not holds:
            return []

        # Filter out the delivery product from inventory operations
        holds = [
            hold for hold in holds if hold["product_id"] != DELIVERY_PRODUCT_ODOO_ID
        ]

        if not holds:
            return []

        # Validate all quantities first
        for hold in holds:
            if hold["quantity"] <= 0:
                raise ValidationException(
                    f"Quantity must be positive for product {hold['product_id']}"
                )

        # Build unique (product_id, store_id) pairs for the query
        inventory_keys = list(set((h["product_id"], h["store_id"]) for h in holds))

        # Lock and fetch all required inventory rows at once
        result = await session.execute(
            select(Inventory)
            .filter(
                tuple_(Inventory.product_id, Inventory.store_id).in_(inventory_keys)
            )
            .with_for_update()
        )
        inventory_items = result.scalars().all()
        inventory_records = {(i.product_id, i.store_id): i for i in inventory_items}

        # Check if all inventory records were found
        if len(inventory_records) != len(inventory_keys):
            found_keys = set(inventory_records.keys())
            missing_keys = [key for key in inventory_keys if key not in found_keys]
            raise ResourceNotFoundException(
                f"Inventory not found for the following (product, store) pairs: {missing_keys}"
            )

        # Validate all holds before applying any changes
        for hold in holds:
            key = (hold["product_id"], hold["store_id"])
            inventory = inventory_records[key]

            new_available = inventory.quantity_available - hold["quantity"]

            if new_available < 0:
                raise ValidationException(
                    f"Insufficient stock for product {hold['product_id']} at store {hold['store_id']}. "
                    f"Available: {inventory.quantity_available}, Requested: {hold['quantity']}"
                )

        # Apply all changes
        results = []
        for hold in holds:
            key = (hold["product_id"], hold["store_id"])
            inventory = inventory_records[key]

            inventory.quantity_available -= hold["quantity"]
            inventory.quantity_on_hold += hold["quantity"]

            results.append(InventorySchema.model_validate(inventory))

        return results

    async def release_holds_bulk(
        self, holds: list[dict], session
    ) -> list[InventorySchema]:
        """
        Release multiple inventory holds in a single optimized operation.

        Args:
            holds: List of dicts with keys: product_id, store_id, quantity
            session: Database session

        Returns:
            List of updated inventory records

        Used for rollback scenarios when order creation fails.
        """
        if not holds:
            return []

        # Filter out the delivery product from inventory operations
        holds = [
            hold for hold in holds if hold["product_id"] != DELIVERY_PRODUCT_ODOO_ID
        ]

        if not holds:
            return []

        # Validate all quantities first
        for hold in holds:
            if hold["quantity"] <= 0:
                raise ValidationException(
                    f"Quantity must be positive for product {hold['product_id']}"
                )

        # Build unique (product_id, store_id) pairs for the query
        inventory_keys = list(set((h["product_id"], h["store_id"]) for h in holds))

        # Lock and fetch all required inventory rows at once
        result = await session.execute(
            select(Inventory)
            .filter(
                tuple_(Inventory.product_id, Inventory.store_id).in_(inventory_keys)
            )
            .with_for_update()
        )
        inventory_items = result.scalars().all()
        inventory_records = {(i.product_id, i.store_id): i for i in inventory_items}

        # Validate all releases before applying any changes
        for hold in holds:
            key = (hold["product_id"], hold["store_id"])
            if key not in inventory_records:
                continue

            inventory = inventory_records[key]
            new_on_hold = inventory.quantity_on_hold - hold["quantity"]

            if new_on_hold < 0:
                # During rollback, just log warning and skip
                self._error_handler.logger.warning(
                    f"Cannot release {hold['quantity']} items on hold for product {hold['product_id']} "
                    f"at store {hold['store_id']}. Current on_hold: {inventory.quantity_on_hold}"
                )
                continue

        # Apply all changes
        results = []
        for hold in holds:
            key = (hold["product_id"], hold["store_id"])
            if key not in inventory_records:
                continue

            inventory = inventory_records[key]

            # Only release what's actually on hold
            release_qty = min(hold["quantity"], inventory.quantity_on_hold)
            inventory.quantity_available += release_qty
            inventory.quantity_on_hold -= release_qty

            results.append(InventorySchema.model_validate(inventory))

        return results
