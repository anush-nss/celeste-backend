from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, func, select

from src.api.promotions.models import (
    CreatePromotionSchema,
    PromotionSchema,
    UpdatePromotionSchema,
)
from src.config.constants import PromotionType
from src.database.connection import AsyncSessionLocal
from src.database.models.promotion import Promotion
from src.shared.exceptions import ResourceNotFoundException


class PromotionService:
    async def create_promotion(
        self, promotion_data: CreatePromotionSchema
    ) -> PromotionSchema:
        async with AsyncSessionLocal() as session:
            new_promotion = Promotion(**promotion_data.model_dump())
            session.add(new_promotion)
            await session.commit()
            await session.refresh(new_promotion)
            return PromotionSchema.model_validate(new_promotion)

    async def get_all_promotions(self) -> List[PromotionSchema]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Promotion).order_by(Promotion.priority.desc())
            )
            promotions = result.scalars().all()
            return [PromotionSchema.model_validate(p) for p in promotions]

    async def get_promotion_by_id(self, promotion_id: int) -> PromotionSchema:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Promotion).where(Promotion.id == promotion_id)
            )
            promotion = result.scalar_one_or_none()
            if not promotion:
                raise ResourceNotFoundException("Promotion not found")
            return PromotionSchema.model_validate(promotion)

    async def update_promotion(
        self, promotion_id: int, promotion_data: UpdatePromotionSchema
    ) -> PromotionSchema:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Promotion).where(Promotion.id == promotion_id)
            )
            promotion = result.scalar_one_or_none()
            if not promotion:
                raise ResourceNotFoundException("Promotion not found")

            update_data = promotion_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(promotion, key, value)

            await session.commit()
            await session.refresh(promotion)
            return PromotionSchema.model_validate(promotion)

    async def delete_promotion(self, promotion_id: int):
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Promotion).where(Promotion.id == promotion_id)
            )
            promotion = result.scalar_one_or_none()
            if not promotion:
                raise ResourceNotFoundException("Promotion not found")

            await session.delete(promotion)
            await session.commit()
            return

    async def get_active_promotions_random(
        self,
        promotion_type: PromotionType,
        product_id: Optional[int] = None,
        category_id: Optional[int] = None,
        limit: int = 1,
    ) -> List[PromotionSchema]:
        async with AsyncSessionLocal() as session:
            now = datetime.now(timezone.utc)

            base_query = select(Promotion).where(
                Promotion.is_active,
                Promotion.promotion_type == promotion_type,
                Promotion.start_date <= now,
                Promotion.end_date >= now,
            )

            filters = []
            if product_id:
                filters.append(Promotion.product_ids.contains([product_id]))
            if category_id:
                filters.append(Promotion.category_ids.contains([category_id]))

            if filters:
                base_query = base_query.where(and_(*filters))

            # Weighted random selection using priority
            # ORDER BY -log(random()) / priority
            query = base_query.order_by(
                -func.log(func.random()) / Promotion.priority
            ).limit(limit)

            result = await session.execute(query)
            promotions = result.scalars().all()

            return [PromotionSchema.model_validate(p) for p in promotions]

    async def get_active_promotions_all(
        self,
        promotion_type: PromotionType,
        product_id: Optional[int] = None,
        category_id: Optional[int] = None,
    ) -> List[PromotionSchema]:
        async with AsyncSessionLocal() as session:
            now = datetime.now(timezone.utc)

            base_query = select(Promotion).where(
                Promotion.is_active,
                Promotion.promotion_type == promotion_type,
                Promotion.start_date <= now,
                Promotion.end_date >= now,
            )

            filters = []
            if product_id:
                filters.append(Promotion.product_ids.contains([product_id]))
            if category_id:
                filters.append(Promotion.category_ids.contains([category_id]))

            if filters:
                base_query = base_query.where(and_(*filters))

            query = base_query.order_by(Promotion.priority.desc())

            result = await session.execute(query)
            promotions = result.scalars().all()

            return [PromotionSchema.model_validate(p) for p in promotions]
