from typing import List, Union

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.categories.models import (
    CategorySchema,
    CreateCategorySchema,
    UpdateCategorySchema,
)
from src.api.categories.service import CategoryService
from src.config.constants import UserRole
from src.dependencies.auth import RoleChecker
from src.shared.exceptions import ResourceNotFoundException
from src.shared.responses import success_response

categories_router = APIRouter(prefix="/categories", tags=["Categories"])
category_service = CategoryService()


@categories_router.get(
    "/",
    summary="Get categories with flexible filtering",
    response_model=List[CategorySchema],
)
async def get_all_categories(
    include_subcategories: bool = Query(
        True, description="Whether to include subcategories in the response"
    ),
    parent_only: bool = Query(
        False, description="Get only parent categories (no parent)"
    ),
    parent_id: int = Query(None, description="Get subcategories of specific parent ID"),
    subcategories_only: bool = Query(
        False, description="Get only subcategories (have parent)"
    ),
):
    categories = await category_service.get_all_categories(
        include_subcategories=include_subcategories,
        parent_only=parent_only,
        parent_id=parent_id,
        subcategories_only=subcategories_only,
    )
    return success_response([c.model_dump(mode="json") for c in categories])


@categories_router.get(
    "/{id}", summary="Get a category by ID", response_model=CategorySchema
)
async def get_category_by_id(id: int):  # Changed id type to int
    category = await category_service.get_category_by_id(id)
    if not category:
        raise ResourceNotFoundException(detail=f"Category with ID {id} not found")
    return success_response(category.model_dump(mode="json"))


@categories_router.post(
    "/",
    summary="Create one or more new categories",
    response_model=Union[CategorySchema, List[CategorySchema]],
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            RoleChecker(
                [UserRole.ADMIN],
            )
        )
    ],
)
async def create_categories(
    payload: Union[CreateCategorySchema, List[CreateCategorySchema]],
):
    is_list = isinstance(payload, list)
    categories_to_create = payload if is_list else [payload]

    if not categories_to_create:
        raise HTTPException(
            status_code=400, detail="Request body cannot be an empty list."
        )

    created_categories = await category_service.create_categories(categories_to_create)

    if is_list:
        return success_response(
            [c.model_dump(mode="json") for c in created_categories],
            status_code=status.HTTP_201_CREATED,
        )
    else:
        return success_response(
            created_categories[0].model_dump(mode="json"),
            status_code=status.HTTP_201_CREATED,
        )


@categories_router.put(
    "/{id}",
    summary="Update a category",
    response_model=CategorySchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_category(
    id: int, category_data: UpdateCategorySchema
):  # Changed id type to int
    updated_category = await category_service.update_category(id, category_data)
    if not updated_category:
        raise ResourceNotFoundException(detail=f"Category with ID {id} not found")
    return success_response(updated_category.model_dump(mode="json"))


@categories_router.delete(
    "/{id}",
    summary="Delete a category",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_category(id: int):  # Changed id type to int
    if not await category_service.delete_category(id):
        raise ResourceNotFoundException(detail=f"Category with ID {id} not found")
    return success_response({"id": id, "message": "Category deleted successfully"})
