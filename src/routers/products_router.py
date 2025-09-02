from fastapi import APIRouter, Depends, status, Query
from typing import Annotated, List, Optional
from src.models.product_models import ProductSchema, CreateProductSchema, UpdateProductSchema, ProductQuerySchema
from src.services.product_service import ProductService
from src.auth.dependencies import RoleChecker
from src.shared.constants import UserRole
from src.core.exceptions import ResourceNotFoundException
from src.core.responses import success_response

products_router = APIRouter(prefix="/products", tags=["Products"])
product_service = ProductService()

@products_router.get("/", summary="Get all products", response_model=List[ProductSchema])
async def get_all_products(
    limit: Optional[int] = Query(None, description="Limit the number of products returned"),
    offset: Optional[int] = Query(None, description="Offset for pagination"),
    includeDiscounts: Optional[bool] = Query(None, description="Include discounts for each product"),
    includeInventory: Optional[bool] = Query(None, description="Include inventory for each product"),
    categoryId: Optional[str] = Query(None, description="Filter by category ID"),
    minPrice: Optional[float] = Query(None, description="Filter by minimum price"),
    maxPrice: Optional[float] = Query(None, description="Filter by maximum price"),
    isFeatured: Optional[bool] = Query(None, description="Filter by featured products"),
):
    query_params = ProductQuerySchema(
        limit=limit,
        offset=offset,
        includeDiscounts=includeDiscounts,
        categoryId=categoryId,
        minPrice=minPrice,
        maxPrice=maxPrice,
        isFeatured=isFeatured
    )
    products = await product_service.get_all_products(query_params)
    return success_response([p.model_dump(mode='json') for p in products])

@products_router.get("/{id}", summary="Get a product by ID", response_model=ProductSchema)
async def get_product_by_id(
    id: str,
    includeDiscounts: Optional[bool] = Query(None, description="Include discounts for the product"),
    includeInventory: Optional[bool] = Query(None, description="Include inventory for the product"),
):
    product = await product_service.get_product_by_id(id)
    if not product:
        raise ResourceNotFoundException(detail=f"Product with ID {id} not found")
    # TODO: Implement logic to include discounts and inventory if requested
    return success_response(product.model_dump(mode='json'))

@products_router.post("/", summary="Create a new product", response_model=ProductSchema, status_code=status.HTTP_201_CREATED, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def create_product(product_data: CreateProductSchema):
    new_product = await product_service.create_product(product_data)
    return success_response(new_product.model_dump(mode='json'), status_code=status.HTTP_201_CREATED)

@products_router.put("/{id}", summary="Update a product", response_model=ProductSchema, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def update_product(id: str, product_data: UpdateProductSchema):
    updated_product = await product_service.update_product(id, product_data)
    if not updated_product:
        raise ResourceNotFoundException(detail=f"Product with ID {id} not found")
    return success_response(updated_product.model_dump(mode='json'))

@products_router.delete("/{id}", summary="Delete a product", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def delete_product(id: str):
    if not await product_service.delete_product(id):
        raise ResourceNotFoundException(detail=f"Product with ID {id} not found")
    return success_response({"id": id, "message": "Product deleted successfully"})