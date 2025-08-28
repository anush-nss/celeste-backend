# Celeste E-Commerce API Documentation

## Table of Contents
1. [Overview](#overview)
2. [Technologies](#technologies)
3. [Database Structure](#database-structure)
4. [Authentication](#authentication)
5. [API Endpoints](#api-endpoints)
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
7. [Extensibility and Modularity](#extensibility-and-modularity)
8. [Data Models](#data-models)
9. [Error Handling](#error-handling)
10. [Response Format](#response-format)
11. [Logging](#logging)
12. [Implementation Notes](#implementation-notes)

## Overview

This document provides a comprehensive guide to the Celeste E-Commerce API, built with NestJS and Firebase. The API follows a modular architecture and implements all the necessary endpoints for a complete e-commerce platform.

## Technologies

- **Framework**: NestJS (TypeScript)
- **Authentication**: Firebase Authentication
- **Database**: Firestore (Firebase)
- **API Documentation**: Swagger/OpenAPI
- **Testing**: Jest
- **Code Quality**: ESLint, Prettier
- **Deployment**: Docker-ready, CI/CD ready

## Database Structure

The database follows a NoSQL structure with the following collections:

### Users
```
/users/{userId}
- name: string
- email: string
- phone: string
- address: string
- role: string ("customer" | "admin")
- createdAt: timestamp
- wishlist: [productId]  // array of favorite products
- cart: [
    {
      productId: string,
      quantity: number,
      addedAt: timestamp
    }
  ]
```

### Categories
```
/categories/{categoryId}
- name: string
- description: string
- imageUrl: string
- parentCategoryId: string | null  // for nested categories
```

### Products
```
/products/{productId}
- name: string
- description: string
- price: number
- stock: number
- unit: string ("kg" | "pcs" | "L" etc.)
- categoryId: string
- imageUrl: string
- createdAt: timestamp
- updatedAt: timestamp
```

### Featured Products
```
/featured/{featuredId}
- productId: string
- featuredFrom: timestamp
- featuredTo: timestamp
```

### Discounts
```
/discounts/{discountId}
- name: string
- type: string ("percentage" | "flat")
- value: number
- validFrom: timestamp
- validTo: timestamp
- applicableProducts: [productId]       // optional, array of product IDs
- applicableCategories: [categoryId]    // optional, array of category IDs
```

### Promotions
```
/promotions/{promotionId}
- title: string
- description: string
- bannerUrl: string
- validFrom: timestamp
- validTo: timestamp
- promotionType: string ("BOGO" | "FlashSale" | "Seasonal")
- applicableProducts: [productId]       // optional
- applicableCategories: [categoryId]    // optional
```

### Orders
```
/orders/{orderId}   // Top-level collection
- userId: string
- items: [
    {
      productId: string,
      name: string,
      price: number,
      quantity: number
    }
  ]
- totalAmount: number
- discountApplied: string | null
- promotionApplied: string | null
- status: string ("pending" | "processing" | "shipped" | "delivered" | "cancelled")
- createdAt: timestamp
- updatedAt: timestamp
```

### Inventory
```
/inventory/{inventoryId}
- productId: string
- stock: number
- lastUpdated: timestamp
```

### Stores
```
/stores/{storeId}
- name: string
- description: string
- address: string
- phone: string
- email: string
- location: {
    latitude: number
    longitude: number
  }
- isActive: boolean
- createdAt: timestamp
- updatedAt: timestamp
```

## Authentication

All API endpoints (except for public endpoints like product/category listings) require authentication using Firebase Authentication. The API expects a valid Firebase ID token in the `Authorization` header:

```
Authorization: Bearer <Firebase_ID_Token>
```

The backend will verify the token and extract user information for authorization checks.

### Public Endpoints

The following endpoints are publicly accessible without authentication:
- `GET /products`
- `GET /products/{productId}`
- `GET /categories`
- `GET /categories/{categoryId}`
- `GET /discounts`
- `GET /discounts/{discountId}`
- `GET /promotions`
- `GET /promotions/{promotionId}`
- `GET /inventory`
- `GET /inventory/{inventoryId}`
- `GET /inventory/product/{productId}`
- `GET /stores`
- `GET /stores/{storeId}`
- `GET /stores/nearby`
- `POST /auth/verify` (for token verification)

All other endpoints require authentication.

## API Endpoints

### Users

#### Get User Profile
```
GET /users/{userId}
```
Retrieves a user's profile information.

#### Create User
```
POST /users
```
Creates a new user profile.

#### Update User Profile
```
PUT /users/{userId}
```
Updates a user's profile information.

#### Delete User
```
DELETE /users/{userId}
```
Deletes a user's profile.

#### Add to Wishlist
```
POST /users/{userId}/wishlist
```
Adds a product to the user's wishlist.

#### Remove from Wishlist
```
DELETE /users/{userId}/wishlist/{productId}
```
Removes a product from the user's wishlist.

#### Add to Cart
```
POST /users/{userId}/cart
```
Adds a product to the user's cart.

#### Update Cart Item
```
PUT /users/{userId}/cart/{productId}
```
Updates the quantity of a product in the user's cart.

#### Remove from Cart
```
DELETE /users/{userId}/cart/{productId}
```
Removes a product from the user's cart.

### Categories

#### Get All Categories
```
GET /categories
```
Retrieves all categories with optional filtering.

#### Get Category by ID
```
GET /categories/{categoryId}
```
Retrieves a specific category by ID.

Note: Categories are managed through a separate administrative system.

### Products

#### Get All Products
```
GET /products
```
Retrieves all products with optional filtering and pagination.

#### Get Product by ID
```
GET /products/{productId}
```
Retrieves a specific product by ID.

Note: Products are managed through a separate administrative system.

### Featured Products

#### Get All Featured Products
```
GET /featured
```
Retrieves all currently featured products.

#### Get Featured Product by ID
```
GET /featured/{featuredId}
```
Retrieves a specific featured product entry.

Note: Featured products are managed through a separate administrative system.

### Discounts

#### Get All Discounts
```
GET /discounts
```
Retrieves all active discounts.

#### Get Discount by ID
```
GET /discounts/{discountId}
```
Retrieves a specific discount by ID.

Note: Discounts are managed through a separate administrative system.

### Promotions

#### Get All Promotions
```
GET /promotions
```
Retrieves all active promotions.

#### Get Promotion by ID
```
GET /promotions/{promotionId}
```
Retrieves a specific promotion by ID.

Note: Promotions are managed through a separate administrative system.

### Orders

#### Get User Orders
```
GET /orders
```
Retrieves all orders for the authenticated user.

#### Get Order by ID
```
GET /orders/{orderId}
```
Retrieves a specific order by ID.

#### Create Order
```
POST /orders
```
Creates a new order from the user's cart.

#### Update Order Status
```
PUT /orders/{orderId}
```
Updates an order status (admin only).

#### Delete Order
```
DELETE /orders/{orderId}
```
Deletes an order (admin only).

### Inventory

#### Get Inventory Items
```
GET /inventory
```
Retrieves all inventory items.

#### Get Inventory by Product ID
```
GET /inventory/product/{productId}
```
Retrieves inventory information for a specific product.

Note: Inventory is managed through a separate administrative system.

### Stores

#### Get All Stores
```
GET /stores
```
Retrieves all stores with optional filtering.

#### Get Store by ID
```
GET /stores/{storeId}
```
Retrieves a specific store by ID.

#### Get Nearby Stores
```
GET /stores/nearby
```
Retrieves stores near a specific location.

Query Parameters:
- `latitude` (required): Latitude of the location
- `longitude` (required): Longitude of the location
- `radius` (optional): Search radius in kilometers (default: 10km)
- `limit` (optional): Maximum number of results (default: 10)

Example:
```
GET /stores/nearby?latitude=6.9271&longitude=79.8612&radius=5&limit=20
```

Note: Stores are managed through a separate administrative system.

## Query Parameters

The API supports various query parameters for filtering, sorting, and pagination:

### Common Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | number | Number of items to return (default: 10) |
| `offset` | number | Number of items to skip (default: 0) |
| `sortBy` | string | Field to sort by |
| `order` | string | Sort order: "asc" or "desc" |

### Product-Specific Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `category` | string | Filter by category ID |
| `minPrice` | number | Minimum price filter |
| `maxPrice` | number | Maximum price filter |
| `featured` | boolean | Filter featured products only |
| `search` | string | Search term for product name/description |

### Order-Specific Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by order status |
| `startDate` | timestamp | Filter orders after this date |
| `endDate` | timestamp | Filter orders before this date |

Example request with query parameters:
```
GET /products?category=electronics&minPrice=100&maxPrice=500&featured=true&limit=20&offset=0&sortBy=price&order=asc
```

## Extensibility and Modularity

The API is designed with modularity and extensibility in mind:

### Module Structure
```
src/
├── auth/
├── users/
├── categories/
├── products/
├── discounts/
├── promotions/
├── orders/
├── inventory/
├── stores/
├── shared/
│   ├── exceptions/
│   ├── interceptors/
│   ├── logger/
│   └── middleware/
└── app.module.ts
```

### Key Design Principles

1. **Separation of Concerns**: Each module handles a specific domain of the application
2. **Reusability**: Shared utilities and services can be used across modules
3. **Scalability**: Modules can be developed and deployed independently
4. **Maintainability**: Clear structure makes it easy to locate and modify code
5. **Testability**: Each module can be unit tested independently

### Extensibility Features

1. **Plugin Architecture**: New modules can be added without affecting existing code
2. **Service Abstraction**: Database services are abstracted for easy replacement
3. **Middleware Support**: Custom middleware can be added for additional functionality
4. **Event System**: Event-based communication between modules for loose coupling
5. **Configuration Management**: Environment-based configuration for different deployments

## Data Models

### User Model
```typescript
interface User {
  id: string;
  name: string;
  email: string;
  phone: string;
  address: string;
  role: 'customer' | 'admin';
  createdAt: Date;
  wishlist: string[];
  cart: CartItem[];
}

interface CartItem {
  productId: string;
  quantity: number;
  addedAt: Date;
}
```

### Category Model
```typescript
interface Category {
  id: string;
  name: string;
  description: string;
  imageUrl: string;
  parentCategoryId: string | null;
}
```

### Product Model
```typescript
interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  stock: number;
  unit: 'kg' | 'pcs' | 'L' | string;
  categoryId: string;
  imageUrl: string;
  createdAt: Date;
  updatedAt: Date;
}

interface FeaturedProduct {
  id: string;
  productId: string;
  featuredFrom: Date;
  featuredTo: Date;
}
```

### Discount Model
```typescript
interface Discount {
  id: string;
  name: string;
  type: 'percentage' | 'flat';
  value: number;
  validFrom: Date;
  validTo: Date;
  applicableProducts?: string[];
  applicableCategories?: string[];
}
```

### Promotion Model
```typescript
interface Promotion {
  id: string;
  title: string;
  description: string;
  bannerUrl: string;
  validFrom: Date;
  validTo: Date;
  promotionType: 'BOGO' | 'FlashSale' | 'Seasonal';
  applicableProducts?: string[];
  applicableCategories?: string[];
}
```

### Order Model
```typescript
interface Order {
  id: string;
  userId: string;
  items: OrderItem[];
  totalAmount: number;
  discountApplied: string | null;
  promotionApplied: string | null;
  status: 'pending' | 'processing' | 'shipped' | 'delivered' | 'cancelled';
  createdAt: Date;
  updatedAt: Date;
}

interface OrderItem {
  productId: string;
  name: string;
  price: number;
  quantity: number;
}
```

### Inventory Model
```typescript
interface Inventory {
  id: string;
  productId: string;
  stock: number;
  lastUpdated: Date;
}
```

### Store Model
```typescript
interface Store {
  id: string;
  name: string;
  description: string;
  address: string;
  phone: string;
  email: string;
  location: {
    latitude: number;
    longitude: number;
  };
  isActive: boolean;
  createdAt: Date;
  updatedAt: Date;
}
```

## Error Handling

The API implements centralized error handling through a global exception filter. All errors are caught and formatted consistently before being sent to the client.

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

### Common Error Types
- **400 Bad Request**: Validation errors or malformed requests
- **401 Unauthorized**: Missing or invalid authentication token
- **403 Forbidden**: Insufficient permissions to access a resource
- **404 Not Found**: Requested resource does not exist
- **500 Internal Server Error**: Unexpected server errors

### Custom Exceptions
The API provides custom exception classes for common error scenarios:
- `ResourceNotFoundException`: When a requested resource is not found
- `ValidationException`: When request data fails validation
- `UnauthorizedException`: When authentication fails
- `ForbiddenException`: When access is denied due to insufficient permissions

## Response Format

All successful API responses follow a standardized format through a global response interceptor.

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

### Response Fields
- **statusCode**: HTTP status code of the response
- **message**: Human-readable message describing the response
- **data**: Actual response data (may be null for DELETE operations)
- **timestamp**: ISO 8601 timestamp of when the response was generated
- **path**: The requested API endpoint

## Logging

The API implements comprehensive logging for monitoring and debugging purposes.

### Log Levels
- **Error**: Critical errors that require immediate attention
- **Warn**: Potentially harmful situations
- **Log**: General informational messages
- **Debug**: Detailed debugging information (only in development)
- **Verbose**: Highly detailed diagnostic information

### Log Information
All logs include:
- Timestamp
- Log level
- Message
- Context (class/method where the log originated)
- Request information (method, URL, IP address)
- Response information (status code, duration)

### Request/Response Logging
Every incoming request and outgoing response is logged with:
- HTTP method
- URL
- IP address
- Response status code
- Request processing time

## Implementation Notes

### Firebase Integration
- Firebase Admin SDK is used for server-side operations
- Firebase Authentication is used for user authentication
- Firestore is used as the primary database
- Environment variables are used for Firebase configuration:
  - `GOOGLE_APPLICATION_CREDENTIALS` - Path to service account key file
  - `FIREBASE_PROJECT_ID` - Firebase project ID
  - `FIREBASE_PRIVATE_KEY` - Private key for service account
  - `FIREBASE_CLIENT_EMAIL` - Client email for service account

### Read-Only Data
- Products, Categories, Discounts, Promotions, Inventory, and Stores can only be read through the API
- These entities are managed through a separate administrative system
- This ensures data integrity and prevents unauthorized modifications

### Featured Products Management
- Featured products are managed separately from the main product data
- This allows for time-based featuring without modifying core product data
- Featured status can be scheduled and managed independently

### User and Order Management
- Users can be created, updated, and deleted through the API
- Orders can be created and their status updated through the API
- All other operations are read-only to maintain data consistency

### Validation
- Zod schemas are used for request validation instead of class-validator
- All incoming requests are validated against Zod schemas
- Validation errors are formatted consistently in the response
- Zod provides both runtime validation and compile-time type safety

### Error Handling
- Standardized error responses with appropriate HTTP status codes
- Detailed error messages for debugging
- Proper logging for monitoring and debugging

### Security
- Role-based access control (RBAC) using Firebase custom claims
- Input validation and sanitization
- Protection against common web vulnerabilities

### Performance
- Pagination for large datasets
- Efficient database queries
- Caching strategies where appropriate

This documentation provides a comprehensive overview of the Celeste E-Commerce API. As the project develops, this document will be updated to reflect any changes or additions to the API.