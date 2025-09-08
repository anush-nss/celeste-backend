from typing import Optional
from src.shared.database import get_async_db, get_async_collection
from src.api.users.models import CreateUserSchema, UserSchema, CartItemSchema
from src.config.constants import UserRole, DEFAULT_FALLBACK_TIER
from src.api.tiers.service import TierService
from src.shared.exceptions import ResourceNotFoundException


class UserService:
    def __init__(self):
        self.tier_service = TierService()

    async def get_users_collection(self):
        return await get_async_collection("users")

    async def create_user(self, user_data: CreateUserSchema, uid: str) -> UserSchema:
        user_dict = user_data.model_dump()
        user_dict["id"] = uid

        # The role and customer_tier fields are already set by default in the models
        # but ensure they are stored as string values in Firestore
        if "role" in user_dict and hasattr(user_dict["role"], "value"):
            user_dict["role"] = user_dict["role"].value
        elif "role" not in user_dict or user_dict["role"] is None:
            user_dict["role"] = UserRole.CUSTOMER.value

        # Set default customer tier when creating user
        default_tier = await self.tier_service.get_default_tier()
        user_dict["customer_tier"] = default_tier

        users_collection = await self.get_users_collection()
        await users_collection.document(uid).set(user_dict)
        created_user_doc = await users_collection.document(uid).get()
        created_dict = created_user_doc.to_dict()
        if created_dict:  # Ensure created_dict is not None
            return UserSchema(**created_dict)
        else:
            # Handle the case where the document doesn't exist after creation
            raise Exception("Failed to create user")

    async def get_user_by_id(self, user_id: str) -> UserSchema | None:
        users_collection = await self.get_users_collection()
        user_doc = await users_collection.document(user_id).get()
        if user_doc.exists:
            user_dict = user_doc.to_dict()
            if user_dict:  # Ensure user_dict is not None
                return UserSchema(**user_dict)
        return None

    async def update_user(self, user_id: str, user_data: dict) -> UserSchema | None:
        users_collection = await self.get_users_collection()
        await users_collection.document(user_id).update(user_data)
        updated_user_doc = await users_collection.document(user_id).get()
        if updated_user_doc.exists:
            updated_dict = updated_user_doc.to_dict()
            if updated_dict:
                return UserSchema(**updated_dict)
        return None

    async def add_to_cart(self, user_id: str, product_id: str, quantity: int) -> dict:
        user = await self.get_user_by_id(user_id)
        if not user:
            raise Exception(f"User with ID {user_id} not found")

        # Initialize cart if it doesn't exist
        if not user.cart:
            user.cart = []

        # Check if product already in cart
        cart_item = None
        for existing_item in user.cart:
            if existing_item.productId == product_id:
                existing_item.quantity += quantity
                cart_item = existing_item
                break

        # If not in cart, create new cart item
        if not cart_item:
            cart_item = CartItemSchema(
                productId=product_id,
                quantity=quantity,
            )
            user.cart.append(cart_item)

        # Update user in database
        user_dict = user.model_dump()
        users_collection = await self.get_users_collection()
        await users_collection.document(user_id).update({"cart": user_dict["cart"]})

        return cart_item.model_dump()

    async def update_cart_item(
        self, user_id: str, product_id: str, quantity: int
    ) -> dict:
        user = await self.get_user_by_id(user_id)
        if not user:
            raise Exception(f"User with ID {user_id} not found")

        # Find the cart item
        cart_item = None
        if user.cart:
            for existing_item in user.cart:
                if existing_item.productId == product_id:
                    existing_item.quantity = quantity
                    cart_item = existing_item
                    break

        if not cart_item:
            raise ResourceNotFoundException(detail=f"Product {product_id} not found in user's cart")

        # Update user in database
        user_dict = user.model_dump()
        users_collection = await self.get_users_collection()
        await users_collection.document(user_id).update({"cart": user_dict["cart"]})

        return cart_item.model_dump()

    async def remove_from_cart(self, user_id: str, product_id: str, quantity: Optional[int] = None) -> dict:
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ResourceNotFoundException(detail=f"User with ID {user_id} not found")

        # Find the cart item
        cart_item = None
        item_index = None
        
        if user.cart:
            for i, item in enumerate(user.cart):
                if item.productId == product_id:
                    cart_item = item
                    item_index = i
                    break
        
        if not cart_item or item_index is None:
            raise ResourceNotFoundException(detail=f"Product {product_id} not found in user's cart")

        result = {"action": "", "previous_quantity": cart_item.quantity}
        
        # Ensure user.cart exists before modifying
        if not user.cart:
            raise ResourceNotFoundException(detail=f"Product {product_id} not found in user's cart")
        
        if quantity is None:
            # Complete removal - remove product entirely
            user.cart.pop(item_index)
            result["action"] = "removed_completely"
            result["new_quantity"] = 0
        else:
            # Partial removal - reduce quantity
            if quantity >= cart_item.quantity:
                # If requested quantity >= current quantity, remove completely
                user.cart.pop(item_index)
                result["action"] = "removed_completely" 
                result["new_quantity"] = 0
                result["note"] = f"Requested quantity ({quantity}) >= available quantity ({cart_item.quantity}), removed completely"
            else:
                # Reduce quantity
                cart_item.quantity -= quantity
                result["action"] = "quantity_reduced"
                result["new_quantity"] = cart_item.quantity
                result["quantity_removed"] = quantity

        # Update user in database
        user_dict = user.model_dump()
        users_collection = await self.get_users_collection()
        await users_collection.document(user_id).update({"cart": user_dict["cart"]})

        return result

    async def get_cart(self, user_id: str) -> list:
        user = await self.get_user_by_id(user_id)
        if not user:
            raise Exception(f"User with ID {user_id} not found")

        # Return cart items as dictionaries
        if user.cart:
            cart_items = []
            for item in user.cart:
                # If item is already a dict (from Firestore), use it directly
                if isinstance(item, dict):
                    cart_items.append(item)
                else:
                    # If item is a CartItemSchema object, convert to dict
                    cart_items.append(item.model_dump())
            return cart_items
        return []

    async def add_to_wishlist(self, user_id: str, product_id: str) -> bool:
        user = await self.get_user_by_id(user_id)
        if not user:
            raise Exception(f"User with ID {user_id} not found")

        # Initialize wishlist if it doesn't exist
        if not user.wishlist:
            user.wishlist = []

        # Add product to wishlist if not already there
        if product_id not in user.wishlist:
            user.wishlist.append(product_id)

        # Update user in database
        user_dict = user.model_dump()
        users_collection = await self.get_users_collection()
        await users_collection.document(user_id).update(
            {"wishlist": user_dict["wishlist"]}
        )

        return True

    async def remove_from_wishlist(self, user_id: str, product_id: str) -> bool:
        user = await self.get_user_by_id(user_id)
        if not user:
            raise Exception(f"User with ID {user_id} not found")

        # Remove product from wishlist
        if user.wishlist:
            if product_id in user.wishlist:
                user.wishlist.remove(product_id)

        # Update user in database
        user_dict = user.model_dump()
        users_collection = await self.get_users_collection()
        await users_collection.document(user_id).update(
            {"wishlist": user_dict["wishlist"]}
        )

        return True

    async def get_wishlist(self, user_id: str) -> list:
        user = await self.get_user_by_id(user_id)
        if not user:
            raise Exception(f"User with ID {user_id} not found")

        return user.wishlist if user.wishlist else []
