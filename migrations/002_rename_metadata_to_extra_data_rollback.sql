-- Rollback Migration: Rename extra_data columns back to metadata
-- Description: Reverts the column rename if needed
-- Date: 2025-10-20
-- WARNING: Only use this if you need to rollback the rename

-- Rename extra_data column back to metadata in search_interactions table
ALTER TABLE search_interactions
RENAME COLUMN extra_data TO metadata;

-- Rename extra_data column back to metadata in product_interactions table
ALTER TABLE product_interactions
RENAME COLUMN extra_data TO metadata;

-- Verify the rollback
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name IN ('search_interactions', 'product_interactions')
  AND column_name = 'metadata'
ORDER BY table_name;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Successfully rolled back extra_data columns to metadata';
END $$;
