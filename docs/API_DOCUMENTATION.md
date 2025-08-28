# Celeste E-Commerce API Documentation

## Table of Contents
1. [Overview](#overview)
2. [Technologies](#technologies)
3. [Database Structure](#database-structure)
4. [Authentication](#authentication)
5. [API Endpoints](#api-endpoints)
   - [Auth](#auth)
   - [Users](#users)
   - [Categories](#categories)
   - [Products](#products)
   - [Featured Products](#featured-products)
   - [Discounts](#discounts)
   - [Promotions](#promotions)
   - [Orders](#orders)
   - [Inventory](#inventory)
   - [Stores](#stores)
6. [Query Parameters](#query-parameters)
7. [Data Models (Zod Schemas)](#data-models-zod-schemas)
8. [Error Handling](#error-handling)
9. [Response Format](#response-format)
10. [Logging](#logging)

## Overview

This document provides a comprehensive guide to the Celeste E-Commerce API, built with NestJS and Firebase. The API follows a modular architecture and implements all the necessary endpoints for a complete e-commerce platform.

## Technologies

- **Framework**: NestJS (TypeScript)
- **Authentication**: Firebase Authentication
- **Database**: Firestore (Firebase)
- **Validation**: Zod
- **Testing**: Jest
- **Code Quality**: ESLint, Prettier

## Database Structure

The database follows a NoSQL structure with the following collections in Firestore:

- `/users/{userId}`
- `/categories/{categoryId}`
- `/products/{productId}`
- `/featured/{featuredId}`
- `/discounts/{discountId}`
- `/promotions/{promotionId}`
- `/orders/{orderId}`
- `/inventory/{inventoryId}`
- `/stores/{storeId}`

*For detailed schemas, see the [Data Models (Zod Schemas)](#data-models-zod-schemas) section.*

## Authentication

Most API endpoints require authentication using Firebase Authentication. The API expects a valid Firebase ID token in the `Authorization` header:

```
Authorization: Bearer <Firebase_ID_Token>
```

The backend verifies the token and extracts user information for authorization checks. Endpoints that are publicly accessible are marked with **(Public)**.

### Public Endpoints

Endpoints for reading data (e.g., `GET /products`, `GET /categories`) are generally public. Endpoints that modify data (e.g., `POST`, `PUT`, `DELETE`) are protected, with the exception of user creation.

## API Endpoints

### Auth

Handles token verification.

#### Verify Token
- **Endpoint**: `POST /auth/verify`
- **Access**: Public
- **Description**: Verifies a Firebase ID token.
- **Request Header**: `Authorization: Bearer <Firebase_ID_Token>`
- **Success Response (200)**:
  ```json
  {
    "valid": true,
    "user": { ...decodedToken }
  }
  ```
- **Error Response (200)**:
  ```json
  {
    "valid": false,
    "message": "Invalid token"
  }
  ```

### Users

Manages user profiles, wishlists, and shopping carts.

- `GET /users/{id}`: Retrieves a user's profile.
- `POST /users`: (Public) Creates a new user.
- `PUT /users/{id}`: Updates a user's profile.
- `DELETE /users/{id}`: Deletes a user.
- `POST /users/{id}/wishlist`: Adds a product to the user's wishlist.
- `DELETE /users/{id}/wishlist/{productId}`: Removes a product from the user's wishlist.
- `POST /users/{id}/cart`: Adds a product to the user's cart.
- `PUT /users/{id}/cart/{productId}`: Updates the quantity of a product in the cart.
- `DELETE /users/{id}/cart/{productId}`: Removes a product from the cart.

### Categories

Manages product categories. Data is read-only via the API.

- `GET /categories`: (Public) Retrieves all categories.
- `GET /categories/{id}`: (Public) Retrieves a specific category.

### Products

Manages products. Data is read-only via the API.

- `GET /products`: (Public) Retrieves all products with filtering and pagination.
- `GET /products/{id}`: (Public) Retrieves a specific product.

### Featured Products

Manages featured products. Data is read-only via the API.

- `GET /featured`: (Public) Retrieves all featured products.
- `GET /featured/{id}`: (Public) Retrieves a specific featured product entry.

### Discounts

Manages discounts. Data is read-only via the API.

- `GET /discounts`: (Public) Retrieves all active discounts.
- `GET /discounts/{id}`: (Public) Retrieves a specific discount.

### Promotions

Manages promotions. Data is read-only via the API.

- `GET /promotions`: (Public) Retrieves all active promotions.
- `GET /promotions/{id}`: (Public) Retrieves a specific promotion.

### Orders

Manages customer orders.

- `GET /orders`: Retrieves all orders for the authenticated user.
- `GET /orders/{id}`: Retrieves a specific order.
- `POST /orders`: Creates a new order from the user's cart.
- `PUT /orders/{id}`: Updates an order status (admin only).
- `DELETE /orders/{id}`: Deletes an order (admin only).

### Inventory

Manages product inventory. Data is read-only via the API.

- `GET /inventory`: (Public) Retrieves all inventory items.
- `GET /inventory/product/{productId}`: (Public) Retrieves inventory for a specific product.

### Stores

Manages physical store locations. Data is read-only via the API.

- `GET /stores`: (Public) Retrieves all stores.
- `GET /stores/{id}`: (Public) Retrieves a specific store.
- `GET /stores/nearby`: (Public) Retrieves stores near a specific location.

## Query Parameters

The API supports various query parameters for filtering, sorting, and pagination:

| Parameter | Type    | Description                               |
|-----------|---------|-------------------------------------------|
| `limit`   | number  | Number of items to return (default: 10)   |
| `offset`  | number  | Number of items to skip (default: 0)      |
| `sortBy`  | string  | Field to sort by                          |
| `order`   | string  | Sort order: "asc" or "desc"             |

## Data Models (Zod Schemas)

Data validation is handled by Zod schemas, which serve as the single source of truth for the application's data structures.

<details>
<summary>User Schemas</summary>

```typescript
// src/users/schemas/user.schema.ts

export const CartItemSchema = z.object({
  productId: z.string(),
  quantity: z.number().int().positive(),
  addedAt: z.date(),
});

export const UserSchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1),
  email: z.string().email(),
  phone: z.string().optional(),
  address: z.string().optional(),
  role: z.enum(['customer', 'admin']),
  createdAt: z.date().optional(),
  wishlist: z.array(z.string()).optional(),
  cart: z.array(CartItemSchema).optional(),
});
```
</details>

<details>
<summary>Category Schema</summary>

```typescript
// src/categories/schemas/category.schema.ts

export const CategorySchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1),
  description: z.string().optional(),
  imageUrl: z.string().optional(),
  parentCategoryId: z.string().nullable(),
});
```
</details>

<details>
<summary>Product Schema</summary>

```typescript
// src/products/schemas/product.schema.ts

export const ProductSchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1),
  description: z.string().optional(),
  price: z.number().nonnegative(),
  stock: z.number().int().nonnegative(),
  unit: z.string(),
  categoryId: z.string(),
  imageUrl: z.string().optional(),
  isFeatured: z.boolean().optional(),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
});
```
</details>

<details>
<summary>Order Schema</summary>

```typescript
// src/orders/schemas/order.schema.ts

export const OrderItemSchema = z.object({
  productId: z.string(),
  name: z.string(),
  price: z.number().nonnegative(),
  quantity: z.number().int().positive(),
});

export const OrderSchema = z.object({
  id: z.string().optional(),
  userId: z.string(),
  items: z.array(OrderItemSchema),
  totalAmount: z.number().nonnegative(),
  discountApplied: z.string().nullable(),
  promotionApplied: z.string().nullable(),
  status: z.enum(['pending', 'processing', 'shipped', 'delivered', 'cancelled']),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
});
```
</details>

*Other schemas for Discounts, Promotions, Inventory, and Stores follow a similar structure.*

## Error Handling

The API uses a global `HttpExceptionFilter` to catch all errors and format them into a standardized JSON response.

### Error Response Format
```json
{
  "statusCode": 404,
  "timestamp": "2023-01-01T00:00:00.000Z",
  "path": "/users/123",
  "method": "GET",
  "message": "User with ID 123 not found"
}
```

### Custom Exceptions

The API uses custom exception classes to handle common error scenarios:

- `ResourceNotFoundException`: Thrown when a requested resource is not found.
- `ValidationException`: Thrown by the `ZodValidationPipe` when request data fails validation.
- `UnauthorizedException`: Thrown when authentication fails.
- `ForbiddenException`: Thrown when access is denied due to insufficient permissions.

## Response Format

All successful API responses are formatted by a global `ResponseInterceptor`.

### Success Response Format
```json
{
  "statusCode": 200,
  "message": "Success",
  "data": {
    "id": "123",
    "name": "Example Product"
  },
  "timestamp": "2023-01-01T00:00:00.000Z",
  "path": "/products/123"
}
```

## Logging

The API implements comprehensive logging using a custom `AppLoggerService` and `LoggingMiddleware`. All incoming requests and outgoing responses are logged with essential information, including method, URL, status code, and processing time.
