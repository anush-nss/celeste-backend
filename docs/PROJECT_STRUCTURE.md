# Celeste E-Commerce API - Project Structure & Architecture

## Project Overview

Celeste is a FastAPI-based e-commerce backend API that provides comprehensive functionality for managing users, products, orders, inventory, and more. The application uses Firebase for authentication and Firestore as the primary database.

## Technology Stack

### Core Technologies
- **FastAPI**: Modern Python web framework for building APIs
- **Python**: Primary programming language
- **Firebase Admin SDK**: For Firebase integration
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server for running the application

### Database & Authentication
- **Firebase Firestore**: NoSQL document database
- **Firebase Auth**: Authentication and user management
- **JWT**: JSON Web Tokens for secure API access

### Development Tools
- **Python-dotenv**: Environment variable management
- **Email-validator**: Email validation utilities
- **Requests**: HTTP library for external API calls

## Project Structure

```
celeste/
├── docs/                           # Documentation
│   ├── API_DOCUMENTATION.md        # API endpoints documentation
│   └── PROJECT_STRUCTURE.md        # This file
├── src/                            # Source code
│   ├── __init__.py
│   ├── auth/                       # Authentication module
│   │   └── dependencies.py         # Auth dependencies, role checking, tier detection
│   ├── core/                       # Core functionality
│   │   ├── exceptions.py           # Custom exceptions
│   │   ├── firebase.py             # Firebase configuration
│   │   ├── logger.py               # Logging configuration
│   │   └── responses.py            # Response formatting
│   ├── models/                     # Pydantic data models
│   │   ├── __init__.py
│   │   ├── auth_models.py          # Authentication models
│   │   ├── category_models.py      # Category models
│   │   ├── discount_models.py      # Discount models
│   │   ├── inventory_models.py     # Inventory models
│   │   ├── order_models.py         # Order models
│   │   ├── pricing_models.py       # ⭐ NEW: Pricing and tier models
│   │   ├── product_models.py       # Enhanced product models with pricing
│   │   ├── store_models.py         # Store models
│   │   ├── token_models.py         # Token models
│   │   └── user_models.py          # Enhanced user models with tiers
│   ├── routers/                    # API route handlers
│   │   ├── auth_router.py          # Authentication routes with tier defaults
│   │   ├── categories_router.py    # Category routes
│   │   ├── dev_router.py           # ⭐ NEW: Development tools
│   │   ├── discounts_router.py     # Discount routes
│   │   ├── inventory_router.py     # Inventory routes
│   │   ├── orders_router.py        # Order routes
│   │   ├── pricing_router.py       # ⭐ NEW: Pricing management routes
│   │   ├── products_router.py      # Enhanced products with smart pricing
│   │   ├── promotions_router.py    # Promotion routes
│   │   ├── stores_router.py        # Store routes
│   │   └── users_router.py         # User routes with tier support
│   ├── services/                   # Business logic services
│   │   ├── pricing_service.py      # ⭐ NEW: Pricing calculations service
│   │   ├── product_service.py      # Enhanced product service with pagination
│   │   └── user_service.py         # Enhanced user service with tiers
│   └── shared/                     # Shared utilities
│       └── constants.py            # Enhanced constants with tiers and pricing
├── main.py                         # Application entry point
├── requirements.txt                # Python dependencies
├── service-account.json            # Firebase service account (gitignored)
└── README.md                       # Project readme
```

## Architecture Components

### 1. Application Entry Point (`main.py`)

The main application file that:
- Initializes the FastAPI application
- Configures middleware for request logging and timing
- Includes all routers
- Sets up global exception handling
- Configures custom OpenAPI schema with JWT authentication

Key features:
- Request timing middleware
- Custom OpenAPI documentation
- Global exception handler
- Bearer token authentication setup

### 2. Authentication & Authorization (`src/auth/`)

#### `dependencies.py`
Contains authentication, authorization, and tier detection logic:
- `get_current_user()`: Validates JWT tokens and returns user information
- `get_optional_user()`: Silent Bearer token extraction (no auth errors)
- `get_user_tier()`: Database-backed customer tier detection
- `RoleChecker`: Dependency class for role-based access control
- Firebase token verification

### 3. Core Components (`src/core/`)

#### `firebase.py`
Firebase configuration and initialization:
- Firebase Admin SDK setup
- Firestore client initialization
- Authentication service setup

#### `exceptions.py`
Custom exception classes:
- `ResourceNotFoundException`: For 404 errors
- `ForbiddenException`: For 403 errors
- Other domain-specific exceptions

#### `responses.py`
Response formatting utilities:
- `success_response()`: Standardizes successful API responses
- `http_exception_handler()`: Global exception handler

#### `logger.py`
Logging configuration:
- Structured logging setup
- Request/response logging
- Error tracking

### 4. Data Models (`src/models/`)

Pydantic models for data validation and serialization:

#### `user_models.py` ⭐ **Enhanced**
- `UserSchema`: Complete user data model with customer tiers
- `CreateUserSchema`: User creation payload with explicit defaults
- `UpdateUserSchema`: User update payload with tier support
- `CartItemSchema`: Cart item structure
- `AddToWishlistSchema`, `AddToCartSchema`: Action schemas

#### `product_models.py` ⭐ **Enhanced**
- `ProductSchema`: Complete product data model
- `EnhancedProductSchema`: Product model with pricing and inventory info
- `PricingInfoSchema`: Detailed pricing breakdown structure
- `PaginatedProductsResponse`: Cursor-based pagination response
- `CreateProductSchema`: Product creation payload
- `UpdateProductSchema`: Product update payload
- `ProductQuerySchema`: Enhanced query parameters with pricing options

#### `pricing_models.py` ⭐ **New**
- `PriceListSchema`: Price list management model
- `PriceListLineSchema`: Individual pricing rule model
- `PriceCalculationRequest/Response`: Price calculation models
- `BulkPriceCalculationRequest/Response`: Bulk pricing models
- Complete CRUD models for price management

#### Other Model Files
- `auth_models.py`: Authentication-related models
- `category_models.py`: Product category models
- `discount_models.py`: Discount and pricing models
- `order_models.py`: Order management models
- `inventory_models.py`: Inventory tracking models
- `store_models.py`: Physical store models
- `token_models.py`: JWT token models

### 5. API Routes (`src/routers/`)

Each router handles a specific domain of functionality:

#### `auth_router.py`
- User registration with Firebase
- Profile management
- Development token generation

#### `users_router.py`
- User profile CRUD operations
- Cart management (add, update, remove, get)
- Wishlist management (add, remove, get)
- Role-based access control

#### `products_router.py` ⭐ **Enhanced**
- Enhanced product CRUD operations
- Smart pricing with automatic tier detection
- Cursor-based pagination (default: 20, max: 100)
- Legacy endpoints for backward compatibility
- Advanced filtering and querying
- Admin-only creation/modification

#### `pricing_router.py` ⭐ **New**
- Complete price list management (Admin only)
- Price list line CRUD operations
- Price calculation endpoints (single and bulk)
- User-specific pricing endpoints
- Comprehensive OpenAPI documentation

#### `auth_router.py` ⭐ **Enhanced**
- User registration with explicit tier defaults
- Firebase Auth integration
- Automatic role and tier assignment
- Profile management

#### `dev_router.py` ⭐ **New** (Development Only)
- Development token generation
- Database management tools
- Collection browsing and data insertion
- Test data creation utilities

#### `orders_router.py`
- Order creation and management
- Status updates
- User-specific order retrieval

#### Other Routers
- `categories_router.py`: Product categorization
- `discounts_router.py`: Discount management
- `inventory_router.py`: Stock tracking
- `stores_router.py`: Physical store management
- `promotions_router.py`: Marketing campaigns
- `users_router.py`: Enhanced user management with tier support

### 6. Business Logic (`src/services/`)

Service classes containing business logic:

#### `pricing_service.py` ⭐ **New**
- Advanced pricing calculation engine
- Tier-based price list discovery and application
- Global price list management with `is_global` field
- Bulk pricing optimization for product listings
- UTC timezone handling for price list validity
- Composite discount application logic

#### `product_service.py` ⭐ **Enhanced**
- Enhanced product service with cursor-based pagination
- Integration with pricing service for bulk calculations
- `get_products_with_pagination()` for efficient listings
- Legacy compatibility with existing methods

#### `user_service.py` ⭐ **Enhanced**
- Database-backed tier storage and retrieval
- Explicit role and tier defaults during user creation
- Enhanced cart and wishlist functionality
- User tier management integration

#### General Service Patterns
- Separation of concerns between routes and business logic
- Database operations and data transformation
- Cross-domain operations and validation
- Error handling with graceful fallbacks

### 7. Shared Components (`src/shared/`)

#### `constants.py` ⭐ **Enhanced**
Application-wide constants with pricing and tier enums:
```python
class UserRole(str, Enum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"

class CustomerTier(str, Enum):  # ⭐ NEW
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"

class PriceListType(str, Enum):  # ⭐ NEW
    PRODUCT = "product"
    CATEGORY = "category"
    ALL = "all"

class DiscountType(str, Enum):  # ⭐ ENHANCED
    percentage = "percentage"
    flat = "flat"

class OrderStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
```

## Design Patterns & Principles

### 1. Separation of Concerns
- **Routers**: Handle HTTP requests and responses
- **Services**: Implement business logic
- **Models**: Define data structures and validation
- **Core**: Provide shared utilities and configuration

### 2. Dependency Injection
- FastAPI's dependency injection system for:
  - Authentication
  - Authorization
  - Service instances
  - Database connections

### 3. Role-Based Access Control (RBAC)
- `UserRole` enum defines available roles
- `RoleChecker` dependency enforces permissions
- Firebase custom claims for role persistence

### 4. Standardized Response Format
All API responses follow consistent structure:
```json
{
  "success": true,
  "data": <response_data>
}
```

### 5. Exception Handling
- Custom exceptions for different error types
- Global exception handler for consistent error responses
- HTTP status code standardization

## Security Features

### 1. Authentication
- Firebase JWT token validation
- Bearer token authentication scheme
- Secure token verification

### 2. Authorization
- Role-based access control
- Resource-level permissions
- User ownership validation

### 3. Data Validation
- Pydantic models for input validation
- Type safety and data integrity
- Automatic request/response serialization

### 4. Environment Security
- Environment variable configuration
- Service account key management
- Development vs production configurations

## Database Schema (Firestore)

### Collections Structure
- `users/`: User profiles and data with customer tiers
- `products/`: Product catalog with base pricing
- `categories/`: Product categories
- `orders/`: Order records
- `inventory/`: Stock levels
- `discounts/`: Discount rules
- `stores/`: Physical store locations
- `promotions/`: Marketing campaigns
- `price_lists/`: ⭐ **NEW** Price list definitions
- `price_list_lines/`: ⭐ **NEW** Individual pricing rules

### Data Relationships
- Users have carts, wishlists, and customer tiers (embedded/fields)
- Products belong to categories (reference)
- Orders contain product references
- Inventory tracks product stock levels
- Price lists contain multiple price list lines (reference)
- Price list lines target products, categories, or all products
- Customer tiers determine applicable price lists

## Development Workflow

### 1. Adding New Features
1. Define data models in `src/models/`
2. Create service layer in `src/services/`
3. Implement router in `src/routers/`
4. Add router to `main.py`
5. Update documentation

### 2. Authentication Flow
1. User registers/logs in through Firebase Auth
2. Client receives ID token
3. Client sends token in Authorization header
4. `get_current_user` dependency validates token
5. Role-based access control applied

### 3. Request Lifecycle
1. Request received by FastAPI
2. Middleware adds timing headers
3. Authentication/authorization checks
4. Router handler processes request
5. Service layer executes business logic
6. Firestore operations performed
7. Response formatted and returned
8. Request logged for monitoring

## Configuration

### Environment Variables
- `GOOGLE_APPLICATION_CREDENTIALS`: Firebase service account path
- `FIREBASE_WEB_API_KEY`: Firebase web API key (dev only)
- `ENVIRONMENT`: Application environment (development/production)

### Firebase Setup Required
1. Firebase project creation
2. Firestore database setup
3. Authentication configuration
4. Service account key generation

## Monitoring & Observability

### Logging
- Structured request/response logging
- Performance timing headers
- Error tracking and context

### Request Monitoring
- Processing time headers
- Request method and URL logging
- Status code tracking

## ⭐ Recently Implemented Features

### Smart Pricing System
- **Automatic Tier Detection**: Bearer tokens automatically detect user tiers for personalized pricing
- **Bulk Price Calculations**: Efficient pricing for multiple products in single requests
- **Global Price Lists**: Enhanced control with `is_global` field support and fallback logic
- **Database-Backed Tiers**: User tiers stored in Firestore with automatic BRONZE defaults
- **UTC Timezone Handling**: Proper datetime handling for price list validity periods

### Enhanced Product Management
- **Smart Product Listings**: Automatic tier-based pricing integration
- **Cursor-Based Pagination**: High-performance pagination using Firebase `startAt`
- **Performance Optimization**: Default limit 20, maximum 100 for optimal performance
- **Legacy Compatibility**: Backward-compatible endpoints for existing integrations
- **Future-Ready Structure**: Inventory placeholders for future expansion

### Development & Management Tools
- **Price List Management**: Complete CRUD operations for pricing rules
- **Development Endpoints**: Database management and token generation tools
- **Enhanced Authentication**: Silent Bearer token extraction and tier detection
- **Error Resilience**: Graceful fallbacks and comprehensive error handling

## Future Enhancements

### Potential Improvements
1. **Caching**: Redis for pricing calculations and session caching
2. **File Storage**: Cloud storage for product images
3. **Search**: Elasticsearch for advanced product search with pricing filters
4. **Notifications**: Push notifications for price changes and promotions
5. **Analytics**: User behavior, pricing effectiveness, and sales analytics
6. **Testing**: Comprehensive test suite for pricing calculations
7. **Advanced Pricing**: Time-based pricing, geographic pricing, bulk tier discounts
8. **Inventory Integration**: Real-time inventory with pricing synchronization

### Scalability Considerations
- Microservices architecture migration (pricing service separation)
- Database sharding strategies for product and pricing data
- API rate limiting for pricing calculations
- Price calculation caching strategies
- Load balancing for high-traffic product listings
- Container orchestration for pricing service scaling

This enhanced architecture provides a comprehensive foundation for a production-ready e-commerce API with advanced pricing capabilities, smart tier management, and efficient performance optimization.