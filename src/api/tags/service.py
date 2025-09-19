from typing import List, Optional, Dict, Any, Union
from sqlalchemy.future import select
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, text
from src.database.connection import AsyncSessionLocal
from src.database.models.product import Tag  # Import the existing Tag model
from src.api.tags.models import CreateTagSchema, UpdateTagSchema
from src.shared.exceptions import ResourceNotFoundException, ConflictException, ValidationException
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

    # Tag filtering functionality
    def parse_tag_filters(self, tags_params: Optional[List[str]]) -> Dict[str, Any]:
        """
        Parse tag filter parameters with flexible syntax:
        - 'organic' -> name:organic (default to name search)
        - 'id:5' -> filter by tag ID
        - 'name:organic' -> filter by tag name
        - 'slug:product-analytic-car' -> filter by tag slug
        - 'type:dietary' -> filter by tag type (maps to product_dietary/store_dietary)
        - 'value:gluten-free' -> filter by tag association value

        Logic: AND within each tags parameter, OR between multiple tags parameters
        """
        if not tags_params:
            return {'conditions': [], 'params': {}, 'needs_joins': False}

        # No hardcoded mappings - build dynamically

        or_conditions = []  # Each element is an AND group
        params = {}
        param_counter = 0

        for tags_param in tags_params:
            if not tags_param or not tags_param.strip():
                continue

            # Split by comma for AND logic within parameter
            filter_strings = [f.strip() for f in tags_param.split(',') if f.strip()]
            if not filter_strings:
                continue

            and_conditions = []  # Conditions for this AND group

            for filter_str in filter_strings:
                condition, filter_params = self._parse_single_tag_filter(
                    filter_str, param_counter
                )
                and_conditions.append(condition)
                params.update(filter_params)
                param_counter += len(filter_params)

            if and_conditions:
                # Join with AND
                and_clause = " AND ".join(and_conditions)
                or_conditions.append(f"({and_clause})")

        return {
            'conditions': or_conditions,  # Will be joined with OR
            'params': params,
            'needs_joins': True
        }

    def _parse_single_tag_filter(self, filter_str: str, param_offset: int) -> tuple[str, Dict[str, Any]]:
        """Parse a single filter string and return SQL condition"""
        table_prefix = "pt" if self.entity_type == "product" else "st"
        tag_alias = "t"

        # Check if it contains ':'
        if ':' not in filter_str:
            # Default to name search
            param_name = f"tag_name_{param_offset}"
            condition = f"{tag_alias}.name = :{param_name}"
            params = {param_name: filter_str}
            return condition, params

        # Parse key:value format
        try:
            filter_key, filter_value = filter_str.split(':', 1)
            filter_key = filter_key.strip().lower()
            filter_value = filter_value.strip()

            if not filter_value:
                raise ValidationException(f"Filter value cannot be empty: {filter_str}")

        except ValueError:
            raise ValidationException(f"Invalid filter format: {filter_str}")

        # Build condition based on filter type
        if filter_key == 'id':
            try:
                tag_id = int(filter_value)
                param_name = f"tag_id_{param_offset}"
                condition = f"{tag_alias}.id = :{param_name}"
                params = {param_name: tag_id}

            except ValueError:
                raise ValidationException(f"Tag ID must be numeric: {filter_value}")

        elif filter_key == 'name':
            param_name = f"tag_name_{param_offset}"
            condition = f"{tag_alias}.name = :{param_name}"
            params = {param_name: filter_value}

        elif filter_key == 'slug':
            param_name = f"tag_slug_{param_offset}"
            condition = f"{tag_alias}.slug = :{param_name}"
            params = {param_name: filter_value}

        elif filter_key == 'type':
            # Build full type name dynamically (e.g., dietary -> product_dietary)
            mapped_type = f"{self.entity_type}_{filter_value.lower()}"
            param_name = f"tag_type_{param_offset}"
            condition = f"{tag_alias}.tag_type = :{param_name}"
            params = {param_name: mapped_type}

        elif filter_key == 'value':
            param_name = f"tag_value_{param_offset}"
            condition = f"{table_prefix}.value = :{param_name}"
            params = {param_name: filter_value}

        else:
            valid_keys = ['id', 'name', 'slug', 'type', 'value']
            raise ValidationException(
                f"Invalid filter key: {filter_key}. Valid keys: {valid_keys}"
            )

        return condition, params

    def build_tag_filter_query_conditions(self, base_conditions: List[str], tag_filter_result: Dict[str, Any]) -> tuple[List[str], Dict[str, Any]]:
        """
        Integrate tag filter conditions into existing query conditions

        Args:
            base_conditions: Existing WHERE conditions
            tag_filter_result: Result from parse_tag_filters()

        Returns:
            Tuple of (updated_conditions, all_params)
        """
        if not tag_filter_result['conditions']:
            return base_conditions, tag_filter_result['params']

        # If we have tag filters, add them as OR conditions
        tag_conditions_str = " OR ".join(tag_filter_result['conditions'])
        tag_filter_condition = f"({tag_conditions_str})"

        updated_conditions = base_conditions + [tag_filter_condition]
        return updated_conditions, tag_filter_result['params']