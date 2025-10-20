-- Migration: Rename metadata columns to extra_data
-- Description: Fixes SQLAlchemy reserved attribute name conflict
-- Date: 2025-10-20

-- Rename metadata column in search_interactions table
ALTER TABLE search_interactions
RENAME COLUMN metadata TO extra_data;

-- Rename metadata column in product_interactions table
ALTER TABLE product_interactions
RENAME COLUMN metadata TO extra_data;

-- Verify the changes
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name IN ('search_interactions', 'product_interactions')
  AND column_name = 'extra_data'
ORDER BY table_name;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Successfully renamed metadata columns to extra_data';
END $$;
