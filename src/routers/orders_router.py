from fastapi import APIRouter, Depends, status, HTTPException
from typing import Annotated, List
from src.models.order_models import OrderSchema, CreateOrderSchema, UpdateOrderSchema
from src.services.order_service import OrderService
from src.auth.dependencies import get_current_user, RoleChecker
from src.shared.constants import UserRole
from src.core.exceptions import ResourceNotFoundException, ForbiddenException
from src.core.responses import success_response

orders_router = APIRouter(prefix="/orders", tags=["Orders"])
order_service = OrderService()

@orders_router.get("/", summary="Retrieve orders", response_model=List[OrderSchema])
async def get_orders(current_user: Annotated[dict, Depends(get_current_user)]):
    if current_user.get("role") == UserRole.ADMIN.value:
        orders = await order_service.get_all_orders() # Admins see all orders
    else:
        user_id = current_user.get("uid")
        if not user_id:
            raise HTTPException(status_code=400, detail="User ID not found in token")
        orders = await order_service.get_all_orders(user_id=user_id) # Customers see only their own
    return success_response([o.model_dump() for o in orders])

@orders_router.get("/{id}", summary="Retrieve a specific order", response_model=OrderSchema)
async def get_order_by_id(id: str, current_user: Annotated[dict, Depends(get_current_user)]):
    order = await order_service.get_order_by_id(id)
    if not order:
        raise ResourceNotFoundException(detail=f"Order with ID {id} not found")
    
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
    
    if current_user.get("role") != UserRole.ADMIN.value and order.userId != user_id:
        raise ForbiddenException("You do not have permission to access this order.")
    
    return success_response(order.model_dump())

@orders_router.post("/", summary="Create a new order", response_model=OrderSchema, status_code=status.HTTP_201_CREATED)
async def create_order(order_data: CreateOrderSchema, current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
    new_order = await order_service.create_order(order_data, user_id)
    return success_response(new_order.model_dump(), status_code=status.HTTP_201_CREATED)

@orders_router.put("/{id}", summary="Update an order status", response_model=OrderSchema, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def update_order(id: str, order_data: UpdateOrderSchema):
    updated_order = await order_service.update_order(id, order_data)
    if not updated_order:
        raise ResourceNotFoundException(detail=f"Order with ID {id} not found")
    return success_response(updated_order.model_dump())

@orders_router.delete("/{id}", summary="Delete an order", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def delete_order(id: str):
    if not await order_service.delete_order(id):
        raise ResourceNotFoundException(detail=f"Order with ID {id} not found")
    return success_response({"id": id, "message": "Order deleted successfully"})
