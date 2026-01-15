from typing import Optional

from sqlalchemy import delete, insert, select, update

from src.api.riders.models import (
    RiderProfileSchema,
    UpdateRiderSchema,
)
from src.database.connection import AsyncSessionLocal
from src.database.models.associations import store_riders
from src.database.models.rider import RiderProfile
from src.database.models.store import Store
from src.shared.error_handler import ErrorHandler
from src.shared.exceptions import ResourceNotFoundException


class RiderService:
    def __init__(self):
        self._error_handler = ErrorHandler(__name__)


    async def update_rider(
        self, rider_id: int, payload: UpdateRiderSchema
    ) -> RiderProfileSchema:
        """Update rider profile"""
        async with AsyncSessionLocal() as session:
            try:
                query = select(RiderProfile).filter(RiderProfile.id == rider_id)
                result = await session.execute(query)
                rider = result.scalars().first()

                if not rider:
                    raise ResourceNotFoundException(detail=f"Rider with ID {rider_id} not found")

                update_data = payload.model_dump(exclude_unset=True)
                for field, value in update_data.items():
                    setattr(rider, field, value)

                await session.commit()
                await session.refresh(rider)

                return RiderProfileSchema.model_validate(rider)
            except Exception as e:
                self._error_handler.log_error("update_rider", e)
                raise

    async def assign_rider_to_store(self, rider_id: int, store_id: int):
        """Assign a rider to a store"""
        async with AsyncSessionLocal() as session:
            try:
                # Validate rider exists (we don't lock, assuming minimal race condition risk here)
                rider_exists = await session.scalar(
                    select(RiderProfile.id).filter(RiderProfile.id == rider_id)
                )
                if not rider_exists:
                    raise ResourceNotFoundException(detail="Rider not found")

                # Validate store exists
                store_exists = await session.scalar(select(Store.id).filter(Store.id == store_id))
                if not store_exists:
                    raise ResourceNotFoundException(detail="Store not found")

                # Check if association already exists
                stmt = select(store_riders).filter(
                    store_riders.c.store_id == store_id,
                    store_riders.c.rider_profile_id == rider_id,
                )
                result = await session.execute(stmt)
                if result.first():
                    # Idempotent success
                    return

                # Create association
                insert_stmt = insert(store_riders).values(
                    store_id=store_id, rider_profile_id=rider_id
                )
                await session.execute(insert_stmt)
                await session.commit()

            except Exception as e:
                self._error_handler.log_error("assign_rider_to_store", e)
                raise

    async def remove_rider_from_store(self, rider_id: int, store_id: int):
        """Remove a rider from a store"""
        async with AsyncSessionLocal() as session:
            try:
                # Remove association
                stmt = delete(store_riders).where(
                    store_riders.c.store_id == store_id,
                    store_riders.c.rider_profile_id == rider_id,
                )
                result = await session.execute(stmt)
                await session.commit()
                
                if result.rowcount == 0:
                     # Could raise 404, but idempotent is usually better. 
                     # However user requested "delete also needed", usually implying explicit action.
                     # We'll return success regardless if it existed or not (standard idempotent DELETE).
                     pass

            except Exception as e:
                self._error_handler.log_error("remove_rider_from_store", e)
                raise
