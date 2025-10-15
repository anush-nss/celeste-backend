from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.api.users.models import (
    AddCartItemSchema,
    CartGroupSchema,
    CartItemDetailSchema,
    CartListSchema,
    CartSchema,
    CartSharingDetailsSchema,
    CartUserSchema,
    CreateCartSchema,
    MultiCartCheckoutSchema,
    OrderPreviewSchema,
    ShareCartSchema,
    UpdateCartItemQuantitySchema,
    UpdateCartSchema,
)
from src.config.constants import CartStatus, CartUserRole, FulfillmentMode
from src.database.connection import AsyncSessionLocal
from src.database.models.address import Address
from src.database.models.cart import Cart, CartItem, CartUser
from src.database.models.product import Product
from src.database.models.store import Store
from src.database.models.user import User
from src.shared.error_handler import handle_service_errors
from src.shared.exceptions import (
    ConflictException,
    ForbiddenException,
    ResourceNotFoundException,
    ValidationException,
)


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
                    Cart.status == CartStatus.ACTIVE,
                )
            )
            existing_cart_result = await session.execute(existing_cart_query)
            existing_cart = existing_cart_result.scalars().first()

            if existing_cart:
                raise ConflictException(
                    detail=f"An active cart with the name '{cart_data.name}' already exists"
                )

            # Create cart
            new_cart = Cart(
                name=cart_data.name,
                description=cart_data.description,
                created_by=user_id,
                status=CartStatus.ACTIVE,
            )
            session.add(new_cart)
            await session.flush()

            # Create owner permission
            cart_user = CartUser(
                cart_id=new_cart.id, user_id=user_id, role=CartUserRole.OWNER
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
                "items_count": 0,
            }

            return CartSchema.model_validate(cart_dict)

    @staticmethod
    @handle_service_errors("retrieving user carts")
    async def get_user_carts(user_id: str) -> CartListSchema:
        """Get all carts accessible to the user (owned + shared)"""
        async with AsyncSessionLocal() as session:
            # Get carts where user has access with all related data
            query = (
                select(Cart, CartUser.role)
                .join(CartUser, Cart.id == CartUser.cart_id)
                .where(CartUser.user_id == user_id)
                .options(selectinload(Cart.items), selectinload(Cart.users))
                .order_by(Cart.updated_at.desc())
            )

            result = await session.execute(query)
            cart_role_pairs = result.all()

            owned_carts = []
            shared_carts = []

            for cart, role in cart_role_pairs:
                # Convert cart items to CartItemDetailSchema
                items = []
                if cart.items:
                    for item in cart.items:
                        items.append(
                            CartItemDetailSchema(
                                id=item.id,
                                product_id=item.product_id,
                                quantity=item.quantity,
                                created_at=item.created_at,
                                updated_at=item.updated_at,
                            )
                        )

                # Convert cart users to CartUserSchema
                users = []
                if cart.users:
                    for cart_user in cart.users:
                        users.append(
                            CartUserSchema(
                                user_id=cart_user.user_id,
                                role=cart_user.role,
                                shared_at=cart_user.shared_at,
                            )
                        )

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
                    "role": role,
                    "items_count": len(items),
                }

                cart_schema = CartSchema.model_validate(cart_dict)

                if role == CartUserRole.OWNER:
                    owned_carts.append(cart_schema)
                else:
                    shared_carts.append(cart_schema)

            return CartListSchema(owned_carts=owned_carts, shared_carts=shared_carts)

    @staticmethod
    @handle_service_errors("retrieving cart details")
    async def get_cart_details(user_id: str, cart_id: int) -> CartSchema:
        """Get detailed cart information"""
        async with AsyncSessionLocal() as session:
            # Check user access
            user_role = await CartService._check_cart_access(session, user_id, cart_id)

            # Get cart with items and users
            query = (
                select(Cart)
                .where(Cart.id == cart_id)
                .options(selectinload(Cart.items), selectinload(Cart.users))
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
                "items_count": len(items),
            }

            return CartSchema.model_validate(cart_dict)

    @staticmethod
    @handle_service_errors("updating cart")
    async def update_cart(
        user_id: str, cart_id: int, cart_data: UpdateCartSchema
    ) -> CartSchema:
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
                        Cart.id != cart_id,  # Exclude current cart
                    )
                )
                existing_cart_result = await session.execute(existing_cart_query)
                existing_cart = existing_cart_result.scalars().first()

                if existing_cart:
                    raise ConflictException(
                        detail=f"An active cart with the name '{cart_data.name}' already exists"
                    )

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
    async def add_cart_item(
        user_id: str, cart_id: int, item_data: AddCartItemSchema
    ) -> CartItemDetailSchema:
        """Add item to cart (owner only)"""
        async with AsyncSessionLocal() as session:
            # Check owner access and cart status
            await CartService._check_cart_owner_access(session, user_id, cart_id)

            try:
                # Check if item already exists
                existing_query = select(CartItem).where(
                    and_(
                        CartItem.cart_id == cart_id,
                        CartItem.product_id == item_data.product_id,
                    )
                )
                existing_result = await session.execute(existing_query)
                existing_item = existing_result.scalar_one_or_none()

                if existing_item:
                    # Update quantity
                    new_quantity = existing_item.quantity + item_data.quantity
                    if new_quantity > 1000:
                        raise ValidationException(
                            detail="Total quantity would exceed maximum limit"
                        )

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
                        quantity=item_data.quantity,
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
    async def update_cart_item(
        user_id: str,
        cart_id: int,
        item_id: int,
        item_data: UpdateCartItemQuantitySchema,
    ) -> CartItemDetailSchema:
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
    async def reduce_cart_item_quantity(
        user_id: str, cart_id: int, item_id: int, quantity_to_reduce: int
    ) -> Optional[CartItemDetailSchema]:
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
                await session.execute(delete(CartItem).where(CartItem.id == item_id))
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
    async def reduce_cart_item_quantity_by_product(
        user_id: str, cart_id: int, product_id: int, quantity_to_reduce: int
    ) -> Optional[CartItemDetailSchema]:
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
                await session.execute(delete(CartItem).where(CartItem.id == item.id))
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
    async def remove_cart_item_by_product(
        user_id: str, cart_id: int, product_id: int
    ) -> None:
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
    async def share_cart(
        user_id: str, cart_id: int, share_data: ShareCartSchema
    ) -> Dict[str, Any]:
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
                and_(
                    CartUser.cart_id == cart_id, CartUser.user_id == share_data.user_id
                )
            )
            existing_result = await session.execute(existing_query)
            existing_share = existing_result.scalar_one_or_none()

            if existing_share:
                raise ConflictException(detail="Cart is already shared with this user")

            # Create share
            cart_user = CartUser(
                cart_id=cart_id, user_id=share_data.user_id, role=CartUserRole.VIEWER
            )
            session.add(cart_user)
            await session.commit()
            await session.refresh(cart_user)

            return {
                "cart_id": cart_id,
                "user_id": share_data.user_id,
                "role": CartUserRole.VIEWER,
                "shared_at": cart_user.shared_at,
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
                        CartUser.role == CartUserRole.VIEWER,
                    )
                )
            )

            if result.rowcount == 0:
                raise ResourceNotFoundException(detail="Cart sharing not found")

            await session.commit()

    @staticmethod
    @handle_service_errors("retrieving cart sharing details")
    async def get_cart_sharing_details(
        user_id: str, cart_id: int
    ) -> CartSharingDetailsSchema:
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
                shared_with.append(
                    {
                        "cart_id": cart_id,
                        "user_id": share.user_id,
                        "role": share.role,
                        "shared_at": share.shared_at,
                    }
                )

            return CartSharingDetailsSchema(cart_id=cart_id, shared_with=shared_with)

    @staticmethod
    @handle_service_errors("retrieving available carts for checkout")
    async def get_available_carts_for_checkout(user_id: str) -> List[Dict[str, Any]]:
        """Get carts available for checkout"""
        async with AsyncSessionLocal() as session:
            # Get active carts with access
            query = (
                select(Cart, CartUser.role)
                .join(CartUser, Cart.id == CartUser.cart_id)
                .where(
                    and_(CartUser.user_id == user_id, Cart.status == CartStatus.ACTIVE)
                )
                .options(selectinload(Cart.items))
            )

            result = await session.execute(query)
            cart_role_pairs = result.all()

            available_carts = []
            for cart, role in cart_role_pairs:
                available_carts.append(
                    {
                        "id": cart.id,
                        "name": cart.name,
                        "role": role,
                        "items_count": len(cart.items),
                        "can_checkout": len(cart.items) > 0,
                    }
                )

            return available_carts

    @staticmethod
    async def validate_checkout_data(
        session, user_id: str, checkout_data: MultiCartCheckoutSchema
    ) -> Dict[str, Any]:
        """Validate user, location, and carts for checkout. Returns validation data."""
        validation_result = {
            "user": None,
            "user_tier_id": None,
            "location_obj": None,
            "cart_role_pairs": [],
            "cart_item_mapping": {},
            "all_product_ids": [],
        }

        # STEP 1: Get user and tier
        user_query = select(User).where(User.firebase_uid == user_id)
        user_result = await session.execute(user_query)
        user = user_result.scalar_one_or_none()
        if not user:
            raise ValidationException(f"User {user_id} not found")

        validation_result["user"] = user
        validation_result["user_tier_id"] = user.tier_id

        # STEP 2: Validate location based on mode
        location_obj = None
        if checkout_data.location.mode in [FulfillmentMode.PICKUP.value, FulfillmentMode.FAR_DELIVERY.value]:
            if not checkout_data.location.address_id:
                raise ValidationException("address_id is required for delivery mode")

            location_query = select(Address).where(
                and_(
                    Address.id == checkout_data.location.address_id,
                    Address.user_id == user_id,
                )
            )
            location_result = await session.execute(location_query)
            location_obj = location_result.scalar_one_or_none()
            if not location_obj:
                raise ValidationException(
                    f"Address {checkout_data.location.address_id} not found or not owned by user"
                )
        elif checkout_data.location.mode == FulfillmentMode.PICKUP.value:
            if not checkout_data.location.store_id:
                raise ValidationException("store_id is required for pickup mode")

            location_query = select(Store).where(
                and_(Store.id == checkout_data.location.store_id, Store.is_active)
            )
            location_result = await session.execute(location_query)
            location_obj = location_result.scalar_one_or_none()
            if not location_obj:
                raise ValidationException(
                    f"Store {checkout_data.location.store_id} not found or inactive"
                )

        validation_result["location_obj"] = location_obj

        # STEP 3: Bulk fetch carts with items and user access validation
        carts_query = (
            select(Cart, CartUser.role)
            .join(CartUser, Cart.id == CartUser.cart_id)
            .where(
                and_(
                    Cart.id.in_(checkout_data.cart_ids),
                    Cart.status == CartStatus.ACTIVE,
                    CartUser.user_id == user_id,
                )
            )
            .options(selectinload(Cart.items))
        )

        carts_result = await session.execute(carts_query)
        cart_role_pairs = carts_result.all()
        if len(cart_role_pairs) != len(checkout_data.cart_ids):
            missing_carts = set(checkout_data.cart_ids) - {
                cart.id for cart, role in cart_role_pairs
            }
            raise ValidationException(
                f"Carts {missing_carts} not found or not accessible"
            )

        validation_result["cart_role_pairs"] = cart_role_pairs

        # STEP 4: Build cart item mapping and collect product IDs
        cart_item_mapping = {}
        all_product_ids = []

        for cart, role in cart_role_pairs:
            cart_item_mapping[cart.id] = {"cart": cart, "role": role}
            for item in cart.items:
                all_product_ids.append(item.product_id)

        validation_result["cart_item_mapping"] = cart_item_mapping
        validation_result["all_product_ids"] = all_product_ids

        return validation_result

    @staticmethod
    async def fetch_products_and_calculate_pricing_with_session(
        session, validation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fetch products and calculate pricing for cart items using provided session. Returns pricing data."""
        all_product_ids = validation_data["all_product_ids"]
        cart_item_mapping = validation_data["cart_item_mapping"]
        user_tier_id = validation_data["user_tier_id"]

        # STEP 1: Bulk fetch all products
        products_query = select(Product).where(Product.id.in_(all_product_ids))
        products_result = await session.execute(products_query)
        products_dict = {p.id: p for p in products_result.scalars().all()}

        # STEP 2: Prepare bulk pricing data
        product_data_for_pricing = []
        for cart_id, cart_data in cart_item_mapping.items():
            cart = cart_data["cart"]
            for item in cart.items:
                product = products_dict.get(item.product_id)
                if not product:
                    raise ValidationException(f"Product {item.product_id} not found")

                product_data_for_pricing.append(
                    {
                        "id": str(product.id),
                        "price": float(product.base_price),
                        "quantity": item.quantity,
                        "category_ids": [],  # TODO: Get actual category IDs if needed
                    }
                )

        # STEP 3: Calculate exact pricing using bulk pricing service
        from src.api.pricing.service import PricingService

        pricing_service = PricingService()
        pricing_results = await pricing_service.calculate_bulk_product_pricing(
            product_data_for_pricing, user_tier_id
        )

        return {
            "products_dict": products_dict,
            "pricing_results": pricing_results,
            "product_data_for_pricing": product_data_for_pricing,
        }

    @staticmethod
    async def fetch_products_and_calculate_pricing(
        validation_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fetch products and calculate pricing for cart items independently. Returns pricing data."""
        all_product_ids = validation_data["all_product_ids"]
        cart_item_mapping = validation_data["cart_item_mapping"]
        user_tier_id = validation_data["user_tier_id"]

        # STEP 1: Bulk fetch all products with own session
        async with AsyncSessionLocal() as session:
            products_query = select(Product).where(Product.id.in_(all_product_ids))
            products_result = await session.execute(products_query)
            products_dict = {p.id: p for p in products_result.scalars().all()}

        # STEP 2: Prepare bulk pricing data
        product_data_for_pricing = []
        for cart_id, cart_data in cart_item_mapping.items():
            cart = cart_data["cart"]
            for item in cart.items:
                product = products_dict.get(item.product_id)
                if not product:
                    raise ValidationException(f"Product {item.product_id} not found")

                product_data_for_pricing.append(
                    {
                        "id": str(product.id),
                        "price": float(product.base_price),
                        "quantity": item.quantity,
                        "category_ids": [],  # TODO: Get actual category IDs if needed
                    }
                )

        # STEP 3: Calculate pricing using pricing service (creates its own session)
        from src.api.pricing.service import PricingService

        pricing_service = PricingService()
        pricing_results = await pricing_service.calculate_bulk_product_pricing(
            product_data_for_pricing, user_tier_id
        )

        return {
            "products_dict": products_dict,
            "pricing_results": pricing_results,
            "product_data_for_pricing": product_data_for_pricing,
        }

    @staticmethod
    def build_cart_groups(
        validation_data: Dict[str, Any], pricing_data: Dict[str, Any]
    ) -> List[CartGroupSchema]:
        """Build cart groups with detailed pricing information."""
        cart_item_mapping = validation_data["cart_item_mapping"]
        products_dict = pricing_data["products_dict"]
        pricing_results = pricing_data["pricing_results"]

        cart_groups = []
        cart_item_index = 0

        for cart_id, cart_data in cart_item_mapping.items():
            cart = cart_data["cart"]
            cart_total = Decimal("0.00")
            cart_subtotal = Decimal("0.00")
            cart_total_savings = Decimal("0.00")
            cart_items = []

            # Process each item in this cart
            for item in cart.items:
                # Get corresponding pricing result
                pricing_result = pricing_results[cart_item_index]

                # Get product details from pre-fetched dict
                product = products_dict.get(item.product_id)
                if not product:
                    raise ValidationException(f"Product {item.product_id} not found")

                # Extract pricing information
                base_price = Decimal(str(pricing_result.base_price))
                final_price = Decimal(str(pricing_result.final_price))
                total_price = final_price * item.quantity
                savings_per_item = base_price - final_price
                total_savings_item = savings_per_item * item.quantity
                discount_percentage = (
                    Decimal(str(pricing_result.discount_percentage))
                    if hasattr(pricing_result, "discount_percentage")
                    else Decimal("0.00")
                )

                # Build applied discounts info
                applied_discounts = []
                if (
                    hasattr(pricing_result, "applied_discounts")
                    and pricing_result.applied_discounts
                ):
                    for discount in pricing_result.applied_discounts:
                        applied_discounts.append(
                            {
                                "price_list_name": discount.get(
                                    "price_list_name", "Unknown"
                                ),
                                "discount_type": discount.get("discount_type", ""),
                                "discount_value": discount.get("discount_value", 0),
                                "savings": float(savings_per_item),
                            }
                        )

                from src.api.users.models import CartItemPricingSchema

                cart_item_pricing = CartItemPricingSchema(
                    product_id=item.product_id,
                    product_name=product.name,
                    quantity=item.quantity,
                    base_price=float(base_price),
                    final_price=float(final_price),
                    total_price=float(total_price),
                    savings_per_item=float(savings_per_item),
                    total_savings=float(total_savings_item),
                    discount_percentage=float(discount_percentage),
                    applied_discounts=applied_discounts,
                )
                cart_items.append(cart_item_pricing)

                # Update cart totals
                cart_subtotal += base_price * item.quantity
                cart_total += total_price
                cart_total_savings += total_savings_item

                cart_item_index += 1

            # Create cart group
            cart_group = CartGroupSchema(
                cart_id=cart.id,
                cart_name=cart.name,
                items=cart_items,
                cart_subtotal=float(cart_subtotal),
                cart_total_savings=float(cart_total_savings),
                cart_total=float(cart_total),
            )
            cart_groups.append(cart_group)

        return cart_groups

    @staticmethod
    async def _check_cart_access(session, user_id: str, cart_id: int) -> CartUserRole:
        """Check if user has access to cart and return role"""
        query = select(CartUser.role).where(
            and_(CartUser.cart_id == cart_id, CartUser.user_id == user_id)
        )
        result = await session.execute(query)
        role = result.scalar_one_or_none()

        if not role:
            raise ForbiddenException(
                detail="You don't have permission to access this cart"
            )

        return role

    @staticmethod
    async def _check_cart_owner_access(session, user_id: str, cart_id: int) -> None:
        """Check if user is owner of cart and cart is modifiable"""
        # Check ownership
        query = (
            select(Cart, CartUser.role)
            .join(CartUser, Cart.id == CartUser.cart_id)
            .where(
                and_(
                    CartUser.cart_id == cart_id,
                    CartUser.user_id == user_id,
                    CartUser.role == CartUserRole.OWNER,
                )
            )
        )
        result = await session.execute(query)
        cart_role = result.first()

        if not cart_role:
            raise ForbiddenException(
                detail="You don't have permission to modify this cart"
            )

        cart, role = cart_role

        # Check if cart is modifiable
        if cart.status == CartStatus.ORDERED:
            raise ConflictException(
                detail="This cart has been ordered and cannot be modified"
            )

    @staticmethod
    @handle_service_errors("previewing multi-cart order")
    async def preview_multi_cart_order(
        user_id: str, checkout_data: MultiCartCheckoutSchema
    ) -> OrderPreviewSchema:
        """Preview multi-cart order with optimized bulk queries, exact pricing, and inventory validation"""
        from src.api.orders.services.store_selection_service import (
            StoreSelectionService,
        )
        from src.api.users.models import (
            InventoryValidationSummary,
        )

        async with AsyncSessionLocal() as session:
            # STEP 1: Validate checkout data (user, location, carts)
            validation_data = await CartService.validate_checkout_data(
                session, user_id, checkout_data
            )

            # STEP 2: Fetch products and calculate pricing
            pricing_data = (
                await CartService.fetch_products_and_calculate_pricing_with_session(
                    session, validation_data
                )
            )

            # STEP 3: Build cart groups with detailed pricing
            cart_groups = CartService.build_cart_groups(validation_data, pricing_data)

            # STEP 4: Handle inventory validation and store assignments
            location_obj = validation_data["location_obj"]
            store_selection_service = StoreSelectionService()
            is_nearby_store = True
            fulfillment_result = None
            can_fulfill = False
            unavailable_items = []

            cart_items_for_inventory = []
            for group in cart_groups:
                for item in group.items:
                    cart_items_for_inventory.append(
                        {"product_id": item.product_id, "quantity": item.quantity}
                    )

            if checkout_data.location.mode == FulfillmentMode.PICKUP.value:
                fulfillment_result = (
                    await store_selection_service.validate_pickup_store(
                        store_id=location_obj.id,
                        cart_items=cart_items_for_inventory,
                        session=session,
                    )
                )
                can_fulfill = fulfillment_result["all_items_available"]
                unavailable_items = fulfillment_result["unavailable_items"]
            elif checkout_data.location.mode == FulfillmentMode.DELIVERY.value and location_obj:
                fulfillment_result = (
                    await store_selection_service.select_stores_for_delivery(
                        address_id=location_obj.id,
                        cart_items=cart_items_for_inventory,
                        session=session,
                        mode=checkout_data.location.mode,
                    )
                )
                can_fulfill = len(fulfillment_result["unavailable_items"]) == 0
                unavailable_items = fulfillment_result["unavailable_items"]
                is_nearby_store = fulfillment_result.get("is_nearby_store", True)

            # Build inventory validation summary
            items_available = len(cart_items_for_inventory) - len(unavailable_items)
            inventory_validation = InventoryValidationSummary(
                can_fulfill_all=can_fulfill,
                items_checked=len(cart_items_for_inventory),
                items_available=items_available,
                items_out_of_stock=len(unavailable_items),
            )

            # Apply fulfillment status to cart items
            # This part is complex, so for now, we rely on the summary
            # A detailed per-item status can be added if needed by enhancing this section

            # STEP 5: Calculate totals and delivery charges
            total_amount = Decimal("0.00")
            total_savings = Decimal("0.00")
            items_count = 0

            for group in cart_groups:
                total_amount += Decimal(str(group.cart_total))
                total_savings += Decimal(str(group.cart_total_savings))
                items_count += len(group.items)

            delivery_charge = Decimal("0.00")
            if checkout_data.location.mode == FulfillmentMode.DELIVERY.value and fulfillment_result:
                store_assignments = []
                store_ids = [
                    int(sid)
                    for sid in fulfillment_result.get("store_assignments", {}).keys()
                ]
                if store_ids:
                    stores_query = select(Store).where(Store.id.in_(store_ids))
                    stores_result = await session.execute(stores_query)
                    stores_dict = {s.id: s for s in stores_result.scalars().all()}
                else:
                    stores_dict = {}

                primary_store_fallback = fulfillment_result.get("primary_store")

                for store_id, items in fulfillment_result.get(
                    "store_assignments", {}
                ).items():
                    store_id_int = int(store_id)
                    store = stores_dict.get(store_id_int)

                    if store:
                        store_lat = float(store.latitude)
                        store_lng = float(store.longitude)
                    elif primary_store_fallback:
                        store_lat = primary_store_fallback["latitude"]
                        store_lng = primary_store_fallback["longitude"]
                    else:
                        store_lat, store_lng = 0.0, 0.0

                    store_assignments.append(
                        {
                            "store_id": store_id_int,
                            "product_ids": [item["product_id"] for item in items],
                            "delivery_lat": float(location_obj.latitude),
                            "delivery_lng": float(location_obj.longitude),
                            "store_lat": store_lat,
                            "store_lng": store_lng,
                        }
                    )
                from src.api.orders.service import OrderService

                order_service = OrderService()
                delivery_charge = order_service.calculate_delivery_charge(
                    store_assignments, is_nearby_store, total_amount, items_count
                )

            # Calculate final totals
            subtotal = total_amount + total_savings
            final_total = total_amount + delivery_charge

            # Build pricing summary
            user_tier_id = validation_data["user_tier_id"]
            pricing_summary = {
                "items_count": items_count,
                "subtotal_before_discounts": float(subtotal),
                "total_discounts_applied": float(total_savings),
                "subtotal_after_discounts": float(total_amount),
                "delivery_charge": float(delivery_charge)
                if delivery_charge > 0
                else 0.0,
                "final_total": float(final_total),
                "user_tier_id": user_tier_id,
                "savings_percentage": float((total_savings / subtotal * 100))
                if subtotal > 0
                else 0.0,
            }

            return OrderPreviewSchema(
                cart_groups=cart_groups,
                subtotal=float(subtotal),
                total_savings=float(total_savings),
                delivery_charge=float(delivery_charge) if delivery_charge > 0 else None,
                total_amount=float(final_total),
                pricing_summary=pricing_summary,
                inventory_validation=inventory_validation,
                is_nearby_store=is_nearby_store,
            )
