from typing import Optional
from sqlalchemy.future import select
from src.database.connection import AsyncSessionLocal
from src.database.models.inventory import Inventory
from src.api.inventory.models import (
    InventorySchema,
    AdjustInventorySchema,
)
from src.shared.exceptions import ResourceNotFoundException, ValidationException
from src.shared.error_handler import ErrorHandler, handle_service_errors


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
            select(Inventory).filter_by(
                product_id=adjustment_data.product_id,
                store_id=adjustment_data.store_id
            ).with_for_update()
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

        # Validate that no quantity goes below zero
        if new_available < 0:
            raise ValidationException("Insufficient stock for this operation.")
        if new_on_hold < 0:
            raise ValidationException("Cannot release more items than are on hold.")
        if new_reserved < 0:
            raise ValidationException("Cannot release more items than are reserved.")

        # Apply changes
        inventory.quantity_available = new_available
        inventory.quantity_on_hold = new_on_hold
        inventory.quantity_reserved = new_reserved

        # Note: session.commit() should be handled by the caller
        await session.refresh(inventory)
        return InventorySchema.model_validate(inventory)

    async def place_hold(self, product_id: int, store_id: int, quantity: int, session) -> InventorySchema:
        """Place a hold on inventory for an order."""
        if quantity <= 0:
            raise ValidationException("Quantity must be positive.")

        adjustment = AdjustInventorySchema(
            product_id=product_id,
            store_id=store_id,
            available_change=-quantity,
            on_hold_change=quantity
        )
        return await self.adjust_inventory_stock(adjustment, session)

    async def release_hold(self, product_id: int, store_id: int, quantity: int, session) -> InventorySchema:
        """Release a hold on inventory (e.g., order cancelled)."""
        if quantity <= 0:
            raise ValidationException("Quantity must be positive.")

        adjustment = AdjustInventorySchema(
            product_id=product_id,
            store_id=store_id,
            available_change=quantity,
            on_hold_change=-quantity
        )
        return await self.adjust_inventory_stock(adjustment, session)

    async def confirm_reservation(self, product_id: int, store_id: int, quantity: int, session) -> InventorySchema:
        """Convert a hold to a reservation (e.g., payment confirmed)."""
        if quantity <= 0:
            raise ValidationException("Quantity must be positive.")

        adjustment = AdjustInventorySchema(
            product_id=product_id,
            store_id=store_id,
            on_hold_change=-quantity,
            reserved_change=quantity
        )
        return await self.adjust_inventory_stock(adjustment, session)

    async def fulfill_order(self, product_id: int, store_id: int, quantity: int, session) -> InventorySchema:
        """Fulfill an order by removing reserved stock."""
        if quantity <= 0:
            raise ValidationException("Quantity must be positive.")

        adjustment = AdjustInventorySchema(
            product_id=product_id,
            store_id=store_id,
            reserved_change=-quantity
        )
        return await self.adjust_inventory_stock(adjustment, session)