# Celeste E-Commerce API Documentation

## Overview

The Celeste API is a comprehensive FastAPI-based e-commerce backend that provides robust functionality for managing users, products, orders, inventory, and more. It uses Firebase for authentication and Firestore as the primary database.

## Base URL
```
http://localhost:8000
```

## Authentication

The API uses JWT-based authentication with Firebase Auth. Most endpoints require a valid Bearer token.

### Security Scheme
```
BearerAuth:
  type: http
  scheme: bearer  
  bearerFormat: JWT
```

### Headers
```
Authorization: Bearer <JWT_TOKEN>
```

## API Endpoints

### Authentication Endpoints (`/auth`)

#### POST `/auth/register`
Register a new user with Firebase authentication.

**Request Body:**
```json
{
  "name": "string",
  "idToken": "string (Firebase ID Token)"
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "message": "Registration successful",
    "user": {
      "uid": "string",
      "role": "CUSTOMER"
    }
  }
}
```

#### GET `/auth/profile`
Get current user profile information.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "uid": "string",
    "email": "string",
    "role": "CUSTOMER",
    "phone_number": "string"
  }
}
```

#### POST `/auth/dev/token` (Development Only)
Generate an ID token for development purposes.

**Request Body:**
```json
{
  "uid": "string"
}
```

---

### User Management (`/users`)

#### GET `/users/me`
Get current user's profile.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "string",
    "name": "string",
    "email": "string",
    "phone": "string",
    "address": "string",
    "role": "CUSTOMER",
    "customer_tier": "bronze",
    "total_orders": 0,
    "lifetime_value": 0.0,
    "createdAt": "datetime",
    "last_order_at": "datetime",
    "wishlist": ["productId1", "productId2"],
    "cart": [
      {
        "productId": "string",
        "quantity": 1
      }
    ]
  }
}
```

#### PUT `/users/me`
Update current user's profile.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "name": "string (optional)",
  "email": "string (optional)",
  "address": "string (optional)"
}
```

#### GET `/users/{id}` (Admin Only)
Get user profile by ID.

**Headers:** `Authorization: Bearer <admin_token>`

#### POST `/users/` (Admin Only)
Create a new user.

**Headers:** `Authorization: Bearer <admin_token>`

#### Cart Management

##### POST `/users/me/cart`
Add item to user's cart.

**Request Body:**
```json
{
  "productId": "string",
  "quantity": 1
}
```

##### PUT `/users/me/cart/{productId}`
Update cart item quantity.

**Request Body:**
```json
{
  "quantity": 2
}
```

##### DELETE `/users/me/cart/{productId}`
Remove item from cart.

##### GET `/users/me/cart`
Get user's cart.

#### Wishlist Management

##### POST `/users/me/wishlist`
Add product to wishlist.

**Request Body:**
```json
{
  "productId": "string"
}
```

##### DELETE `/users/me/wishlist/{productId}`
Remove product from wishlist.

##### GET `/users/me/wishlist`
Get user's wishlist.

---

### Product Management (`/products`)

#### GET `/products/` ⭐ **Enhanced with Smart Pricing**
Get all products with smart pricing and cursor-based pagination.

**Query Parameters:**
- `limit`: Number of products to return (default: 20, max: 100)
- `cursor`: Cursor for pagination (product ID to start from)
- `include_pricing`: Include pricing calculations (default: true)
- `categoryId`: Filter by category ID
- `minPrice`: Minimum price filter
- `maxPrice`: Maximum price filter
- `isFeatured`: Filter featured products only

**Headers (Optional):** `Authorization: Bearer <token>` (for tier-based pricing)

**Response (200):**
```json
{
  "success": true,
  "data": {
    "products": [
      {
        "id": "string",
        "name": "string",
        "description": "string",
        "price": 99.99,
        "unit": "string",
        "categoryId": "string",
        "imageUrl": "string",
        "createdAt": "datetime",
        "updatedAt": "datetime",
        "pricing": {
          "base_price": 99.99,
          "final_price": 84.99,
          "discount_applied": 15.00,
          "discount_percentage": 15.15,
          "applied_price_lists": ["Gold Customer Discounts"],
          "customer_tier": "gold"
        },
        "inventory": {
          "in_stock": true,
          "quantity_available": 50,
          "reserved_quantity": 5,
          "reorder_level": 10
        }
      }
    ],
    "pagination": {
      "current_cursor": null,
      "next_cursor": "product_abc123",
      "has_more": true,
      "total_returned": 20
    }
  }
}
```

#### GET `/products/{id}` ⭐ **Enhanced with Smart Pricing**
Get product by ID with automatic tier-based pricing.

**Query Parameters:**
- `include_pricing`: Include pricing calculations (default: true)
- `quantity`: Quantity for bulk pricing (default: 1)

**Headers (Optional):** `Authorization: Bearer <token>` (for tier-based pricing)

#### GET `/products/legacy`
Get all products in legacy format (backward compatibility).

**Query Parameters:**
- `limit`: Number of products to return
- `includeDiscounts`: Include discount information
- `categoryId`: Filter by category ID
- `minPrice`: Minimum price filter  
- `maxPrice`: Maximum price filter
- `isFeatured`: Filter featured products only

#### POST `/products/` (Admin Only)
Create a new product.

**Headers:** `Authorization: Bearer <admin_token>`

**Request Body:**
```json
{
  "name": "string",
  "description": "string (optional)",
  "price": 99.99,
  "unit": "string",
  "categoryId": "string",
  "imageUrl": "string (optional)"
}
```

#### PUT `/products/{id}` (Admin Only)
Update a product.

#### DELETE `/products/{id}` (Admin Only)
Delete a product.

---

### Pricing Management (`/pricing`) ⭐ **New**

#### Price List Management (Admin Only)

##### GET `/pricing/price-lists`
Get all price lists with filtering.

**Headers:** `Authorization: Bearer <admin_token>`

**Query Parameters:**
- `active_only`: Filter to show only active price lists (default: false)

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "string",
      "name": "Gold Customer Discounts",
      "priority": 1,
      "active": true,
      "valid_from": "2024-01-01T00:00:00Z",
      "valid_until": "2024-12-31T23:59:59Z",
      "created_at": "datetime",
      "updated_at": "datetime"
    }
  ]
}
```

##### POST `/pricing/price-lists`
Create a new price list.

**Headers:** `Authorization: Bearer <admin_token>`

**Request Body:**
```json
{
  "name": "string",
  "priority": 1,
  "active": true,
  "valid_from": "2024-01-01T00:00:00Z",
  "valid_until": "2024-12-31T23:59:59Z"
}
```

##### GET `/pricing/price-lists/{id}/lines`
Get price list lines for a specific price list.

##### POST `/pricing/price-lists/{id}/lines`
Add a price list line.

**Request Body:**
```json
{
  "type": "product",
  "product_id": "string",
  "discount_type": "percentage",
  "amount": 15.0,
  "min_product_qty": 1,
  "max_product_qty": 100
}
```

#### Price Calculation Endpoints

##### POST `/pricing/calculate-price`
Calculate price for a single product.

**Request Body:**
```json
{
  "product_id": "string",
  "customer_tier": "gold",
  "quantity": 1
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "product_id": "string",
    "base_price": 99.99,
    "final_price": 84.99,
    "discount_applied": 15.00,
    "discount_percentage": 15.15,
    "quantity": 1,
    "customer_tier": "gold",
    "applied_price_lists": ["Gold Customer Discounts"]
  }
}
```

##### POST `/pricing/calculate-bulk-prices`
Calculate prices for multiple products (cart scenarios).

**Request Body:**
```json
{
  "customer_tier": "gold",
  "items": [
    {
      "product_id": "string",
      "quantity": 2
    }
  ]
}
```

##### GET `/pricing/my-price/{product_id}`
Get product price for current authenticated user.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `quantity`: Quantity for bulk pricing (default: 1)

---

### Development Tools (`/dev`) ⭐ **Development Environment Only**

#### POST `/dev/auth/token`
Generate development tokens for testing.

**Request Body:**
```json
{
  "uid": "string"
}
```

#### POST `/dev/db/add`
Add test data to database collections.

**Request Body:**
```json
{
  "collection": "string",
  "data": {}
}
```

#### GET `/dev/db/collections`
List all database collections.

#### GET `/dev/db/{collection}`
Get all documents from a collection.

---

### Category Management (`/categories`)

#### GET `/categories/`
Get all categories.

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "string",
      "name": "string",
      "description": "string"
    }
  ]
}
```

#### GET `/categories/{id}`
Get category by ID.

#### POST `/categories/` (Admin Only)
Create a new category.

#### PUT `/categories/{id}` (Admin Only)
Update a category.

#### DELETE `/categories/{id}` (Admin Only)
Delete a category.

---

### Order Management (`/orders`)

#### GET `/orders/`
Get orders (admins see all, customers see their own).

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "string",
      "userId": "string",
      "items": [
        {
          "productId": "string",
          "quantity": 1,
          "price": 99.99
        }
      ],
      "totalAmount": 99.99,
      "status": "pending",
      "createdAt": "datetime"
    }
  ]
}
```

#### GET `/orders/{id}`
Get specific order (with authorization checks).

#### POST `/orders/`
Create a new order.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "items": [
    {
      "productId": "string",
      "quantity": 1
    }
  ],
  "deliveryAddress": "string"
}
```

#### PUT `/orders/{id}` (Admin Only)
Update order status.

#### DELETE `/orders/{id}` (Admin Only)
Delete an order.

---

### Discount Management (`/discounts`)

#### GET `/discounts/`
Get all discounts.

#### GET `/discounts/{id}`
Get discount by ID.

#### POST `/discounts/` (Admin Only)
Create a new discount.

#### PUT `/discounts/{id}` (Admin Only)
Update a discount.

#### DELETE `/discounts/{id}` (Admin Only)
Delete a discount.

---

### Inventory Management (`/inventory`)

#### GET `/inventory/`
Get all inventory records.

#### GET `/inventory/{id}`
Get inventory by ID.

#### POST `/inventory/` (Admin Only)
Create inventory record.

#### PUT `/inventory/{id}` (Admin Only)
Update inventory.

#### DELETE `/inventory/{id}` (Admin Only)
Delete inventory record.

---

### Store Management (`/stores`)

#### GET `/stores/`
Get all stores.

#### GET `/stores/{id}`
Get store by ID.

#### POST `/stores/` (Admin Only)
Create a new store.

#### PUT `/stores/{id}` (Admin Only)
Update a store.

#### DELETE `/stores/{id}` (Admin Only)
Delete a store.

---

### Promotions (`/promotions`)

#### GET `/promotions/`
Get all promotions.

#### POST `/promotions/` (Admin Only)
Create a new promotion.

---

## Data Models

### User Roles
- `CUSTOMER`: Regular customer with limited access (default)
- `ADMIN`: Administrator with full access

### Customer Tiers ⭐ **New**
- `bronze`: Default tier for new customers (0 discount)
- `silver`: Mid-tier customer (higher discounts)
- `gold`: High-value customer (premium discounts)
- `platinum`: VIP customer (maximum discounts)

### Order Status
- `pending`: Order placed but not processed
- `processing`: Order being processed  
- `shipped`: Order shipped
- `delivered`: Order delivered
- `cancelled`: Order cancelled

### Discount Types
- `percentage`: Percentage-based discount
- `flat`: Fixed amount discount

### Price List Types ⭐ **New**
- `product`: Product-specific pricing rules
- `category`: Category-specific pricing rules
- `all`: Global pricing rules (applies to all products)

## Error Handling

The API uses standardized error responses:

```json
{
  "success": false,
  "error": {
    "message": "Error description",
    "code": "ERROR_CODE",
    "details": {}
  }
}
```

### Common HTTP Status Codes
- `200`: Success
- `201`: Created
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `422`: Validation Error
- `500`: Internal Server Error

## Rate Limiting & Performance

- All requests include a `X-Process-Time` header showing processing time
- Requests are logged with detailed information for monitoring

## Development Features

In development environment, additional endpoints are available:
- `/auth/dev/token`: Generate development tokens
- Enhanced logging and debugging features

## Firebase Integration

The API integrates with Firebase services:
- **Firebase Auth**: User authentication and authorization
- **Firestore**: Primary database for all data storage
- **Custom Claims**: Role-based access control

## ⭐ New Features & Enhancements

### Smart Product Pricing System
- **Automatic Tier Detection**: Bearer tokens automatically detect user tier for personalized pricing
- **Bulk Price Calculations**: Efficient pricing for multiple products in a single request
- **Cursor-Based Pagination**: High-performance pagination using Firebase `startAt`
- **Global Price Lists**: Enhanced price list control with `is_global` field support
- **Database-Backed Tiers**: User tiers stored in Firestore with automatic BRONZE default

### Enhanced Product API
- **Smart Pricing Integration**: Products automatically include tier-based pricing when authenticated
- **Performance Optimization**: Default limit 20, maximum 100 for optimal performance
- **Inventory Placeholders**: Future-ready structure for inventory management
- **Backward Compatibility**: Legacy endpoints maintain existing functionality

### Development Features
- **Database Management**: Tools for adding test data and managing collections
- **Token Generation**: Development token creation for testing authentication
- **Collection Browsing**: Direct database collection viewing and management

### Performance Features
- **Efficient Queries**: Firestore queries optimized to avoid composite indexes
- **Memory Optimization**: Bulk processing and reduced database calls
- **Graceful Fallbacks**: Error-resilient tier detection with automatic defaults
- **UTC Timezone Handling**: Proper datetime handling for price list validity

## Response Format

All successful responses follow this format:
```json
{
  "success": true,
  "data": <response_data>
}
```

All error responses follow this format:
```json
{
  "success": false,
  "error": {
    "message": "string",
    "code": "string",
    "details": {}
  }
}
```