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

Handles user authentication and token management.

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

#### Log In
- **Endpoint**: `POST /auth/log-in`
- **Access**: Public
- **Description**: Logs in a user using a Firebase ID token obtained from client-side phone authentication.
- **Request Body**:
  ```json
  {
    "token": "string" // Firebase ID Token
  }
  ```
- **Success Response (200)**:
  ```json
  {
    "message": "Login successful",
    "user": { ...decodedToken }
  }
  ```
- **Error Response (401)**:
  ```json
  {
    "statusCode": 401,
    "message": "Invalid token or login failed"
  }
  ```

#### Register
- **Endpoint**: `POST /auth/register`
- **Access**: Public
- **Description**: Registers a new user with a phone number and name. The user ID in Firestore will match the Firebase Authentication UID.
- **Request Body**:
  ```json
  {
    "phoneNumber": "string",
    "name": "string",
    "role": "customer" | "admin" // Default is 'customer' if not specified in request
  }
  ```
- **Success Response (201)**:
  ```json
  {
    "message": "Registration successful",
    "user": { "uid": "string", "role": "string" }
  }
  ```
- **Error Response (401)**:
  ```json
  {
    "statusCode": 401,
    "message": "Registration failed: <error_message>"
  }
  ```

### Users

Manages user profiles, wishlists, and shopping carts.

- `GET /users/{id}`: Retrieves a user's profile.
- `POST /users`: (Public) Creates a new user. (See `/auth/register` for phone-based registration).
- `PUT /users/{id}`: Updates a user's profile.
- `DELETE /users/{id}`: Deletes a user.
- `POST /users/{id}/wishlist`: Adds a product to the user's wishlist.
  - **Request Body**: `{ "productId": "string" }`
- `DELETE /users/{id}/wishlist/{productId}`: Removes a product from the user's wishlist.
- `POST /users/{id}/cart`: Adds a product to the user's cart.
  - **Request Body**: `{ "productId": "string", "quantity": number }`
- `PUT /users/{id}/cart/{productId}`: Updates the quantity of a product in the cart.
  - **Request Body**: `{ "quantity": number }`
- `DELETE /users/{id}/cart/{productId}`: Removes a product from the cart.

### Categories

Manages product categories.

- `GET /categories`: (Public) Retrieves all categories.
- `GET /categories/{id}`: (Public) Retrieves a specific category.
- `POST /categories`: (Admin) Creates a new category.
- `PUT /categories/{id}`: (Admin) Updates a category.
- `DELETE /categories/{id}`: (Admin) Deletes a category.

### Products

Manages products.

- `GET /products`: (Public) Retrieves all products with filtering, pagination, and optional discount details.
  - **Query Parameters**:
    - `limit` (number): Number of items to return.
    - `offset` (number): Number of items to skip.
    - `includeDiscounts` (boolean): Set to `true` to include applicable discount details.
- `GET /products/{id}`: (Public) Retrieves a specific product.
- `POST /products`: (Admin) Creates a new product.
- `PUT /products/{id}`: (Admin) Updates a product.
- `DELETE /products/{id}`: (Admin) Deletes a product.

### Featured Products

Manages featured products. Data is read-only via the API.

- `GET /featured`: (Public) Retrieves all featured products.
- `GET /featured/{id}`: (Public) Retrieves a specific featured product entry.

### Discounts

Manages discounts.

- `GET /discounts`: (Public) Retrieves all discounts with optional filtering and population.
  - **Query Parameters**:
    - `availableOnly` (boolean): Set to `true` to get only currently active discounts.
    - `populateReferences` (boolean): Set to `true` to populate `applicableProducts` and `applicableCategories` with full details.
- `GET /discounts/{id}`: (Public) Retrieves a specific discount.
- `POST /discounts`: (Admin) Creates a new discount.
- `PUT /discounts/{id}`: (Admin) Updates a discount.
- `DELETE /discounts/{id}`: (Admin) Deletes a discount.

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

| Parameter          | Type    | Description                               | Applicable Endpoints |
|--------------------|---------|-------------------------------------------|----------------------|
| `limit`            | number  | Number of items to return (default: 10)   | Products             |
| `offset`           | number  | Number of items to skip (default: 0)      | Products             |
| `includeDiscounts` | boolean | For products, set to `true` to include applicable discount details. | Products             |
| `availableOnly`    | boolean | For discounts, set to `true` to get only currently active discounts. | Discounts            |
| `populateReferences`| boolean | For discounts, set to `true` to populate `applicableProducts` and `applicableCategories` with full details. | Discounts            |
| `sortBy`           | string  | Field to sort by                          | (General)            |
| `order`            | string  | Sort order: "asc" or "desc"             | (General)            |

## Data Models (Zod Schemas)

Data validation is handled by Zod schemas, which serve as the single source of truth for the application's data structures.

<details>
<summary>Auth Schemas</summary>

```typescript
// src/auth/schemas/auth.schema.ts
import { z } from 'zod';
import { USER_ROLES } from '../../shared/constants';

export const LoginSchema = z.object({
  token: z.string().min(1),
});

export const RegisterSchema = z.object({
  phoneNumber: z.string().min(1),
  name: z.string().min(1),
  role: z.enum([USER_ROLES.CUSTOMER, USER_ROLES.ADMIN]).optional(), // Role is optional for registration, defaults to CUSTOMER
});

export type LoginDto = z.infer<typeof LoginSchema>;
export type RegisterDto = z.infer<typeof RegisterSchema>;
```
</details>

<details>
<summary>User Schemas</summary>

```typescript
// src/users/schemas/user.schema.ts
import { z } from 'zod';
import { USER_ROLES } from '../../shared/constants';

export const CartItemSchema = z.object({
  productId: z.string(),
  quantity: z.number().int().positive(),
  addedAt: z.date(),
});

export const UserSchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1),
  email: z.string().email().optional(), // Email is optional for phone-based login
  phone: z.string().optional(),
  address: z.string().optional(),
  role: z.enum([USER_ROLES.CUSTOMER, USER_ROLES.ADMIN]),
  createdAt: z.date().optional(),
  wishlist: z.array(z.string()).optional(),
  cart: z.array(CartItemSchema).optional(),
});

export const CreateUserSchema = UserSchema.omit({
  id: true,
  createdAt: true,
  wishlist: true,
  cart: true
});

export const UpdateUserSchema = UserSchema.partial().omit({
  id: true,
  createdAt: true
});

export const AddToWishlistSchema = z.object({
  productId: z.string().min(1),
});

export const AddToCartSchema = z.object({
  productId: z.string().min(1),
  quantity: z.number().int().positive(),
});

export const UpdateCartItemSchema = z.object({
  quantity: z.number().int().positive(),
});

export type User = z.infer<typeof UserSchema>;
export type CreateUserDto = z.infer<typeof CreateUserSchema>;
export type UpdateUserDto = z.infer<typeof UpdateUserSchema>;
export type CartItem = z.infer<typeof CartItemSchema>;
export type AddToWishlistDto = z.infer<typeof AddToWishlistSchema>;
export type AddToCartDto = z.infer<typeof AddToCartSchema>;
export type UpdateCartItemDto = z.infer<typeof UpdateCartItemSchema>;
```
</details>

<details>
<summary>Category Schema</summary>

```typescript
// src/categories/schemas/category.schema.ts
import { z } from 'zod';

export const CategorySchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1),
  description: z.string().optional(),
  imageUrl: z.string().optional(),
  parentCategoryId: z.string().nullable(),
});

export const CreateCategorySchema = CategorySchema.omit({ id: true });
export const UpdateCategorySchema = CategorySchema.partial().omit({ id: true });

export type Category = z.infer<typeof CategorySchema>;
export type CreateCategoryDto = z.infer<typeof CreateCategorySchema>;
export type UpdateCategoryDto = z.infer<typeof UpdateCategorySchema>;
```
</details>

<details>
<summary>Product Schema</summary>

```typescript
// src/products/schemas/product.schema.ts
import { z } from 'zod';

export const ProductSchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1),
  description: z.string().optional(),
  price: z.number().nonnegative(),
  unit: z.string(),
  categoryId: z.string(), // Represents Firestore DocumentReference ID
  imageUrl: z.string().optional(),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
});

export const CreateProductSchema = ProductSchema.omit({
  id: true,
  createdAt: true,
  updatedAt: true,
});
export const UpdateProductSchema = ProductSchema.partial().omit({
  id: true,
  createdAt: true,
});

export const ProductQuerySchema = z.object({
  limit: z.preprocess(
    (a) => parseInt(z.string().parse(a), 10),
    z.number().int().positive().optional(),
  ),
  offset: z.preprocess(
    (a) => parseInt(z.string().parse(a), 10),
    z.number().int().nonnegative().optional(),
  ),
  includeDiscounts: z.preprocess(
    (a) => z.string().parse(a).toLowerCase() === 'true',
    z.boolean().optional(),
  ),
}).partial();

export type Product = z.infer<typeof ProductSchema>;
export type CreateProductDto = z.infer<typeof CreateProductSchema>;
export type UpdateProductDto = z.infer<typeof UpdateProductSchema>;
export type ProductQueryDto = z.infer<typeof ProductQuerySchema>;
```
</details>

<details>
<summary>Discount Schema</summary>

```typescript
// src/discounts/schemas/discount.schema.ts
import { z } from 'zod';
import { DISCOUNT_TYPES } from '../../shared/constants';

export const DiscountSchema = z.object({
  id: z.string().optional(),
  name: z.string().min(1),
  description: z.string().optional(),
  type: z.enum([DISCOUNT_TYPES.PERCENTAGE, DISCOUNT_TYPES.FLAT]),
  value: z.number().nonnegative(),
  validFrom: z.date(),
  validTo: z.date(),
  applicableProducts: z.array(z.string()).optional(), // Represents array of Firestore DocumentReference IDs
  applicableCategories: z.array(z.string()).optional(), // Represents array of Firestore DocumentReference IDs
});

export const CreateDiscountSchema = DiscountSchema.omit({ id: true });
export const UpdateDiscountSchema = DiscountSchema.partial().omit({ id: true });

export const DiscountQuerySchema = z.object({
  availableOnly: z.preprocess(
    (a) => z.string().parse(a).toLowerCase() === 'true',
    z.boolean().optional(),
  ),
  populateReferences: z.preprocess(
    (a) => z.string().parse(a).toLowerCase() === 'true',
    z.boolean().optional(),
  ),
}).partial();

export type Discount = z.infer<typeof DiscountSchema>;
export type CreateDiscountDto = z.infer<typeof CreateDiscountSchema>;
export type UpdateDiscountDto = z.infer<typeof UpdateDiscountSchema>;
export type DiscountQueryDto = z.infer<typeof DiscountQuerySchema>;
```
</details>

<details>
<summary>Order Schema</summary>

```typescript
// src/orders/schemas/order.schema.ts
import { z } from 'zod';

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

export const CreateOrderSchema = OrderSchema.omit({
  id: true,
  createdAt: true,
  updatedAt: true,
});
export const UpdateOrderSchema = OrderSchema.partial().omit({
  id: true,
  createdAt: true,
  userId: true,
  items: true,
  totalAmount: true,
});

export type Order = z.infer<typeof OrderSchema>;
export type CreateOrderDto = z.infer<typeof CreateOrderSchema>;
export type UpdateOrderDto = z.infer<typeof UpdateOrderSchema>;
export type OrderItem = z.infer<typeof OrderItemSchema>;
```
</details>

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