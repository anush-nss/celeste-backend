# Import all models to ensure they are registered with SQLAlchemy
# This ensures all relationships can be resolved properly

from .address import Address
from .associations import product_categories
from .cart import Cart, CartItem, CartUser
from .category import Category
from .favorite import Favorite
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
from .payment import PaymentTransaction
from .user import User
from .product_vector import ProductVector
from .search_interaction import SearchInteraction
from .user_preference import UserPreference
from .product_interaction import ProductInteraction
from .product_popularity import ProductPopularity
from .search_suggestion import SearchSuggestion

__all__ = [
    "User",
    "Address",
    "Cart",
    "CartUser",
    "CartItem",
    "Category",
    "Favorite",
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
    "PaymentTransaction",
    "ProductVector",
    "SearchInteraction",
    "UserPreference",
    "ProductInteraction",
    "ProductPopularity",
    "SearchSuggestion",
]
