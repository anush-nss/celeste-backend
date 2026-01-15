from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.riders.models import RiderProfileSchema
from src.database.connection import AsyncSessionLocal
from src.database.models.rider import RiderProfile
from src.database.models.store import Store
from src.shared.error_handler import ErrorHandler


class RiderQueryService:
    def __init__(self):
        self._error_handler = ErrorHandler(__name__)

    async def get_rider_by_id(self, rider_id: int) -> Optional[RiderProfileSchema]:
        """Get rider by ID"""
        async with AsyncSessionLocal() as session:
            try:
                query = select(RiderProfile).filter(RiderProfile.id == rider_id)
                result = await session.execute(query)
                rider = result.scalars().first()
                if rider:
                    return RiderProfileSchema.model_validate(rider)
                return None
            except Exception as e:
                self._error_handler.log_error("get_rider_by_id", e)
                raise

    async def get_rider_by_phone(self, phone: str) -> Optional[RiderProfileSchema]:
        """Get rider by phone number"""
        async with AsyncSessionLocal() as session:
            try:
                query = select(RiderProfile).filter(RiderProfile.phone == phone)
                result = await session.execute(query)
                rider = result.scalars().first()
                if rider:
                    return RiderProfileSchema.model_validate(rider)
                return None
            except Exception as e:
                self._error_handler.log_error("get_rider_by_phone", e)
                raise

    async def get_rider_by_user_id(self, user_id: str) -> Optional[RiderProfileSchema]:
        """Get rider by Firebase User ID"""
        async with AsyncSessionLocal() as session:
            try:
                query = select(RiderProfile).filter(RiderProfile.user_id == user_id)
                result = await session.execute(query)
                rider = result.scalars().first()
                if rider:
                    return RiderProfileSchema.model_validate(rider)
                return None
            except Exception as e:
                self._error_handler.log_error("get_rider_by_user_id", e)
                raise

    async def get_riders(self, store_id: Optional[int] = None) -> List[RiderProfileSchema]:
        """Get all riders, optionally filtered by store_id"""
        async with AsyncSessionLocal() as session:
            try:
                query = select(RiderProfile)

                if store_id:
                    # Filter by store relationship
                    query = query.join(RiderProfile.stores).filter(Store.id == store_id)

                # Order by created_at desc
                query = query.order_by(RiderProfile.created_at.desc())

                result = await session.execute(query)
                riders = result.scalars().all()

                return [RiderProfileSchema.model_validate(r) for r in riders]
            except Exception as e:
                self._error_handler.log_error("get_riders", e)
                raise
