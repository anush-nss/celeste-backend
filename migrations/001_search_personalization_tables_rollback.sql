-- Rollback Migration: Search & Personalization Tables
-- Description: Drops all search and personalization tables
-- Date: 2025-10-20
-- WARNING: This will delete all data in these tables!

-- Drop tables in reverse dependency order
DROP TABLE IF EXISTS search_suggestions CASCADE;
DROP TABLE IF NOT EXISTS product_popularity CASCADE;
DROP TABLE IF EXISTS product_interactions CASCADE;
DROP TABLE IF EXISTS search_interactions CASCADE;
DROP TABLE IF EXISTS user_preferences CASCADE;
DROP TABLE IF EXISTS product_vectors CASCADE;

-- Verify tables were dropped
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

-- Note: pgvector extension is NOT dropped as it may be used elsewhere
-- If you want to drop it, run: DROP EXTENSION IF EXISTS vector CASCADE;
