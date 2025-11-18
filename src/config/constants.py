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
    DELIVERY = "delivery"
    PICKUP = "pickup"
    FAR_DELIVERY = "far_delivery"


class DeliveryServiceLevel(str, Enum):
    PRIORITY = "priority"
    PREMIUM = "premium"
    STANDARD = "standard"


class OdooSyncStatus(str, Enum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"


class PromotionType(str, Enum):
    BANNER = "banner"
    POPUP = "popup"
    SEARCH = "search"


class Platform(str, Enum):
    WEB = "web"
    ANDROID = "android"
    IOS = "ios"


# Default fallback tier when no default tier is found in database
DEFAULT_FALLBACK_TIER_ID = 1


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


# ============================================================================
# SEARCH & PERSONALIZATION CONSTANTS
# ============================================================================


# Search modes
class SearchMode(str, Enum):
    DROPDOWN = "dropdown"
    FULL = "full"


# Search configuration
SEARCH_VECTOR_DIM = 384  # MiniLM embedding dimension
SEARCH_TFIDF_MAX_FEATURES = 5000  # Maximum features for TF-IDF vectorizer
SEARCH_MIN_QUERY_LENGTH = 2  # Minimum query length for search
SEARCH_MAX_QUERY_LENGTH = 200  # Maximum query length
SEARCH_DROPDOWN_LIMIT = 5  # Max results for dropdown mode
SEARCH_FULL_DEFAULT_LIMIT = 20  # Default limit for full search
SEARCH_FULL_MAX_LIMIT = 100  # Max limit for full search

# Hybrid search weights
SEARCH_HYBRID_WEIGHT_TFIDF = 0.3  # Weight for TF-IDF score
SEARCH_HYBRID_WEIGHT_SEMANTIC = 0.7  # Weight for semantic similarity

# Sentence transformer model
SENTENCE_TRANSFORMER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SENTENCE_TRANSFORMER_BATCH_SIZE = (
    8  # Batch size for vectorization (low-memory optimized)
)


# Interaction types and scoring
class InteractionType(str, Enum):
    SEARCH_CLICK = "search_click"
    VIEW = "view"
    CART_ADD = "cart_add"
    WISHLIST_ADD = "wishlist_add"
    ORDER = "order"


# Interaction scores (weighted importance)
INTERACTION_SCORES = {
    InteractionType.SEARCH_CLICK: 1.0,
    InteractionType.VIEW: 2.0,
    InteractionType.CART_ADD: 5.0,
    InteractionType.WISHLIST_ADD: 3.0,
    InteractionType.ORDER: 10.0,
}

# User interaction tracking
MAX_USER_INTERACTIONS = 100  # Keep last 100 interactions for personalization
INTERACTION_DECAY_DAYS = 30  # Apply time decay after 30 days


# Popularity modes
class PopularityMode(str, Enum):
    TRENDING = "trending"  # Time-decayed recent activity
    MOST_VIEWED = "most_viewed"  # Most viewed products
    MOST_CARTED = "most_carted"  # Most added to cart
    MOST_ORDERED = "most_ordered"  # Best sellers
    MOST_SEARCHED = "most_searched"  # Most searched products
    OVERALL = "overall"  # Overall popularity score


# Time windows for popularity
class TimeWindow(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    ALL_TIME = "all_time"


# Time window to hours mapping
TIME_WINDOW_HOURS = {
    TimeWindow.DAY: 24,
    TimeWindow.WEEK: 168,
    TimeWindow.MONTH: 720,
    TimeWindow.ALL_TIME: None,  # No time limit
}

# Popularity calculation settings
POPULARITY_MIN_INTERACTIONS = 5  # Minimum interactions to be considered popular
POPULARITY_TIME_DECAY_HOURS = 72  # Half-life for trending score (3 days)
TRENDING_RECENT_DAYS = 7  # Consider last 7 days for trending
POPULARITY_DEFAULT_LIMIT = 20  # Default number of popular products
POPULARITY_MAX_LIMIT = 100  # Maximum popular products per request
POPULARITY_WEIGHT_SEARCHES = 1.0

# Trending score decay (exponential decay factor)
TRENDING_DECAY_HALF_LIFE_HOURS = 72  # Half-life of 3 days


# Personalization settings
PERSONALIZATION_MIN_INTERACTIONS = 5  # Minimum interactions before personalizing
PERSONALIZATION_CATEGORY_WEIGHT = 1.0  # Weight for category affinity
PERSONALIZATION_VECTOR_WEIGHT = 1.5  # Weight for vector similarity
PERSONALIZATION_BRAND_WEIGHT = 0.5  # Weight for brand affinity
PERSONALIZATION_SEARCH_WEIGHT = 0.3  # Weight for search keyword matching
PERSONALIZATION_DIVERSITY_THRESHOLD = 0.7  # Threshold for diversity filtering

# Final product ranking weights (when personalizing)
RANKING_BASE_RELEVANCE_WEIGHT = 0.5  # Price, inventory, etc.
RANKING_PERSONALIZATION_WEIGHT = 0.3  # User preferences
RANKING_POPULARITY_WEIGHT = 0.2  # Global popularity

# Diversity settings
MAX_PRODUCTS_PER_CATEGORY_IN_RESULTS = 3  # Max products from same category in top 20
PERSONALIZATION_RECENT_ORDER_MULTIPLIER = (
    0.3  # Reduce score by 70% for recently ordered items
)
RECENT_ORDER_DAYS_THRESHOLD = 30  # Consider orders in last 30 days as "recent"

# Collaborative filtering
COLLABORATIVE_MIN_COMMON_USERS = 3  # Min users who interacted with both products
COLLABORATIVE_TOP_SIMILAR_PRODUCTS = 20  # Store top 20 similar products per product
COLLABORATIVE_RECOMMENDATION_LIMIT = 10  # Default recommendations to return

# Cold start handling
COLD_START_MIN_INTERACTIONS = 5  # Min interactions before personalization kicks in
COLD_START_FALLBACK_TO_POPULAR = True  # Show popular items for new users

# Background task schedules (in seconds for APScheduler)
TASK_UPDATE_POPULARITY_INTERVAL = 1800  # 30 minutes
TASK_UPDATE_USER_PREFERENCES_INTERVAL = 300  # 5 minutes
TASK_CALCULATE_ITEM_SIMILARITY_INTERVAL = 86400  # 24 hours
TASK_CLEANUP_OLD_INTERACTIONS_INTERVAL = 3600  # 1 hour

# Cache TTLs (in seconds)
CACHE_TTL_PRODUCT_VECTORS = 3600  # 1 hour
CACHE_TTL_POPULAR_PRODUCTS = 900  # 15 minutes
CACHE_TTL_SEARCH_SUGGESTIONS = 1800  # 30 minutes
CACHE_TTL_USER_PREFERENCES = 300  # 5 minutes
CACHE_TTL_ITEM_SIMILARITY = 7200  # 2 hours

# Search suggestions
MIN_SEARCH_COUNT_FOR_SUGGESTION = 5  # Min times searched to become a suggestion
MIN_SUCCESS_RATE_FOR_SUGGESTION = 0.1  # Min 10% click-through rate
