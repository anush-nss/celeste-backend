# Celeste E-Commerce API Documentation

## Table of Contents
1. [Overview](#overview)
2. [Technologies](#technologies)
3. [Setup & Configuration](#setup--configuration)
    - [Environment Variables](#environment-variables)
    - [Firebase Service Account](#firebase-service-account)
4. [Database Structure](#database-structure)
5. [Authentication](#authentication)
6. [API Endpoints](#api-endpoints)
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
7. [Query Parameters](#query-parameters)
8. [Data Models (Zod Schemas)](#data-models-zod-schemas)
9. [Error Handling](#error-handling)
10. [Response Format](#response-format)
11. [Logging](#logging)

## Overview

This document provides a comprehensive guide to the Celeste E-Commerce API, built with NestJS and Firebase. The API follows a modular architecture and implements all the necessary endpoints for a complete e-commerce platform.

## Technologies

- **Framework**: NestJS (TypeScript)
- **Authentication**: Firebase Authentication
- **Database**: Firestore (Firebase)
- **Validation**: Zod & class-validator
- **API Documentation**: Swagger (OpenAPI) at `/docs`
- **Testing**: Jest
- **Code Quality**: ESLint, Prettier

## Setup & Configuration

### Environment Variables

Create a `.env` file in the root of the project with the following variables. You can use `.env.example` as a template.

```bash
# Firebase Configuration
# Path to your Firebase service account JSON file
GOOGLE_APPLICATION_CREDENTIALS=path/to/your/service-account-key.json

# Firebase Web API Key for your project
FIREBASE_WEB_API_KEY=your_firebase_web_api_key

# API Configuration
# Port the application will run on
PORT=3000

# Application environment
NODE_ENV=development
```

### Firebase Service Account

To connect to Firebase, you need a service account key.

1.  Go to your Firebase project settings.
2.  Navigate to the "Service accounts" tab.
3.  Click "Generate new private key" to download a JSON file.
4.  Save this file securely and point the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to its path.
5.  The `.gitignore` file is already configured to ignore `service-account.json`.

The service account JSON file has the following structure:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "your-private-key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "firebase-adminsdk-....@your-project-id.iam.gserviceaccount.com",
  "client_id": "your-client-id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-..."
}
```

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

Most API endpoints are protected and require a Firebase ID token to be passed in the `Authorization` header.

```
Authorization: Bearer <Firebase_ID_Token>
```

The backend uses an `AuthGuard` to verify the token for all incoming requests. Endpoints that are publicly accessible are decorated with `@Public()` and are explicitly marked as **(Public)** in this documentation.

Role-based access control is managed by the `RolesGuard`. Endpoints restricted to certain user roles (e.g., `admin`) are decorated with `@Roles()` and are marked accordingly.

### Public Endpoints

Endpoints for reading data (e.g., `GET /products`, `GET /categories`) are generally public. Endpoints that modify data (e.g., `POST`, `PUT`, `DELETE`) are protected, with the exception of user registration.

## API Endpoints

### Auth

Handles user authentication and registration.

#### Verify Token
- **Endpoint**: `POST /auth/verify`
- **Access**: Public
- **Description**: Verifies a Firebase ID token and returns the decoded token if valid.
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

#### Register
- **Endpoint**: `POST /auth/register`
- **Access**: Public
- **Description**: Registers a new user with a phone number and name. This creates a user in both Firebase Authentication and Firestore. The user ID in Firestore will match the Firebase Authentication UID.
- **Request Body**:
  ```json
  {
    "phoneNumber": "string",
    "name": "string"
  }
  ```
- **Success Response (201)**:
  ```json
  {
    "message": "Registration successful",
    "user": { "uid": "string", "role": "customer" }
  }
  ```
- **Error Response (401)**:
  ```json
  {
    "statusCode": 401,
    "message": "Registration failed: <error_message>"
  }
  ```

#### Get Profile
- **Endpoint**: `GET /auth/profile`
- **Access**: Authenticated Users
- **Description**: Retrieves the profile of the currently authenticated user from the JWT payload.
- **Success Response (200)**: Returns the user object from the token.

### Users

Manages user profiles, wishlists, and shopping carts. Most endpoints require the user to be authenticated.

- `GET /users/{id}`: Retrieves a user's profile.
- `POST /users`: (Public) Creates a new user directly. **Note**: Phone-based registration via `/auth/register` is the preferred method.
- `PUT /users/{id}`: Updates a user's profile. (Requires user to be self or an admin).
- `DELETE /users/{id}`: (Admin) Deletes a user.
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
    - `categoryId` (string): Filter by product category ID.
    - `minPrice` (number): Filter by minimum price.
    - `maxPrice` (number): Filter by maximum price.
    - `isFeatured` (boolean): Filter by featured products.
- `GET /products/{id}`: (Public) Retrieves a specific product.
- `POST /products`: (Admin) Creates a new product.
- `PUT /products/{id}`: (Admin) Updates a product.
- `DELETE /products/{id}`: (Admin) Deletes a product.

### Featured Products

Manages featured products. This collection is typically managed internally and is read-only via the API.

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

Manages promotions (e.g., banners, special offers). This collection is typically managed internally and is read-only via the API.

- `GET /promotions`: (Public) Retrieves all active promotions.
- `GET /promotions/{id}`: (Public) Retrieves a specific promotion.

### Orders

Manages customer orders. All endpoints require authentication.

- `GET /orders`: (Customer/Admin) Retrieves orders. Admins see all orders; customers see only their own.
- `GET /orders/{id}`: (Customer/Admin) Retrieves a specific order. (Authorization check required to ensure customers only access their own orders).
- `POST /orders`: (Customer) Creates a new order for the authenticated user.
  - **Request Body**:
    ```json
    {
      "items": [
        {
          "productId": "string",
          "name": "string",
          "price": "number",
          "quantity": "number"
        }
      ],
      "totalAmount": "number",
      "discountApplied": "string | null",
      "promotionApplied": "string | null",
      "status": "pending"
    }
    ```
- `PUT /orders/{id}`: (Admin) Updates an order status.
  - **Request Body**:
    ```json
    {
      "status": "pending" | "processing" | "shipped" | "delivered" | "cancelled"
    }
    ```
- `DELETE /orders/{id}`: (Admin) Deletes an order.

### Inventory

Manages product inventory. This is a read-only endpoint for clients.

- `GET /inventory`: (Public) Retrieves all inventory items.
- `GET /inventory/product/{productId}`: (Public) Retrieves inventory for a specific product.

### Stores

Manages physical store locations. This is a read-only endpoint for clients.

- `GET /stores`: (Public) Retrieves all stores.
- `GET /stores/{id}`: (Public) Retrieves a specific store.
- `GET /stores/nearby`: (Public) Retrieves stores near a specific location (latitude/longitude).
  - **Query Parameters**: `lat` (string), `lon` (string).

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

export const LoginSchema = z.object({
  token: z.string().min(1),
});

export const RegisterSchema = z.object({
  phoneNumber: z.string().min(1),
  name: z.string().min(1),
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
  email: z.string().email().optional(),
  phone: z.string().optional(),
  address: z.string().optional(),
  role: z.enum([USER_ROLES.CUSTOMER, USER_ROLES.ADMIN]).default(USER_ROLES.CUSTOMER),
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
  imageUrl: z.string().url().optional(),
  parentCategoryId: z.string().nullable().optional(),
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
  categoryId: z.string(),
  imageUrl: z.string().url().optional(),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
  isFeatured: z.boolean().optional(),
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
  limit: z.string().transform(Number).optional(),
  offset: z.string().transform(Number).optional(),
  includeDiscounts: z.string().transform((val) => val === 'true').optional(),
  categoryId: z.string().optional(),
  minPrice: z.string().transform(Number).optional(),
  maxPrice: z.string().transform(Number).optional(),
  isFeatured: z.string().transform((val) => val === 'true').optional(),
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
  validFrom: z.coerce.date(),
  validTo: z.coerce.date(),
  applicableProducts: z.array(z.string()).optional(),
  applicableCategories: z.array(z.string()).optional(),
});

export const CreateDiscountSchema = DiscountSchema.omit({ id: true });
export const UpdateDiscountSchema = DiscountSchema.partial().omit({ id: true });

export const DiscountQuerySchema = z.object({
  availableOnly: z.string().transform((val) => val === 'true').optional(),
  populateReferences: z.string().transform((val) => val === 'true').optional(),
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
  discountApplied: z.string().nullable().optional(),
  promotionApplied: z.string().nullable().optional(),
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
export type UpdateOrderDto = z.infer<typeof UpdateOrderDto>;
export type OrderItem = z.infer<typeof OrderItemSchema>;
```
</details>

## Error Handling

The API uses a global `HttpExceptionFilter` to catch all `HttpException` instances and format them into a standardized JSON response.

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

- `ResourceNotFoundException`: Thrown when a requested resource is not found (HTTP 404).
- `ValidationException`: Thrown by the `ZodValidationPipe` when request data fails validation (HTTP 400).
- `UnauthorizedException`: Thrown when authentication fails (HTTP 401).
- `ForbiddenException`: Thrown when access is denied due to insufficient permissions (HTTP 403).

## Response Format

All successful API responses are wrapped by a global `ResponseInterceptor` to ensure a consistent structure.

### Success Response Format
```json
{
  "statusCode": 200,
  "message": "Success",
  "data": {
    "id": "123",
    "name": "Example Product"
  },
  "timestamp": "2025-09-01T10:00:00.000Z",
  "path": "/products/123"
}
```

## Logging

The API implements comprehensive logging using a custom `AppLoggerService` (powered by Winston) and `LoggingMiddleware`. All incoming requests and outgoing responses are logged with essential information, including method, URL, status code, and processing time.
```