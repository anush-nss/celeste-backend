# Search & Personalization System - Implementation Status

**Date:** 2025-10-20
**Author:** Claude Code
**Status:** 🟡 In Progress (Search Complete, Personalization Pending)

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [✅ Completed Components](#-completed-components)
3. [🔨 Pending Components](#-pending-components)
4. [Setup & Configuration](#setup--configuration)
5. [Testing & Verification](#testing--verification)
6. [File Structure](#file-structure)
7. [API Documentation](#api-documentation)
8. [Database Schema](#database-schema)

---

## Overview

This document tracks the implementation of an advanced search and personalization system for the Celeste e-commerce platform. The system includes:

- **Vector-based semantic search** using sentence transformers
- **Hybrid search** combining AI embeddings + keyword matching
- **User interaction tracking** for personalization
- **Collaborative filtering** for recommendations
- **Popular products** ranking system
- **Real-time search suggestions** (as-you-type)

### Technology Stack

- **Embeddings:** sentence-transformers (all-MiniLM-L6-v2, 384 dimensions)
- **Vector DB:** PostgreSQL with pgvector extension
- **Search:** Hybrid (70% semantic, 30% keyword)
- **Background Tasks:** APScheduler (Cloud Run compatible)
- **Tracking:** User interactions stored for last 100 actions

---

## ✅ Completed Components

### 1. Constants & Configuration ✅

**File:** `src/config/constants.py`

**Added:**
- Search modes (`SearchMode.DROPDOWN`, `SearchMode.FULL`)
- Vector dimensions (`SEARCH_VECTOR_DIM = 384`)
- Interaction types and scores
- Popularity modes and time windows
- Personalization weights
- Background task intervals
- All configurable constants (no hardcoded values)

**Key Constants:**
```python
SENTENCE_TRANSFORMER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SEARCH_HYBRID_WEIGHT_SEMANTIC = 0.7
SEARCH_HYBRID_WEIGHT_TFIDF = 0.3
MAX_USER_INTERACTIONS = 100
INTERACTION_SCORES = {
    InteractionType.SEARCH_CLICK: 1.0,
    InteractionType.VIEW: 2.0,
    InteractionType.CART_ADD: 5.0,
    InteractionType.WISHLIST_ADD: 3.0,
    InteractionType.ORDER: 10.0,
}
```

---

### 2. Database Models ✅

**Files:** `src/database/models/`

#### ProductVector Model
**File:** `product_vector.py`

Stores vector embeddings for semantic search.

**Fields:**
- `product_id` (FK to products, unique)
- `vector_embedding` (vector(384)) - Semantic embedding
- `tfidf_vector` (JSONB) - TF-IDF representation
- `text_content` (TEXT) - Combined searchable text
- `last_updated` (TIMESTAMP)
- `version` (INT) - Model version tracking

**Text Content Includes:**
- Product name (weighted 3x)
- Description
- Brand (weighted 2x)
- Category names (weighted 2x)
- Category descriptions
- Tag names (excluding NEXT_DAY_DELIVERY_ONLY)

#### SearchInteraction Model
**File:** `search_interaction.py`

Tracks all user searches (authenticated users only).

**Fields:**
- `user_id` (required) - Firebase UID
- `query` (TEXT) - Search query
- `mode` (VARCHAR) - 'dropdown' or 'full'
- `results_count` (INT)
- `clicked_product_ids` (ARRAY[INT])
- `timestamp` (TIMESTAMP)
- `extra_data` (JSONB) - Filters, search time, etc.

#### UserPreference Model
**File:** `user_preference.py`

Aggregated user interests for personalization.

**Fields:**
- `user_id` (unique) - Firebase UID
- `interest_vector` (vector(384)) - Weighted average of interactions
- `category_scores` (JSONB) - {category_id: score}
- `brand_scores` (JSONB) - {brand: score}
- `search_keywords` (JSONB) - {keyword: frequency}
- `last_updated` (TIMESTAMP)
- `total_interactions` (INT)

#### ProductInteraction Model
**File:** `product_interaction.py`

Detailed interaction tracking for collaborative filtering.

**Fields:**
- `user_id` (required)
- `product_id` (FK)
- `interaction_type` (VARCHAR) - search_click, view, cart_add, order, wishlist_add
- `interaction_score` (FLOAT) - Weighted score
- `timestamp` (TIMESTAMP)
- `extra_data` (JSONB)

#### ProductPopularity Model
**File:** `product_popularity.py`

Aggregated popularity metrics.

**Fields:**
- `product_id` (unique, FK)
- `search_count` (INT)
- `search_click_count` (INT)
- `view_count` (INT)
- `cart_add_count` (INT)
- `order_count` (INT)
- `popularity_score` (FLOAT) - Weighted aggregate
- `trending_score` (FLOAT) - Time-decayed score
- `last_updated` (TIMESTAMP)

#### SearchSuggestion Model
**File:** `search_suggestion.py`

Popular search queries for autocomplete.

**Fields:**
- `query` (VARCHAR, unique)
- `search_count` (INT)
- `success_rate` (FLOAT) - Click-through rate (0.0 to 1.0)
- `last_searched` (TIMESTAMP)
- `is_trending` (BOOLEAN)

**All models registered in:** `src/database/models/__init__.py`

---

### 3. Database Migrations ✅

**Files:** `migrations/`

#### Migration Script
**File:** `001_search_personalization_tables.sql`

**Creates:**
- All 6 tables with proper indexes
- pgvector extension
- IVFFlat index for fast vector similarity search
- Full-text search indexes
- Composite indexes for complex queries

**Run with:**
```bash
psql -d your_database -f migrations/001_search_personalization_tables.sql
```

#### Rollback Script
**File:** `001_search_personalization_tables_rollback.sql`

Drops all search/personalization tables (use with caution).

---

### 4. VectorService ✅

**File:** `src/api/products/services/vector_service.py`

Service for creating and managing product embeddings.

**Features:**
- Lazy-loads sentence transformer model
- Builds comprehensive searchable text for products
- Batch vectorization for efficiency
- Single product vectorization
- Update/delete vector operations
- Excludes NEXT_DAY_DELIVERY_ONLY tag from text

**Key Methods:**
```python
async def vectorize_product(product_id: int) -> bool
async def vectorize_products_batch(product_ids: List[int]) -> dict
async def vectorize_all_products() -> dict
async def update_product_vector(product_id: int) -> bool
async def delete_product_vector(product_id: int) -> bool
```

**Batch Processing:**
- Default batch size: 32 products
- Progress bar during vectorization
- Error handling per product
- Returns success/failed/skipped counts

---

### 5. Vectorization Script ✅

**File:** `scripts/db/vectorize_products.py`

Command-line tool for vectorizing products.

**Usage:**
```bash
# Vectorize all products
python scripts/db/vectorize_products.py

# Re-vectorize all (force update)
python scripts/db/vectorize_products.py --force

# Vectorize specific product
python scripts/db/vectorize_products.py --product-id 123
```

**Features:**
- Progress reporting
- Success/failure statistics
- Model auto-download (~80MB on first run)
- Comprehensive error handling

---

### 6. SearchService ✅

**File:** `src/api/search/service.py`

Core search functionality with hybrid algorithm.

**Features:**

#### Hybrid Search Algorithm
- **70% Semantic Similarity:** Uses sentence transformers + cosine distance
- **30% Keyword Matching:** PostgreSQL full-text search with ts_rank
- **pgvector Integration:** Fast IVFFlat index for similarity search
- **Minimum Threshold:** 0.1 similarity score

**Search SQL:**
```sql
WITH ranked_products AS (
    SELECT
        pv.product_id,
        1 - (pv.vector_embedding <=> :query_vector::vector) AS similarity,
        ts_rank(to_tsvector('english', pv.text_content), plainto_tsquery('english', :query)) AS keyword_rank
    FROM product_vectors pv
)
SELECT product_id, (:semantic_weight * similarity + :keyword_weight * keyword_rank) AS combined_score
FROM ranked_products
WHERE similarity > 0.1 OR keyword_rank > 0
ORDER BY combined_score DESC
```

#### Search Modes

**Dropdown Mode:**
- Returns: Search suggestions + top 5 products
- Lightweight product data (id, name, image, prices)
- Optimized for as-you-type experience

**Full Mode:**
- Returns: Complete product data with all relationships
- Supports filters (categories, price range, inventory)
- Comprehensive EnhancedProductSchema

#### Search Tracking
- Tracks all searches for authenticated users
- Records query, mode, results count, timestamp
- Async tracking (doesn't slow down search)
- Metadata includes filters and search time

**Key Methods:**
```python
async def search_products(...) -> dict
async def _search_dropdown(...) -> dict
async def _search_full(...) -> dict
async def _search_hybrid(...) -> List[EnhancedProductSchema]
async def _get_search_suggestions(...) -> List[dict]
async def track_search_click(user_id, query, product_id) -> bool
```

---

### 7. Search API Endpoints ✅

**File:** `src/api/search/routes.py`

**Endpoints:**

#### GET /products/search
Main search endpoint with two modes.

**Query Parameters:**
- `q` (required) - Search query (min 2 chars)
- `mode` - 'dropdown' or 'full' (default: full)
- `limit` - Max results (5 for dropdown, 20 for full)
- `include_pricing` - Include pricing info (default: true)
- `include_categories` - Include categories (default: false)
- `include_tags` - Include tags (default: false)
- `include_inventory` - Include inventory (default: true)
- `category_ids` - Filter by categories
- `min_price` / `max_price` - Price range filter
- `latitude` / `longitude` - Location for inventory

**Examples:**
```bash
# Dropdown search (as-you-type)
GET /products/search?q=org&mode=dropdown

# Full search
GET /products/search?q=organic milk&mode=full&limit=20

# Search with filters
GET /products/search?q=coffee&category_ids=5&min_price=10&max_price=50

# Search with location
GET /products/search?q=milk&latitude=6.9271&longitude=79.8612
```

**Response (Dropdown):**
```json
{
  "success": true,
  "data": {
    "suggestions": [
      {"query": "organic milk", "type": "popular", "search_count": 245}
    ],
    "products": [
      {
        "id": 123,
        "name": "Organic Milk 1L",
        "ref": "MLK001",
        "image_url": "https://...",
        "base_price": 5.99,
        "final_price": 5.49
      }
    ],
    "total_results": 5,
    "search_metadata": {
      "query": "org",
      "search_time_ms": 45.2,
      "mode": "dropdown"
    }
  }
}
```

**Response (Full):**
```json
{
  "success": true,
  "data": {
    "products": [
      {
        "id": 123,
        "name": "Organic Milk 1L",
        // ... full EnhancedProductSchema
        "pricing": { ... },
        "inventory": { ... },
        "categories": [ ... ]
      }
    ],
    "total_results": 15,
    "search_metadata": {
      "query": "organic milk",
      "search_time_ms": 78.5,
      "mode": "full"
    }
  }
}
```

#### POST /products/search/click
Track search result clicks (requires authentication).

**Request Body:**
```json
{
  "query": "organic milk",
  "product_id": 123
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "message": "Search click tracked successfully"
  }
}
```

---

### 8. Pydantic Models ✅

**File:** `src/api/search/models.py`

**Models:**
- `SearchQuerySchema` - Request validation
- `SearchSuggestionSchema` - Suggestion format
- `DropdownProductSchema` - Lightweight product for dropdown
- `SearchMetadataSchema` - Search analytics
- `SearchDropdownResponse` - Dropdown response
- `SearchFullResponse` - Full search response
- `SearchClickSchema` - Click tracking request
- `SearchClickResponse` - Click tracking response

---

### 9. Router Registration ✅

**File:** `main.py`

Search router registered and available at `/products/search`.

---

## 🔨 Pending Components

### 1. PopularityService 🔲

**Location:** `src/api/products/services/popularity_service.py`

**Responsibilities:**
- Calculate product popularity scores
- Track trending products (time-decayed)
- Aggregate interaction metrics
- Update `product_popularity` table

**Methods to Implement:**
```python
async def get_popular_products(
    mode: PopularityMode,
    time_window: TimeWindow,
    limit: int,
    category_ids: Optional[List[int]] = None,
    customer_tier: Optional[int] = None,
    store_ids: Optional[List[int]] = None,
) -> List[EnhancedProductSchema]

async def update_product_popularity(
    product_id: int,
    interaction_type: InteractionType
) -> bool

async def calculate_popularity_scores() -> dict

async def calculate_trending_scores() -> dict
```

**Popularity Score Formula:**
```python
popularity_score = (
    POPULARITY_WEIGHT_ORDERS * order_count +
    POPULARITY_WEIGHT_CART_ADDS * cart_add_count +
    POPULARITY_WEIGHT_VIEWS * view_count +
    POPULARITY_WEIGHT_SEARCHES * search_count
)
```

**Trending Score Formula:**
```python
# Exponential decay based on time
time_decay = exp(-time_hours / TRENDING_DECAY_HALF_LIFE_HOURS)
trending_score = popularity_score * time_decay
```

---

### 2. Popular Products Endpoint 🔲

**Location:** `src/api/products/routes.py`

**Endpoint:** `GET /products/popular`

**Query Parameters:**
- `mode` - 'best_sellers', 'most_searched', 'trending', 'most_added_to_cart'
- `time_window` - 'day', 'week', 'month', 'all_time'
- `limit` - Max results (default: 20)
- `category_ids` - Filter by categories
- `include_pricing` - Include pricing (default: true)
- `include_inventory` - Include inventory (default: true)
- `latitude` / `longitude` - For inventory lookup

**Response Format:**
```json
{
  "success": true,
  "data": {
    "products": [
      {
        "id": 456,
        "name": "Premium Coffee Beans",
        // ... full EnhancedProductSchema
        "popularity_metrics": {
          "order_count": 342,
          "popularity_score": 8.7,
          "trending_score": 9.2
        }
      }
    ],
    "mode": "best_sellers",
    "time_window": "week",
    "total_results": 20
  }
}
```

**Implementation Steps:**
1. Create `PopularityService`
2. Add route to `products_router`
3. Create Pydantic models for request/response
4. Implement background task to update popularity scores

---

### 3. PersonalizationService 🔲

**Location:** `src/api/personalization/service.py` (new directory)

**Responsibilities:**
- Build user preference vectors
- Calculate personalization scores
- Update user preferences from interactions
- Apply diversity filters
- Cold start handling

**Methods to Implement:**
```python
async def get_user_preferences(user_id: str) -> Optional[UserPreference]

async def update_user_preferences(
    user_id: str,
    interaction_type: InteractionType,
    product_ids: List[int]
) -> bool

async def calculate_personalization_scores(
    user_id: str,
    products: List[EnhancedProductSchema]
) -> List[float]

async def apply_diversity_filter(
    products: List[EnhancedProductSchema],
    user_id: str
) -> List[EnhancedProductSchema]

async def get_personalized_product_ranking(
    user_id: str,
    products: List[EnhancedProductSchema],
    base_scores: Optional[List[float]] = None
) -> List[EnhancedProductSchema]
```

**Personalization Score Formula:**
```python
personalization_score = (
    PERSONALIZATION_CATEGORY_WEIGHT * category_affinity +
    PERSONALIZATION_BRAND_WEIGHT * brand_affinity +
    PERSONALIZATION_VECTOR_WEIGHT * vector_similarity +
    PERSONALIZATION_RECENCY_WEIGHT * recency_boost
)
```

**Diversity Filter Logic:**
- Max 3 products per category in top 20
- Penalize recently ordered products (0.3x score)
- Boost variety across brands

---

### 4. Update GET /products/ for Personalization 🔲

**Location:** `src/api/products/routes.py` and `src/api/products/services/query_service.py`

**Changes Needed:**

1. **Detect authenticated user in route**
2. **Pass user_id to query service**
3. **In query service, check if user has preferences**
4. **If yes, apply personalization scoring**
5. **Re-rank products based on final score**

**Final Ranking Formula:**
```python
final_score = (
    RANKING_BASE_RELEVANCE_WEIGHT * base_score +      # 0.5
    RANKING_PERSONALIZATION_WEIGHT * personalization_score +  # 0.3
    RANKING_POPULARITY_WEIGHT * popularity_score      # 0.2
)
```

**Implementation:**
```python
# In get_all_products route
user_id = current_user.uid if current_user else None

# In query service
if user_id and personalization_enabled:
    products = await personalization_service.get_personalized_product_ranking(
        user_id=user_id,
        products=products,
        base_scores=relevance_scores
    )
```

---

### 5. Interaction Tracking Helpers 🔲

**Location:** `src/api/interactions/` (new directory)

**Purpose:** Centralized interaction tracking across the app

**Files to Create:**

#### `service.py`
```python
class InteractionService:
    async def track_cart_add(user_id: str, product_id: int, cart_id: int)
    async def track_order(user_id: str, product_ids: List[int], order_id: int)
    async def track_view(user_id: str, product_id: int)
    async def track_wishlist_add(user_id: str, product_id: int)
```

#### `middleware.py`
Optional middleware to auto-track certain interactions.

**Integration Points:**

1. **Cart Service:** Call `track_cart_add()` when adding to cart
2. **Order Service:** Call `track_order()` when order confirmed
3. **Product Routes:** Call `track_view()` when GET /{id} or /ref/{ref}

---

### 6. APScheduler Background Tasks 🔲

**Location:** `src/scheduler/` (new directory)

**Purpose:** Periodic background tasks for Cloud Run

**Files to Create:**

#### `scheduler.py`
```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# Update popularity scores every 30 minutes
@scheduler.scheduled_job('interval', seconds=TASK_UPDATE_POPULARITY_INTERVAL)
async def update_popularity():
    # Aggregate interaction counts
    # Calculate popularity scores
    # Update product_popularity table

# Update user preferences every 5 minutes
@scheduler.scheduled_job('interval', seconds=TASK_UPDATE_USER_PREFERENCES_INTERVAL)
async def update_user_preferences():
    # Get users with recent interactions
    # Recalculate preference vectors
    # Update user_preferences table

# Calculate item similarity daily at 2 AM
@scheduler.scheduled_job('cron', hour=2, minute=0)
async def calculate_item_similarity():
    # Build user-item interaction matrix
    # Calculate product similarity
    # Store for collaborative filtering

# Cleanup old interactions hourly
@scheduler.scheduled_job('interval', seconds=TASK_CLEANUP_OLD_INTERACTIONS_INTERVAL)
async def cleanup_old_interactions():
    # Keep only last 100 interactions per user
    # Delete old search interactions (>90 days)

# Update search suggestions every 30 minutes
@scheduler.scheduled_job('interval', seconds=1800)
async def update_search_suggestions():
    # Aggregate search queries
    # Calculate success rates
    # Update search_suggestions table
```

#### `tasks/` (directory)
Individual task modules:
- `popularity_tasks.py`
- `preference_tasks.py`
- `similarity_tasks.py`
- `cleanup_tasks.py`

#### Integration in `main.py`
```python
from src.scheduler.scheduler import scheduler

@app.on_event("startup")
async def startup_event():
    scheduler.start()

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
```

---

### 7. Collaborative Filtering (Optional) 🔲

**Location:** `src/api/recommendations/` (new directory)

**Purpose:** Item-based collaborative filtering for "Customers who bought this also bought"

**Algorithm:**
1. Build user-item interaction matrix
2. Calculate item-item similarity (cosine similarity)
3. For each product, store top 20 similar products
4. Use for recommendations

**Files to Create:**

#### `service.py`
```python
class RecommendationService:
    async def get_collaborative_recommendations(
        user_id: str,
        limit: int = 10
    ) -> List[EnhancedProductSchema]

    async def get_similar_products(
        product_id: int,
        limit: int = 10
    ) -> List[EnhancedProductSchema]

    async def calculate_item_similarity_matrix() -> dict
```

#### `routes.py`
```python
# GET /products/{id}/recommendations
# GET /recommendations/for-you  (personalized)
```

---

### 8. Update Documentation 🔲

**Files to Update:**

#### `docs/API_DOCUMENTATION.md`
Add documentation for:
- `/products/search` endpoint
- `/products/popular` endpoint
- `/products/search/click` endpoint
- Search modes and parameters
- Personalization behavior

#### `docs/PROJECT_REQUIREMENTS.md`
Update implementation status:
- Mark search as ✅ Complete
- Update Phase 2 status
- Add personalization progress

#### `docs/DEVELOPMENT_GUIDELINES.md`
Add patterns for:
- Using VectorService
- Tracking interactions
- Personalization integration

#### `README.md`
Update features list:
- Add AI-powered search
- Add personalization features

---

## Setup & Configuration

### Prerequisites

1. **PostgreSQL with pgvector**
   ```bash
   # Install pgvector extension
   CREATE EXTENSION vector;
   ```

2. **Python Packages**
   ```bash
   uv add sentence-transformers
   uv add scikit-learn
   uv add numpy
   uv add scipy
   uv add pgvector
   uv add apscheduler
   ```

3. **Environment Variables** (no new ones needed)

---

### Installation Steps

#### 1. Run Database Migrations
```bash
psql -d celeste_db -f migrations/001_search_personalization_tables.sql
```

**Verify tables created:**
```sql
SELECT tablename FROM pg_tables
WHERE tablename IN (
    'product_vectors',
    'user_preferences',
    'search_interactions',
    'product_interactions',
    'product_popularity',
    'search_suggestions'
);
```

#### 2. Vectorize Existing Products
```bash
# Vectorize all products (first time)
python scripts/db/vectorize_products.py

# Expected output:
# ✅ Successfully vectorized: 500 products
# ❌ Failed to vectorize:    0 products
# ⏭️  Skipped (no text):      5 products
```

**Note:** First run downloads the model (~80MB), may take 5-10 minutes for large catalogs.

#### 3. Verify Vectorization
```sql
-- Check vector count
SELECT COUNT(*) FROM product_vectors;

-- Sample vector data
SELECT
    pv.product_id,
    p.name,
    LENGTH(pv.text_content) as text_length,
    pv.last_updated
FROM product_vectors pv
JOIN products p ON p.id = pv.product_id
LIMIT 5;
```

#### 4. Test Search Endpoint
```bash
# Start server
uvicorn main:app --reload --port 8000

# Test dropdown search
curl "http://localhost:8000/products/search?q=org&mode=dropdown"

# Test full search
curl "http://localhost:8000/products/search?q=organic+milk&mode=full"
```

---

## Testing & Verification

### Manual Testing Checklist

#### Search Functionality

- [ ] **Dropdown Search**
  ```bash
  GET /products/search?q=cof&mode=dropdown
  ```
  - Returns suggestions
  - Returns top 5 products
  - Response < 100ms

- [ ] **Full Search**
  ```bash
  GET /products/search?q=organic coffee&mode=full&limit=20
  ```
  - Returns complete product data
  - Includes pricing
  - Search time in metadata

- [ ] **Search with Filters**
  ```bash
  GET /products/search?q=milk&category_ids=5&min_price=5&max_price=15
  ```
  - Filters applied correctly
  - Results match criteria

- [ ] **Search with Location**
  ```bash
  GET /products/search?q=milk&latitude=6.9271&longitude=79.8612&include_inventory=true
  ```
  - Inventory data included
  - Nearby stores prioritized

- [ ] **Click Tracking**
  ```bash
  POST /products/search/click
  {
    "query": "organic coffee",
    "product_id": 123
  }
  ```
  - Requires authentication
  - Interaction recorded in DB

#### Database Verification

- [ ] **Product Vectors Created**
  ```sql
  SELECT COUNT(*) FROM product_vectors;
  -- Should match total products (minus those without text)
  ```

- [ ] **Search Interactions Tracked**
  ```sql
  SELECT * FROM search_interactions ORDER BY timestamp DESC LIMIT 10;
  -- Should show recent searches
  ```

- [ ] **Product Interactions Recorded**
  ```sql
  SELECT * FROM product_interactions ORDER BY timestamp DESC LIMIT 10;
  -- Should show clicks, views, etc.
  ```

#### Performance Testing

- [ ] **Search Speed**
  - Dropdown: < 100ms
  - Full search: < 300ms
  - With 1000+ products

- [ ] **Vectorization Speed**
  - 100 products: ~30 seconds
  - 1000 products: ~5 minutes

- [ ] **Concurrent Searches**
  - Test with 10 concurrent users
  - No timeouts or errors

---

## File Structure

```
celeste/
├── migrations/
│   ├── 001_search_personalization_tables.sql           ✅
│   └── 001_search_personalization_tables_rollback.sql  ✅
│
├── scripts/
│   └── db/
│       └── vectorize_products.py                       ✅
│
├── src/
│   ├── api/
│   │   ├── products/
│   │   │   └── services/
│   │   │       └── vector_service.py                   ✅
│   │   │
│   │   └── search/                                     ✅
│   │       ├── __init__.py                             ✅
│   │       ├── models.py                               ✅
│   │       ├── routes.py                               ✅
│   │       └── service.py                              ✅
│   │
│   ├── config/
│   │   └── constants.py                                ✅ (updated)
│   │
│   └── database/
│       └── models/
│           ├── __init__.py                             ✅ (updated)
│           ├── product.py                              ✅ (updated - added vector relationship)
│           ├── product_vector.py                       ✅
│           ├── search_interaction.py                   ✅
│           ├── user_preference.py                      ✅
│           ├── product_interaction.py                  ✅
│           ├── product_popularity.py                   ✅
│           └── search_suggestion.py                    ✅
│
├── main.py                                             ✅ (updated - registered search_router)
└── SEARCH_PERSONALIZATION_IMPLEMENTATION.md            ✅ (this file)
```

**Legend:**
- ✅ Completed
- 🔲 Pending

---

## API Documentation

### Search Endpoints

#### GET /products/search

**Description:** Hybrid semantic + keyword product search with two modes

**Authentication:** Optional (enables tracking)

**Query Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `q` | string | Yes | - | Search query (min 2 chars) |
| `mode` | enum | No | `full` | 'dropdown' or 'full' |
| `limit` | int | No | 20 (full), 5 (dropdown) | Max results |
| `include_pricing` | bool | No | true | Include pricing info |
| `include_categories` | bool | No | false | Include categories |
| `include_tags` | bool | No | false | Include tags |
| `include_inventory` | bool | No | true | Include inventory |
| `category_ids` | int[] | No | - | Filter by categories |
| `min_price` | float | No | - | Minimum price |
| `max_price` | float | No | - | Maximum price |
| `latitude` | float | No | - | User latitude (-90 to 90) |
| `longitude` | float | No | - | User longitude (-180 to 180) |

**Response (Dropdown Mode):**
```json
{
  "success": true,
  "data": {
    "suggestions": [
      {
        "query": "organic milk",
        "type": "popular",
        "search_count": 245
      }
    ],
    "products": [
      {
        "id": 123,
        "name": "Organic Milk 1L",
        "ref": "MLK001",
        "image_url": "https://...",
        "base_price": 5.99,
        "final_price": 5.49
      }
    ],
    "total_results": 5,
    "search_metadata": {
      "query": "org",
      "search_time_ms": 45.2,
      "mode": "dropdown"
    }
  }
}
```

**Response (Full Mode):**
```json
{
  "success": true,
  "data": {
    "products": [
      {
        "id": 123,
        "name": "Organic Milk 1L",
        "ref": "MLK001",
        "description": "...",
        "base_price": 5.99,
        "pricing": {
          "final_price": 5.49,
          "discount_applied": 0.50,
          "discount_percentage": 8.35
        },
        "inventory": { ... },
        "categories": [ ... ]
      }
    ],
    "total_results": 15,
    "search_metadata": {
      "query": "organic milk",
      "search_time_ms": 78.5,
      "mode": "full"
    }
  }
}
```

---

#### POST /products/search/click

**Description:** Track when user clicks a product from search results

**Authentication:** Required

**Request Body:**
```json
{
  "query": "organic milk",
  "product_id": 123
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "message": "Search click tracked successfully"
  }
}
```

---

## Database Schema

### product_vectors

```sql
CREATE TABLE product_vectors (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE UNIQUE,
    vector_embedding vector(384) NOT NULL,
    tfidf_vector JSONB,
    text_content TEXT NOT NULL,
    last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_product_vectors_embedding ON product_vectors
USING ivfflat (vector_embedding vector_cosine_ops) WITH (lists = 100);
```

### search_interactions

```sql
CREATE TABLE search_interactions (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    query TEXT NOT NULL,
    mode VARCHAR(50) NOT NULL,
    results_count INTEGER NOT NULL DEFAULT 0,
    clicked_product_ids INTEGER[],
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    extra_data JSONB
);
```

### user_preferences

```sql
CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    interest_vector vector(384),
    category_scores JSONB,
    brand_scores JSONB,
    search_keywords JSONB,
    last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    total_interactions INTEGER NOT NULL DEFAULT 0
);
```

### product_interactions

```sql
CREATE TABLE product_interactions (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    interaction_type VARCHAR(50) NOT NULL,
    interaction_score DOUBLE PRECISION NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    extra_data JSONB
);
```

### product_popularity

```sql
CREATE TABLE product_popularity (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE UNIQUE,
    search_count INTEGER NOT NULL DEFAULT 0,
    search_click_count INTEGER NOT NULL DEFAULT 0,
    view_count INTEGER NOT NULL DEFAULT 0,
    cart_add_count INTEGER NOT NULL DEFAULT 0,
    order_count INTEGER NOT NULL DEFAULT 0,
    popularity_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    trending_score DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

### search_suggestions

```sql
CREATE TABLE search_suggestions (
    id SERIAL PRIMARY KEY,
    query VARCHAR(255) NOT NULL UNIQUE,
    search_count INTEGER NOT NULL DEFAULT 0,
    success_rate DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    last_searched TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_trending BOOLEAN NOT NULL DEFAULT FALSE
);
```

---

## Next Steps

### Immediate (Phase 1)
1. ✅ Test search endpoints thoroughly
2. ✅ Verify vectorization works correctly
3. ✅ Monitor search performance

### Short Term (Phase 2)
1. 🔲 Implement PopularityService
2. 🔲 Create /products/popular endpoint
3. 🔲 Set up APScheduler for background tasks
4. 🔲 Implement interaction tracking helpers

### Medium Term (Phase 3)
1. 🔲 Implement PersonalizationService
2. 🔲 Update GET /products/ with personalization
3. 🔲 Test personalized ranking

### Long Term (Phase 4)
1. 🔲 Implement collaborative filtering
2. 🔲 Add recommendation endpoints
3. 🔲 Optimize performance
4. 🔲 Add analytics dashboard

---

## Notes & Best Practices

### Vectorization
- Run vectorization script after bulk product imports
- Re-vectorize products when name/description/categories change
- Monitor vector quality with sample searches

### Search Performance
- pgvector IVFFlat index requires VACUUM ANALYZE after bulk inserts
- Consider increasing `lists` parameter for larger catalogs (>10k products)
- Monitor search_time_ms in metadata

### User Privacy
- Only track authenticated users
- Anonymize old interaction data (>90 days)
- Allow users to clear search history

### Background Tasks
- Use APScheduler with AsyncIOScheduler for Cloud Run
- Schedule heavy tasks during low-traffic hours
- Monitor task execution time and errors

### Production Deployment
- Ensure pgvector extension is installed
- Pre-load sentence transformer model in container
- Set up monitoring for search performance
- Configure appropriate worker count for Cloud Run

---

**Last Updated:** 2025-10-20
**Status:** Search complete ✅, Personalization pending 🔲
