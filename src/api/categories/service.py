import asyncio
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, joinedload
from src.database.connection import AsyncSessionLocal
from src.database.models.category import Category
from src.config.cache_config import cache_config
from .cache import categories_cache
from src.api.categories.models import (
    CategorySchema,
    CreateCategorySchema,
    UpdateCategorySchema,
)
from src.config.constants import Collections
from src.shared.cache_invalidation import cache_invalidation_manager
from src.shared.exceptions import ResourceNotFoundException, ValidationException, ConflictException
from src.shared.error_handler import ErrorHandler, handle_service_errors
from src.shared.performance_utils import async_timer, QueryOptimizer
from src.shared.sqlalchemy_utils import safe_model_validate, safe_model_validate_list


class CategoryService:
    """Category service with caching for improved performance"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self._query_optimizer = QueryOptimizer()

    @handle_service_errors("retrieving all categories")
    @async_timer("get_all_categories")
    async def get_all_categories(self) -> list[CategorySchema]:
        """Get all categories with optimized caching and loading"""
        # Check cache first
        cached_categories = categories_cache.get_all_categories()
        if cached_categories is not None:
            return [CategorySchema.model_validate(c) for c in cached_categories]

        async with AsyncSessionLocal() as session:
            # Optimized query with selective loading
            stmt = select(Category).options(
                selectinload(Category.subcategories)
            ).order_by(Category.sort_order)

            result = await session.execute(stmt)
            categories = result.scalars().unique().all()

            if categories:
                # Convert SQLAlchemy models to Pydantic schemas using safe converter
                pydantic_categories = safe_model_validate_list(
                    CategorySchema,
                    categories,
                    include_relationships={'subcategories'}
                )
                # Cache the dict representations asynchronously (non-blocking)
                category_dicts = [cat.model_dump(mode="json") for cat in pydantic_categories]
                categories_cache.set_all_categories(category_dicts)
                return pydantic_categories

            return []

    async def get_category_by_id(self, category_id: int) -> CategorySchema | None:
        """Get category by ID with caching"""
        cached_category = categories_cache.get_category(category_id)
        if cached_category is not None:
            return CategorySchema.model_validate(cached_category)

        async with AsyncSessionLocal() as session:
            stmt = select(Category).options(
                selectinload(Category.subcategories)
            ).filter(Category.id == category_id)
            result = await session.execute(stmt)
            category = result.scalars().first()
            if category:
                # Convert SQLAlchemy model to Pydantic schema using safe converter
                pydantic_category = safe_model_validate(
                    CategorySchema, 
                    category,
                    include_relationships={'subcategories'}
                )
                if pydantic_category.id:
                    categories_cache.set_category(pydantic_category.id, pydantic_category.model_dump(mode="json"))
                return pydantic_category
        return None

    @handle_service_errors("creating category")
    @async_timer("create_category")
    async def create_category(
        self, category_data: CreateCategorySchema
    ) -> CategorySchema:
        """Create a new category with validation and optimization"""
        if not category_data.name or not category_data.name.strip():
            raise ValidationException(detail="Category name is required")

        if category_data.sort_order < 0:
            raise ValidationException(detail="Sort order cannot be negative")

        async with AsyncSessionLocal() as session:
            # Check for duplicate name
            existing = await session.execute(
                select(Category).filter(Category.name == category_data.name.strip())
            )
            if existing.scalars().first():
                raise ConflictException(detail=f"Category with name '{category_data.name}' already exists")

            # Validate parent category if provided
            if category_data.parent_category_id:
                parent = await session.execute(
                    select(Category).filter(Category.id == category_data.parent_category_id)
                )
                if not parent.scalars().first():
                    raise ResourceNotFoundException(
                        detail=f"Parent category with ID {category_data.parent_category_id} not found"
                    )

            new_category = Category(
                name=category_data.name.strip(),
                description=category_data.description.strip() if category_data.description else None,
                sort_order=category_data.sort_order,
                image_url=category_data.image_url,
                parent_category_id=category_data.parent_category_id
            )
            session.add(new_category)
            await session.commit()
            await session.refresh(new_category)

            # Explicitly load subcategories after refresh
            await session.refresh(new_category, ["subcategories"])

            # Convert SQLAlchemy model to Pydantic schema using safe converter
            pydantic_category = safe_model_validate(
                CategorySchema,
                new_category,
                include_relationships={'subcategories'}
            )
            # After commit and refresh, the ID should always be present
            assert pydantic_category.id is not None, "Category ID should be present after database commit"
            categories_cache.set_category(pydantic_category.id, pydantic_category.model_dump(mode="json"))
            cache_invalidation_manager.invalidate_category()  # Invalidate all categories cache

            return pydantic_category

    async def update_category(
        self, category_id: int, category_data: UpdateCategorySchema
    ) -> CategorySchema | None:
        """Update an existing category"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Category).filter(Category.id == category_id))
            category = result.scalars().first()

            if not category:
                return None

            update_dict = category_data.model_dump(exclude_unset=True)
            for field, value in update_dict.items():
                setattr(category, field, value)

            await session.commit()
            await session.refresh(category)
            
            # Explicitly load subcategories after refresh
            await session.refresh(category, ["subcategories"])

            # Convert SQLAlchemy model to Pydantic schema using safe converter
            pydantic_category = safe_model_validate(
                CategorySchema, 
                category,
                include_relationships={'subcategories'}
            )
            # After commit and refresh, the ID should always be present
            assert pydantic_category.id is not None, "Category ID should be present after database commit"
            categories_cache.set_category(pydantic_category.id, pydantic_category.model_dump(mode="json"))
            cache_invalidation_manager.invalidate_category(pydantic_category.id) # Invalidate specific category cache

            return pydantic_category

    async def delete_category(self, category_id: int) -> bool:
        """Delete a category""" 
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Category).filter(Category.id == category_id))
            category = result.scalars().first()

            if not category:
                return False

            await session.delete(category)
            await session.commit()

            categories_cache.invalidate_category_cache(category_id) # Invalidate specific category cache
            cache_invalidation_manager.invalidate_category() # Invalidate all categories cache

            return True

    async def get_categories_by_ids(
        self, category_ids: list[int]
    ) -> list[CategorySchema]:
        """Get multiple categories by their IDs efficiently"""
        if not category_ids:
            return []

        async with AsyncSessionLocal() as session:
            stmt = select(Category).options(
                selectinload(Category.subcategories)
            ).filter(Category.id.in_(category_ids))
            result = await session.execute(stmt)
            categories = result.scalars().unique().all()

            return safe_model_validate_list(
                CategorySchema, 
                categories,
                include_relationships={'subcategories'}
            )