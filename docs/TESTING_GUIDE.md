# Search & Personalization System - Testing Guide

This guide provides step-by-step instructions for testing the AI-powered search and personalization features implemented in the Celeste E-Commerce platform.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Setup](#initial-setup)
3. [Testing Search](#testing-search)
4. [Testing Similar Products](#testing-similar-products)
5. [Testing Popular Products](#testing-popular-products)
6. [Testing Personalization](#testing-personalization)
7. [Testing Interaction Tracking](#testing-interaction-tracking)
8. [Testing Manual Triggers](#testing-manual-triggers)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Tools
- API client (Postman, Insomnia, or curl)
- Access to the development server (default: `http://localhost:8000`)
- Firebase authentication credentials for testing
- Python 3.12+ environment for running scripts

### Environment Setup
1. Ensure PostgreSQL with pgvector extension is installed and running
2. Database migrations completed (`alembic upgrade head`)
3. Environment variables configured in `.env`
4. Server running: `uvicorn main:app --reload --port 8000`

---

## Initial Setup

### Step 1: Vectorize Products

Before you can test search functionality, you need to generate vector embeddings for all products.

```bash
# Run the vectorization script
python scripts/db/vectorize_products.py
```

**Expected Output:**
```
Starting product vectorization...
Processing products: 100%|████████████| 50/50
✅ Successfully vectorized 50 products
⚠️  Failed: 0 products
Total time: 12.5s
```

**What this does:**
- Generates 384-dimension embeddings for each product using all-MiniLM-L6-v2 model
- Stores embeddings in `product_vectors` PostgreSQL table
- Creates searchable text content from product name, description, and categories
- Enables semantic search functionality

### Step 2: Get Authentication Token

For personalization and user-specific features, you need an authentication token.

**Option A: Using existing Firebase user**
```bash
POST http://localhost:8000/dev/auth/token
Content-Type: application/json

{
  "uid": "your_firebase_uid_here"
}
```

**Option B: Register new user**
```bash
POST http://localhost:8000/auth/register
Content-Type: application/json

{
  "idToken": "firebase_id_token_from_client",
  "name": "Test User"
}
```

**Save the token** for subsequent requests:
```
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## Testing Search

### Test 1: Basic Semantic Search

Test the AI-powered semantic search with a simple query.

```bash
GET http://localhost:8000/search/products?q=healthy snacks&limit=10
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "products": [
      {
        "id": 15,
        "name": "Organic Granola Bar",
        "description": "Healthy whole grain snack",
        "price": 2.99,
        "search_score": 0.85
      },
      {
        "id": 42,
        "name": "Mixed Nuts Pack",
        "description": "Nutritious protein snack",
        "price": 5.49,
        "search_score": 0.78
      }
    ],
    "total": 8,
    "limit": 10,
    "search_query": "healthy snacks"
  }
}
```

**What to verify:**
- ✅ Products semantically related to "healthy snacks" appear (even if they don't contain exact keywords)
- ✅ Results ranked by `search_score` (higher = more relevant)
- ✅ Response time < 500ms for ~50 products

### Test 2: Hybrid Search (Semantic + Keyword)

Test with specific product names to see keyword matching.

```bash
GET http://localhost:8000/search/products?q=organic milk&limit=5
```

**What to verify:**
- ✅ Products with "organic" or "milk" in name/description rank highly
- ✅ Semantically similar items (yogurt, dairy) also appear
- ✅ Exact matches score higher than semantic matches

### Test 3: Search with Filters

Combine search with category filtering and pricing.

```bash
GET http://localhost:8000/search/products?q=coffee&include_pricing=true&include_categories=true&store_id=1
```

**What to verify:**
- ✅ Only products from specified store returned
- ✅ Tier-based pricing included in response
- ✅ Category information included

### Test 4: Edge Cases

Test search behavior with various inputs:

**Empty query:**
```bash
GET http://localhost:8000/search/products?q=
# Expected: 400 Bad Request (query required)
```

**Very long query:**
```bash
GET http://localhost:8000/search/products?q=looking for some really good high quality organic fresh locally sourced sustainable
# Expected: 200 OK with relevant results
```

**No results:**
```bash
GET http://localhost:8000/search/products?q=xyzabc123notfound
# Expected: 200 OK with empty products array
```

---

## Testing Similar Products

### Test 4.5: Find Similar Products

Test the vector similarity-based product recommendations.

**Basic similar products request:**
```bash
GET http://localhost:8000/products/15/similar?limit=5
```

**Expected Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 42,
      "name": "Similar Product Name",
      "description": "Product description",
      "price": 12.99,
      "similarity_score": 0.87,
      "category_ids": [1, 3],
      "tags": ["organic", "healthy"]
    },
    {
      "id": 27,
      "name": "Another Similar Product",
      "price": 10.49,
      "similarity_score": 0.78
    }
  ]
}
```

**What to verify:**
- ✅ Products returned are semantically similar to the source product
- ✅ Products sorted by `similarity_score` (highest first)
- ✅ All scores >= `min_similarity` threshold
- ✅ Response time < 500ms for ~50 products

### Test 4.6: Similar Products with Filters

Combine similarity search with pricing and inventory enrichment.

```bash
GET http://localhost:8000/products/15/similar?limit=10&min_similarity=0.7&include_pricing=true&include_inventory=true&store_id=1
```

**What to verify:**
- ✅ Only products with similarity >= 0.7 returned
- ✅ Tier-based pricing included
- ✅ Inventory information included for specified store
- ✅ All enrichment features work like regular product endpoints

### Test 4.7: Similar Products Edge Cases

Test edge cases for similar products:

**Product without vector:**
```bash
GET http://localhost:8000/products/999/similar
# Expected: 200 OK with empty array
```

**Very high similarity threshold:**
```bash
GET http://localhost:8000/products/15/similar?min_similarity=0.99
# Expected: 200 OK with few or no results
```

**Non-existent product:**
```bash
GET http://localhost:8000/products/99999/similar
# Expected: 200 OK with empty array (product not found means no vector)
```

**What to verify:**
- ✅ Graceful handling when source product has no vector
- ✅ Empty array returned (not 404) when no similar products found
- ✅ High thresholds return only very similar products

---

## Testing Popular Products

### Test 5: Overall Popularity

Get the most popular products across all time.

```bash
GET http://localhost:8000/products/popular?mode=overall&limit=10
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "products": [
      {
        "id": 23,
        "name": "Best Selling Product",
        "popularity_score": 0.95,
        "view_count": 2500,
        "cart_add_count": 850,
        "order_count": 320
      }
    ],
    "total": 10,
    "mode": "overall"
  }
}
```

**What to verify:**
- ✅ Products sorted by `popularity_score` descending
- ✅ Metrics (view_count, cart_add_count, order_count) included
- ✅ No authentication required (public endpoint)

### Test 6: Trending Products

Get products trending in the last 7 days with time decay.

```bash
GET http://localhost:8000/products/popular?mode=trending&days=7&limit=10
```

**What to verify:**
- ✅ Recently interacted products rank higher
- ✅ `trending_score` reflects time decay (recent interactions weighted more)
- ✅ Different results than `overall` mode

### Test 7: Specific Popularity Modes

Test each of the 6 popularity modes:

**Most Viewed:**
```bash
GET http://localhost:8000/products/popular?mode=most_viewed&limit=5
```

**Most Added to Cart:**
```bash
GET http://localhost:8000/products/popular?mode=most_carted&limit=5
```

**Most Ordered:**
```bash
GET http://localhost:8000/products/popular?mode=most_ordered&limit=5
```

**Most Searched:**
```bash
GET http://localhost:8000/products/popular?mode=most_searched&limit=5
```

**What to verify for each mode:**
- ✅ Results reflect the specific metric (e.g., most_viewed shows highest view_count)
- ✅ Different rankings for different modes
- ✅ Appropriate metric emphasized in response

---

## Testing Personalization

### Test 8: Personalized Product Listings

Get personalized product recommendations (requires authentication).

```bash
GET http://localhost:8000/products/?enable_personalization=true&limit=20
Authorization: Bearer YOUR_TOKEN_HERE
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "products": [
      {
        "id": 34,
        "name": "Product You'll Love",
        "personalization_score": 0.88,
        "category_affinity": 0.75,
        "brand_affinity": 0.60
      }
    ],
    "total": 50,
    "is_personalized": true
  }
}
```

**What to verify:**
- ✅ Products ranked by `personalization_score`
- ✅ `is_personalized: true` in response
- ✅ Different results for different users
- ✅ Category affinity and brand affinity scores included

### Test 9: Personalization Without Authentication

Test that personalization degrades gracefully without auth.

```bash
GET http://localhost:8000/products/?enable_personalization=true&limit=20
# No Authorization header
```

**What to verify:**
- ✅ Returns products without error
- ✅ `is_personalized: false` or not included
- ✅ Standard sorting (no personalization applied)

### Test 10: Minimum Interaction Requirement

Test personalization with a new user (< 5 interactions).

**Steps:**
1. Create a new user
2. Track 2-3 interactions
3. Request personalized products

**Expected Behavior:**
- ✅ Returns products but without strong personalization
- ✅ Falls back to popularity-based ranking
- ✅ After 5+ interactions, personalization becomes active

### Test 11: Diversity Filtering

Test that personalization prevents filter bubble.

```bash
GET http://localhost:8000/products/?enable_personalization=true&limit=20
Authorization: Bearer YOUR_TOKEN_HERE
```

**What to verify:**
- ✅ No more than 3 consecutive products from same category
- ✅ Diverse categories represented even if user has strong preference
- ✅ Balance between personalization and diversity

---

## Testing Interaction Tracking

### Test 12: Automatic Cart Tracking

Test that adding items to cart automatically tracks interactions.

**Step 1: Add item to cart**
```bash
POST http://localhost:8000/users/me/carts/1/items
Authorization: Bearer YOUR_TOKEN_HERE
Content-Type: application/json

{
  "product_id": 42,
  "quantity": 2
}
```

**Step 2: Verify interaction tracked**
```bash
# Check product popularity after cart add
GET http://localhost:8000/dev/triggers
Content-Type: application/json

{
  "action": "update_popularity",
  "product_id": 42
}
```

**What to verify:**
- ✅ `cart_add_count` incremented for product
- ✅ Background task triggered (non-blocking)
- ✅ Cart add endpoint returns successfully before tracking completes

### Test 13: Automatic Order Tracking

Test that completed orders track interactions.

**Step 1: Complete order with payment**
```bash
POST http://localhost:8000/orders/payment/callback
Content-Type: application/json

{
  "order_id": 123,
  "status": "success",
  "transaction_id": "txn_123"
}
```

**Step 2: Verify bulk tracking**
- Check that all products in order have `order_count` incremented
- Verify user preferences updated after order

**What to verify:**
- ✅ All order items tracked in single batch
- ✅ Highest interaction score (10.0) applied
- ✅ User preferences automatically updated

### Test 14: Tracking Failures Don't Break Features

Test fault tolerance of tracking system.

**Scenario: Database temporarily unavailable**

**What to verify:**
- ✅ Cart add still succeeds even if tracking fails
- ✅ Error logged but not returned to user
- ✅ User experience not impacted by tracking issues

---

## Testing Manual Triggers

The `/dev/triggers` endpoint allows manual testing of all search/personalization components.

### Test 15: Update Product Popularity

Manually trigger popularity calculation for a product.

```bash
POST http://localhost:8000/dev/triggers
Content-Type: application/json

{
  "action": "update_popularity",
  "product_id": 42
}
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "action": "update_popularity",
    "product_id": 42,
    "success": true,
    "metrics": {
      "view_count": 150,
      "cart_add_count": 45,
      "order_count": 12,
      "search_click_count": 8,
      "trending_score": 7.5,
      "overall_score": 0.82
    }
  }
}
```

**What to verify:**
- ✅ Popularity metrics returned
- ✅ Scores calculated from interactions
- ✅ Trending score reflects recent activity

### Test 16: Update All Popularity

Update popularity for all products (use cautiously on large datasets).

```bash
POST http://localhost:8000/dev/triggers
Content-Type: application/json

{
  "action": "update_all_popularity"
}
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "action": "update_all_popularity",
    "results": {
      "success": 48,
      "failed": 2,
      "skipped": 10
    },
    "message": "Updated 48 products, 2 failed"
  }
}
```

**What to verify:**
- ✅ Success count matches products with interactions
- ✅ Skipped count reflects products without interactions
- ✅ Response time reasonable (< 30s for 100 products)

### Test 17: Update User Preferences

Manually trigger preference calculation for a user.

```bash
POST http://localhost:8000/dev/triggers
Content-Type: application/json

{
  "action": "update_preferences",
  "user_id": "firebase_uid_here"
}
```

**Expected Response:**
```json
{
  "success": true,
  "data": {
    "action": "update_preferences",
    "user_id": "firebase_uid_here",
    "success": true,
    "preferences": {
      "total_interactions": 47,
      "category_scores": {
        "1": 0.85,
        "3": 0.72,
        "5": 0.45
      },
      "brand_scores": {
        "Brand A": 0.90,
        "Brand B": 0.55
      },
      "search_keywords": {
        "organic": 12,
        "healthy": 8,
        "snacks": 5
      }
    }
  }
}
```

**What to verify:**
- ✅ Category scores reflect interaction frequency
- ✅ Brand scores show brand loyalty
- ✅ Search keywords aggregated from search history
- ✅ Total interactions count accurate

### Test 18: Track Interaction Manually

Manually create test interactions for various scenarios.

**Track a View:**
```bash
POST http://localhost:8000/dev/triggers
Content-Type: application/json

{
  "action": "track_interaction",
  "user_id": "firebase_uid_here",
  "product_id": 42,
  "interaction_type": "view"
}
```

**Track a Cart Add:**
```bash
POST http://localhost:8000/dev/triggers
Content-Type: application/json

{
  "action": "track_interaction",
  "user_id": "firebase_uid_here",
  "product_id": 42,
  "interaction_type": "cart_add",
  "quantity": 3
}
```

**Track an Order:**
```bash
POST http://localhost:8000/dev/triggers
Content-Type: application/json

{
  "action": "track_interaction",
  "user_id": "firebase_uid_here",
  "product_id": 42,
  "interaction_type": "order",
  "order_id": 123,
  "quantity": 2
}
```

**What to verify:**
- ✅ Interaction recorded in database
- ✅ Background tasks triggered for popularity/preferences
- ✅ Different interaction types have different scores

---

## Complete Testing Flow

### Scenario: New User Journey

Simulate a complete user journey from first visit to repeat purchase.

**Step 1: New user searches for products**
```bash
# No auth - public search
GET http://localhost:8000/search/products?q=coffee
```
✅ Returns relevant results without personalization

**Step 2: User registers**
```bash
POST http://localhost:8000/auth/register
# Creates new user with BRONZE tier
```

**Step 3: User browses popular products**
```bash
GET http://localhost:8000/products/popular?mode=trending
```
✅ Sees trending products (no personalization yet)

**Step 4: User views product details (interaction #1)**
```bash
# Manually track view for testing
POST http://localhost:8000/dev/triggers
{
  "action": "track_interaction",
  "user_id": "new_user_uid",
  "product_id": 15,
  "interaction_type": "view"
}
```

**Step 5: User adds to cart (interaction #2)**
```bash
POST http://localhost:8000/users/me/carts/1/items
Authorization: Bearer NEW_USER_TOKEN
{
  "product_id": 15,
  "quantity": 1
}
```
✅ Automatic tracking triggered

**Step 6: User adds 3 more products to cart (interactions #3-5)**
```bash
# Repeat cart adds for products 16, 17, 18
```

**Step 7: Check user preferences**
```bash
POST http://localhost:8000/dev/triggers
{
  "action": "update_preferences",
  "user_id": "new_user_uid"
}
```
✅ Now has 5 interactions - personalization activated!

**Step 8: User completes order (interactions #6-9)**
```bash
POST http://localhost:8000/users/me/checkout/order
# Order with 4 products
```
✅ Bulk tracking triggered for all products

**Step 9: User returns - sees personalized products**
```bash
GET http://localhost:8000/products/?enable_personalization=true
Authorization: Bearer NEW_USER_TOKEN
```
✅ Products ranked by personalization score
✅ Similar categories to purchased items ranked higher
✅ Diversity filtering prevents filter bubble

**Step 10: User searches again**
```bash
GET http://localhost:8000/search/products?q=coffee
Authorization: Bearer NEW_USER_TOKEN
```
✅ Search results still semantic/hybrid (not personalized)
✅ But popular products may reflect user's past behavior

---

## Troubleshooting

### Issue: Search returns empty results

**Symptoms:**
- Search query returns `{"products": [], "total": 0}`
- All search queries return no results

**Solutions:**
1. **Verify products are vectorized:**
   ```bash
   python scripts/db/vectorize_products.py
   ```

2. **Check database:**
   ```sql
   SELECT COUNT(*) FROM product_vectors;
   -- Should match product count
   ```

3. **Verify pgvector extension:**
   ```sql
   SELECT * FROM pg_extension WHERE extname = 'vector';
   ```

### Issue: Personalization not working

**Symptoms:**
- `is_personalized: false` or missing
- All users see same product order

**Solutions:**
1. **Check interaction count:**
   ```bash
   POST /dev/triggers
   {
     "action": "update_preferences",
     "user_id": "your_uid"
   }
   # Look at total_interactions - needs 5+
   ```

2. **Manually create test interactions:**
   ```bash
   # Track 5+ interactions using /dev/triggers
   ```

3. **Verify authentication token:**
   ```bash
   # Ensure Bearer token is valid and included
   ```

### Issue: Popularity scores all zero

**Symptoms:**
- All products have `popularity_score: 0`
- Popular products endpoint returns empty

**Solutions:**
1. **Track test interactions:**
   ```bash
   POST /dev/triggers
   {
     "action": "track_interaction",
     "user_id": "test_uid",
     "product_id": 1,
     "interaction_type": "order"
   }
   ```

2. **Update popularity:**
   ```bash
   POST /dev/triggers
   {
     "action": "update_all_popularity"
   }
   ```

3. **Check interaction tracking:**
   ```sql
   SELECT COUNT(*) FROM product_interactions;
   -- Should have interaction records
   ```

### Issue: Slow search performance

**Symptoms:**
- Search takes > 2 seconds
- Timeout errors

**Solutions:**
1. **Check database indexes:**
   ```sql
   SELECT * FROM pg_indexes WHERE tablename = 'product_vectors';
   -- Should have IVFFlat index on vector_embedding
   ```

2. **Reduce result limit:**
   ```bash
   GET /search/products?q=test&limit=10
   # Lower limits = faster queries
   ```

3. **Monitor model loading:**
   - Model should load once at startup
   - Check logs for repeated model loading

### Issue: Background tasks not triggering

**Symptoms:**
- Popularity/preferences not updating automatically
- Manual triggers work but automatic tracking doesn't

**Solutions:**
1. **Check error logs:**
   ```bash
   # Look for asyncio task errors in logs
   ```

2. **Verify services initialized:**
   ```python
   # In routes.py, ensure services instantiated:
   interaction_service = InteractionService()
   ```

3. **Test manual triggers:**
   ```bash
   # If manual triggers work, issue is with automatic tracking integration
   ```

---

## Next Steps

After completing all tests:

1. **✅ Production Deployment:**
   - Run full vectorization on production data
   - Set up scheduled background tasks (APScheduler)
   - Monitor performance metrics

2. **✅ Analytics Integration:**
   - Track search queries for insights
   - Monitor personalization effectiveness
   - Measure conversion rates by ranking mode

3. **✅ A/B Testing:**
   - Test different hybrid weights (semantic vs keyword)
   - Test personalization parameters
   - Optimize time decay for trending

4. **✅ Feature Enhancements:**
   - Add search suggestions/autocomplete
   - Implement collaborative filtering
   - Add image-based search

---

## API Quick Reference

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/search/products` | GET | Optional | AI-powered search |
| `/products/{id}/similar` | GET | Optional | Similar products by vector similarity |
| `/products/popular` | GET | No | Popular products (6 modes) |
| `/products/` | GET | Optional | Personalized listings |
| `/dev/triggers` | POST | No | Manual testing triggers |

## Interaction Scores

| Type | Score | Auto-Update |
|------|-------|-------------|
| VIEW | 2.0 | No |
| SEARCH_CLICK | 1.0 | Yes |
| CART_ADD | 5.0 | Yes (popularity only) |
| WISHLIST_ADD | 3.0 | Yes (popularity only) |
| ORDER | 10.0 | Yes (both) |

## Configuration Constants

Located in `src/config/constants.py`:

```python
SEARCH_VECTOR_DIM = 384
SENTENCE_TRANSFORMER_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SEARCH_HYBRID_WEIGHT_SEMANTIC = 0.7
SEARCH_HYBRID_WEIGHT_TFIDF = 0.3

POPULARITY_MIN_INTERACTIONS = 5
POPULARITY_TIME_DECAY_HOURS = 72  # 3-day half-life

PERSONALIZATION_MIN_INTERACTIONS = 5
PERSONALIZATION_CATEGORY_WEIGHT = 1.0
PERSONALIZATION_BRAND_WEIGHT = 0.5
PERSONALIZATION_SEARCH_WEIGHT = 0.3
```

---

**Happy Testing! 🚀**
