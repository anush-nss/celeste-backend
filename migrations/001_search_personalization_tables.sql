-- Migration: Add Search & Personalization Tables
-- Description: Creates tables for product vectors, user preferences, interactions,
--              popularity metrics, and search tracking
-- Date: 2025-10-20

-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================================
-- 1. PRODUCT_VECTORS TABLE
-- Stores vector embeddings for products for semantic search
-- ============================================================================
CREATE TABLE IF NOT EXISTS product_vectors (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE UNIQUE,
    vector_embedding vector(384) NOT NULL,  -- MiniLM 384-dimensional embedding
    tfidf_vector JSONB,  -- Sparse TF-IDF vector
    text_content TEXT NOT NULL,  -- Combined searchable text
    last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    version INTEGER NOT NULL DEFAULT 1  -- Track embedding model version
);

-- Indexes for product_vectors
CREATE UNIQUE INDEX IF NOT EXISTS idx_product_vectors_product_id
    ON product_vectors(product_id);

CREATE INDEX IF NOT EXISTS idx_product_vectors_updated
    ON product_vectors(last_updated);

-- pgvector IVFFlat index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS idx_product_vectors_embedding
    ON product_vectors
    USING ivfflat (vector_embedding vector_cosine_ops)
    WITH (lists = 100);

-- ============================================================================
-- 2. USER_PREFERENCES TABLE
-- Stores aggregated user interests and preferences
-- ============================================================================
CREATE TABLE IF NOT EXISTS user_preferences (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE,  -- Firebase UID
    interest_vector vector(384),  -- Aggregated interest vector
    category_scores JSONB,  -- {category_id: score}
    brand_scores JSONB,  -- {brand: score}
    search_keywords JSONB,  -- {keyword: frequency}
    last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    total_interactions INTEGER NOT NULL DEFAULT 0
);

-- Indexes for user_preferences
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_preferences_user_id
    ON user_preferences(user_id);

CREATE INDEX IF NOT EXISTS idx_user_preferences_updated
    ON user_preferences(last_updated);

CREATE INDEX IF NOT EXISTS idx_user_preferences_interactions
    ON user_preferences(total_interactions);

-- ============================================================================
-- 3. SEARCH_INTERACTIONS TABLE
-- Tracks all user search queries and results
-- ============================================================================
CREATE TABLE IF NOT EXISTS search_interactions (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,  -- Firebase UID
    query TEXT NOT NULL,
    mode VARCHAR(50) NOT NULL,  -- 'dropdown' or 'full'
    results_count INTEGER NOT NULL DEFAULT 0,
    clicked_product_ids INTEGER[],  -- Array of clicked product IDs
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    extra_data JSONB  -- Additional context (filters, search time, etc.)
);

-- Indexes for search_interactions
CREATE INDEX IF NOT EXISTS idx_search_interactions_user_id
    ON search_interactions(user_id);

CREATE INDEX IF NOT EXISTS idx_search_interactions_timestamp
    ON search_interactions(timestamp);

CREATE INDEX IF NOT EXISTS idx_search_interactions_user_time
    ON search_interactions(user_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_search_interactions_query
    ON search_interactions(query);

CREATE INDEX IF NOT EXISTS idx_search_interactions_mode
    ON search_interactions(mode);

-- ============================================================================
-- 4. PRODUCT_INTERACTIONS TABLE
-- Tracks detailed user interactions with products
-- ============================================================================
CREATE TABLE IF NOT EXISTS product_interactions (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,  -- Firebase UID
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    interaction_type VARCHAR(50) NOT NULL,  -- search_click, view, cart_add, order, wishlist_add
    interaction_score DOUBLE PRECISION NOT NULL,  -- Weighted score
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    extra_data JSONB  -- Additional context
);

-- Indexes for product_interactions
CREATE INDEX IF NOT EXISTS idx_product_interactions_user_id
    ON product_interactions(user_id);

CREATE INDEX IF NOT EXISTS idx_product_interactions_product_id
    ON product_interactions(product_id);

CREATE INDEX IF NOT EXISTS idx_product_interactions_timestamp
    ON product_interactions(timestamp);

CREATE INDEX IF NOT EXISTS idx_product_interactions_type
    ON product_interactions(interaction_type);

CREATE INDEX IF NOT EXISTS idx_product_interactions_user_time
    ON product_interactions(user_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_product_interactions_user_product
    ON product_interactions(user_id, product_id);

-- ============================================================================
-- 5. PRODUCT_POPULARITY TABLE
-- Aggregated popularity metrics for products
-- ============================================================================
CREATE TABLE IF NOT EXISTS product_popularity (
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

-- Indexes for product_popularity
CREATE UNIQUE INDEX IF NOT EXISTS idx_product_popularity_product_id
    ON product_popularity(product_id);

CREATE INDEX IF NOT EXISTS idx_product_popularity_score
    ON product_popularity(popularity_score);

CREATE INDEX IF NOT EXISTS idx_product_popularity_trending
    ON product_popularity(trending_score);

CREATE INDEX IF NOT EXISTS idx_product_popularity_orders
    ON product_popularity(order_count);

CREATE INDEX IF NOT EXISTS idx_product_popularity_cart
    ON product_popularity(cart_add_count);

CREATE INDEX IF NOT EXISTS idx_product_popularity_searches
    ON product_popularity(search_count);

CREATE INDEX IF NOT EXISTS idx_product_popularity_updated
    ON product_popularity(last_updated);

-- ============================================================================
-- 6. SEARCH_SUGGESTIONS TABLE
-- Stores popular search queries for autocomplete
-- ============================================================================
CREATE TABLE IF NOT EXISTS search_suggestions (
    id SERIAL PRIMARY KEY,
    query VARCHAR(255) NOT NULL UNIQUE,
    search_count INTEGER NOT NULL DEFAULT 0,
    success_rate DOUBLE PRECISION NOT NULL DEFAULT 0.0,  -- 0.0 to 1.0
    last_searched TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    is_trending BOOLEAN NOT NULL DEFAULT FALSE
);

-- Indexes for search_suggestions
CREATE UNIQUE INDEX IF NOT EXISTS idx_search_suggestions_query
    ON search_suggestions(query);

CREATE INDEX IF NOT EXISTS idx_search_suggestions_count
    ON search_suggestions(search_count);

CREATE INDEX IF NOT EXISTS idx_search_suggestions_trending
    ON search_suggestions(is_trending);

CREATE INDEX IF NOT EXISTS idx_search_suggestions_success
    ON search_suggestions(success_rate);

CREATE INDEX IF NOT EXISTS idx_search_suggestions_last_searched
    ON search_suggestions(last_searched);

-- ============================================================================
-- MIGRATION COMPLETE
-- ============================================================================

-- Verify tables were created
SELECT
    tablename,
    schemaname
FROM pg_tables
WHERE tablename IN (
    'product_vectors',
    'user_preferences',
    'search_interactions',
    'product_interactions',
    'product_popularity',
    'search_suggestions'
)
ORDER BY tablename;

-- Display table counts
SELECT
    'product_vectors' as table_name,
    COUNT(*) as row_count
FROM product_vectors
UNION ALL
SELECT
    'user_preferences' as table_name,
    COUNT(*) as row_count
FROM user_preferences
UNION ALL
SELECT
    'search_interactions' as table_name,
    COUNT(*) as row_count
FROM search_interactions
UNION ALL
SELECT
    'product_interactions' as table_name,
    COUNT(*) as row_count
FROM product_interactions
UNION ALL
SELECT
    'product_popularity' as table_name,
    COUNT(*) as row_count
FROM product_popularity
UNION ALL
SELECT
    'search_suggestions' as table_name,
    COUNT(*) as row_count
FROM search_suggestions;
