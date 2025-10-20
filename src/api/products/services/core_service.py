from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.api.products.cache import products_cache
from src.api.products.models import (
    CreateProductSchema,
    EnhancedProductSchema,
    ProductSchema,
    UpdateProductSchema,
)
from src.config.constants import Collections
from src.database.connection import AsyncSessionLocal
from src.database.models.category import Category
from src.database.models.product import Product, ProductTag
from src.shared.cache_invalidation import cache_invalidation_manager
from src.shared.error_handler import ErrorHandler, handle_service_errors
from src.shared.exceptions import (
    ConflictException,
    ResourceNotFoundException,
    ValidationException,
)
from src.shared.sqlalchemy_utils import safe_model_validate


class ProductCoreService:
    """Handles core CRUD operations for products"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)

    @handle_service_errors("retrieving product by ID")
    async def get_product_by_id(
        self,
        product_id: int,
        include_categories: bool = True,
        include_tags: bool = True,
    ) -> EnhancedProductSchema | None:
        """Get product by ID with relationships."""
        if product_id <= 0:
            raise ValidationException(detail="Product ID must be a positive integer")

        cached_product = products_cache.get_product(str(product_id))
        if cached_product:
            return EnhancedProductSchema.model_validate(cached_product)

        async with AsyncSessionLocal() as session:
            query = select(Product).filter(Product.id == product_id)

            if include_categories:
                query = query.options(selectinload(Product.categories))
            if include_tags:
                query = query.options(
                    selectinload(Product.product_tags).selectinload(ProductTag.tag)
                )

            result = await session.execute(query)
            product = result.scalars().first()

            if product:
                pydantic_product = safe_model_validate(
                    EnhancedProductSchema, product, max_depth=3
                )

                products_cache.set_product(
                    str(product_id), pydantic_product.model_dump(mode="json")
                )
                return pydantic_product

            return None

    @handle_service_errors("retrieving product by ref")
    async def get_product_by_ref(
        self,
        product_ref: str,
        include_categories: bool = True,
        include_tags: bool = True,
    ) -> EnhancedProductSchema | None:
        """Get product by ref with relationships."""
        if not product_ref or not product_ref.strip():
            raise ValidationException(detail="Product ref cannot be empty")

        product_ref = product_ref.strip()

        async with AsyncSessionLocal() as session:
            query = select(Product).filter(Product.ref == product_ref)

            if include_categories:
                query = query.options(selectinload(Product.categories))
            if include_tags:
                query = query.options(
                    selectinload(Product.product_tags).selectinload(ProductTag.tag)
                )

            result = await session.execute(query)
            product = result.scalars().first()

            if product:
                pydantic_product = safe_model_validate(
                    EnhancedProductSchema, product, max_depth=3
                )
                return pydantic_product

            return None

    @handle_service_errors("creating product")
    async def create_product(self, product_data: CreateProductSchema) -> ProductSchema:
        """Create a new product with categories and tags"""
        if not product_data.name or not product_data.name.strip():
            raise ValidationException(detail="Product name is required")

        if product_data.base_price < 0:
            raise ValidationException(detail="Product price cannot be negative")

        if not product_data.unit_measure or not product_data.unit_measure.strip():
            raise ValidationException(detail="Product unit measure is required")

        if product_data.ref:
            if not product_data.ref.strip():
                raise ValidationException(detail="Product ref cannot be empty")

        async with AsyncSessionLocal() as session:
            # Check if ref already exists
            if product_data.ref:
                existing_ref = await session.execute(
                    select(Product).filter(Product.ref == product_data.ref.strip())
                )
                if existing_ref.scalars().first():
                    raise ConflictException(
                        detail=f"Product with ref '{product_data.ref}' already exists"
                    )

            # Check if ID is manually specified and already exists
            if product_data.id:
                existing_id = await session.execute(
                    select(Product).filter(Product.id == product_data.id)
                )
                if existing_id.scalars().first():
                    raise ConflictException(
                        detail=f"Product with ID {product_data.id} already exists"
                    )

            # Create the product
            product_kwargs = {
                "name": product_data.name.strip(),
                "description": product_data.description.strip()
                if product_data.description
                else None,
                "brand": product_data.brand.strip() if product_data.brand else None,
                "base_price": product_data.base_price,
                "unit_measure": product_data.unit_measure.strip(),
                "image_urls": product_data.image_urls or [],
                "ref": product_data.ref.strip() if product_data.ref else None,
            }

            if product_data.id:
                product_kwargs["id"] = product_data.id

            new_product = Product(**product_kwargs)
            session.add(new_product)
            await session.commit()
            await session.refresh(new_product)

            # Add categories if provided
            if product_data.category_ids:
                category_result = await session.execute(
                    select(Category).filter(Category.id.in_(product_data.category_ids))
                )
                categories = category_result.scalars().all()

                found_category_ids = {cat.id for cat in categories}
                missing_category_ids = (
                    set(product_data.category_ids) - found_category_ids
                )
                if missing_category_ids:
                    raise ResourceNotFoundException(
                        detail=f"Categories with IDs {list(missing_category_ids)} not found"
                    )

                await session.refresh(new_product, ["categories"])
                new_product.categories.extend(categories)

            # Add tags if provided
            if product_data.tag_ids:
                unique_tag_ids = list(set(product_data.tag_ids))
                for tag_id in unique_tag_ids:
                    product_tag = ProductTag(
                        product_id=new_product.id, tag_id=tag_id, created_by="system"
                    )
                    session.add(product_tag)

            await session.commit()
            await session.refresh(new_product)
            await session.refresh(new_product, ["categories", "product_tags"])

            pydantic_product = safe_model_validate(
                ProductSchema, new_product, max_depth=3
            )

            cache_invalidation_manager.invalidate_entity(Collections.PRODUCTS)
            return pydantic_product

    async def update_product(
        self, product_id: int, product_data: UpdateProductSchema
    ) -> ProductSchema | None:
        """Update an existing product"""
        async with AsyncSessionLocal() as session:
            if product_data.alternative_product_ids is not None:
                # Validate alternative_product_ids
                result = await session.execute(select(Product.id))
                existing_product_ids = {row[0] for row in result}
                invalid_ids = (
                    set(product_data.alternative_product_ids) - existing_product_ids
                )
                if invalid_ids:
                    raise ValidationException(
                        detail=f"Alternative products with IDs {list(invalid_ids)} not found"
                    )

            try:
                result = await session.execute(
                    select(Product).filter(Product.id == product_id)
                )
                product = result.scalars().first()

                if not product:
                    return None

                # Update basic fields
                update_dict = product_data.model_dump(
                    mode="json", exclude_unset=True, exclude={"category_ids", "tag_ids"}
                )
                for field, value in update_dict.items():
                    setattr(product, field, value)

                # Update categories if provided
                if product_data.category_ids is not None:
                    await session.refresh(product, ["categories"])
                    product.categories.clear()
                    if product_data.category_ids:
                        category_result = await session.execute(
                            select(Category).filter(
                                Category.id.in_(product_data.category_ids)
                            )
                        )
                        categories = category_result.scalars().all()

                        found_category_ids = {cat.id for cat in categories}
                        missing_category_ids = (
                            set(product_data.category_ids) - found_category_ids
                        )
                        if missing_category_ids:
                            raise ResourceNotFoundException(
                                detail=f"Categories with IDs {list(missing_category_ids)} not found"
                            )

                        product.categories.extend(categories)

                # Update tags if provided
                if product_data.tag_ids is not None:
                    await session.execute(
                        ProductTag.__table__.delete().where(
                            ProductTag.product_id == product_id
                        )
                    )
                    unique_tag_ids = list(set(product_data.tag_ids))
                    for tag_id in unique_tag_ids:
                        product_tag = ProductTag(
                            product_id=product_id, tag_id=tag_id, created_by="system"
                        )
                        session.add(product_tag)

                await session.commit()
                await session.refresh(product)
                await session.refresh(product, ["categories", "product_tags"])

                pydantic_product = safe_model_validate(
                    ProductSchema, product, max_depth=3
                )

                products_cache.invalidate_product_cache(str(product_id))
                cache_invalidation_manager.invalidate_entity(
                    Collections.PRODUCTS, str(product_id)
                )

                return pydantic_product

            except IntegrityError as e:
                await session.rollback()
                if "tag_id" in str(e.orig) and "is not present" in str(e.orig):
                    raise ResourceNotFoundException(
                        detail="One or more specified tags not found"
                    )
                else:
                    raise

    async def delete_product(self, product_id: int) -> bool:
        """Delete a product"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Product).filter(Product.id == product_id)
            )
            product = result.scalars().first()

            if not product:
                return False

            await session.delete(product)
            await session.commit()

            products_cache.invalidate_product_cache(str(product_id))
            cache_invalidation_manager.invalidate_entity(
                Collections.PRODUCTS, str(product_id)
            )

            return True
