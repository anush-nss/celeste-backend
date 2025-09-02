from fastapi import APIRouter, Depends, status, HTTPException
from typing import Annotated, List
from datetime import datetime
from src.models.user_models import UserSchema, CreateUserSchema, UpdateUserSchema, AddToWishlistSchema, AddToCartSchema, UpdateCartItemSchema, CartItemSchema
from src.services.user_service import UserService
from src.auth.dependencies import get_current_user, RoleChecker
from src.shared.constants import UserRole
from src.core.exceptions import ResourceNotFoundException, ForbiddenException
from src.core.responses import success_response

users_router = APIRouter(prefix="/users", tags=["Users"])
user_service = UserService()

@users_router.post("/", summary="Create a new user", status_code=status.HTTP_201_CREATED, dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def create_user(user_data: CreateUserSchema):
    # This endpoint is public for initial user creation, but Firebase auth register is preferred.
    # For simplicity, we'll generate a dummy UID here if not coming from Firebase auth.
    # In a real app, this might be protected or integrated with Firebase auth more deeply.
    import uuid
    dummy_uid = str(uuid.uuid4())
    new_user = await user_service.create_user(user_data, dummy_uid)
    return success_response(new_user.model_dump(), status_code=status.HTTP_201_CREATED)

@users_router.get("/me", summary="Get current user profile")
async def get_user_profile(current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    user = await user_service.get_user_by_id(user_id)

    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")
    return success_response(user.model_dump())

@users_router.get("/{id}", summary="Get user profile by ID (for admins)", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def get_user_by_id_admin(id: str):
    user = await user_service.get_user_by_id(id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {id} not found")
    return success_response(user.model_dump())

@users_router.put("/me", summary="Update current user profile")
async def update_user_profile(user_data: UpdateUserSchema, current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")

    # Prevent phone number from being updated
    if user_data.phone is not None:
        del user_data.phone

    updated_data = user_data.model_dump(exclude_unset=True)
    updated_user = await user_service.update_user(user_id, updated_data)
    if not updated_user:
        raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")
    
    return success_response(updated_user.model_dump())

@users_router.put("/{id}", summary="Update user profile by ID (for admins)", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def update_user_by_id_admin(id: str, user_data: UpdateUserSchema):
    # Prevent phone number from being updated
    if user_data.phone is not None:
        del user_data.phone

    updated_data = user_data.model_dump(exclude_unset=True)
    updated_user = await user_service.update_user(id, updated_data)
    if not updated_user:
        raise ResourceNotFoundException(detail=f"User with ID {id} not found")
    
    return success_response(updated_user.model_dump())

@users_router.delete("/{id}", summary="Delete a user", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def delete_user(id: str):
    # Placeholder for delete logic
    # In a real application, you would delete the user from Firestore and Firebase Auth
    user = await user_service.get_user_by_id(id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {id} not found")
    
    # await user_service.delete_user(id)
    return success_response({"id": id, "message": "User deleted successfully"})

@users_router.post("/me/wishlist", summary="Add a product to the user's wishlist")
async def add_to_wishlist(item: AddToWishlistSchema, current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
        
    # Placeholder for wishlist logic
    # In a real app, you would add the product to the user's wishlist in Firestore
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")
    
    if not user.wishlist:
        user.wishlist = []
    if item.productId not in user.wishlist:
        user.wishlist.append(item.productId)
    
    # await user_service.update_user_wishlist(id, user.wishlist)
    return success_response({"userId": user_id, "productId": item.productId})

@users_router.delete("/me/wishlist/{productId}", summary="Remove a product from the user's wishlist")
async def remove_from_wishlist(productId: str, current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
        
    # Placeholder for wishlist logic
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")
    
    if user.wishlist and productId in user.wishlist:
        user.wishlist.remove(productId)
    
    # await user_service.update_user_wishlist(id, user.wishlist)
    return success_response({"userId": user_id, "productId": productId})

@users_router.post("/me/cart", summary="Add an item to the user's cart")
async def add_to_cart(item: AddToCartSchema, current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
        
    # Placeholder for cart logic
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")
    
    if not user.cart:
        user.cart = []
    
    # Check if product already in cart
    cart_item = None
    for existing_item in user.cart:
        if existing_item.productId == item.productId:
            existing_item.quantity += item.quantity
            cart_item = existing_item
            break
    if not cart_item:
        # Create proper CartItemSchema instance with addedAt timestamp
        cart_item = CartItemSchema(
            productId=item.productId,
            quantity=item.quantity,
            addedAt=datetime.now()
        )
        user.cart.append(cart_item)
    
    # await user_service.update_user_cart(id, user.cart)
    # Return the cart item (either updated or newly created)
    return success_response(cart_item.model_dump()) # Return the added item

@users_router.put("/me/cart/{productId}", summary="Update an item in the user's cart")
async def update_cart_item(productId: str, item: UpdateCartItemSchema, current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
        
    # Placeholder for cart logic
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")
    
    cart_item = None
    if user.cart:
        for existing_item in user.cart:
            if existing_item.productId == productId:
                existing_item.quantity = item.quantity
                cart_item = existing_item
                break
    
    if not cart_item:
        raise ResourceNotFoundException(detail=f"Product {productId} not found in user's cart.")
    
    # await user_service.update_user_cart(id, user.cart)
    return success_response(cart_item.model_dump()) # Return the updated item

@users_router.delete("/me/cart/{productId}", summary="Remove an item from the user's cart")
async def remove_from_cart(productId: str, current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
        
    # Placeholder for cart logic
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")
    
    if user.cart:
        user.cart = [item for item in user.cart if item.productId != productId]
    
    # await user_service.update_user_cart(id, user.cart)
    return success_response({"userId": user_id, "productId": productId})
