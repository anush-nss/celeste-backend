from fastapi import APIRouter, Depends, status, Query
from typing import Annotated, List
from src.api.categories.models import (
    CategorySchema,
    CreateCategorySchema,
    UpdateCategorySchema,
    CategoryQuerySchema,
)
from src.api.categories.service import CategoryService
from src.dependencies.auth import RoleChecker
from src.config.constants import UserRole
from src.shared.exceptions import ResourceNotFoundException
from src.shared.responses import success_response

categories_router = APIRouter(prefix="/categories", tags=["Categories"])
category_service = CategoryService()


@categories_router.get(
    "/", summary="Get all categories", response_model=List[CategorySchema]
)
async def get_all_categories(query: CategoryQuerySchema):
    if query is None:
        query = CategoryQuerySchema()
    categories = await category_service.get_all_categories(include_subcategories=query.include_subcategories)
    return success_response([c.model_dump(mode="json") for c in categories])


@categories_router.get(
    "/{id}", summary="Get a category by ID", response_model=CategorySchema
)
async def get_category_by_id(id: int): # Changed id type to int
    category = await category_service.get_category_by_id(id)
    if not category:
        raise ResourceNotFoundException(detail=f"Category with ID {id} not found")
    return success_response(category.model_dump(mode="json"))


@categories_router.post(
    "/",
    summary="Create a new category",
    response_model=CategorySchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            RoleChecker(
                [UserRole.ADMIN],
            )
        )
    ],
)
async def create_category(category_data: CreateCategorySchema):
    new_category = await category_service.create_category(category_data)
    return success_response(
        new_category.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


@categories_router.put(
    "/{id}",
    summary="Update a category",
    response_model=CategorySchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_category(id: int, category_data: UpdateCategorySchema): # Changed id type to int
    updated_category = await category_service.update_category(id, category_data)
    if not updated_category:
        raise ResourceNotFoundException(detail=f"Category with ID {id} not found")
    return success_response(updated_category.model_dump(mode="json"))


@categories_router.delete(
    "/{id}",
    summary="Delete a category",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_category(id: int): # Changed id type to int
    if not await category_service.delete_category(id):
        raise ResourceNotFoundException(detail=f"Category with ID {id} not found")
    return success_response({"id": id, "message": "Category deleted successfully"})