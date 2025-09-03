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
    "createdAt": "datetime",
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

#### GET `/products/`
Get all products with optional filtering.

**Query Parameters:**
- `limit`: Number of products to return
- `offset`: Pagination offset
- `includeDiscounts`: Include discount information
- `includeInventory`: Include inventory information
- `categoryId`: Filter by category ID
- `minPrice`: Minimum price filter
- `maxPrice`: Maximum price filter
- `isFeatured`: Filter featured products only

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "string",
      "name": "string",
      "description": "string",
      "price": 99.99,
      "unit": "string",
      "categoryId": "string",
      "imageUrl": "string",
      "createdAt": "datetime",
      "updatedAt": "datetime"
    }
  ]
}
```

#### GET `/products/{id}`
Get product by ID.

**Query Parameters:**
- `includeDiscounts`: Include discount information
- `includeInventory`: Include inventory information

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
- `CUSTOMER`: Regular customer with limited access
- `ADMIN`: Administrator with full access

### Order Status
- `pending`: Order placed but not processed
- `processing`: Order being processed  
- `shipped`: Order shipped
- `delivered`: Order delivered
- `cancelled`: Order cancelled

### Discount Types
- `PERCENTAGE`: Percentage-based discount
- `FLAT`: Fixed amount discount

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