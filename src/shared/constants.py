from enum import Enum

class UserRole(str, Enum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"

class DiscountType(str, Enum):
    PERCENTAGE = "PERCENTAGE"
    FLAT = "FLAT"

class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"

class CustomerTier(str, Enum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"

class PriceListType(str, Enum):
    PRODUCT = "product"
    CATEGORY = "category"
    ALL = "all"

class Collections(str, Enum):
    USERS = "users"
    PRODUCTS = "products"
    ORDERS = "orders"
    CATEGORIES = "categories"
    DISCOUNTS = "discounts"
    INVENTORY = "inventory"
    STORES = "stores"
    PROMOTIONS = "promotions"
    PRICE_LISTS = "price_lists"
    PRICE_LIST_LINES = "price_list_lines"
    CUSTOMER_TIERS = "customer_tiers"
