# Celeste E-Commerce API Documentation

## Overview

The Celeste API is a comprehensive FastAPI-based e-commerce backend that provides robust functionality for managing users, products, orders, inventory, and more. It uses Firebase for authentication and Firestore as the primary database, with a Redis-based caching layer for high performance.

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

## Caching Strategy ⭐ NEW

The Celeste API uses a sophisticated caching layer to ensure high performance and reduce database load. The caching is implemented using Redis.

### Cache Layers

-   **Redis Cache:** A distributed cache shared across all instances of the application. It is used to cache frequently accessed data such as products, categories, price lists, and customer tiers.

### Cache Invalidation

-   **Automatic Invalidation:** The cache is automatically invalidated when data is created, updated, or deleted.
-   **Cross-Domain Invalidation:** A centralized cache invalidation manager ensures that changes in one domain (e.g., tiers) correctly invalidate dependent data in other domains (e.g., pricing).

### Cached Data

The following data is cached:
-   Products
-   Categories
-   Price Lists and Price List Lines
-   Customer Tiers
-   Stores (non-location based queries only)

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
- `only_discounted`: Filter for products with discounts applied (default: false)

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

### Pricing Management (`/pricing`)

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

---

### Customer Tiers (`/tiers`)

Customer tier management system for automatic tier evaluation, benefits, and progress tracking.

#### GET `/tiers/`
Get all customer tiers (public endpoint).

**Query Parameters:**
- `active_only`: Filter to show only active tiers (default: true)

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "string",
      "name": "Bronze",
      "tier_code": "bronze",
      "level": 1,
      "requirements": {
        "min_orders": 0,
        "min_lifetime_value": 0.0,
        "min_monthly_orders": 0
      },
      "benefits": {
        "price_list_ids": [],
        "delivery_discount": 0.0,
        "priority_support": false,
        "early_access": false
      },
      "color": "#CD7F32",
      "active": true
    }
  ]
}
```

#### GET `/tiers/{tier_id}`
Get specific customer tier by ID (public endpoint).

#### POST `/tiers/` (Admin Only)
Create a new customer tier.

**Request Body:**
```json
{
  "name": "Platinum",
  "tier_code": "platinum",
  "level": 4,
  "requirements": {
    "min_orders": 50,
    "min_lifetime_value": 2000.0,
    "min_monthly_orders": 5
  },
  "benefits": {
    "price_list_ids": ["premium-prices"],
    "delivery_discount": 15.0,
    "priority_support": true,
    "early_access": true
  },
  "color": "#E5E4E2"
}
```

#### PUT `/tiers/{tier_id}` (Admin Only)
Update an existing customer tier.

#### DELETE `/tiers/{tier_id}` (Admin Only)
Delete a customer tier.

#### POST `/tiers/initialize-defaults` (Admin Only)
Initialize default customer tiers (Bronze, Silver, Gold, Platinum).

#### User Tier Endpoints

##### GET `/tiers/users/me/tier`
Get current user's complete tier information.

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "user_id": "string",
    "current_tier": "silver",
    "tier_info": {
      "name": "Silver",
      "level": 2,
      "requirements": {...},
      "benefits": {...}
    },
    "progress": {
      "current_tier": "silver",
      "next_tier": "gold",
      "progress": {
        "orders": {
          "current": 8,
          "required": 20,
          "progress_percentage": 40
        }
      }
    },
    "statistics": {
      "total_orders": 8,
      "lifetime_value": 150.0,
      "monthly_orders": 2
    }
  }
}
```

##### GET `/tiers/users/me/tier-progress`
Get current user's tier progress towards next level.

##### POST `/tiers/users/me/evaluate-tier`
Evaluate what tier the current user should be in.

##### POST `/tiers/users/me/auto-update-tier`
Automatically evaluate and update current user's tier.

#### Admin User Tier Management

##### GET `/tiers/users/{user_id}/tier` (Admin Only)
Get tier information for specific user.

##### POST `/tiers/users/{user_id}/evaluate-tier` (Admin Only)
Evaluate tier for specific user.

##### POST `/tiers/users/{user_id}/auto-update-tier` (Admin Only)
Auto-evaluate and update tier for specific user.

##### PUT `/tiers/users/{user_id}/tier` (Admin Only)
Manually update a user's tier.

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

### Store Management (`/stores`) ⭐ **Enhanced with Geospatial Features**

The store management system provides comprehensive functionality for managing physical store locations with advanced geospatial capabilities using geopy for precise distance calculations.

#### GET `/stores/` ⭐ **Unified Store Endpoint**
Get all stores with optional location-based filtering and distance calculations.

**Query Parameters:**
- `latitude`: User latitude for distance calculations (optional)
- `longitude`: User longitude for distance calculations (optional)  
- `radius`: Search radius in km for filtering (optional, requires lat/lon)
- `limit`: Maximum number of stores to return (default: 20, max: 100)
- `isActive`: Filter by store status (default: true)
- `features`: Filter by store features (can specify multiple)
- `includeDistance`: Include distance calculations in km (default: true when lat/lon provided)
- `includeOpenStatus`: Include open/closed status (default: false)

**Response (200):**
```json
{
  "success": true,
  "data": {
    "stores": [
      {
        "id": "string",
        "name": "Downtown Store",
        "description": "Main downtown location",
        "address": "123 Main St, City, State 12345",
        "location": {
          "latitude": 40.7128,
          "longitude": -74.0060
        },
        "contact": {
          "phone": "+1234567890",
          "email": "store@example.com"
        },
        "hours": {
          "monday": {
            "open": "09:00",
            "close": "18:00",
            "closed": false
          }
        },
        "features": ["wifi", "parking", "wheelchair_accessible"],
        "isActive": true,
        "created_at": "datetime",
        "updated_at": "datetime",
        "distance": 2.3,
        "is_open_now": true,
        "next_change": "18:00"
      }
    ],
    "user_location": {
      "latitude": 40.7128,
      "longitude": -74.0060
    },
    "search_radius": null,
    "total_found": 15,
    "returned": 15
  }
}
```

**Usage Examples:**
```bash
# Get all stores (cached, no distances)
GET /stores

# Get all stores with distances (no radius filtering)
GET /stores?latitude=40.7128&longitude=-74.0060&includeDistance=true

# Get stores with features filtering
GET /stores?features=wifi&features=parking&limit=10

# Get nearby stores within radius
GET /stores?latitude=40.7128&longitude=-74.0060&radius=5&includeDistance=true

# Get stores with business hours status
GET /stores?includeOpenStatus=true
```

#### GET `/stores/nearby` ⭐ **Optimized Nearby Search**
Specialized endpoint for location-based store searches (requires coordinates).

**Query Parameters (Required):**
- `latitude`: User latitude (required)
- `longitude`: User longitude (required)

**Query Parameters (Optional):**
- `radius`: Search radius in km (default: 10, max: 50)
- `limit`: Maximum stores to return (default: 20, max: 100)
- `features`: Required store features
- `includeDistance`: Include distance calculations (default: true)
- `includeOpenStatus`: Include business hours status (default: true)

**Response:** Same format as `/stores` but sorted by distance.

#### GET `/stores/{id}`
Get detailed information about a specific store.

**Query Parameters:**
- `includeInventory`: Include store inventory (default: false)

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "string",
    "name": "Downtown Store",
    "description": "Main downtown location",
    "address": "123 Main St, City, State 12345",
    "location": {
      "latitude": 40.7128,
      "longitude": -74.0060
    },
    "contact": {
      "phone": "+1234567890",
      "email": "store@example.com"
    },
    "hours": {
      "monday": {"open": "09:00", "close": "18:00", "closed": false},
      "tuesday": {"open": "09:00", "close": "18:00", "closed": false},
      "sunday": {"closed": true}
    },
    "features": ["wifi", "parking", "wheelchair_accessible", "drive_through"],
    "isActive": true,
    "created_at": "datetime",
    "updated_at": "datetime"
  }
}
```

#### GET `/stores/{store_id}/distance`
Calculate distance from user location to specific store.

**Query Parameters (Required):**
- `latitude`: User latitude
- `longitude`: User longitude

**Response (200):**
```json
{
  "success": true,
  "data": {
    "store_id": "string",
    "store_name": "Downtown Store",
    "user_location": {
      "latitude": 40.7128,
      "longitude": -74.0060
    },
    "store_location": {
      "latitude": 40.7580,
      "longitude": -73.9855
    },
    "distance_km": 5.2,
    "store_address": "123 Main St, City, State 12345"
  }
}
```

#### POST `/stores/` (Admin Only)
Create a new store with location coordinates.

**Headers:** `Authorization: Bearer <admin_token>`

**Request Body:**
```json
{
  "name": "New Store Location",
  "description": "Store description",
  "address": "456 Oak Ave, City, State 12345",
  "location": {
    "latitude": 40.7580,
    "longitude": -73.9855
  },
  "contact": {
    "phone": "+1234567890",
    "email": "newstore@example.com"
  },
  "hours": {
    "monday": {"open": "09:00", "close": "18:00", "closed": false}
  },
  "features": ["wifi", "parking"],
  "isActive": true
}
```

#### PUT `/stores/{id}` (Admin Only)
Update an existing store.

**Headers:** `Authorization: Bearer <admin_token>`

**Request Body:** Same as POST but all fields optional

#### DELETE `/stores/{id}` (Admin Only)
Delete a store.

**Headers:** `Authorization: Bearer <admin_token>`

#### Store Features
Available store features for filtering:
- `parking`: Parking available
- `wifi`: Free WiFi
- `wheelchair_accessible`: Wheelchair accessible
- `drive_through`: Drive-through service
- `pickup_available`: Curbside pickup
- `delivery_available`: Local delivery service

---


## Data Models

### User Roles
- `CUSTOMER`: Regular customer with limited access (default)
- `ADMIN`: Administrator with full access

### Customer Tiers
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

### Price List Types
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
