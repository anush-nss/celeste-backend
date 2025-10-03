from fastapi import APIRouter, Depends, status, Query, HTTPException
from typing import Annotated, List, Union
from src.api.ecommerce_categories.models import (
    CreateEcommerceCategorySchema,
    UpdateEcommerceCategorySchema,
    EcommerceCategorySchema,
)
from src.api.ecommerce_categories.service import EcommerceCategoryService
from src.dependencies.auth import RoleChecker
from src.config.constants import UserRole
from src.shared.exceptions import ResourceNotFoundException
from src.shared.responses import success_response

ecommerce_categories_router = APIRouter(prefix="/ecommerce-categories", tags=["Ecommerce Categories"])
ecommerce_category_service = EcommerceCategoryService()


@ecommerce_categories_router.get(
    "/",
    summary="Get all ecommerce categories",
    response_model=List[EcommerceCategorySchema],
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def get_all_ecommerce_categories(include_subcategories: bool = Query(True, description="Whether to include subcategories in the response")):
    categories = await ecommerce_category_service.get_all_categories(include_subcategories=include_subcategories)
    return success_response([c.model_dump(mode="json") for c in categories])


@ecommerce_categories_router.get(
    "/{id}",
    summary="Get an ecommerce category by ID",
    response_model=EcommerceCategorySchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def get_ecommerce_category_by_id(id: int):
    category = await ecommerce_category_service.get_category_by_id(id)
    if not category:
        raise ResourceNotFoundException(detail=f"Ecommerce category with ID {id} not found")
    return success_response(category.model_dump(mode="json"))


@ecommerce_categories_router.post(
    "/",
    summary="Create one or more new ecommerce categories",
    response_model=Union[EcommerceCategorySchema, List[EcommerceCategorySchema]],
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(
            RoleChecker(
                [UserRole.ADMIN],
            )
        )
    ],
)
async def create_ecommerce_categories(payload: Union[CreateEcommerceCategorySchema, List[CreateEcommerceCategorySchema]]):
    is_list = isinstance(payload, list)
    categories_to_create = payload if is_list else [payload]

    if not categories_to_create:
        raise HTTPException(status_code=400, detail="Request body cannot be an empty list.")

    created_categories = await ecommerce_category_service.create_categories(categories_to_create)

    if is_list:
        return success_response(
            [c.model_dump(mode="json") for c in created_categories], status_code=status.HTTP_201_CREATED
        )
    else:
        return success_response(
            created_categories[0].model_dump(mode="json"), status_code=status.HTTP_201_CREATED
        )


@ecommerce_categories_router.put(
    "/{id}",
    summary="Update an ecommerce category",
    response_model=EcommerceCategorySchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_ecommerce_category(id: int, category_data: UpdateEcommerceCategorySchema):
    updated_category = await ecommerce_category_service.update_category(id, category_data)
    if not updated_category:
        raise ResourceNotFoundException(detail=f"Ecommerce category with ID {id} not found")
    return success_response(updated_category.model_dump(mode="json"))


@ecommerce_categories_router.delete(
    "/{id}",
    summary="Delete an ecommerce category",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def delete_ecommerce_category(id: int):
    if not await ecommerce_category_service.delete_category(id):
        raise ResourceNotFoundException(detail=f"Ecommerce category with ID {id} not found")
    return success_response({"id": id, "message": "Ecommerce category deleted successfully"})