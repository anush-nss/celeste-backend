from decimal import Decimal
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.auth.models import DecodedToken
from src.api.carts.service import CartService
from src.api.interactions.service import InteractionService
from src.api.orders.service import OrderService
from src.api.users.models import (
    AddCartItemSchema,
    AddressCreationSchema,
    AddressResponseSchema,
    AddressWithDeliverySchema,
    CreateCartSchema,
    ShareCartSchema,
    UpdateCartItemQuantitySchema,
    UpdateCartSchema,
    UpdateUserSchema,
    AddFavoriteSchema,
)
from src.api.products.models import EnhancedProductSchema
from src.api.users.service import UserService
from src.dependencies.auth import get_current_user
from src.shared.exceptions import (
    ResourceNotFoundException,
    UnauthorizedException,
    ValidationException,
)
from src.shared.responses import success_response

from src.api.users.checkout_models import (
    CheckoutRequestSchema,
    CheckoutResponse,
    PaymentInfo,
)
from src.api.users.checkout_service import CheckoutService
from src.api.payments.service import PaymentService
from src.api.payments.models import InitiatePaymentSchema

users_router = APIRouter(prefix="/users", tags=["Users"])

user_service = UserService()
order_service = OrderService()
payment_service = PaymentService()
checkout_service = CheckoutService()
interaction_service = InteractionService()


@users_router.get("/me", summary="Get current user profile")
async def get_user_profile(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
    include_addresses: bool = Query(
        True, description="Include user's addresses in the response"
    ),
    include_favorites: bool = Query(
        False, description="Include user's favorites in the response"
    ),
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    user = await user_service.get_user_by_id(
        user_id,
        include_addresses=include_addresses,
        include_favorites=include_favorites,
    )

    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")
    return success_response(user.model_dump(mode="json"))


@users_router.put("/me", summary="Update current user profile")
async def update_user_profile(
    user_data: UpdateUserSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    updated_data = user_data.model_dump(exclude_unset=True)
    if len(updated_data) == 0:
        raise ValidationException(detail="No data provided for update")
    updated_user = await user_service.update_user(user_id, updated_data)
    if not updated_user:
        raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")

    return success_response(updated_user.model_dump(mode="json"))


# Favorites Management Endpoints


@users_router.post(
    "/me/favorites",
    summary="Add a product to user favorites",
    status_code=status.HTTP_201_CREATED,
)
async def add_favorite(
    favorite_data: AddFavoriteSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    product_ids = await user_service.add_favorite(user_id, favorite_data.product_id)

    return success_response(
        {"product_ids": product_ids}, status_code=status.HTTP_201_CREATED
    )


@users_router.delete(
    "/me/favorites/{product_id}",
    summary="Remove a product from user favorites",
)
async def remove_favorite(
    product_id: int,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    product_ids = await user_service.remove_favorite(user_id, product_id)

    return success_response({"product_ids": product_ids})


@users_router.get(
    "/me/favorites",
    summary="Get user favorites",
    response_model=List[EnhancedProductSchema],
)
async def get_favorites(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
    include_products: bool = Query(True, description="Include full product details"),
    latitude: Optional[float] = Query(None, description="Latitude for inventory check"),
    longitude: Optional[float] = Query(
        None, description="Longitude for inventory check"
    ),
    store_ids: Optional[List[int]] = Query(
        None, description="Specific store IDs to check inventory"
    ),
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    favorites = await user_service.get_favorites(
        user_id,
        include_products=include_products,
        latitude=latitude,
        longitude=longitude,
        store_ids=store_ids,
    )

    if include_products:
        serialized_favorites = []
        for fav in favorites:
            if isinstance(fav, EnhancedProductSchema):
                serialized_favorites.append(fav.model_dump(mode="json"))
            else:
                serialized_favorites.append(fav)
        return success_response(serialized_favorites)
    else:
        # If not including products, we might need a different response model or just return IDs.
        # But the type hint says List[EnhancedProductSchema].
        # If include_products is False, get_favorites returns List[int].
        # So we should probably wrap it.
        return success_response(favorites)


# Address Management Endpoints
@users_router.post(
    "/me/addresses",
    summary="Add a new address for the current user",
    response_model=AddressWithDeliverySchema,
)
async def add_address(
    address_data: AddressCreationSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    new_address = await user_service.add_address(user_id, address_data)
    if not new_address:
        raise HTTPException(status_code=500, detail="Failed to add address")

    return success_response(
        new_address.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


@users_router.get(
    "/me/addresses",
    summary="Get all addresses for the current user",
    response_model=List[AddressResponseSchema],
)
async def get_addresses(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    addresses = await user_service.get_addresses(user_id)
    return success_response([addr.model_dump(mode="json") for addr in addresses])


@users_router.get(
    "/me/addresses/{address_id}",
    summary="Get a specific address for the current user",
    response_model=AddressResponseSchema,
)
async def get_address_by_id(
    address_id: int,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    address = await user_service.get_address_by_id(user_id, address_id)
    if not address:
        raise ResourceNotFoundException(
            detail=f"Address with ID {address_id} not found"
        )

    return success_response(address.model_dump(mode="json"))


@users_router.delete(
    "/me/addresses/{address_id}",
    summary="Delete a specific address for the current user",
)
async def delete_address(
    address_id: int,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    success = await user_service.delete_address(user_id, address_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete address")

    return success_response({"message": "Address deleted successfully"})


@users_router.put(
    "/me/addresses/{address_id}/set_default",
    summary="Set a specific address as default for the current user",
    response_model=AddressWithDeliverySchema,
)
async def set_default_address(
    address_id: int,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    default_address = await user_service.set_default_address(user_id, address_id)
    if not default_address:
        raise HTTPException(status_code=500, detail="Failed to set default address")

    return success_response(default_address.model_dump(mode="json"))


# Multi-Cart System Routes


@users_router.post(
    "/me/carts", summary="Create a new cart", status_code=status.HTTP_201_CREATED
)
async def create_cart(
    cart_data: CreateCartSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    cart = await CartService.create_cart(user_id, cart_data)
    return success_response(
        cart.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


@users_router.get("/me/carts", summary="Get all user carts (owned + shared)")
async def get_user_carts(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    carts = await CartService.get_user_carts(user_id)
    return success_response(carts.model_dump(mode="json"))


@users_router.get("/me/carts/{cart_id}", summary="Get cart details")
async def get_cart_details(
    cart_id: int,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    cart = await CartService.get_cart_details(user_id, cart_id)
    return success_response(cart.model_dump(mode="json"))


@users_router.put("/me/carts/{cart_id}", summary="Update cart details (owner only)")
async def update_cart(
    cart_id: int,
    cart_data: UpdateCartSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    cart = await CartService.update_cart(user_id, cart_id, cart_data)
    return success_response(cart.model_dump(mode="json"))


@users_router.delete(
    "/me/carts/{cart_id}",
    summary="Delete cart (owner only)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_cart(
    cart_id: int,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    await CartService.delete_cart(user_id, cart_id)
    return success_response(
        {"message": "Cart deleted successfully"}, status_code=status.HTTP_204_NO_CONTENT
    )


# Cart Items Management


@users_router.post(
    "/me/carts/{cart_id}/items",
    summary="Add item to cart (owner only)",
    status_code=status.HTTP_201_CREATED,
)
async def add_cart_item(
    cart_id: int,
    item_data: AddCartItemSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    item = await CartService.add_cart_item(user_id, cart_id, item_data)

    # Track cart add interaction (background task)
    await interaction_service.track_cart_add(
        user_id=user_id,
        product_id=item_data.product_id,
        quantity=item_data.quantity,
        auto_update=True,  # Auto-update popularity
    )

    return success_response(
        item.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


@users_router.put(
    "/me/carts/{cart_id}/items/{item_id}",
    summary="Update cart item quantity (owner only)",
)
async def update_cart_item(
    cart_id: int,
    item_id: int,
    item_data: UpdateCartItemQuantitySchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    item = await CartService.update_cart_item(user_id, cart_id, item_id, item_data)
    return success_response(item.model_dump(mode="json"))


@users_router.delete(
    "/me/carts/{cart_id}/items/{product_id}",
    summary="Remove product from cart or reduce quantity (owner only)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_cart_item(
    cart_id: int,
    product_id: int,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
    quantity: Optional[int] = Query(
        None,
        description="Quantity to reduce. If not provided, removes entire product from cart",
        ge=1,
    ),
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    if quantity is not None:
        # Reduce quantity by specified amount
        item = await CartService.reduce_cart_item_quantity_by_product(
            user_id, cart_id, product_id, quantity
        )
        if item:
            return success_response(item.model_dump(mode="json"))
        else:
            return success_response(
                {"message": "Product removed from cart (quantity reached zero)"},
                status_code=status.HTTP_204_NO_CONTENT,
            )
    else:
        # Remove entire product from cart
        await CartService.remove_cart_item_by_product(user_id, cart_id, product_id)
        return success_response(
            {"message": "Product removed from cart"},
            status_code=status.HTTP_204_NO_CONTENT,
        )


# Cart Sharing


@users_router.post(
    "/me/carts/{cart_id}/share",
    summary="Share cart with another user (owner only)",
    status_code=status.HTTP_201_CREATED,
)
async def share_cart(
    cart_id: int,
    share_data: ShareCartSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    result = await CartService.share_cart(user_id, cart_id, share_data)
    return success_response(result, status_code=status.HTTP_201_CREATED)


@users_router.delete(
    "/me/carts/{cart_id}/share/{target_user_id}",
    summary="Remove cart sharing (owner only)",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unshare_cart(
    cart_id: int,
    target_user_id: str,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    await CartService.unshare_cart(user_id, cart_id, target_user_id)
    return success_response(
        {"message": "Cart sharing removed"}, status_code=status.HTTP_204_NO_CONTENT
    )


@users_router.get(
    "/me/carts/{cart_id}/shares", summary="Get cart sharing details (owner only)"
)
async def get_cart_sharing_details(
    cart_id: int,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    details = await CartService.get_cart_sharing_details(user_id, cart_id)
    return success_response(details.model_dump(mode="json"))


# Multi-Cart Checkout


@users_router.get("/me/checkout/carts", summary="Get available carts for checkout")
async def get_available_carts_for_checkout(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    carts = await CartService.get_available_carts_for_checkout(user_id)
    return success_response({"available_carts": carts})


@users_router.post(
    "/me/checkout/preview",
    summary="Preview multi-cart order",
    response_model=CheckoutResponse,
)
async def preview_multi_cart_order(
    checkout_data: CheckoutRequestSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    preview = await checkout_service.preview_order(user_id, checkout_data)
    return success_response(preview.model_dump(mode="json"))


@users_router.post(
    "/me/checkout/order",
    summary="Create multi-cart order",
    status_code=status.HTTP_201_CREATED,
    response_model=CheckoutResponse,
)
async def create_multi_cart_order(
    checkout_data: CheckoutRequestSchema,
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    # Generate preview to get totals and items without creating orders yet
    order_summary = await checkout_service.preview_order(user_id, checkout_data)

    # Initiate payment with checkout intent
    payment_data = InitiatePaymentSchema(
        amount=Decimal(str(order_summary.overall_total)),
        currency="LKR",
        cart_ids=checkout_data.cart_ids,
        save_card=checkout_data.save_card,
        source_token_id=checkout_data.source_token_id,
        checkout_data=checkout_data.model_dump(mode="json"),
    )
    payment_info_dict = await payment_service.initiate_payment(
        payment_data=payment_data,
        user_id=user_id,
    )
    order_summary.payment_info = PaymentInfo(
        payment_reference=payment_info_dict["payment_reference"],
        session_id=payment_info_dict["session_id"],
        merchant_id=payment_info_dict["merchant_id"],
        success_indicator=payment_info_dict["success_indicator"],
        amount=float(order_summary.overall_total),
        currency="LKR",
    )

    return success_response(
        order_summary.model_dump(mode="json"), status_code=status.HTTP_201_CREATED
    )


@users_router.get(
    "/me/search-history",
    summary="Get current user's search history",
    response_model=List[str],
)
async def get_search_history(
    current_user: Annotated[DecodedToken, Depends(get_current_user)],
    limit: int = Query(
        10, ge=1, le=50, description="Number of recent searches to return"
    ),
):
    user_id = current_user.uid
    if not user_id:
        raise UnauthorizedException(detail="User ID not found in token")

    search_history = await user_service.get_search_history(user_id, limit)
    return success_response(search_history)
