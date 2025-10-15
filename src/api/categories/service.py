from typing import Optional

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.api.categories.models import (
    CategorySchema,
    CreateCategorySchema,
    UpdateCategorySchema,
)
from src.database.connection import AsyncSessionLocal
from src.database.models.category import Category
from src.shared.cache_invalidation import cache_invalidation_manager
from src.shared.error_handler import ErrorHandler, handle_service_errors
from src.shared.exceptions import (
    ConflictException,
    ResourceNotFoundException,
    ValidationException,
)
from src.shared.performance_utils import QueryOptimizer, async_timer
from src.shared.sqlalchemy_utils import safe_model_validate, safe_model_validate_list

from .cache import categories_cache


class CategoryService:
    """Category service with caching for improved performance"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self._query_optimizer = QueryOptimizer()

    @handle_service_errors("retrieving all categories")
    @async_timer("get_all_categories")
    async def get_all_categories(
        self,
        include_subcategories: Optional[bool] = True,
        parent_only: Optional[bool] = False,
        parent_id: Optional[int] = None,
        subcategories_only: Optional[bool] = False,
    ) -> list[CategorySchema]:
        """Get categories with flexible filtering options"""
        # Generate cache key based on filter parameters
        filter_type = None
        filter_value = None

        if parent_only:
            filter_type = "parent_only" + (
                "_with_subs" if include_subcategories else ""
            )
        elif parent_id is not None:
            filter_type = "parent"
            filter_value = str(parent_id) + (
                "_with_subs" if include_subcategories else ""
            )
        elif subcategories_only:
            filter_type = "subcategories_only" + (
                "_with_subs" if include_subcategories else ""
            )
        else:
            # Default 'all' case
            if include_subcategories:
                cached_categories = categories_cache.get_all_categories()
                if cached_categories is not None:
                    return [CategorySchema.model_validate(c) for c in cached_categories]

        # Check cache for filtered results
        if filter_type:
            cached_categories = categories_cache.get_filtered_categories(
                filter_type, filter_value
            )
            if cached_categories is not None:
                return [CategorySchema.model_validate(c) for c in cached_categories]

        async with AsyncSessionLocal() as session:
            # Build query with filters
            stmt = select(Category)

            # Apply filtering conditions
            if parent_only:
                stmt = stmt.filter(Category.parent_category_id.is_(None))
            elif parent_id is not None:
                stmt = stmt.filter(Category.parent_category_id == parent_id)
            elif subcategories_only:
                stmt = stmt.filter(Category.parent_category_id.is_not(None))

            # Add subcategories loading if requested
            if include_subcategories:
                stmt = stmt.options(selectinload(Category.subcategories))

            # Order by sort_order
            stmt = stmt.order_by(Category.sort_order)

            result = await session.execute(stmt)
            categories = result.scalars().unique().all()

            if categories:
                # Convert SQLAlchemy models to Pydantic schemas using safe converter
                include_relationships = (
                    {"subcategories"} if include_subcategories else set()
                )
                pydantic_categories = safe_model_validate_list(
                    CategorySchema,
                    categories,
                    include_relationships=include_relationships,
                )

                # Cache results based on filter type
                category_dicts = [
                    cat.model_dump(mode="json") for cat in pydantic_categories
                ]

                if filter_type:
                    # Cache filtered results
                    categories_cache.set_filtered_categories(
                        category_dicts, filter_type, filter_value
                    )
                else:
                    # Default 'all categories' case
                    if include_subcategories:
                        categories_cache.set_all_categories(category_dicts)

                return pydantic_categories

            return []

    async def get_category_by_id(self, category_id: int) -> CategorySchema | None:
        """Get category by ID with caching"""
        cached_category = categories_cache.get_category(category_id)
        if cached_category is not None:
            return CategorySchema.model_validate(cached_category)

        async with AsyncSessionLocal() as session:
            stmt = (
                select(Category)
                .options(selectinload(Category.subcategories))
                .filter(Category.id == category_id)
            )
            result = await session.execute(stmt)
            category = result.scalars().first()
            if category:
                # Convert SQLAlchemy model to Pydantic schema using safe converter
                pydantic_category = safe_model_validate(
                    CategorySchema, category, include_relationships={"subcategories"}
                )
                if pydantic_category.id:
                    categories_cache.set_category(
                        pydantic_category.id, pydantic_category.model_dump(mode="json")
                    )
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
            # Check if ID is manually specified and already exists
            if category_data.id:
                existing_id = await session.execute(
                    select(Category).filter(Category.id == category_data.id)
                )
                if existing_id.scalars().first():
                    raise ConflictException(
                        detail=f"Category with ID {category_data.id} already exists"
                    )

            # Validate parent category if provided
            if category_data.parent_category_id:
                parent = await session.execute(
                    select(Category).filter(
                        Category.id == category_data.parent_category_id
                    )
                )
                if not parent.scalars().first():
                    raise ResourceNotFoundException(
                        detail=f"Parent category with ID {category_data.parent_category_id} not found"
                    )

            # Create category with optional ID
            category_kwargs = {
                "name": category_data.name.strip(),
                "description": category_data.description.strip()
                if category_data.description
                else None,
                "sort_order": category_data.sort_order,
                "image_url": category_data.image_url,
                "parent_category_id": category_data.parent_category_id,
            }

            # Add manual ID if specified
            if category_data.id:
                category_kwargs["id"] = category_data.id

            new_category = Category(**category_kwargs)
            session.add(new_category)
            await session.commit()
            await session.refresh(new_category)

            # Explicitly load subcategories after refresh
            await session.refresh(new_category, ["subcategories"])

            # Convert SQLAlchemy model to Pydantic schema using safe converter
            pydantic_category = safe_model_validate(
                CategorySchema, new_category, include_relationships={"subcategories"}
            )
            # After commit and refresh, the ID should always be present
            assert pydantic_category.id is not None, (
                "Category ID should be present after database commit"
            )
            categories_cache.set_category(
                pydantic_category.id, pydantic_category.model_dump(mode="json")
            )
            cache_invalidation_manager.invalidate_category()  # Invalidate all categories cache

            return pydantic_category

    async def update_category(
        self, category_id: int, category_data: UpdateCategorySchema
    ) -> CategorySchema | None:
        """Update an existing category"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Category).filter(Category.id == category_id)
            )
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
                CategorySchema, category, include_relationships={"subcategories"}
            )
            # After commit and refresh, the ID should always be present
            assert pydantic_category.id is not None, (
                "Category ID should be present after database commit"
            )
            categories_cache.set_category(
                pydantic_category.id, pydantic_category.model_dump(mode="json")
            )
            cache_invalidation_manager.invalidate_category(
                pydantic_category.id
            )  # Invalidate specific category cache

            return pydantic_category

    async def delete_category(self, category_id: int) -> bool:
        """Delete a category"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Category).filter(Category.id == category_id)
            )
            category = result.scalars().first()

            if not category:
                return False

            await session.delete(category)
            await session.commit()

            categories_cache.invalidate_category_cache(
                category_id
            )  # Invalidate specific category cache
            cache_invalidation_manager.invalidate_category()  # Invalidate all categories cache

            return True

    async def create_categories(
        self, categories_data: list[CreateCategorySchema]
    ) -> list[CategorySchema]:
        """Create multiple new categories with validation and optimization"""
        if not categories_data:
            raise ValidationException(detail="Category list cannot be empty")

        async with AsyncSessionLocal() as session:
            created_categories = []
            for category_data in categories_data:
                if not category_data.name or not category_data.name.strip():
                    raise ValidationException(detail="Category name is required")

                if category_data.sort_order < 0:
                    raise ValidationException(detail="Sort order cannot be negative")

                # Check if ID is manually specified and already exists
                if category_data.id:
                    existing_id = await session.execute(
                        select(Category).filter(Category.id == category_data.id)
                    )
                    if existing_id.scalars().first():
                        raise ConflictException(
                            detail=f"Category with ID {category_data.id} already exists"
                        )

                # Validate parent category if provided
                if category_data.parent_category_id:
                    parent = await session.execute(
                        select(Category).filter(
                            Category.id == category_data.parent_category_id
                        )
                    )
                    if not parent.scalars().first():
                        raise ResourceNotFoundException(
                            detail=f"Parent category with ID {category_data.parent_category_id} not found"
                        )

                # Create category with optional ID
                category_kwargs = {
                    "name": category_data.name.strip(),
                    "description": category_data.description.strip()
                    if category_data.description
                    else None,
                    "sort_order": category_data.sort_order,
                    "image_url": category_data.image_url,
                    "parent_category_id": category_data.parent_category_id,
                }

                # Add manual ID if specified
                if category_data.id:
                    category_kwargs["id"] = category_data.id

                new_category = Category(**category_kwargs)
                session.add(new_category)
                created_categories.append(new_category)

            await session.commit()

            for category in created_categories:
                await session.refresh(category, ["subcategories"])

            pydantic_categories = safe_model_validate_list(
                CategorySchema,
                created_categories,
                include_relationships={"subcategories"},
            )

            for pydantic_category in pydantic_categories:
                assert pydantic_category.id is not None, (
                    "Category ID should be present after database commit"
                )
                categories_cache.set_category(
                    pydantic_category.id, pydantic_category.model_dump(mode="json")
                )

            cache_invalidation_manager.invalidate_category()

            return pydantic_categories

    async def get_categories_by_ids(
        self, category_ids: list[int]
    ) -> list[CategorySchema]:
        """Get multiple categories by their IDs efficiently"""
        if not category_ids:
            return []

        async with AsyncSessionLocal() as session:
            stmt = (
                select(Category)
                .options(selectinload(Category.subcategories))
                .filter(Category.id.in_(category_ids))
                .order_by(Category.sort_order)
            )
            result = await session.execute(stmt)
            categories = result.scalars().unique().all()

            return safe_model_validate_list(
                CategorySchema, categories, include_relationships={"subcategories"}
            )
