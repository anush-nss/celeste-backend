from typing import Annotated, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import select

from src.api.auth.models import DecodedToken
from src.api.orders.models import (
    CreateOrderSchema,
    OrderSchema,
    PaginatedOrdersResponse,
    PaymentCallbackSchema,
    UpdateOrderSchema,
    OrderUpdateResponse,
)
from src.api.orders.service import OrderService
from src.config.constants import OdooSyncStatus, OrderStatus, UserRole
from src.database.connection import AsyncSessionLocal
from src.database.models.order import Order
from src.dependencies.auth import RoleChecker, get_current_user
from src.integrations.odoo.order_sync import OdooOrderSync
from src.shared.exceptions import ForbiddenException, ResourceNotFoundException
from src.shared.responses import success_response

orders_router = APIRouter(prefix="/orders", tags=["Orders"])
order_service = OrderService()


@orders_router.get(
    "/",
    summary="Retrieve orders",
    response_model=PaginatedOrdersResponse,
)
async def get_orders(
    current_user: DecodedToken = Depends(get_current_user),
    cart_id: Optional[List[int]] = Query(
        None, description="Filter orders by source cart ID(s)"
    ),
    status: Optional[List[OrderStatus]] = Query(
        None, description="Filter orders by status (e.g., pending, confirmed)"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    include_products: bool = Query(
        False, description="Include full product details in order items"
    ),
    include_stores: bool = Query(False, description="Include full store details"),
    include_addresses: bool = Query(
        False, description="Include full delivery address details"
    ),
    include_rider: bool = Query(
        True, description="Include assigned rider details (if any)"
    ),
):
    """
    Retrieve orders with optional population of related data and pagination.
    """
    if current_user.role == UserRole.ADMIN:
        result = await order_service.get_orders_paginated(
            cart_ids=cart_id,
            status=[s.value for s in status] if status else None,
            page=page,
            limit=limit,
            include_products=include_products,
            include_stores=include_stores,
            include_addresses=include_addresses,
            include_rider=include_rider,
        )
    else:
        result = await order_service.get_orders_paginated(
            user_id=current_user.uid,
            cart_ids=cart_id,
            status=[s.value for s in status] if status else None,
            page=page,
            limit=limit,
            include_products=include_products,
            include_stores=include_stores,
            include_addresses=include_addresses,
            include_rider=include_rider,
        )

    # Manually dump models for JSON compatibility
    orders_data = [order.model_dump(mode="json") for order in result["orders"]]

    return success_response({"orders": orders_data, "pagination": result["pagination"]})


@orders_router.get(
    "/{order_id}", summary="Retrieve a specific order", response_model=OrderSchema
)
async def get_order_by_id(
    order_id: int,
    current_user: DecodedToken = Depends(get_current_user),
    include_products: bool = Query(
        True, description="Include full product details in order items"
    ),
    include_stores: bool = Query(True, description="Include full store details"),
    include_addresses: bool = Query(
        True, description="Include full delivery address details"
    ),
):
    """
    Retrieve a specific order with optional population of related data.

    By default, products, stores, and addresses are fully populated.
    Set query parameters to False to exclude them for faster responses.
    """
    order = await order_service.get_order_by_id(
        order_id,
        include_products=include_products,
        include_stores=include_stores,
        include_addresses=include_addresses,
    )
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
    new_order = await order_service.create_order(
        order_data, current_user.uid, platform=order_data.platform
    )
    return success_response(
        new_order.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


@orders_router.put(
    "/{order_id}/status",
    summary="Update an order status",
    response_model=OrderUpdateResponse,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.RIDER]))],
)
async def update_order_status(
    order_id: int,
    order_data: UpdateOrderSchema,
    current_user: DecodedToken = Depends(get_current_user),
):
    updated_order = await order_service.update_order_status(
        order_id,
        order_data,
        current_user={"role": current_user.role, "uid": current_user.uid},
    )
    return success_response(
        updated_order.model_dump(), message="Order status updated successfully"
    )


@orders_router.post(
    "/{order_id}/assign/{rider_id}",
    summary="Assign a rider to an order (Admin only)",
    description="Assigns a rider to a PACKED order.",
    response_model=OrderSchema,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def assign_rider_to_order(order_id: int, rider_id: int):
    updated_order = await order_service.assign_rider(order_id, rider_id)
    return success_response(updated_order.model_dump(mode="json"))


@orders_router.delete(
    "/{order_id}/assign",
    summary="Remove rider assignment from an order (Admin only)",
    description="Unassigns a rider from a PACKED order.",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def unassign_rider_from_order(order_id: int):
    result = await order_service.unassign_rider(order_id)
    return success_response(result)


@orders_router.post(
    "/payment/callback",
    summary="Handle payment gateway callback",
    status_code=status.HTTP_200_OK,
)
async def payment_callback(
    callback_data: PaymentCallbackSchema, background_tasks: BackgroundTasks
):
    """Handle payment gateway callback (webhook)"""

    # Process callback through order service (with background tasks for Odoo sync)
    result = await order_service.process_payment_callback(
        callback_data.model_dump(), background_tasks
    )

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


@orders_router.get(
    "/odoo/failed-syncs",
    summary="List orders with failed or pending Odoo sync (Admin only)",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def get_failed_odoo_syncs(limit: int = 50, include_pending: bool = False):
    """
    Get list of orders where Odoo sync failed or is pending.

    Returns orders with sync status FAILED, and optionally PENDING.
    Useful for monitoring and debugging Odoo sync issues.

    - **limit**: Maximum number of orders to return (default: 50)
    - **include_pending**: Whether to include orders with PENDING sync status (default: False)
    """
    try:
        async with AsyncSessionLocal() as session:
            statuses_to_fetch = [OdooSyncStatus.FAILED]
            if include_pending:
                statuses_to_fetch.append(OdooSyncStatus.PENDING)

            # Query orders with failed or pending Odoo sync
            query = (
                select(Order)
                .where(Order.odoo_sync_status.in_(statuses_to_fetch))
                .order_by(
                    Order.odoo_last_retry_at.desc().nulls_last(),
                    Order.created_at.desc(),
                )
                .limit(limit)
            )

            result = await session.execute(query)
            orders = result.scalars().all()

            # Format response
            failed_syncs = []
            for order in orders:
                failed_syncs.append(
                    {
                        "order_id": order.id,
                        "user_id": order.user_id,
                        "total_amount": float(order.total_amount),
                        "status": order.status,
                        "created_at": order.created_at.isoformat(),
                        "odoo_sync_status": order.odoo_sync_status,
                        "odoo_sync_error": order.odoo_sync_error,
                        "odoo_last_retry_at": (
                            order.odoo_last_retry_at.isoformat()
                            if order.odoo_last_retry_at
                            else None
                        ),
                    }
                )

            return success_response(
                {
                    "count": len(failed_syncs),
                    "failed_syncs": failed_syncs,
                }
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve failed Odoo syncs: {str(e)}",
        )


@orders_router.post(
    "/{order_id}/odoo/retry-sync",
    summary="Retry Odoo sync for a specific order (Admin only)",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def retry_odoo_sync(order_id: int, background_tasks: BackgroundTasks):
    """
    Manually retry Odoo sync for an order that previously failed.

    This endpoint will:
    1. Verify the order exists and is confirmed
    2. Attempt to sync the order to Odoo again
    3. Update the order's sync status based on the result

    Useful for recovering from transient errors or after fixing Odoo configuration issues.

    - **order_id**: ID of the order to retry sync for
    """
    try:
        # Verify order exists and is confirmed
        async with AsyncSessionLocal() as session:
            query = select(Order).where(Order.id == order_id)
            result = await session.execute(query)
            order = result.scalar_one_or_none()

            if not order:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Order {order_id} not found",
                )

            if order.status != "confirmed":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Order {order_id} is not confirmed. Only confirmed orders can be synced to Odoo.",
                )

        # Attempt sync in the background
        odoo_sync = OdooOrderSync()
        background_tasks.add_task(odoo_sync.sync_order_to_odoo, order_id)

        return success_response(
            {
                "message": f"Odoo sync for order {order_id} has been queued.",
                "order_id": order_id,
                "sync_status": "queued",
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry Odoo sync: {str(e)}",
        )
