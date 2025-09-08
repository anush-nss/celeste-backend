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

# Geospatial constants
GEOHASH_PRECISION = 9
EARTH_RADIUS_KM = 6371.0

# Cache optimization constants
CACHE_GEOCODE_PRECISION = (
    4  # Geohash precision for cache keys (4 = ~20km, 5 = ~2.4km, 6 = ~610m)
)
CACHE_RADIUS_PRECISION = 1  # Decimal places for radius in cache keys

# Coordinate validation
MIN_LATITUDE = -90.0
MAX_LATITUDE = 90.0
MIN_LONGITUDE = -180.0
MAX_LONGITUDE = 180.0

# Distance calculation precision (kilometers)
DISTANCE_PRECISION = 0.1

# Business hours format
HOUR_FORMAT = "%H:%M"

# Default cache TTL for stores (in seconds)
STORES_CACHE_TTL = 300  # 5 minutes
