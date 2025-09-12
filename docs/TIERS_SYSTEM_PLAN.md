# Simplified Tiers System Implementation Plan

## Overview
A simplified customer tiers system with basic benefits and tier-based pricing.

## 1. Database Schema Design

### 1.1 Tiers Table
```sql
CREATE TABLE tiers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT true,
    
    -- Simple requirements
    min_total_spent DECIMAL(10,2) DEFAULT 0.0,
    min_orders_count INTEGER DEFAULT 0,
    min_monthly_spent DECIMAL(10,2) DEFAULT 0.0,
    min_monthly_orders INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_tiers_active_sort ON tiers(is_active, sort_order);
```

### 1.2 Tier Benefits (Simplified)
```sql
CREATE TABLE tier_benefits (
    id SERIAL PRIMARY KEY,
    tier_id INTEGER REFERENCES tiers(id) ON DELETE CASCADE,
    benefit_type VARCHAR(30) NOT NULL CHECK (benefit_type IN ('delivery_discount', 'order_discount', 'free_shipping')),
    
    -- Simple discount fields
    discount_type VARCHAR(20) CHECK (discount_type IN ('percentage', 'flat')),
    discount_value DECIMAL(10,2),
    max_discount_amount DECIMAL(10,2), -- Cap for percentage discounts
    min_order_amount DECIMAL(10,2) DEFAULT 0.0,
    
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_tier_benefits_tier ON tier_benefits(tier_id, is_active);
```

### 1.3 Price Lists System
```sql
-- Price Lists
CREATE TABLE price_lists (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    priority INTEGER DEFAULT 0,
    
    -- Validity
    valid_from TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    valid_until TIMESTAMP WITH TIME ZONE, -- NULL = no expiry
    is_active BOOLEAN DEFAULT true,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Many-to-Many Relationship between Tiers and Price Lists
CREATE TABLE tier_price_lists (
    id SERIAL PRIMARY KEY,
    tier_id INTEGER REFERENCES tiers(id) ON DELETE CASCADE,
    price_list_id INTEGER REFERENCES price_lists(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(tier_id, price_list_id)
);

-- Price List Lines
CREATE TABLE price_list_lines (
    id SERIAL PRIMARY KEY,
    price_list_id INTEGER REFERENCES price_lists(id) ON DELETE CASCADE,
    
    -- Pricing Target (product-specific has highest priority)
    product_id INTEGER REFERENCES products(id) ON DELETE CASCADE, -- NULL = all products
    category_id INTEGER REFERENCES categories(id) ON DELETE CASCADE, -- NULL = all products
    -- If both product_id and category_id are NULL, applies to all products
    
    -- Pricing Rules
    discount_type VARCHAR(20) NOT NULL CHECK (discount_type IN ('percentage', 'flat', 'fixed_price')),
    discount_value DECIMAL(10,2) NOT NULL,
    max_discount_amount DECIMAL(10,2), -- Cap for percentage discounts
    
    -- Minimum quantity for bulk pricing
    min_quantity INTEGER DEFAULT 1,
    
    -- Conditions
    min_order_amount DECIMAL(10,2), -- NULL = no minimum order requirement
    
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_price_lists_priority ON price_lists(priority DESC, is_active);
CREATE INDEX idx_price_lists_active_validity ON price_lists(is_active, valid_from, valid_until);
CREATE INDEX idx_tier_price_lists_tier ON tier_price_lists(tier_id);
CREATE INDEX idx_tier_price_lists_price_list ON tier_price_lists(price_list_id);
CREATE INDEX idx_price_list_lines_product ON price_list_lines(product_id, price_list_id, is_active);
CREATE INDEX idx_price_list_lines_category ON price_list_lines(category_id, price_list_id, is_active);
```

## 2. Example Usage

### 2.1 Simple Tier Setup
```sql
-- Create basic tiers
INSERT INTO tiers (name, description, sort_order, min_total_spent, min_orders_count, min_monthly_spent, min_monthly_orders) VALUES
('Bronze', 'Default tier', 1, 0, 0, 0, 0),
('Silver', 'Premium tier', 2, 500.00, 5, 100.00, 2),
('Gold', 'VIP tier', 3, 2000.00, 20, 300.00, 5);

-- Add benefits
INSERT INTO tier_benefits (tier_id, benefit_type, discount_type, discount_value, max_discount_amount, min_order_amount) VALUES
(2, 'delivery_discount', 'percentage', 10.0, 50.00, 0),
(2, 'free_shipping', NULL, NULL, NULL, 200.00),
(3, 'delivery_discount', 'percentage', 15.0, 100.00, 0),
(3, 'order_discount', 'percentage', 5.0, 200.00, 100.00),
(3, 'free_shipping', NULL, NULL, NULL, 100.00);

-- Add price lists
INSERT INTO price_lists (name, description, priority) VALUES
('Gold Exclusive Discounts', 'Special pricing for Gold tier members', 10),
('General Bulk Discounts', 'Volume discounts for all customers', 5);

-- Link price lists to tiers (price list 1 for Gold tier only, price list 2 for all tiers)
INSERT INTO tier_price_lists (tier_id, price_list_id) VALUES
(3, 1); -- Gold tier gets the exclusive discounts

-- Add pricing rules (price list lines)
INSERT INTO price_list_lines (price_list_id, product_id, discount_type, discount_value, min_quantity) VALUES
(1, 1, 'percentage', 15.0, 1), -- 15% off product 1 for Gold members
(1, 2, 'percentage', 10.0, 1), -- 10% off product 2 for Gold members
(2, NULL, 'percentage', 5.0, 10); -- 5% off all products for orders of 10+ items
```

### 2.2 Price Calculation Query
```sql
-- Get best price for a product based on user tier
WITH applicable_prices AS (
    SELECT 
        pll.discount_type,
        pll.discount_value,
        pl.priority,
        CASE 
            WHEN pll.product_id IS NOT NULL THEN 3  -- Product-specific
            WHEN pll.category_id IS NOT NULL THEN 2 -- Category-specific  
            ELSE 1                                  -- General
        END as specificity_score
    FROM price_list_lines pll
    JOIN price_lists pl ON pll.price_list_id = pl.id
    LEFT JOIN tier_price_lists tpl ON pl.id = tpl.price_list_id
    WHERE pll.is_active = true
        AND pl.is_active = true
        AND (tpl.tier_id = $user_tier_id OR tpl.tier_id IS NULL)
        AND (pll.product_id = $product_id OR 
             pll.category_id = $product_category_id OR 
             (pll.product_id IS NULL AND pll.category_id IS NULL))
        AND (pl.valid_from <= NOW())
        AND (pl.valid_until IS NULL OR pl.valid_until >= NOW())
        AND pll.min_quantity <= $quantity
)
SELECT 
    p.base_price,
    COALESCE(ap.discount_type, 'none') as discount_type,
    COALESCE(ap.discount_value, 0) as discount_value,
    CASE 
        WHEN ap.discount_type = 'percentage' THEN 
            p.base_price * (1 - ap.discount_value / 100.0)
        WHEN ap.discount_type = 'flat' THEN 
            GREATEST(p.base_price - ap.discount_value, 0)
        WHEN ap.discount_type = 'fixed_price' THEN 
            ap.discount_value
        ELSE p.base_price
    END as final_price
FROM products p
LEFT JOIN (
    SELECT * FROM applicable_prices
    ORDER BY specificity_score DESC, priority DESC
    LIMIT 1
) ap ON true
WHERE p.id = $product_id;
```

## 3. Implementation Plan

### 3.1 Database Setup
1. Create the 3 simple tables: `tiers`, `tier_benefits`, `tier_price_lists`
2. Add basic indexes for performance
3. Insert default Bronze tier

### 3.2 Models & Services
1. Create SQLAlchemy models for the 3 tables
2. Basic TierService for CRUD operations
3. Integration with existing user model (add tier_id)

### 3.3 API Routes
1. Admin: Manage tiers and benefits
2. Public: Get user tier info and pricing

This simplified design focuses on:
- **3 simple tables** instead of complex relationships
- **Basic tier-based pricing** without over-engineering
- **Simple benefits system** with just 3 benefit types
- **Straightforward price resolution** using direct table lookups

Ready to implement this simplified version?