from typing import Optional, List, Dict, Any
from decimal import Decimal
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, update, delete, func
from src.database.connection import AsyncSessionLocal
from src.database.models.cart import Cart, CartUser, CartItem
from src.database.models.order import Order, OrderItem
from src.database.models.user import User
from src.api.users.models import (
    CreateCartSchema, UpdateCartSchema, CartSchema, CartListSchema,
    AddCartItemSchema, UpdateCartItemQuantitySchema, ShareCartSchema,
    CartSharingDetailsSchema, MultiCartCheckoutSchema, OrderPreviewSchema,
    CheckoutResponseSchema, CartGroupSchema, CartItemDetailSchema, CartUserSchema
)
from src.config.constants import CartStatus, CartUserRole, OrderStatus
from src.shared.exceptions import ResourceNotFoundException, ConflictException, ValidationException, ForbiddenException
from src.shared.sqlalchemy_utils import safe_model_validate, safe_model_validate_list
from src.shared.error_handler import handle_service_errors
from sqlalchemy.exc import IntegrityError


class CartService:

    @staticmethod
    @handle_service_errors("creating cart")
    async def create_cart(user_id: str, cart_data: CreateCartSchema) -> CartSchema:
        """Create a new cart for the user"""
        async with AsyncSessionLocal() as session:
            # Check for duplicate active cart names for this user
            existing_cart_query = select(Cart).where(
                and_(
                    Cart.created_by == user_id,
                    Cart.name == cart_data.name,
                    Cart.status == CartStatus.ACTIVE
                )
            )
            existing_cart_result = await session.execute(existing_cart_query)
            existing_cart = existing_cart_result.scalar_one_or_none()

            if existing_cart:
                raise ConflictException(detail=f"An active cart with the name '{cart_data.name}' already exists")

            # Create cart
            new_cart = Cart(
                name=cart_data.name,
                description=cart_data.description,
                created_by=user_id,
                status=CartStatus.ACTIVE
            )
            session.add(new_cart)
            await session.flush()

            # Create owner permission
            cart_user = CartUser(
                cart_id=new_cart.id,
                user_id=user_id,
                role=CartUserRole.OWNER
            )
            session.add(cart_user)

            await session.commit()
            await session.refresh(new_cart)

            # Convert to schema
            cart_dict = {
                "id": new_cart.id,
                "name": new_cart.name,
                "description": new_cart.description,
                "status": new_cart.status,
                "created_by": new_cart.created_by,
                "created_at": new_cart.created_at,
                "updated_at": new_cart.updated_at,
                "ordered_at": new_cart.ordered_at,
                "items": [],
                "users": [],
                "role": CartUserRole.OWNER,
                "items_count": 0
            }

            return CartSchema.model_validate(cart_dict)

    @staticmethod
    @handle_service_errors("retrieving user carts")
    async def get_user_carts(user_id: str) -> CartListSchema:
        """Get all carts accessible to the user (owned + shared)"""
        async with AsyncSessionLocal() as session:
            # Get carts where user has access
            query = select(Cart, CartUser.role).join(
                CartUser, Cart.id == CartUser.cart_id
            ).where(
                CartUser.user_id == user_id
            ).options(
                selectinload(Cart.items)
            ).order_by(Cart.updated_at.desc())

            result = await session.execute(query)
            cart_role_pairs = result.all()

            owned_carts = []
            shared_carts = []

            for cart, role in cart_role_pairs:
                cart_dict = {
                    "id": cart.id,
                    "name": cart.name,
                    "description": cart.description,
                    "status": cart.status,
                    "created_by": cart.created_by,
                    "created_at": cart.created_at,
                    "updated_at": cart.updated_at,
                    "ordered_at": cart.ordered_at,
                    "role": role,
                    "items_count": len(cart.items) if cart.items else 0
                }

                cart_schema = CartSchema.model_validate(cart_dict)

                if role == CartUserRole.OWNER:
                    owned_carts.append(cart_schema)
                else:
                    shared_carts.append(cart_schema)

            return CartListSchema(
                owned_carts=owned_carts,
                shared_carts=shared_carts
            )

    @staticmethod
    @handle_service_errors("retrieving cart details")
    async def get_cart_details(user_id: str, cart_id: int) -> CartSchema:
        """Get detailed cart information"""
        async with AsyncSessionLocal() as session:
            # Check user access
            user_role = await CartService._check_cart_access(session, user_id, cart_id)

            # Get cart with items and users
            query = select(Cart).where(Cart.id == cart_id).options(
                selectinload(Cart.items),
                selectinload(Cart.users)
            )
            result = await session.execute(query)
            cart = result.scalar_one_or_none()

            if not cart:
                raise ResourceNotFoundException(detail="Cart not found")

            # Convert items
            items = []
            if cart.items:
                for item in cart.items:
                    items.append(CartItemDetailSchema.model_validate(item))

            # Convert users (only show to owner)
            users = []
            if user_role == CartUserRole.OWNER and cart.users:
                for cart_user in cart.users:
                    users.append(CartUserSchema.model_validate(cart_user))

            cart_dict = {
                "id": cart.id,
                "name": cart.name,
                "description": cart.description,
                "status": cart.status,
                "created_by": cart.created_by,
                "created_at": cart.created_at,
                "updated_at": cart.updated_at,
                "ordered_at": cart.ordered_at,
                "items": items,
                "users": users,
                "role": user_role,
                "items_count": len(items)
            }

            return CartSchema.model_validate(cart_dict)

    @staticmethod
    @handle_service_errors("updating cart")
    async def update_cart(user_id: str, cart_id: int, cart_data: UpdateCartSchema) -> CartSchema:
        """Update cart details (owner only)"""
        async with AsyncSessionLocal() as session:
            # Check owner access and cart status
            await CartService._check_cart_owner_access(session, user_id, cart_id)

            # If name is being updated, check for duplicates among active carts
            if cart_data.name is not None:
                existing_cart_query = select(Cart).where(
                    and_(
                        Cart.created_by == user_id,
                        Cart.name == cart_data.name,
                        Cart.status == CartStatus.ACTIVE,
                        Cart.id != cart_id  # Exclude current cart
                    )
                )
                existing_cart_result = await session.execute(existing_cart_query)
                existing_cart = existing_cart_result.scalar_one_or_none()

                if existing_cart:
                    raise ConflictException(detail=f"An active cart with the name '{cart_data.name}' already exists")

            # Update cart
            update_data = {}
            if cart_data.name is not None:
                update_data["name"] = cart_data.name
            if cart_data.description is not None:
                update_data["description"] = cart_data.description

            if update_data:
                await session.execute(
                    update(Cart).where(Cart.id == cart_id).values(**update_data)
                )
                await session.commit()

            # Return updated cart
            return await CartService.get_cart_details(user_id, cart_id)

    @staticmethod
    @handle_service_errors("deleting cart")
    async def delete_cart(user_id: str, cart_id: int) -> None:
        """Delete cart (owner only)"""
        async with AsyncSessionLocal() as session:
            # Check owner access and cart status
            await CartService._check_cart_owner_access(session, user_id, cart_id)

            # Delete cart (cascades to items and users)
            await session.execute(delete(Cart).where(Cart.id == cart_id))
            await session.commit()

    @staticmethod
    @handle_service_errors("adding cart item")
    async def add_cart_item(user_id: str, cart_id: int, item_data: AddCartItemSchema) -> CartItemDetailSchema:
        """Add item to cart (owner only)"""
        async with AsyncSessionLocal() as session:
            # Check owner access and cart status
            await CartService._check_cart_owner_access(session, user_id, cart_id)

            try:
                # Check if item already exists
                existing_query = select(CartItem).where(
                    and_(CartItem.cart_id == cart_id, CartItem.product_id == item_data.product_id)
                )
                existing_result = await session.execute(existing_query)
                existing_item = existing_result.scalar_one_or_none()

                if existing_item:
                    # Update quantity
                    new_quantity = existing_item.quantity + item_data.quantity
                    if new_quantity > 1000:
                        raise ValidationException(detail="Total quantity would exceed maximum limit")

                    await session.execute(
                        update(CartItem)
                        .where(CartItem.id == existing_item.id)
                        .values(quantity=new_quantity)
                    )
                    await session.commit()

                    # Refresh and return
                    await session.refresh(existing_item)
                    return CartItemDetailSchema.model_validate(existing_item)
                else:
                    # Create new item
                    new_item = CartItem(
                        cart_id=cart_id,
                        product_id=item_data.product_id,
                        quantity=item_data.quantity
                    )
                    session.add(new_item)
                    await session.commit()
                    await session.refresh(new_item)

                    return CartItemDetailSchema.model_validate(new_item)

            except IntegrityError:
                await session.rollback()
                raise ValidationException(detail="Invalid product ID or cart ID")

    @staticmethod
    @handle_service_errors("updating cart item")
    async def update_cart_item(user_id: str, cart_id: int, item_id: int,
                              item_data: UpdateCartItemQuantitySchema) -> CartItemDetailSchema:
        """Update cart item quantity (owner only)"""
        async with AsyncSessionLocal() as session:
            # Check owner access and cart status
            await CartService._check_cart_owner_access(session, user_id, cart_id)

            # Get and update item
            query = select(CartItem).where(
                and_(CartItem.id == item_id, CartItem.cart_id == cart_id)
            )
            result = await session.execute(query)
            item = result.scalar_one_or_none()

            if not item:
                raise ResourceNotFoundException(detail="Cart item not found")

            await session.execute(
                update(CartItem)
                .where(CartItem.id == item_id)
                .values(quantity=item_data.quantity)
            )
            await session.commit()
            await session.refresh(item)

            return CartItemDetailSchema.model_validate(item)

    @staticmethod
    @handle_service_errors("reducing cart item quantity")
    async def reduce_cart_item_quantity(user_id: str, cart_id: int, item_id: int, quantity_to_reduce: int) -> Optional[CartItemDetailSchema]:
        """Reduce cart item quantity by specified amount (owner only)"""
        async with AsyncSessionLocal() as session:
            # Check owner access and cart status
            await CartService._check_cart_owner_access(session, user_id, cart_id)

            # Get current item
            query = select(CartItem).where(
                and_(CartItem.id == item_id, CartItem.cart_id == cart_id)
            )
            result = await session.execute(query)
            item = result.scalar_one_or_none()

            if not item:
                raise ResourceNotFoundException(detail="Cart item not found")

            # Calculate new quantity
            new_quantity = item.quantity - quantity_to_reduce

            if new_quantity <= 0:
                # Remove item completely if quantity reaches zero or below
                await session.execute(
                    delete(CartItem).where(CartItem.id == item_id)
                )
                await session.commit()
                return None
            else:
                # Update to new quantity
                await session.execute(
                    update(CartItem)
                    .where(CartItem.id == item_id)
                    .values(quantity=new_quantity)
                )
                await session.commit()
                await session.refresh(item)
                return CartItemDetailSchema.model_validate(item)

    @staticmethod
    @handle_service_errors("reducing cart item quantity by product")
    async def reduce_cart_item_quantity_by_product(user_id: str, cart_id: int, product_id: int, quantity_to_reduce: int) -> Optional[CartItemDetailSchema]:
        """Reduce cart item quantity by product ID (owner only)"""
        async with AsyncSessionLocal() as session:
            # Check owner access and cart status
            await CartService._check_cart_owner_access(session, user_id, cart_id)

            # Get current item by product_id
            query = select(CartItem).where(
                and_(CartItem.cart_id == cart_id, CartItem.product_id == product_id)
            )
            result = await session.execute(query)
            item = result.scalar_one_or_none()

            if not item:
                raise ResourceNotFoundException(detail="Product not found in cart")

            # Calculate new quantity
            new_quantity = item.quantity - quantity_to_reduce

            if new_quantity <= 0:
                # Remove item completely if quantity reaches zero or below
                await session.execute(
                    delete(CartItem).where(CartItem.id == item.id)
                )
                await session.commit()
                return None
            else:
                # Update to new quantity
                await session.execute(
                    update(CartItem)
                    .where(CartItem.id == item.id)
                    .values(quantity=new_quantity)
                )
                await session.commit()
                await session.refresh(item)
                return CartItemDetailSchema.model_validate(item)

    @staticmethod
    @handle_service_errors("removing cart item by product")
    async def remove_cart_item_by_product(user_id: str, cart_id: int, product_id: int) -> None:
        """Remove item from cart by product ID (owner only)"""
        async with AsyncSessionLocal() as session:
            # Check owner access and cart status
            await CartService._check_cart_owner_access(session, user_id, cart_id)

            # Delete item by product_id
            result = await session.execute(
                delete(CartItem).where(
                    and_(CartItem.cart_id == cart_id, CartItem.product_id == product_id)
                )
            )

            if result.rowcount == 0:
                raise ResourceNotFoundException(detail="Product not found in cart")

            await session.commit()

    @staticmethod
    @handle_service_errors("sharing cart")
    async def share_cart(user_id: str, cart_id: int, share_data: ShareCartSchema) -> Dict[str, Any]:
        """Share cart with another user (owner only)"""
        async with AsyncSessionLocal() as session:
            # Check owner access
            await CartService._check_cart_owner_access(session, user_id, cart_id)

            # Check if target user exists
            user_query = select(User).where(User.firebase_uid == share_data.user_id)
            user_result = await session.execute(user_query)
            target_user = user_result.scalar_one_or_none()

            if not target_user:
                raise ResourceNotFoundException(detail="User not found")

            # Check if already shared
            existing_query = select(CartUser).where(
                and_(CartUser.cart_id == cart_id, CartUser.user_id == share_data.user_id)
            )
            existing_result = await session.execute(existing_query)
            existing_share = existing_result.scalar_one_or_none()

            if existing_share:
                raise ConflictException(detail="Cart is already shared with this user")

            # Create share
            cart_user = CartUser(
                cart_id=cart_id,
                user_id=share_data.user_id,
                role=CartUserRole.VIEWER
            )
            session.add(cart_user)
            await session.commit()
            await session.refresh(cart_user)

            return {
                "cart_id": cart_id,
                "user_id": share_data.user_id,
                "role": CartUserRole.VIEWER,
                "shared_at": cart_user.shared_at
            }

    @staticmethod
    @handle_service_errors("unsharing cart")
    async def unshare_cart(user_id: str, cart_id: int, target_user_id: str) -> None:
        """Remove cart sharing (owner only)"""
        async with AsyncSessionLocal() as session:
            # Check owner access
            await CartService._check_cart_owner_access(session, user_id, cart_id)

            # Remove sharing (but not owner)
            result = await session.execute(
                delete(CartUser).where(
                    and_(
                        CartUser.cart_id == cart_id,
                        CartUser.user_id == target_user_id,
                        CartUser.role == CartUserRole.VIEWER
                    )
                )
            )

            if result.rowcount == 0:
                raise ResourceNotFoundException(detail="Cart sharing not found")

            await session.commit()

    @staticmethod
    @handle_service_errors("retrieving cart sharing details")
    async def get_cart_sharing_details(user_id: str, cart_id: int) -> CartSharingDetailsSchema:
        """Get cart sharing details (owner only)"""
        async with AsyncSessionLocal() as session:
            # Check owner access
            await CartService._check_cart_owner_access(session, user_id, cart_id)

            # Get sharing details
            query = select(CartUser).where(
                and_(CartUser.cart_id == cart_id, CartUser.role == CartUserRole.VIEWER)
            )
            result = await session.execute(query)
            shares = result.scalars().all()

            shared_with = []
            for share in shares:
                shared_with.append({
                    "cart_id": cart_id,
                    "user_id": share.user_id,
                    "role": share.role,
                    "shared_at": share.shared_at
                })

            return CartSharingDetailsSchema(
                cart_id=cart_id,
                shared_with=shared_with
            )

    @staticmethod
    @handle_service_errors("retrieving available carts for checkout")
    async def get_available_carts_for_checkout(user_id: str) -> List[Dict[str, Any]]:
        """Get carts available for checkout"""
        async with AsyncSessionLocal() as session:
            # Get active carts with access
            query = select(Cart, CartUser.role).join(
                CartUser, Cart.id == CartUser.cart_id
            ).where(
                and_(
                    CartUser.user_id == user_id,
                    Cart.status == CartStatus.ACTIVE
                )
            ).options(selectinload(Cart.items))

            result = await session.execute(query)
            cart_role_pairs = result.all()

            available_carts = []
            for cart, role in cart_role_pairs:
                # Calculate estimated total (simplified - would need pricing logic)
                estimated_total = len(cart.items) * 10.0  # Placeholder calculation

                available_carts.append({
                    "id": cart.id,
                    "name": cart.name,
                    "role": role,
                    "items_count": len(cart.items),
                    "estimated_total": estimated_total,
                    "can_checkout": len(cart.items) > 0
                })

            return available_carts

    @staticmethod
    async def _check_cart_access(session, user_id: str, cart_id: int) -> CartUserRole:
        """Check if user has access to cart and return role"""
        query = select(CartUser.role).where(
            and_(CartUser.cart_id == cart_id, CartUser.user_id == user_id)
        )
        result = await session.execute(query)
        role = result.scalar_one_or_none()

        if not role:
            raise ForbiddenException(detail="You don't have permission to access this cart")

        return role

    @staticmethod
    async def _check_cart_owner_access(session, user_id: str, cart_id: int) -> None:
        """Check if user is owner of cart and cart is modifiable"""
        # Check ownership
        query = select(Cart, CartUser.role).join(
            CartUser, Cart.id == CartUser.cart_id
        ).where(
            and_(
                CartUser.cart_id == cart_id,
                CartUser.user_id == user_id,
                CartUser.role == CartUserRole.OWNER
            )
        )
        result = await session.execute(query)
        cart_role = result.first()

        if not cart_role:
            raise ForbiddenException(detail="You don't have permission to modify this cart")

        cart, role = cart_role

        # Check if cart is modifiable
        if cart.status == CartStatus.ORDERED:
            raise ConflictException(detail="This cart has been ordered and cannot be modified")

    @staticmethod
    @handle_service_errors("previewing multi-cart order")
    async def preview_multi_cart_order(user_id: str, checkout_data: MultiCartCheckoutSchema) -> OrderPreviewSchema:
        """Preview multi-cart order without creating it"""
        async with AsyncSessionLocal() as session:
            cart_groups = []
            total_amount = 0.0

            for cart_id in checkout_data.cart_ids:
                # Check access
                await CartService._check_cart_access(session, user_id, cart_id)

                # Get cart with items
                query = select(Cart).where(
                    and_(Cart.id == cart_id, Cart.status == CartStatus.ACTIVE)
                ).options(selectinload(Cart.items))

                result = await session.execute(query)
                cart = result.scalar_one_or_none()

                if not cart:
                    raise ValidationException(detail=f"Cart {cart_id} not found or not available for checkout")

                # Calculate cart total (simplified)
                cart_total = 0.0
                items = []

                for item in cart.items:
                    # Placeholder pricing - would integrate with pricing service
                    unit_price = 10.0  # Would get actual price
                    item_total = unit_price * item.quantity
                    cart_total += item_total

                    items.append({
                        "product_id": item.product_id,
                        "quantity": item.quantity,
                        "unit_price": unit_price,
                        "total_price": item_total
                    })

                cart_groups.append(CartGroupSchema(
                    cart_id=cart.id,
                    cart_name=cart.name,
                    items=items,
                    cart_total=cart_total
                ))

                total_amount += cart_total

            return OrderPreviewSchema(
                cart_groups=cart_groups,
                total_amount=total_amount
            )