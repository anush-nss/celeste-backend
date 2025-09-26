# Multi-Cart Implementation Plan

## Overview

This document outlines the implementation plan for a multi-cart system where users can create multiple carts, share them read-only with others, and combine multiple carts (owned + shared) during checkout. Shared carts remain live-synced until ordering, after which they become immutable.

## Business Rules

### Cart Ownership & Sharing
1. **Cart Creation**: Users create carts and add items (only the owner can modify)
2. **Read-Only Sharing**: Owner shares cart with other users for viewing only
3. **Live Updates**: Shared users see updates when they refresh/reload cart data
4. **Multi-Cart Checkout**: Users can select multiple carts (owned + shared) for single order
5. **Post-Order Immutability**: Once any cart is used in an order, it becomes uneditable

### Cart Lifecycle
- **`active`**: Cart can be modified by owner, visible to shared users
- **`ordered`**: Cart was used in an order, becomes read-only for everyone
- **`inactive`**: Cart archived by owner (optional)

## Database Schema Design

### Core Tables (4 Main Tables)

#### 1. `carts` Table
```sql
CREATE TABLE carts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL DEFAULT 'Cart',
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- active, inactive, ordered
    created_by VARCHAR(128) NOT NULL REFERENCES users(firebase_uid) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ordered_at TIMESTAMP WITH TIME ZONE NULL,

    CONSTRAINT check_cart_status CHECK (status IN ('active', 'inactive', 'ordered')),
    INDEX idx_carts_created_by (created_by),
    INDEX idx_carts_status (status),
    INDEX idx_carts_created_at (created_at)
);
```

#### 2. `cart_users` Table (Read-Only Sharing)
```sql
CREATE TABLE cart_users (
    cart_id INTEGER NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
    user_id VARCHAR(128) NOT NULL REFERENCES users(firebase_uid) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'owner', -- owner, viewer
    shared_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    PRIMARY KEY (cart_id, user_id),
    CONSTRAINT check_cart_user_role CHECK (role IN ('owner', 'viewer')),
    INDEX idx_cart_users_user_id (user_id),
    INDEX idx_cart_users_role (role)
);
```

#### 3. `cart_items` Table
```sql
CREATE TABLE cart_items (
    id SERIAL PRIMARY KEY,
    cart_id INTEGER NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE KEY unique_cart_product (cart_id, product_id),
    CONSTRAINT check_cart_item_quantity_positive CHECK (quantity > 0),
    CONSTRAINT check_cart_item_quantity_reasonable CHECK (quantity <= 1000),
    INDEX idx_cart_items_cart_id (cart_id),
    INDEX idx_cart_items_product_id (product_id)
);
```

#### 4. `orders` Table
```sql
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL REFERENCES users(firebase_uid) ON DELETE CASCADE,
    total_amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    INDEX idx_orders_user_id (user_id),
    INDEX idx_orders_status (status),
    INDEX idx_orders_created_at (created_at)
);
```

#### 5. `order_items` Table (Grouped by Source Cart)
```sql
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    source_cart_id INTEGER NOT NULL REFERENCES carts(id), -- Which cart this item came from
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    total_price DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    CONSTRAINT check_order_item_quantity_positive CHECK (quantity > 0),
    CONSTRAINT check_order_item_price_positive CHECK (unit_price >= 0 AND total_price >= 0),
    INDEX idx_order_items_order_id (order_id),
    INDEX idx_order_items_source_cart_id (source_cart_id),
    INDEX idx_order_items_product_id (product_id)
);
```

## Key Workflows

### 1. Cart Creation & Management
```
1. User creates cart with name/description
2. User adds/modifies items (only owner can modify)
3. Cart status remains 'active' for editing
```

### 2. Cart Sharing Workflow
```
1. Owner shares cart with user_id (creates cart_users entry with role='viewer')
2. Shared user sees cart in their "Shared with me" section
3. Any changes by owner are immediately visible to shared users
4. Shared users cannot modify cart items (read-only access)
```

### 3. Multi-Cart Checkout Process
```
1. User views available carts:
   - Own carts (role='owner')
   - Shared carts (role='viewer')
2. User selects multiple carts for checkout
3. System validates all selected carts are 'active'
4. Creates single order with items grouped by source_cart_id
5. Updates ALL selected carts status to 'ordered'
6. Carts become permanently read-only
```

### 4. Cart State Management
```
- Active Cart: Owner can modify, shared users see updates on refresh
- Ordered Cart: Immutable for everyone, historical reference
- Simple Updates: Shared users see changes when they reload cart data
```

## Permission Matrix

| User Role | Cart Status | View | Add Items | Modify Items | Delete Items | Share Cart |
|-----------|-------------|------|-----------|--------------|--------------|------------|
| Owner     | active      | ✓    | ✓         | ✓            | ✓            | ✓          |
| Owner     | ordered     | ✓    | ✗         | ✗            | ✗            | ✗          |
| Viewer    | active      | ✓    | ✗         | ✗            | ✗            | ✗          |
| Viewer    | ordered     | ✓    | ✗         | ✗            | ✗            | ✗          |

## API Routes Plan

### Cart Management Routes

#### 1. Cart CRUD Operations

**Create Cart**
```
POST /api/carts
Authorization: Bearer <token>
Body: {
  "name": "Groceries",
  "description": "Weekly grocery shopping"
}
Response: 201 Created
{
  "id": 1,
  "name": "Groceries",
  "description": "Weekly grocery shopping",
  "status": "active",
  "created_by": "user123",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z",
  "items": [],
  "role": "owner"
}
```

**Get User's Carts (Own + Shared)**
```
GET /api/carts
Authorization: Bearer <token>
Response: 200 OK
{
  "owned_carts": [
    {
      "id": 1,
      "name": "Groceries",
      "status": "active",
      "items_count": 5,
      "role": "owner",
      "created_at": "2023-01-01T00:00:00Z"
    }
  ],
  "shared_carts": [
    {
      "id": 2,
      "name": "John's Electronics",
      "status": "active",
      "items_count": 3,
      "role": "viewer",
      "shared_by": "john_user_id",
      "shared_at": "2023-01-02T00:00:00Z"
    }
  ]
}
```

**Get Single Cart Details**
```
GET /api/carts/{cart_id}
Authorization: Bearer <token>
Response: 200 OK
{
  "id": 1,
  "name": "Groceries",
  "description": "Weekly grocery shopping",
  "status": "active",
  "created_by": "user123",
  "role": "owner",
  "items": [
    {
      "id": 1,
      "product_id": 101,
      "quantity": 2,
      "created_at": "2023-01-01T00:00:00Z"
    }
  ],
  "shared_with": [
    {
      "user_id": "friend123",
      "role": "viewer",
      "shared_at": "2023-01-02T00:00:00Z"
    }
  ]
}
```

**Update Cart (Owner Only)**
```
PUT /api/carts/{cart_id}
Authorization: Bearer <token>
Body: {
  "name": "Updated Cart Name",
  "description": "Updated description"
}
Response: 200 OK
```

**Delete Cart (Owner Only)**
```
DELETE /api/carts/{cart_id}
Authorization: Bearer <token>
Response: 204 No Content
```

#### 2. Cart Items Management

**Add Item to Cart (Owner Only)**
```
POST /api/carts/{cart_id}/items
Authorization: Bearer <token>
Body: {
  "product_id": 101,
  "quantity": 2
}
Response: 201 Created
```

**Update Cart Item Quantity (Owner Only)**
```
PUT /api/carts/{cart_id}/items/{item_id}
Authorization: Bearer <token>
Body: {
  "quantity": 5
}
Response: 200 OK
```

**Remove Item from Cart (Owner Only)**
```
DELETE /api/carts/{cart_id}/items/{item_id}
Authorization: Bearer <token>
Response: 204 No Content
```

**Get Cart Items**
```
GET /api/carts/{cart_id}/items
Authorization: Bearer <token>
Response: 200 OK
{
  "cart_id": 1,
  "cart_name": "Groceries",
  "user_role": "owner",
  "cart_status": "active",
  "items": [
    {
      "id": 1,
      "product_id": 101,
      "product_name": "Milk",
      "quantity": 2,
      "price": 3.99,
      "total": 7.98
    }
  ],
  "total_amount": 7.98
}
```

#### 3. Cart Sharing Routes

**Share Cart (Owner Only)**
```
POST /api/carts/{cart_id}/share
Authorization: Bearer <token>
Body: {
  "user_id": "friend123"
}
Response: 201 Created
{
  "cart_id": 1,
  "user_id": "friend123",
  "role": "viewer",
  "shared_at": "2023-01-02T00:00:00Z"
}
```

**Unshare Cart (Owner Only)**
```
DELETE /api/carts/{cart_id}/share/{user_id}
Authorization: Bearer <token>
Response: 204 No Content
```

**Get Cart Sharing Details (Owner Only)**
```
GET /api/carts/{cart_id}/shares
Authorization: Bearer <token>
Response: 200 OK
{
  "cart_id": 1,
  "shared_with": [
    {
      "user_id": "friend123",
      "user_name": "John Doe",
      "role": "viewer",
      "shared_at": "2023-01-02T00:00:00Z"
    }
  ]
}
```

### Multi-Cart Checkout Routes

#### 4. Checkout Process

**Get Available Carts for Checkout**
```
GET /api/checkout/carts
Authorization: Bearer <token>
Response: 200 OK
{
  "available_carts": [
    {
      "id": 1,
      "name": "Groceries",
      "role": "owner",
      "items_count": 3,
      "estimated_total": 25.99,
      "can_checkout": true
    },
    {
      "id": 2,
      "name": "Electronics",
      "role": "viewer",
      "items_count": 2,
      "estimated_total": 199.99,
      "can_checkout": true
    }
  ]
}
```

**Preview Multi-Cart Order**
```
POST /api/checkout/preview
Authorization: Bearer <token>
Body: {
  "cart_ids": [1, 2, 3],
  "store_id": 1
}
Response: 200 OK
{
  "order_preview": {
    "cart_groups": [
      {
        "cart_id": 1,
        "cart_name": "Groceries",
        "items": [
          {
            "product_id": 101,
            "quantity": 2,
            "unit_price": 3.99,
            "total_price": 7.98
          }
        ],
        "cart_total": 7.98
      }
    ],
    "total_amount": 225.97,
    "estimated_delivery": "2023-01-03T00:00:00Z"
  }
}
```

**Create Multi-Cart Order**
```
POST /api/checkout/order
Authorization: Bearer <token>
Body: {
  "cart_ids": [1, 2, 3],
  "store_id": 1,
  "delivery_address_id": 5
}
Response: 201 Created
{
  "order_id": 100,
  "total_amount": 225.97,
  "status": "pending",
  "cart_groups": [
    {
      "source_cart_id": 1,
      "cart_name": "Groceries",
      "items": [
        {
          "product_id": 101,
          "quantity": 2,
          "unit_price": 3.99,
          "total_price": 7.98
        }
      ]
    }
  ],
  "created_at": "2023-01-01T00:00:00Z"
}
```

### Analytics & Management Routes

#### 5. Admin/Analytics Routes

**Cart Analytics**
```
GET /api/admin/carts/analytics
Authorization: Bearer <admin_token>
Query: ?start_date=2023-01-01&end_date=2023-01-31
Response: 200 OK
{
  "cart_metrics": {
    "total_carts_created": 150,
    "active_carts": 45,
    "ordered_carts": 105,
    "conversion_rate": 70.0,
    "avg_items_per_cart": 3.2,
    "most_shared_carts": [
      {
        "cart_id": 10,
        "cart_name": "Holiday Shopping",
        "shares_count": 8
      }
    ]
  }
}
```

**Sharing Analytics**
```
GET /api/admin/carts/sharing-stats
Authorization: Bearer <admin_token>
Response: 200 OK
{
  "sharing_metrics": {
    "total_shared_carts": 25,
    "avg_viewers_per_cart": 2.4,
    "most_active_sharers": [
      {
        "user_id": "user123",
        "carts_shared": 5
      }
    ],
    "shared_cart_conversion_rate": 85.0
  }
}
```

### Error Handling & Permissions

#### 6. Permission-Based Responses

**Unauthorized Cart Access**
```
GET /api/carts/999
Authorization: Bearer <token>
Response: 403 Forbidden
{
  "error": "CART_ACCESS_DENIED",
  "message": "You don't have permission to access this cart"
}
```

**Attempt to Modify Shared Cart**
```
POST /api/carts/2/items
Authorization: Bearer <token>
Response: 403 Forbidden
{
  "error": "CART_READ_ONLY",
  "message": "You can only view this shared cart, not modify it"
}
```

**Attempt to Modify Ordered Cart**
```
PUT /api/carts/1/items/5
Authorization: Bearer <token>
Response: 409 Conflict
{
  "error": "CART_IMMUTABLE",
  "message": "This cart has been ordered and cannot be modified"
}
```

**Cart Not Found**
```
GET /api/carts/999
Authorization: Bearer <token>
Response: 404 Not Found
{
  "error": "CART_NOT_FOUND",
  "message": "Cart not found or you don't have access to it"
}
```

### Route Implementation Notes

#### Middleware Requirements
1. **Authentication Middleware**: Validate Bearer tokens on all routes
2. **Cart Permission Middleware**: Check user role (owner/viewer) for cart operations
3. **Cart Status Middleware**: Prevent modifications on ordered carts
4. **Rate Limiting**: Especially for sharing operations

#### Permission Logic
```python
def check_cart_permission(user_id: str, cart_id: int, required_role: str = "viewer"):
    # Query cart_users table to verify user has required role
    cart_user = get_cart_user(cart_id, user_id)
    if not cart_user:
        raise CartAccessDenied()

    if required_role == "owner" and cart_user.role != "owner":
        raise InsufficientPermissions()

    # Check cart status for modification operations
    cart = get_cart(cart_id)
    if cart.status == "ordered" and operation_is_modification():
        raise CartImmutable()
```

#### Real-time Updates
- **Standard API Polling**: Shared users can refresh cart data via GET requests
- **Cache Invalidation**: Update cached cart data when changes occur
- **Database Updates**: Changes immediately visible on next API call

#### Performance Optimizations
- **Pagination**: For carts list and cart items
- **Eager Loading**: Load cart items and sharing info efficiently
- **Caching**: Cache frequently accessed cart data
- **Bulk Operations**: Efficient multi-cart operations for checkout

## Order Structure with Cart Grouping

### Order Response Structure
```json
{
  "order_id": 1,
  "user_id": "user123",
  "total_amount": 150.00,
  "status": "pending",
  "cart_groups": [
    {
      "source_cart_id": 1,
      "cart_name": "Groceries",
      "items": [
        {"product_id": 101, "quantity": 2, "unit_price": 25.00, "total_price": 50.00},
        {"product_id": 102, "quantity": 1, "unit_price": 15.00, "total_price": 15.00}
      ],
      "cart_total": 65.00
    },
    {
      "source_cart_id": 2,
      "cart_name": "Electronics",
      "items": [
        {"product_id": 201, "quantity": 3, "unit_price": 20.00, "total_price": 60.00},
        {"product_id": 202, "quantity": 1, "unit_price": 25.00, "total_price": 25.00}
      ],
      "cart_total": 85.00
    }
  ]
}
```

## Analytics Capabilities

### Cart Performance Analytics
```sql
-- Conversion rate by cart
SELECT
    c.id,
    c.name,
    CASE WHEN c.status = 'ordered' THEN 'Converted' ELSE 'Active' END as status,
    COUNT(ci.id) as item_count,
    COALESCE(SUM(oi.total_price), 0) as revenue_generated
FROM carts c
LEFT JOIN cart_items ci ON c.id = ci.cart_id
LEFT JOIN order_items oi ON c.id = oi.source_cart_id
GROUP BY c.id, c.name, c.status;
```

### Multi-Cart Order Analysis
```sql
-- Orders using multiple carts
SELECT
    o.id as order_id,
    COUNT(DISTINCT oi.source_cart_id) as carts_used,
    o.total_amount,
    STRING_AGG(DISTINCT c.name, ', ') as cart_names
FROM orders o
JOIN order_items oi ON o.id = oi.order_id
JOIN carts c ON oi.source_cart_id = c.id
GROUP BY o.id, o.total_amount
HAVING COUNT(DISTINCT oi.source_cart_id) > 1;
```

### Cart Contribution Analysis
```sql
-- Revenue contribution by cart type/pattern
SELECT
    c.name,
    COUNT(DISTINCT oi.order_id) as orders_contributed,
    SUM(oi.total_price) as total_revenue,
    AVG(oi.total_price) as avg_contribution
FROM carts c
JOIN order_items oi ON c.id = oi.source_cart_id
GROUP BY c.name
ORDER BY total_revenue DESC;
```

## Migration from Current System

### Data Migration Strategy
```sql
-- Step 1: Create default cart for each user from existing cart data
INSERT INTO carts (created_by, name, created_at, updated_at)
SELECT DISTINCT user_id, 'Main Cart', MIN(created_at), MAX(updated_at)
FROM cart_legacy
GROUP BY user_id;

-- Step 2: Set ownership permissions
INSERT INTO cart_users (cart_id, user_id, role)
SELECT c.id, c.created_by, 'owner'
FROM carts c;

-- Step 3: Migrate cart items
INSERT INTO cart_items (cart_id, product_id, quantity, added_by, created_at, updated_at)
SELECT c.id, cl.product_id, cl.quantity, cl.user_id, cl.created_at, cl.updated_at
FROM cart_legacy cl
JOIN carts c ON c.created_by = cl.user_id;

-- Step 4: Update existing orders to use order_items structure
-- (Implement based on current order structure)
```

## Implementation Benefits

### For Users
- **Organization**: Separate carts for different shopping purposes
- **Collaboration**: Share carts with family/team members
- **Flexibility**: Combine multiple carts into single order
- **Transparency**: See which cart contributed each item in order

### For Business
- **Analytics**: Detailed insights into cart usage patterns
- **Conversion**: Better understanding of cart-to-order conversion
- **Fulfillment**: Efficient order processing grouped by cart origin
- **Marketing**: Target users based on cart behavior and collaboration patterns

### For System
- **Scalability**: Clean separation of concerns
- **Maintainability**: Simple 4-table structure
- **Performance**: Efficient queries with proper indexing
- **Extensibility**: Easy to add features like cart templates, favorites, etc.

This design maintains simplicity while providing powerful multi-cart functionality with comprehensive order tracking and analytics capabilities.