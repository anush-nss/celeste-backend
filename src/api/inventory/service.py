from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select

from src.api.inventory.models import (
    AdjustInventorySchema,
    CreateInventorySchema,
    InventorySchema,
    UpdateInventorySchema,
)
from src.api.inventory.services import InventoryTransactionService
from src.database.connection import AsyncSessionLocal
from src.database.models.inventory import Inventory
from src.shared.error_handler import ErrorHandler, handle_service_errors
from src.shared.exceptions import (
    ConflictException,
    ResourceNotFoundException,
    ValidationException,
)


class InventoryService:
    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self.transaction_service = InventoryTransactionService()

    @handle_service_errors("retrieving inventory")
    async def get_inventory_by_product_and_store(
        self, product_id: int, store_id: int
    ) -> InventorySchema | None:
        """Get inventory by product and store ID, raising an error if not found."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Inventory).filter_by(product_id=product_id, store_id=store_id)
            )
            inventory = result.scalars().first()
            if not inventory:
                raise ResourceNotFoundException(
                    f"Inventory for product {product_id} at store {store_id} not found"
                )
            return InventorySchema.model_validate(inventory)

    @handle_service_errors("retrieving all inventory")
    async def get_all_inventory(
        self, product_id: Optional[int] = None, store_id: Optional[int] = None
    ) -> list[InventorySchema]:
        """Get all inventory items with optional filtering."""
        async with AsyncSessionLocal() as session:
            query = select(Inventory)
            if product_id is not None:
                query = query.filter(Inventory.product_id == product_id)
            if store_id is not None:
                query = query.filter(Inventory.store_id == store_id)

            result = await session.execute(query)
            inventory_items = result.scalars().all()
            return [InventorySchema.model_validate(item) for item in inventory_items]

    @handle_service_errors("retrieving inventory by ID")
    async def get_inventory_by_id(self, inventory_id: int) -> InventorySchema | None:
        """Get a single inventory item by its ID."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Inventory).filter_by(id=inventory_id))
            inventory = result.scalars().first()
            return InventorySchema.model_validate(inventory) if inventory else None

    @handle_service_errors("creating inventory")
    async def create_inventory(
        self, inventory_data: CreateInventorySchema
    ) -> InventorySchema:
        """Create a new inventory item."""
        try:
            async with AsyncSessionLocal() as session:
                new_inventory = Inventory(**inventory_data.model_dump())
                session.add(new_inventory)
                await session.commit()
                await session.refresh(new_inventory)
                return InventorySchema.model_validate(new_inventory)
        except IntegrityError:
            raise ConflictException(
                "Inventory entry for this product and store already exists."
            )

    @handle_service_errors("creating multiple inventory items")
    async def create_inventory_items(
        self, inventory_data_list: List[CreateInventorySchema]
    ) -> List[InventorySchema]:
        """Create multiple inventory items in a single transaction."""
        if not inventory_data_list:
            return []

        try:
            async with AsyncSessionLocal() as session:
                created_inventory_items = []

                for inventory_data in inventory_data_list:
                    new_inventory = Inventory(**inventory_data.model_dump())
                    session.add(new_inventory)
                    created_inventory_items.append(new_inventory)

                await session.commit()

                # Refresh all items to get their IDs and updated timestamps
                for inventory in created_inventory_items:
                    await session.refresh(inventory)

                return [
                    InventorySchema.model_validate(inventory)
                    for inventory in created_inventory_items
                ]

        except IntegrityError as e:
            # Check if it's a unique constraint violation
            if (
                "unique constraint" in str(e).lower()
                or "duplicate key" in str(e).lower()
            ):
                raise ConflictException(
                    "One or more inventory entries for the specified product and store combinations already exist."
                )
            raise ConflictException(f"Database integrity error: {str(e)}")
        except Exception as e:
            raise ValidationException(f"Error creating inventory items: {str(e)}")

    @handle_service_errors("updating inventory")
    async def update_inventory(
        self, inventory_id: int, inventory_data: UpdateInventorySchema
    ) -> InventorySchema:
        """Update an existing inventory item's stock levels."""
        async with AsyncSessionLocal() as session:
            # Use SELECT ... FOR UPDATE to lock the row
            result = await session.execute(
                select(Inventory).filter_by(id=inventory_id).with_for_update()
            )
            inventory = result.scalars().first()

            if not inventory:
                raise ResourceNotFoundException(
                    f"Inventory item with ID {inventory_id} not found"
                )

            update_data = inventory_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(inventory, key, value)

            await session.commit()
            await session.refresh(inventory)
            return InventorySchema.model_validate(inventory)

    @handle_service_errors("deleting inventory")
    async def delete_inventory(self, inventory_id: int) -> bool:
        """Delete an inventory item."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Inventory).filter_by(id=inventory_id))
            inventory = result.scalars().first()
            if not inventory:
                return False

            await session.delete(inventory)
            await session.commit()
            return True

    # Transaction methods - delegated to InventoryTransactionService
    async def adjust_inventory_stock(
        self, adjustment_data: AdjustInventorySchema, session
    ) -> InventorySchema:
        """Atomically adjust stock, hold, or reserved quantities."""
        return await self.transaction_service.adjust_inventory_stock(
            adjustment_data, session
        )

    async def place_hold(
        self, product_id: int, store_id: int, quantity: int, session
    ) -> InventorySchema:
        """Place a hold on inventory for an order."""
        return await self.transaction_service.place_hold(
            product_id, store_id, quantity, session
        )

    async def release_hold(
        self, product_id: int, store_id: int, quantity: int, session
    ) -> InventorySchema:
        """Release a hold on inventory (e.g., order cancelled)."""
        return await self.transaction_service.release_hold(
            product_id, store_id, quantity, session
        )

    async def confirm_reservation(
        self, product_id: int, store_id: int, quantity: int, session
    ) -> InventorySchema:
        """Convert a hold to a reservation (e.g., payment confirmed)."""
        return await self.transaction_service.confirm_reservation(
            product_id, store_id, quantity, session
        )

    async def fulfill_order(
        self, product_id: int, store_id: int, quantity: int, session
    ) -> InventorySchema:
        """Fulfill an order by removing reserved stock."""
        return await self.transaction_service.fulfill_order(
            product_id, store_id, quantity, session
        )

    async def place_holds_bulk(
        self, holds: list[dict], session
    ) -> list[InventorySchema]:
        """Place multiple inventory holds in a single optimized operation."""
        return await self.transaction_service.place_holds_bulk(holds, session)

    async def release_holds_bulk(
        self, holds: list[dict], session
    ) -> list[InventorySchema]:
        """Release multiple inventory holds in a single optimized operation."""
        return await self.transaction_service.release_holds_bulk(holds, session)

    @handle_service_errors("retrieving inventory for products")
    async def get_inventory_for_products_in_store(
        self, product_ids: List[int], store_id: int
    ) -> List[InventorySchema]:
        """Get inventory for a list of products in a specific store."""
        if not product_ids:
            return []

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Inventory).filter(
                    Inventory.product_id.in_(product_ids),
                    Inventory.store_id == store_id,
                )
            )
            inventory_items = result.scalars().all()
            return [InventorySchema.model_validate(item) for item in inventory_items]

    @handle_service_errors("retrieving inventory for products in multiple stores")
    async def get_inventory_for_products_in_stores(
        self, product_ids: List[int], store_ids: List[int]
    ) -> List[InventorySchema]:
        """Get inventory for a list of products across multiple stores efficiently."""
        if not product_ids or not store_ids:
            return []

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Inventory).filter(
                    Inventory.product_id.in_(product_ids),
                    Inventory.store_id.in_(store_ids),
                )
            )
            inventory_items = result.scalars().all()
            return [InventorySchema.model_validate(item) for item in inventory_items]
