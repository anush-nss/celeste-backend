-- Drop the trigger
DROP TRIGGER IF EXISTS update_promotions_updated_at ON promotions;

-- Drop the trigger function if it's no longer needed by other tables
-- For safety, we might just drop the trigger and leave the function,
-- but for a clean rollback, we'll assume it's specific to this context for now.
-- A better approach in a large system might be to check if other tables use it.
DROP FUNCTION IF EXISTS update_updated_at_column();

-- Drop the table
DROP TABLE IF EXISTS promotions;

-- Drop the ENUM type
DROP TYPE IF EXISTS promotiontype;
