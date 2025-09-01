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

@users_router.post("/", summary="Create a new user", status_code=status.HTTP_201_CREATED)
async def create_user(user_data: CreateUserSchema):
    # This endpoint is public for initial user creation, but Firebase auth register is preferred.
    # For simplicity, we'll generate a dummy UID here if not coming from Firebase auth.
    # In a real app, this might be protected or integrated with Firebase auth more deeply.
    import uuid
    dummy_uid = str(uuid.uuid4())
    new_user = await user_service.create_user(user_data, dummy_uid)
    return success_response(new_user.model_dump(), status_code=status.HTTP_201_CREATED)

@users_router.get("/{id}", summary="Get user profile")
async def get_user_profile(id: str):
    user = await user_service.get_user_by_id(id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {id} not found")
    return success_response(user.model_dump())

@users_router.put("/{id}", summary="Update user profile")
async def update_user_profile(id: str, user_data: UpdateUserSchema, current_user: Annotated[dict, Depends(get_current_user)]):
    # Allow user to update their own profile, or admin to update any profile
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
        
    if user_id != id and current_user.get("role") != UserRole.ADMIN.value:
        raise ForbiddenException(detail="You can only update your own profile unless you are an admin.")
    
    # Placeholder for update logic
    # In a real application, you would fetch the user, update fields, and save.
    user = await user_service.get_user_by_id(id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {id} not found")
    
    # Apply updates (simplified for now)
    updated_data = user_data.model_dump(exclude_unset=True)
    for key, value in updated_data.items():
        setattr(user, key, value)
    
    # In a real app, save the updated user to Firestore
    # await user_service.update_user(id, user_data)
    return success_response(user.model_dump())

@users_router.delete("/{id}", summary="Delete a user", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def delete_user(id: str):
    # Placeholder for delete logic
    # In a real application, you would delete the user from Firestore and Firebase Auth
    user = await user_service.get_user_by_id(id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {id} not found")
    
    # await user_service.delete_user(id)
    return success_response({"id": id, "message": "User deleted successfully"})

@users_router.post("/{id}/wishlist", summary="Add a product to the user's wishlist")
async def add_to_wishlist(id: str, item: AddToWishlistSchema, current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
        
    if user_id != id:
        raise ForbiddenException(detail="You can only modify your own wishlist.")
    
    # Placeholder for wishlist logic
    # In a real app, you would add the product to the user's wishlist in Firestore
    user = await user_service.get_user_by_id(id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {id} not found")
    
    if not user.wishlist:
        user.wishlist = []
    if item.productId not in user.wishlist:
        user.wishlist.append(item.productId)
    
    # await user_service.update_user_wishlist(id, user.wishlist)
    return success_response({"userId": id, "productId": item.productId})

@users_router.delete("/{id}/wishlist/{productId}", summary="Remove a product from the user's wishlist")
async def remove_from_wishlist(id: str, productId: str, current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
        
    if user_id != id:
        raise ForbiddenException(detail="You can only modify your own wishlist.")
    
    # Placeholder for wishlist logic
    user = await user_service.get_user_by_id(id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {id} not found")
    
    if user.wishlist and productId in user.wishlist:
        user.wishlist.remove(productId)
    
    # await user_service.update_user_wishlist(id, user.wishlist)
    return success_response({"userId": id, "productId": productId})

@users_router.post("/{id}/cart", summary="Add an item to the user's cart")
async def add_to_cart(id: str, item: AddToCartSchema, current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
        
    if user_id != id:
        raise ForbiddenException(detail="You can only modify your own cart.")
    
    # Placeholder for cart logic
    user = await user_service.get_user_by_id(id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {id} not found")
    
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

@users_router.put("/{id}/cart/{productId}", summary="Update an item in the user's cart")
async def update_cart_item(id: str, productId: str, item: UpdateCartItemSchema, current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
        
    if user_id != id:
        raise ForbiddenException(detail="You can only modify your own cart.")
    
    # Placeholder for cart logic
    user = await user_service.get_user_by_id(id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {id} not found")
    
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

@users_router.delete("/{id}/cart/{productId}", summary="Remove an item from the user's cart")
async def remove_from_cart(id: str, productId: str, current_user: Annotated[dict, Depends(get_current_user)]):
    user_id = current_user.get("uid")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found in token")
        
    if user_id != id:
        raise ForbiddenException(detail="You can only modify your own cart.")
    
    # Placeholder for cart logic
    user = await user_service.get_user_by_id(id)
    if not user:
        raise ResourceNotFoundException(detail=f"User with ID {id} not found")
    
    if user.cart:
        user.cart = [item for item in user.cart if item.productId != productId]
    
    # await user_service.update_user_cart(id, user.cart)
    return success_response({"userId": id, "productId": productId})
