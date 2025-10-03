# Celeste E-Commerce API Documentation

## Overview

The Celeste API is a comprehensive FastAPI-based e-commerce backend that provides robust functionality for managing users, products, orders, inventory, and more. It uses Firebase for authentication and PostgreSQL as the primary database, with a Redis-based caching layer for high performance.

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
  "idToken": "string (Firebase ID Token)",
  "name": "string"
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
      "role": "CUSTOMER",
      "tier_id": "integer"
    }
  }
}
```

### Development Endpoints (`/dev`)

#### POST `/dev/auth/token`
Generate a development ID token for an existing user.

**Request Body:**
```json
{
  "uid": "string"
}
```

#### POST `/dev/db/add`
Add data to a database collection.

#### GET `/dev/db/collections`
List all collections in the database.

#### GET `/dev/db/{collection}`
Get all documents from a collection.

#### DELETE `/dev/db/{collection}`
Clear all documents from a collection.

---

### User Management (`/users`)

#### GET `/users/me`
Get current user's profile.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `include_addresses`: boolean (default: true)

**Response (200):**
```json
{
  "success": true,
  "data": {
    "firebase_uid": "string",
    "name": "string",
    "email": "string",
    "phone": "string",
    "role": "CUSTOMER",
    "tier_id": "integer",
    "total_orders": 0,
    "lifetime_value": 0.0,
    "created_at": "datetime",
    "last_order_at": "datetime",
    "addresses": [
      {
        "id": "integer",
        "address": "string",
        "latitude": "float",
        "longitude": "float",
        "is_default": "boolean",
        "created_at": "datetime",
        "updated_at": "datetime"
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
  "is_delivery": "boolean (optional)"
}
```

#### Address Management

##### POST `/users/me/addresses`
Add a new address for the current user.

##### GET `/users/me/addresses`
Get all addresses for the current user.

##### GET `/users/me/addresses/{address_id}`
Get a specific address for the current user.

##### PUT `/users/me/addresses/{address_id}`
Update a specific address for the current user.

##### DELETE `/users/me/addresses/{address_id}`
Delete a specific address for the current user.

##### PUT `/users/me/addresses/{address_id}/set_default`
Set a specific address as default for the current user.

#### Multi-Cart System

##### POST `/users/me/carts`
Create a new cart.

##### GET `/users/me/carts`
Get all user carts (owned + shared).

##### GET `/users/me/carts/{cart_id}`
Get cart details.

##### PUT `/users/me/carts/{cart_id}`
Update cart details (owner only).

##### DELETE `/users/me/carts/{cart_id}`
Delete cart (owner only).

##### POST `/users/me/carts/{cart_id}/items`
Add item to cart (owner only).

##### PUT `/users/me/carts/{cart_id}/items/{item_id}`
Update cart item quantity (owner only).

##### DELETE `/users/me/carts/{cart_id}/items/{product_id}`
Remove product from cart or reduce quantity (owner only).

##### POST `/users/me/carts/{cart_id}/share`
Share cart with another user (owner only).

##### DELETE `/users/me/carts/{cart_id}/share/{target_user_id}`
Remove cart sharing (owner only).

##### GET `/users/me/carts/{cart_id}/shares`
Get cart sharing details (owner only).

#### Checkout

##### GET `/users/me/checkout/carts`
Get available carts for checkout.

##### POST `/users/me/checkout/preview`
Preview multi-cart order.

##### POST `/users/me/checkout/order`
Create multi-cart order.

---

### Product Management (`/products`)

#### GET `/products/`
Get all products with smart pricing and pagination.

**Query Parameters:**
- `limit`, `cursor`, `include_pricing`, `include_categories`, `include_tags`, `category_ids`, `tags`, `min_price`, `max_price`, `only_discounted`, `store_id`, `include_inventory`, `latitude`, `longitude`

#### GET `/products/recents`
Get recently bought products for the current user.

#### GET `/products/{id}`
Get a product by ID with smart pricing and location support.

#### GET `/products/ref/{ref}`
Get a product by reference/SKU with smart pricing and location support.

#### POST `/products/` (Admin Only)
Create one or more new products.

#### PUT `/products/{id}` (Admin Only)
Update a product.

#### DELETE `/products/{id}` (Admin Only)
Delete a product.

#### Product Tag Management

##### POST `/products/tags` (Admin Only)
Create one or more new product tags.

##### GET `/products/tags`
Get all product tags.

##### GET `/products/tags/types`
Get all available product tag types.

##### GET `/products/tags/{tag_id}`
Get a tag by ID.

##### PUT `/products/tags/{tag_id}` (Admin Only)
Update a tag.

##### DELETE `/products/tags/{tag_id}` (Admin Only)
Delete a tag.

##### POST `/{product_id}/tags/{tag_id}` (Admin Only)
Assign a tag to a product.

##### DELETE `/{product_id}/tags/{tag_id}` (Admin Only)
Remove a tag from a product.

---

### Category Management (`/categories`)

Standard CRUD endpoints for categories: `GET /`, `GET /{id}`, `POST /`, `PUT /{id}`, `DELETE /{id}`.

---

### Ecommerce Category Management (`/ecommerce-categories`)

Standard CRUD endpoints for ecommerce categories (Admin only): `GET /`, `GET /{id}`, 'POST /', `PUT /{id}`, `DELETE /{id}`.

---

### Order Management (`/orders`)

#### GET `/orders/`
Retrieve orders (admins see all, customers see their own).

#### GET `/orders/{order_id}`
Retrieve a specific order.

#### POST `/orders/` (Admin Only)
Create a new order.

#### PUT `/orders/{order_id}/status` (Admin Only)
Update an order status.

#### POST `/orders/payment/callback`
Handle payment gateway callback.

#### POST `/orders/{order_id}/payment/verify`
Verify payment status.

---

### Inventory Management (`/inventory`)

Standard CRUD endpoints for inventory: `GET /`, `GET /{inventory_id}`, `POST /`, `PUT /{inventory_id}`, `DELETE /{inventory_id}`. Also includes `POST /adjust` for stock adjustments.

---

### Store Management (`/stores`)

#### GET `/stores/`
Get all stores with optional location filtering.

#### GET `/stores/nearby`
Optimized nearby stores search.

#### GET `/stores/{store_id}`
Get store by ID.

#### GET `/stores/{store_id}/distance`
Calculate distance to specific store.

#### POST `/stores/` (Admin Only)
Create a new store.

#### PUT `/stores/{store_id}` (Admin Only)
Update a store.

#### DELETE `/stores/{store_id}` (Admin Only)
Delete a store.

#### Store Tag Management
- `POST /tags`
- `GET /tags`
- `GET /tags/types`
- `GET /tags/{tag_id}`
- `PUT /tags/{tag_id}`
- `DELETE /tags/{tag_id}`
- `POST /{store_id}/tags/{tag_id}`
- `DELETE /{store_id}/tags/{tag_id}`
- `GET /{store_id}/tags`

---

### Pricing Management (`/pricing`)

#### Price List Management (Admin Only)
- `GET /price-lists`
- `GET /price-lists/{price_list_id}`
- `POST /price-lists`
- `PUT /price-lists/{price_list_id}`
- `DELETE /price-lists/{price_list_id}`

#### Price List Lines Management (Admin Only)
- `GET /price-lists/{price_list_id}/lines`
- `POST /price-lists/{price_list_id}/lines`
- `PUT /price-lists/lines/{line_id}`
- `DELETE /price-lists/lines/{line_id}`

#### Tier Price List Association (Admin Only)
- `POST /tiers/{tier_id}/price-lists/{price_list_id}`
- `DELETE /tiers/{tier_id}/price-lists/{price_list_id}`
- `GET /tiers/{tier_id}/price-lists`

#### Pricing Calculation
- `GET /calculate/product/{product_id}`
- `POST /calculate/bulk`

---

### Customer Tiers (`/tiers`)

#### Public Endpoints
- `GET /`
- `GET /{tier_id}`

#### Admin-only Endpoints
- `POST /`
- `PUT /{tier_id}`
- `DELETE /{tier_id}`
- `POST /initialize-defaults`
- `GET /users/{user_id}/tier`
- `POST /users/{user_id}/evaluate-tier`
- `POST /users/{user_id}/auto-update-tier`
- `PUT /users/{user_id}/tier`

#### User-specific Endpoints
- `GET /users/me/tier`
- `GET /users/me/tier-progress`
- `POST /users/me/evaluate-tier`
- `POST /users/me/auto-update-tier`

#### Benefits CRUD (Admin only)
- `GET /benefits/`
- `GET /benefits/{benefit_id}`
- `POST /benefits/`
- `PUT /benefits/{benefit_id}`
- `DELETE /benefits/{benefit_id}`

#### Tier-Benefit Association (Admin only)
- `GET /{tier_id}/benefits`
- `POST /{tier_id}/benefits/{benefit_id}`
- `DELETE /{tier_id}/benefits/{benefit_id}`

---

### Tags (`/tags`)

General CRUD for tags: `POST /`, `GET /`, `GET /types`, `GET /{tag_id}`, `PUT /{tag_id}`, `DELETE /{tag_id}`.