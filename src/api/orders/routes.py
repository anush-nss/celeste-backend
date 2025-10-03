from typing import Annotated, List

from fastapi import APIRouter, Depends, Request, status

from src.api.auth.models import DecodedToken
from src.api.orders.models import CreateOrderSchema, OrderSchema, UpdateOrderSchema
from src.api.orders.service import OrderService
from src.config.constants import UserRole
from src.dependencies.auth import RoleChecker, get_current_user
from src.shared.exceptions import ForbiddenException, ResourceNotFoundException
from src.shared.responses import success_response

orders_router = APIRouter(prefix="/orders", tags=["Orders"])
order_service = OrderService()


@orders_router.get("/", summary="Retrieve orders", response_model=List[OrderSchema])
async def get_orders(current_user: DecodedToken = Depends(get_current_user)):
    if current_user.role == UserRole.ADMIN:
        orders = await order_service.get_all_orders()
    else:
        orders = await order_service.get_all_orders(user_id=current_user.uid)
    return success_response([order.model_dump(mode="json") for order in orders])


@orders_router.get(
    "/{order_id}", summary="Retrieve a specific order", response_model=OrderSchema
)
async def get_order_by_id(
    order_id: int, current_user: DecodedToken = Depends(get_current_user)
):
    order = await order_service.get_order_by_id(order_id)
    if not order:
        raise ResourceNotFoundException(detail=f"Order with ID {order_id} not found")

    if current_user.role != UserRole.ADMIN and order.user_id != current_user.uid:
        raise ForbiddenException("You do not have permission to access this order.")

    return success_response(order.model_dump(mode="json"))


@orders_router.post(
    "/",
    summary="Create a new order (Admin only)",
    response_model=OrderSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create__order(
    order_data: CreateOrderSchema,
    current_user: DecodedToken = Depends(get_current_user),
):
    new_order = await order_service.create_order(order_data, current_user.uid)
    return success_response(
        new_order.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


@orders_router.put(
    "/{order_id}/status",
    summary="Update an order status",
    response_model=OrderSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def update_order_status(order_id: int, order_data: UpdateOrderSchema):
    updated_order = await order_service.update_order_status(order_id, order_data)
    return success_response(updated_order.model_dump(mode="json"))


@orders_router.post(
    "/payment/callback",
    summary="Handle payment gateway callback",
    status_code=status.HTTP_200_OK,
)
async def payment_callback(request: Request):
    """Handle payment gateway callback (webhook)"""

    # Get callback data from request body
    callback_data = await request.json()

    # Process callback through order service
    result = await order_service.process_payment_callback(callback_data)

    if result["status"] == "success":
        return success_response(result)
    else:
        return success_response(result, status_code=400)


@orders_router.post(
    "/{order_id}/payment/verify",
    summary="Verify payment status",
    dependencies=[Depends(get_current_user)],
)
async def verify_payment(
    order_id: int,
    payment_reference: str,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    """Verify payment status for an order"""

    # Check if user owns the order or is admin
    order = await order_service.get_order_by_id(order_id)
    if not order:
        raise ResourceNotFoundException(detail=f"Order with ID {order_id} not found")

    if current_user.role != UserRole.ADMIN and order.user_id != current_user.uid:
        raise ForbiddenException("You do not have permission to verify this payment")

    # Verify payment with gateway
    verification_result = await order_service.payment_service.verify_payment(
        payment_reference, order_id
    )

    return success_response(verification_result)
