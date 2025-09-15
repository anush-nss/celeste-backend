from typing import List, Optional
from sqlalchemy.future import select
from sqlalchemy.orm import Session
from src.database.connection import AsyncSessionLocal
from src.database.models.product import Tag  # Import the existing Tag model
from src.api.tags.models import CreateTagSchema, UpdateTagSchema
from src.shared.exceptions import ResourceNotFoundException, ConflictException
from sqlalchemy.exc import IntegrityError
import re


class TagService:
    """Generic tag service for any entity type"""

    def __init__(self, entity_type: str):
        self.entity_type = entity_type  # e.g., "product", "store"

    def _generate_slug(self, name: str, tag_type_suffix: Optional[str] = None) -> str:
        """Generate URL-friendly slug with format: {entity}-{type_suffix}-{name}"""
        # Clean the name part
        name_slug = re.sub(r'[^\w\s-]', '', name.lower())
        name_slug = re.sub(r'[-\s]+', '-', name_slug)
        name_slug = name_slug.strip('-')

        # Build the full slug
        if tag_type_suffix:
            # Clean the type suffix
            suffix_slug = re.sub(r'[^\w\s-]', '', tag_type_suffix.lower())
            suffix_slug = re.sub(r'[-\s]+', '-', suffix_slug)
            suffix_slug = suffix_slug.strip('-')

            return f"{self.entity_type}-{suffix_slug}-{name_slug}"
        else:
            return f"{self.entity_type}-{name_slug}"

    async def create_tag(self, tag_data: CreateTagSchema) -> Tag:
        """Create a new tag with entity type prefix"""
        async with AsyncSessionLocal() as session:
            # Generate slug if not provided (using the new format: entity-suffix-name)
            slug = tag_data.slug or self._generate_slug(tag_data.name, tag_data.tag_type)

            # Ensure slug is unique
            existing_tag = await session.execute(
                select(Tag).filter(Tag.slug == slug)
            )
            if existing_tag.scalars().first():
                raise ConflictException(detail=f"Tag with slug '{slug}' already exists")

            # Use tag_type from the schema, prefixed with entity type
            tag_type = f"{self.entity_type}_{tag_data.tag_type}" if tag_data.tag_type else self.entity_type

            new_tag = Tag(
                tag_type=tag_type,
                name=tag_data.name,
                slug=slug,
                description=tag_data.description
            )

            try:
                session.add(new_tag)
                await session.commit()
                await session.refresh(new_tag)
                return new_tag
            except IntegrityError as e:
                await session.rollback()
                raise ConflictException(detail="Tag creation failed due to constraint violation")

    async def create_tags(self, tags_data: list[CreateTagSchema]) -> list[Tag]:
        """Create multiple new tags with entity type prefix"""
        async with AsyncSessionLocal() as session:
            new_tags = []
            for tag_data in tags_data:
                # Generate slug if not provided (using the new format: entity-suffix-name)
                slug = tag_data.slug or self._generate_slug(tag_data.name, tag_data.tag_type)

                # Ensure slug is unique
                existing_tag = await session.execute(
                    select(Tag).filter(Tag.slug == slug)
                )
                if existing_tag.scalars().first():
                    raise ConflictException(detail=f"Tag with slug '{slug}' already exists")

                # Use tag_type from the schema, prefixed with entity type
                tag_type = f"{self.entity_type}_{tag_data.tag_type}" if tag_data.tag_type else self.entity_type

                new_tag = Tag(
                    tag_type=tag_type,
                    name=tag_data.name,
                    slug=slug,
                    description=tag_data.description
                )
                new_tags.append(new_tag)

            try:
                session.add_all(new_tags)
                await session.commit()
                for tag in new_tags:
                    await session.refresh(tag)
                return new_tags
            except IntegrityError as e:
                await session.rollback()
                raise ConflictException(detail="Tag creation failed due to constraint violation")

    async def get_tags_by_type(self, is_active: Optional[bool] = True, tag_type_suffix: Optional[str] = None) -> List[Tag]:
        """Get all tags for this entity type, optionally filtered by tag type suffix"""
        async with AsyncSessionLocal() as session:
            if tag_type_suffix:
                # Filter by specific tag type like "product_color"
                tag_type = f"{self.entity_type}_{tag_type_suffix}"
                query = select(Tag).filter(Tag.tag_type == tag_type)
            else:
                # Get all tags starting with entity type prefix
                query = select(Tag).filter(Tag.tag_type.like(f"{self.entity_type}_%"))

            if is_active is not None:
                query = query.filter(Tag.is_active == is_active)

            query = query.order_by(Tag.name)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_tag_by_id(self, tag_id: int) -> Optional[Tag]:
        """Get tag by ID if it matches this entity type"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tag).filter(
                    Tag.id == tag_id,
                    Tag.tag_type.like(f"{self.entity_type}_%")
                )
            )
            return result.scalars().first()

    async def get_tag_by_slug(self, slug: str) -> Optional[Tag]:
        """Get tag by slug if it matches this entity type"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tag).filter(
                    Tag.slug == slug,
                    Tag.tag_type.like(f"{self.entity_type}_%")
                )
            )
            return result.scalars().first()

    async def update_tag(self, tag_id: int, tag_data: UpdateTagSchema) -> Optional[Tag]:
        """Update an existing tag"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tag).filter(
                    Tag.id == tag_id,
                    Tag.tag_type.like(f"{self.entity_type}_%")
                )
            )
            tag = result.scalars().first()

            if not tag:
                return None

            update_dict = tag_data.model_dump(exclude_unset=True)
            # Handle tag_type update with prefix
            if 'tag_type' in update_dict:
                update_dict['tag_type'] = f"{self.entity_type}_{update_dict['tag_type']}"

            for field, value in update_dict.items():
                setattr(tag, field, value)

            try:
                await session.commit()
                await session.refresh(tag)
                return tag
            except IntegrityError:
                await session.rollback()
                raise ConflictException(detail="Tag update failed due to constraint violation")

    async def deactivate_tag(self, tag_id: int) -> bool:
        """Soft delete a tag by setting is_active to False"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tag).filter(
                    Tag.id == tag_id,
                    Tag.tag_type.like(f"{self.entity_type}_%")
                )
            )
            tag = result.scalars().first()

            if not tag:
                return False

            tag.is_active = False
            await session.commit()
            return True

    async def hard_delete_tag(self, tag_id: int) -> bool:
        """Permanently delete a tag from the database"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Tag).filter(
                    Tag.id == tag_id,
                    Tag.tag_type.like(f"{self.entity_type}_%")
                )
            )
            tag = result.scalars().first()

            if not tag:
                return False

            await session.delete(tag)
            await session.commit()
            return True

    async def get_all_tag_types(self) -> List[str]:
        """Get all unique tag types for this entity"""
        async with AsyncSessionLocal() as session:
            from sqlalchemy import distinct
            result = await session.execute(
                select(distinct(Tag.tag_type))
                .filter(Tag.is_active == True)
                .filter(Tag.tag_type.like(f"{self.entity_type}_%"))
                .order_by(Tag.tag_type)
            )
            return list(result.scalars().all())

    async def assign_tag_to_entity(self, entity_id: int, tag_id: int, value: Optional[str] = None):
        """Assign a tag to an entity (product, store, etc.)"""
        async with AsyncSessionLocal() as session:
            try:
                if self.entity_type == "product":
                    from src.database.models.product import ProductTag
                    entity_tag = ProductTag(
                        product_id=entity_id,
                        tag_id=tag_id,
                        value=value,
                        created_by="system"
                    )
                elif self.entity_type == "store":
                    from src.database.models.store_tag import StoreTag
                    entity_tag = StoreTag(
                        store_id=entity_id,
                        tag_id=tag_id,
                        value=value,
                        created_by="system"
                    )
                else:
                    raise ValueError(f"Unsupported entity type: {self.entity_type}")

                session.add(entity_tag)
                await session.commit()
            except IntegrityError as e:
                await session.rollback()
                error_detail = str(e.orig)
                if f"{self.entity_type}_id" in error_detail and "is not present" in error_detail:
                    raise ResourceNotFoundException(detail=f"{self.entity_type.capitalize()} with ID {entity_id} not found")
                elif "tag_id" in error_detail and "is not present" in error_detail:
                    raise ResourceNotFoundException(detail=f"Tag with ID {tag_id} not found")
                elif "duplicate key" in error_detail:
                    raise ConflictException(detail=f"{self.entity_type.capitalize()} {entity_id} already has tag {tag_id}")
                else:
                    raise

    async def remove_tag_from_entity(self, entity_id: int, tag_id: int) -> bool:
        """Remove a tag from an entity"""
        async with AsyncSessionLocal() as session:
            try:
                if self.entity_type == "product":
                    from src.database.models.product import ProductTag
                    result = await session.execute(
                        select(ProductTag).filter(
                            ProductTag.product_id == entity_id,
                            ProductTag.tag_id == tag_id
                        )
                    )
                    entity_tag = result.scalars().first()
                elif self.entity_type == "store":
                    from src.database.models.store_tag import StoreTag
                    result = await session.execute(
                        select(StoreTag).filter(
                            StoreTag.store_id == entity_id,
                            StoreTag.tag_id == tag_id
                        )
                    )
                    entity_tag = result.scalars().first()
                else:
                    raise ValueError(f"Unsupported entity type: {self.entity_type}")

                if not entity_tag:
                    return False

                await session.delete(entity_tag)
                await session.commit()
                return True
            except IntegrityError as e:
                await session.rollback()
                raise