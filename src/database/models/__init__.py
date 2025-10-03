# Import all models to ensure they are registered with SQLAlchemy
# This ensures all relationships can be resolved properly

from .address import Address
from .associations import product_categories
from .cart import Cart, CartItem, CartUser
from .category import Category
from .inventory import Inventory
from .order import Order, OrderItem
from .price_list import PriceList
from .price_list_line import PriceListLine
from .product import Product, ProductTag, Tag
from .store import Store
from .store_tag import StoreTag
from .tier import Tier
from .tier_benefit import Benefit, tier_benefits
from .tier_price_list import TierPriceList
from .user import User

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
    "StoreTag",
    "Inventory",
    "Order",
    "OrderItem",
]
