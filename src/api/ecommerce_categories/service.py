from typing import List, Optional
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.database.connection import AsyncSessionLocal
from src.database.models.ecommerce_category import EcommerceCategory
from src.api.ecommerce_categories.models import (
    EcommerceCategorySchema,
    CreateEcommerceCategorySchema,
    UpdateEcommerceCategorySchema,
)
from src.shared.exceptions import ResourceNotFoundException, ConflictException
from src.shared.sqlalchemy_utils import safe_model_validate, safe_model_validate_list


class EcommerceCategoryService:
    async def get_all_categories(self, include_subcategories: bool = True) -> List[EcommerceCategorySchema]:
        """Get all ecommerce categories, optionally including subcategories"""
        async with AsyncSessionLocal() as session:
            if include_subcategories:
                stmt = select(EcommerceCategory).options(
                    selectinload(EcommerceCategory.subcategories)
                ).where(EcommerceCategory.parent_category_id.is_(None))
            else:
                stmt = select(EcommerceCategory)

            result = await session.execute(stmt)
            categories = result.scalars().all()

            include_relationships = {'subcategories'} if include_subcategories else set()
            return safe_model_validate_list(
                EcommerceCategorySchema,
                categories,
                include_relationships=include_relationships
            )

    async def get_category_by_id(self, category_id: int) -> Optional[EcommerceCategorySchema]:
        """Get an ecommerce category by ID"""
        async with AsyncSessionLocal() as session:
            stmt = select(EcommerceCategory).options(
                selectinload(EcommerceCategory.subcategories)
            ).where(EcommerceCategory.id == category_id)

            result = await session.execute(stmt)
            category = result.scalar_one_or_none()

            if category:
                return safe_model_validate(
                    EcommerceCategorySchema,
                    category,
                    include_relationships={'subcategories'}
                )
            return None

    async def create_categories(self, categories_data: List[CreateEcommerceCategorySchema]) -> List[EcommerceCategorySchema]:
        """Create one or more ecommerce categories"""
        async with AsyncSessionLocal() as session:
            created_categories = []

            for category_data in categories_data:
                # Check if manual ID is provided and already exists
                if category_data.id:
                    existing = await session.execute(
                        select(EcommerceCategory).where(EcommerceCategory.id == category_data.id)
                    )
                    if existing.scalar_one_or_none():
                        raise ConflictException(detail=f"Ecommerce category with ID {category_data.id} already exists")

                # Validate parent category exists if provided
                if category_data.parent_category_id:
                    parent_result = await session.execute(
                        select(EcommerceCategory).where(EcommerceCategory.id == category_data.parent_category_id)
                    )
                    if not parent_result.scalar_one_or_none():
                        raise ResourceNotFoundException(detail=f"Parent category with ID {category_data.parent_category_id} not found")

                # Create category
                category_dict = category_data.model_dump(exclude_unset=True)
                category = EcommerceCategory(**category_dict)

                session.add(category)
                created_categories.append(category)

            try:
                await session.commit()

                # Refresh to get the generated IDs and relationships
                for category in created_categories:
                    await session.refresh(category, ["subcategories"])

                return safe_model_validate_list(
                    EcommerceCategorySchema,
                    created_categories,
                    include_relationships={'subcategories'}
                )

            except IntegrityError as e:
                await session.rollback()
                if "duplicate key" in str(e).lower():
                    raise ConflictException(detail="Ecommerce category with this ID already exists")
                raise ConflictException(detail="Database constraint violation")

    async def update_category(self, category_id: int, category_data: UpdateEcommerceCategorySchema) -> Optional[EcommerceCategorySchema]:
        """Update an ecommerce category"""
        async with AsyncSessionLocal() as session:
            stmt = select(EcommerceCategory).where(EcommerceCategory.id == category_id)
            result = await session.execute(stmt)
            category = result.scalar_one_or_none()

            if not category:
                return None

            # Validate parent category exists if provided
            if category_data.parent_category_id:
                parent_result = await session.execute(
                    select(EcommerceCategory).where(EcommerceCategory.id == category_data.parent_category_id)
                )
                if not parent_result.scalar_one_or_none():
                    raise ResourceNotFoundException(detail=f"Parent category with ID {category_data.parent_category_id} not found")

            # Update fields
            update_data = category_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(category, field, value)

            try:
                await session.commit()
                await session.refresh(category, ["subcategories"])
                return safe_model_validate(
                    EcommerceCategorySchema,
                    category,
                    include_relationships={'subcategories'}
                )
            except IntegrityError:
                await session.rollback()
                raise ConflictException(detail="Database constraint violation")

    async def delete_category(self, category_id: int) -> bool:
        """Delete an ecommerce category"""
        async with AsyncSessionLocal() as session:
            stmt = select(EcommerceCategory).where(EcommerceCategory.id == category_id)
            result = await session.execute(stmt)
            category = result.scalar_one_or_none()

            if not category:
                return False

            await session.delete(category)
            await session.commit()
            return True