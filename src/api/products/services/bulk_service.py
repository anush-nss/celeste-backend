from typing import List
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from src.database.connection import AsyncSessionLocal
from src.database.models.product import Product, ProductTag, Tag
from src.database.models.category import Category
from src.api.products.models import (
    CreateProductSchema,
    ProductSchema,
)
from src.config.constants import Collections
from src.shared.cache_invalidation import cache_invalidation_manager
from src.shared.sqlalchemy_utils import safe_model_validate_list
from src.shared.exceptions import ValidationException, ConflictException, ResourceNotFoundException
from src.shared.error_handler import ErrorHandler, handle_service_errors


class ProductBulkService:
    """Handles bulk operations for products"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)

    @handle_service_errors("creating multiple products")
    async def create_products(self, products_data: list[CreateProductSchema]) -> list[ProductSchema]:
        """Create multiple new products with validation and optimization"""
        if not products_data:
            raise ValidationException(detail="Product list cannot be empty")

        async with AsyncSessionLocal() as session:
            # Step 1: Bulk validation
            all_category_ids = {cid for p in products_data for cid in p.category_ids}
            all_tag_ids = {tid for p in products_data for tid in p.tag_ids}
            product_names = {p.name for p in products_data}

            # Collect refs and IDs for validation
            product_refs = {p.ref for p in products_data if p.ref and p.ref.strip()}
            product_ids = {p.id for p in products_data if p.id}

            # Check for duplicate refs in the request
            ref_counts = {}
            for p in products_data:
                if p.ref and p.ref.strip():
                    ref = p.ref.strip()
                    ref_counts[ref] = ref_counts.get(ref, 0) + 1
                    if ref_counts[ref] > 1:
                        raise ValidationException(detail=f"Duplicate ref '{ref}' found in request")

            # Check for duplicate IDs in the request
            id_counts = {}
            for p in products_data:
                if p.id:
                    id_counts[p.id] = id_counts.get(p.id, 0) + 1
                    if id_counts[p.id] > 1:
                        raise ValidationException(detail=f"Duplicate ID {p.id} found in request")

            # Check for existing product names
            existing_products = (await session.execute(select(Product).filter(Product.name.in_(product_names)))).scalars().all()
            if existing_products:
                raise ConflictException(f"Products with these names already exist: {[p.name for p in existing_products]}")

            # Check for existing refs
            if product_refs:
                existing_refs = (await session.execute(select(Product).filter(Product.ref.in_(product_refs)))).scalars().all()
                if existing_refs:
                    raise ConflictException(f"Products with these refs already exist: {[p.ref for p in existing_refs]}")

            # Check for existing IDs
            if product_ids:
                existing_ids = (await session.execute(select(Product).filter(Product.id.in_(product_ids)))).scalars().all()
                if existing_ids:
                    raise ConflictException(f"Products with these IDs already exist: {[p.id for p in existing_ids]}")

            # Check for existing categories
            if all_category_ids:
                categories = (await session.execute(select(Category).filter(Category.id.in_(all_category_ids)))).scalars().all()
                if len(categories) != len(all_category_ids):
                    raise ResourceNotFoundException("One or more categories not found.")

            # Check for existing tags
            if all_tag_ids:
                tags = (await session.execute(select(Tag).filter(Tag.id.in_(all_tag_ids)))).scalars().all()
                if len(tags) != len(all_tag_ids):
                    raise ResourceNotFoundException("One or more tags not found.")

            # Step 2: Create Product ORM objects
            new_products = []
            for data in products_data:
                product_kwargs = data.model_dump(exclude={'category_ids', 'tag_ids'})

                # Clean up ref field (strip whitespace, set to None if empty)
                if 'ref' in product_kwargs and product_kwargs['ref']:
                    product_kwargs['ref'] = product_kwargs['ref'].strip() or None

                new_products.append(Product(**product_kwargs))

            session.add_all(new_products)
            await session.flush()  # Assigns IDs (or uses manual IDs if provided)

            # Step 3: Create associations using bulk inserts
            product_category_associations = []
            product_tag_associations = []
            for i, product in enumerate(new_products):
                data = products_data[i]
                if data.category_ids:
                    for cid in data.category_ids:
                        product_category_associations.append({'product_id': product.id, 'category_id': cid})
                if data.tag_ids:
                    for tid in data.tag_ids:
                        product_tag_associations.append({'product_id': product.id, 'tag_id': tid, 'created_by': 'system'})

            if product_category_associations:
                from src.database.models.associations import product_categories
                await session.execute(product_categories.insert(), product_category_associations)

            if product_tag_associations:
                await session.execute(ProductTag.__table__.insert(), product_tag_associations)

            await session.commit()

            # Step 4: Fetch created products with relationships for the response
            created_ids = [p.id for p in new_products]
            query = select(Product).where(Product.id.in_(created_ids)).options(
                selectinload(Product.categories),
                selectinload(Product.product_tags).selectinload(ProductTag.tag)
            )
            result = await session.execute(query)
            final_products = result.scalars().unique().all()

            pydantic_products = safe_model_validate_list(
                ProductSchema,
                final_products,
                max_depth=3
            )

            cache_invalidation_manager.invalidate_entity(Collections.PRODUCTS)
            return pydantic_products