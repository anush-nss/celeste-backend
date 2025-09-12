from fastapi import APIRouter, Depends, status, HTTPException, Query
from typing import Annotated, List, Optional
from datetime import datetime

from src.api.users.models import (
    UserSchema,
    CreateUserSchema,
    UpdateUserSchema,
    AddToCartSchema,
    UpdateCartItemSchema,
    AddressSchema,
    UpdateAddressSchema,
    CartItemSchema
)
from src.api.auth.models import DecodedToken
from src.api.users.service import UserService
from src.dependencies.auth import get_current_user, RoleChecker
from src.config.constants import UserRole
from src.shared.exceptions import ResourceNotFoundException, ForbiddenException
from src.shared.responses import success_response

users_router = APIRouter(prefix="/users", tags=["Users"])
user_service = UserService()


@users_router.post(
    "/",
    summary="Create a new user",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))],
)
async def create_user(user_data: CreateUserSchema):
    # This endpoint is public for initial user creation, but Firebase auth register is preferred.
    # For simplicity, we'll generate a dummy UID here if not coming from Firebase auth.
    # In a real app, this might be protected or integrated with Firebase auth more deeply.
    import uuid

    dummy_uid = str(uuid.uuid4())
    new_user = await user_service.create_user(user_data, dummy_uid)
    return success_response(new_user.model_dump(mode="json"), status_code=status.HTTP_201_CREATED)


@users_router.get("/me", summary="Get current user profile")
async def get_user_profile(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
    include_cart: bool = Query(True, description="Include user's cart in the response"),
    include_addresses: bool = Query(True, description="Include user's addresses in the response"),
):
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    user = await user_service.get_user_by_id(user_id, include_cart=include_cart, include_addresses=include_addresses)

    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")
    return success_response(user.model_dump(mode="json"))


@users_router.put("/me", summary="Update current user profile")
async def update_user_profile(
    user_data: UpdateUserSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    print(current_user)
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    # Prevent phone number from being updated
    if user_data.phone is not None:
        del user_data.phone

    updated_data = user_data.model_dump(exclude_unset=True)
    updated_user = await user_service.update_user(user_id, updated_data)
    if not updated_user:
        raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")

    return success_response(updated_user.model_dump(mode="json"))


@users_router.post("/me/cart", summary="Add an item to the user's cart")
async def add_to_cart(
    item: AddToCartSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    cart_item = await user_service.add_to_cart(user_id, item.product_id, item.quantity)
    if not cart_item:
        raise HTTPException(status_code=500, detail="Failed to add item to cart")

    return success_response(cart_item)


@users_router.put("/me/cart/{product_id}", summary="Update an item in the user's cart")
async def update_cart_item(
    product_id: str,
    item: UpdateCartItemSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    cart_item = await user_service.update_cart_item(user_id, product_id, item.quantity)
    if not cart_item:
        raise HTTPException(status_code=500, detail="Failed to update cart item")

    return success_response(cart_item)


@users_router.delete(
    "/me/cart/{product_id}", summary="Remove an item from the user's cart"
)
async def remove_from_cart(
    product_id: str,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
    quantity: Optional[int] = Query(None, ge=1, description="Quantity to remove (if not specified, removes product completely)")
):
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    result = await user_service.remove_from_cart(user_id, product_id, quantity)

    return success_response({
        "userId": user_id,
        "product_id": product_id,
        **result
    })


@users_router.get("/me/cart", summary="Get the user's cart")
async def get_cart(current_user: Annotated[DecodedToken, Depends(get_current_user)]):
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    cart = await user_service.get_cart(user_id)
    return success_response(cart)


# Address Management Endpoints
@users_router.post("/me/addresses", summary="Add a new address for the current user")
async def add_address(
    address_data: AddressSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    new_address = await user_service.add_address(user_id, address_data)
    if not new_address:
        raise HTTPException(status_code=500, detail="Failed to add address")

    return success_response(new_address.model_dump(mode="json"), status_code=status.HTTP_201_CREATED)


@users_router.get("/me/addresses", summary="Get all addresses for the current user")
async def get_addresses(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    addresses = await user_service.get_addresses(user_id)
    return success_response([addr.model_dump(mode="json") for addr in addresses])


@users_router.get("/me/addresses/{address_id}", summary="Get a specific address for the current user")
async def get_address_by_id(
    address_id: int,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    address = await user_service.get_address_by_id(user_id, address_id)
    if not address:
        raise ResourceNotFoundException(detail=f"Address with ID {address_id} not found")

    return success_response(address.model_dump(mode="json"))


@users_router.put("/me/addresses/{address_id}", summary="Update a specific address for the current user")
async def update_address(
    address_id: int,
    address_data: UpdateAddressSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    updated_address = await user_service.update_address(user_id, address_id, address_data)
    if not updated_address:
        raise HTTPException(status_code=500, detail="Failed to update address")

    return success_response(updated_address.model_dump(mode="json"))


@users_router.delete("/me/addresses/{address_id}", summary="Delete a specific address for the current user")
async def delete_address(
    address_id: int,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    success = await user_service.delete_address(user_id, address_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete address")

    return success_response({"message": "Address deleted successfully"})


@users_router.put("/me/addresses/{address_id}/set_default", summary="Set a specific address as default for the current user")
async def set_default_address(
    address_id: int,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    default_address = await user_service.set_default_address(user_id, address_id)
    if not default_address:
        raise HTTPException(status_code=500, detail="Failed to set default address")

    return success_response(default_address.model_dump(mode="json"))