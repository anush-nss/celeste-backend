-- Create the ENUM type for promotion_type
CREATE TYPE promotiontype AS ENUM ('banner', 'popup', 'search');

-- Create the promotions table
CREATE TABLE promotions (
    id SERIAL PRIMARY KEY,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    promotion_type promotiontype NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ NOT NULL,
    product_ids INTEGER[],
    category_ids INTEGER[],
    image_urls_web TEXT[],
    image_urls_mobile TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT priority_must_be_positive CHECK (priority > 0)
);

-- Add indexes
CREATE INDEX idx_promotions_type_active_dates ON promotions (promotion_type, is_active, start_date, end_date);
CREATE INDEX idx_promotions_product_ids ON promotions USING GIN (product_ids);
CREATE INDEX idx_promotions_category_ids ON promotions USING GIN (category_ids);

-- Create a trigger function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply the trigger to the promotions table
CREATE TRIGGER update_promotions_updated_at
BEFORE UPDATE ON promotions
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
