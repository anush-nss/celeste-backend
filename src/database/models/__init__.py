# Import all models to ensure they are registered with SQLAlchemy
# This ensures all relationships can be resolved properly

from .user import User
from .address import Address
from .cart import Cart, CartUser, CartItem
from .category import Category
from .product import Product, Tag, ProductTag
from .associations import product_categories
from .tier import Tier
from .tier_benefit import Benefit, tier_benefits
from .price_list import PriceList
from .price_list_line import PriceListLine
from .tier_price_list import TierPriceList
from .store import Store
from .inventory import Inventory
from .order import Order, OrderItem

__all__ = [
    "User",
    "Address",
    "Cart",
    "CartUser",
    "CartItem",
    "Category",
    "Product",
    "Tag",
    "ProductTag",
    "product_categories",
    "Tier",
    "Benefit",
    "tier_benefits",
    "PriceList",
    "PriceListLine",
    "TierPriceList",
    "Store",
    "Inventory",
    "Order",
    "OrderItem",
]