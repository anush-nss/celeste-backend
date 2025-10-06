from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status

from src.api.tags.models import CreateTagSchema, TagSchema, UpdateTagSchema
from src.api.tags.service import TagService
from src.config.constants import UserRole
from src.dependencies.auth import RoleChecker
from src.shared.exceptions import ResourceNotFoundException, ValidationException
from src.shared.responses import success_response

tags_router = APIRouter(prefix="/tags", tags=["Tags"])


# We'll use a general TagService for all operations
def get_tag_service():
    return TagService(entity_type="")  # Empty entity type for general operations


@tags_router.post(
    "/",
    summary="Create a new tag",
    response_model=TagSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_tag(tag_data: CreateTagSchema):
    """
    Create a new tag (Admin only).

    Tag type must follow the format: {entity}_{suffix} (e.g., 'product_color', 'store_features')
    """
    # Validate tag_type format
    if not tag_data.tag_type or "_" not in tag_data.tag_type:
        raise ValidationException(
            detail="Tag type must follow format: {entity}_{suffix} (e.g., 'product_color', 'store_features')"
        )

    parts = tag_data.tag_type.split("_")
    if len(parts) < 2:
        raise ValidationException(
            detail="Tag type must follow format: {entity}_{suffix} (e.g., 'product_color', 'store_features')"
        )

    entity_type = parts[0]
    suffix = "_".join(
        parts[1:]
    )  # Handle multi-part suffixes like 'store_opening_hours'

    # Validate entity type
    valid_entities = ["product", "store"]
    if entity_type not in valid_entities:
        raise ValidationException(
            detail=f"Entity type must be one of: {valid_entities}"
        )

    # Use entity-specific service to create tag
    tag_service = TagService(entity_type=entity_type)

    # Create tag data with just the suffix (service will add prefix)
    tag_creation_data = CreateTagSchema(
        tag_type=suffix,
        name=tag_data.name,
        slug=tag_data.slug,
        description=tag_data.description,
    )

    new_tag = await tag_service.create_tag(tag_creation_data)
    return success_response(
        TagSchema.model_validate(new_tag).model_dump(mode="json"),
        status_code=status.HTTP_201_CREATED,
    )


@tags_router.get(
    "/",
    summary="Get all tags",
    response_model=List[TagSchema],
)
async def get_all_tags(
    entity_type: Optional[str] = Query(
        None, description="Filter by entity type (product, store)"
    ),
    tag_type: Optional[str] = Query(
        None, description="Filter by specific tag type (e.g., 'product_color')"
    ),
    is_active: Optional[bool] = Query(True, description="Filter by active status"),
):
    """Get all tags with optional filtering."""
    if tag_type:
        # If specific tag_type provided, validate format and use appropriate service
        if "_" not in tag_type:
            raise ValidationException(
                detail="Tag type must follow format: {entity}_{suffix} (e.g., 'product_color', 'store_features')"
            )

        entity = tag_type.split("_")[0]
        suffix = "_".join(tag_type.split("_")[1:])

        tag_service = TagService(entity_type=entity)
        tags = await tag_service.get_tags_by_type(is_active, suffix)
    elif entity_type:
        # If entity_type provided, get all tags for that entity
        tag_service = TagService(entity_type=entity_type)
        tags = await tag_service.get_tags_by_type(is_active)
    else:
        # Get all tags by querying each entity type
        all_tags = []
        for entity in ["product", "store"]:
            tag_service = TagService(entity_type=entity)
            entity_tags = await tag_service.get_tags_by_type(is_active)
            all_tags.extend(entity_tags)
        tags = all_tags

    return success_response(
        [TagSchema.model_validate(tag).model_dump(mode="json") for tag in tags]
    )


@tags_router.get(
    "/types",
    summary="Get all tag types",
    response_model=List[str],
)
async def get_all_tag_types():
    """Get all unique tag types across all entities."""
    all_types = []
    for entity in ["product", "store"]:
        tag_service = TagService(entity_type=entity)
        entity_types = await tag_service.get_all_tag_types()
        all_types.extend(entity_types)

    # Remove duplicates and sort
    unique_types = sorted(list(set(all_types)))

    return success_response(unique_types)


@tags_router.get(
    "/{tag_id}",
    summary="Get tag by ID",
    response_model=TagSchema,
)
async def get_tag_by_id(tag_id: int):
    """Get a specific tag by ID."""
    # Try to find the tag in any entity type
    tag = None
    for entity in ["product", "store"]:
        tag_service = TagService(entity_type=entity)
        tag = await tag_service.get_tag_by_id(tag_id)
        if tag:
            break

    if not tag:
        raise ResourceNotFoundException(detail=f"Tag with ID {tag_id} not found")

    return success_response(TagSchema.model_validate(tag).model_dump(mode="json"))


@tags_router.put(
    "/{tag_id}",
    summary="Update a tag",
    response_model=TagSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_tag(tag_id: int, tag_data: UpdateTagSchema):
    """Update an existing tag (Admin only)."""
    # Find which entity this tag belongs to
    tag = None
    tag_service = None
    for entity in ["product", "store"]:
        service = TagService(entity_type=entity)
        tag = await service.get_tag_by_id(tag_id)
        if tag:
            tag_service = service
            break

    if not tag or not tag_service:
        raise ResourceNotFoundException(detail=f"Tag with ID {tag_id} not found")

    # If tag_type is being updated, validate it matches the entity
    if tag_data.tag_type:
        current_entity = tag.tag_type.split("_")[0]
        if not tag_data.tag_type.startswith(f"{current_entity}_"):
            # Extract just the suffix part
            if "_" in tag_data.tag_type:
                new_suffix = "_".join(tag_data.tag_type.split("_")[1:])
            else:
                new_suffix = tag_data.tag_type

            # Update with just the suffix
            update_data = UpdateTagSchema(
                tag_type=new_suffix,
                name=tag_data.name,
                slug=tag_data.slug,
                description=tag_data.description,
                is_active=tag_data.is_active,
            )
        else:
            update_data = tag_data
    else:
        update_data = tag_data

    updated_tag = await tag_service.update_tag(tag_id, update_data)
    if not updated_tag:
        raise ResourceNotFoundException(detail=f"Tag with ID {tag_id} not found")

    return success_response(
        TagSchema.model_validate(updated_tag).model_dump(mode="json")
    )


@tags_router.delete(
    "/{tag_id}",
    summary="Delete a tag",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_tag(
    tag_id: int,
    hard_delete: bool = Query(
        False, description="Permanently delete the tag (default: soft delete)"
    ),
):
    """Delete a tag - soft delete (deactivate) by default, or hard delete if specified (Admin only)."""
    # Find which entity this tag belongs to
    tag_service = None
    for entity in ["product", "store"]:
        service = TagService(entity_type=entity)
        tag = await service.get_tag_by_id(tag_id)
        if tag:
            tag_service = service
            break

    if not tag_service:
        raise ResourceNotFoundException(detail=f"Tag with ID {tag_id} not found")

    if hard_delete:
        success = await tag_service.hard_delete_tag(tag_id)
        message = "Tag permanently deleted successfully"
    else:
        success = await tag_service.deactivate_tag(tag_id)
        message = "Tag deactivated successfully"

    if not success:
        raise ResourceNotFoundException(detail=f"Tag with ID {tag_id} not found")

    return success_response(
        {"tag_id": tag_id, "message": message, "hard_delete": hard_delete}
    )
