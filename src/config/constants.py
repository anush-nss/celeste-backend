from enum import Enum


class UserRole(str, Enum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"


class DiscountType(str, Enum):
    PERCENTAGE = "PERCENTAGE"
    FLAT = "FLAT"


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    PACKED = "packed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class FulfillmentMode(str, Enum):
    PICKUP = "pickup"
    DELIVERY = "delivery"
    FAR_DELIVERY = "far_delivery"


class OdooSyncStatus(str, Enum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"


# Default fallback tier when no default tier is found in database
DEFAULT_FALLBACK_TIER = "BRONZE"


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
    CARTS = "carts"
    CART_USERS = "cart_users"
    CART_ITEMS = "cart_items"


# Store-related constants
class StoreFeatures(str, Enum):
    PARKING = "parking"
    WIFI = "wifi"
    WHEELCHAIR_ACCESSIBLE = "wheelchair_accessible"
    DRIVE_THROUGH = "drive_through"
    PICKUP_AVAILABLE = "pickup_available"
    DELIVERY_AVAILABLE = "delivery_available"


class StoreSort(str, Enum):
    DISTANCE = "distance"
    NAME = "name"


# Location and radius constants
DEFAULT_SEARCH_RADIUS_KM = 10.0
MAX_SEARCH_RADIUS_KM = 50.0
DEFAULT_STORES_LIMIT = 20
MAX_STORES_LIMIT = 100

# Default fallback stores for distant users (when no stores found in radius)
DEFAULT_STORE_IDS = [1]

# Products with this tag ID will NOT show inventory from default stores
# These are typically next-day delivery products that can't serve distant users
NEXT_DAY_DELIVERY_ONLY_TAG_ID = 1

# Geospatial constants (removed geohash functionality)

# Coordinate validation
MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0

# Distance calculation precision (kilometers)
DISTANCE_PRECISION = 0.1

# Business hours format
HOUR_FORMAT = "%H:%M"


# Cart-related constants
class CartStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ORDERED = "ordered"


class CartUserRole(str, Enum):
    OWNER = "owner"
    VIEWER = "viewer"


# Odoo-related constants
DELIVERY_PRODUCT_ODOO_ID = 20906


# Cache invalidation scope constants
class CacheScopes(str, Enum):
    SPECIFIC = "specific"
    DOMAIN = "domain"
    CROSS_DOMAIN = "cross_domain"
    GLOBAL = "global"
