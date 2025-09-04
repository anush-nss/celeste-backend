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
│   ├── api/                        # Modular API structure
│   │   ├── admin/                  # Admin functionality
│   │   │   ├── routes.py           # Admin routes (dev tools)
│   │   │   ├── models.py           # Admin models
│   │   │   ├── service.py          # Admin services
│   │   │   └── __init__.py
│   │   ├── auth/                   # Authentication module
│   │   │   ├── routes.py           # Authentication routes with tier defaults
│   │   │   ├── models.py           # Authentication models
│   │   │   ├── token_models.py     # Token models
│   │   │   └── __init__.py
│   │   ├── categories/             # Category management
│   │   │   ├── routes.py           # Category routes
│   │   │   ├── models.py           # Category models
│   │   │   ├── service.py          # Category services
│   │   │   └── __init__.py
│   │   ├── inventory/              # Inventory management
│   │   │   ├── routes.py           # Inventory routes
│   │   │   ├── models.py           # Inventory models
│   │   │   ├── service.py          # Inventory services
│   │   │   └── __init__.py
│   │   ├── orders/                 # Order management
│   │   │   ├── routes.py           # Order routes
│   │   │   ├── models.py           # Order models
│   │   │   ├── service.py          # Order services
│   │   │   └── __init__.py
│   │   ├── pricing/                # ⭐ NEW: Pricing management
│   │   │   ├── routes.py           # Pricing management routes
│   │   │   ├── models.py           # Pricing and tier models
│   │   │   ├── service.py          # Pricing calculations service
│   │   │   └── __init__.py
│   │   ├── products/               # Product management
│   │   │   ├── routes.py           # Enhanced products with smart pricing
│   │   │   ├── models.py           # Enhanced product models with pricing
│   │   │   ├── service.py          # Enhanced product service with pagination
│   │   │   └── __init__.py
│   │   ├── stores/                 # Store management
│   │   │   ├── routes.py           # Store routes
│   │   │   ├── models.py           # Store models
│   │   │   ├── service.py          # Store services
│   │   │   └── __init__.py
│   │   ├── tiers/                  # ⭐ NEW: Customer tier management
│   │   │   ├── routes.py           # Tier management routes (admin + user)
│   │   │   ├── models.py           # Customer tier models and schemas
│   │   │   ├── service.py          # Tier evaluation and management service
│   │   │   └── __init__.py
│   │   └── users/                  # User management
│   │       ├── routes.py           # User routes with tier support
│   │       ├── models.py           # Enhanced user models with tiers
│   │       ├── service.py          # Enhanced user service with tiers
│   │       └── __init__.py
│   ├── config/                     # Configuration management
│   │   ├── constants.py            # Enhanced constants with tiers and pricing
│   │   └── settings.py             # Application settings
│   ├── dependencies/               # Dependency injection
│   │   ├── auth.py                 # Auth dependencies and role checking
│   │   ├── tiers.py                # ⭐ NEW: Tier-related dependencies
│   │   └── __init__.py
│   ├── middleware/                 # Middleware components
│   │   ├── timing.py               # Request timing middleware
│   │   ├── logging.py              # Request logging middleware
│   │   └── __init__.py
│   └── shared/                     # Shared utilities
│       ├── database.py             # Firebase configuration and database connection
│       ├── exceptions.py           # Custom exceptions
│       ├── logger.py               # Logging configuration
│       └── responses.py            # Response formatting
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

### 2. Authentication & Authorization (`src/dependencies/auth.py`)

#### `auth.py`
Contains authentication and authorization logic:
- `get_current_user()`: Validates JWT tokens and returns user information
- `get_optional_user()`: Silent Bearer token extraction (no auth errors)
- `RoleChecker`: Dependency class for role-based access control
- Firebase token verification

#### `tiers.py` ⭐ **NEW**
Contains tier-related dependency logic:
- `get_user_tier()`: Database-backed customer tier detection
- Integration with tier service for user tier retrieval

### 3. Shared Components (`src/shared/`)

#### `database.py`
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

### 4. Data Models (Domain-Specific `src/api/{domain}/models.py`)

Pydantic models for data validation and serialization, organized by domain:

#### `src/api/users/models.py` ⭐ **Enhanced**
- `UserSchema`: Complete user data model with customer tiers
- `CreateUserSchema`: User creation payload with explicit defaults
- `UpdateUserSchema`: User update payload with tier support
- `CartItemSchema`: Cart item structure
- `AddToWishlistSchema`, `AddToCartSchema`: Action schemas

#### `src/api/products/models.py` ⭐ **Enhanced**
- `ProductSchema`: Complete product data model
- `EnhancedProductSchema`: Product model with pricing and inventory info
- `PricingInfoSchema`: Detailed pricing breakdown structure
- `PaginatedProductsResponse`: Cursor-based pagination response
- `CreateProductSchema`: Product creation payload
- `UpdateProductSchema`: Product update payload
- `ProductQuerySchema`: Enhanced query parameters with pricing options

#### `src/api/pricing/models.py` ⭐ **New**
- `PriceListSchema`: Price list management model
- `PriceListLineSchema`: Individual pricing rule model
- `PriceCalculationRequest/Response`: Price calculation models
- `BulkPriceCalculationRequest/Response`: Bulk pricing models
- Complete CRUD models for price management

#### `src/api/tiers/models.py` ⭐ **NEW**
- `CustomerTierSchema`: Complete customer tier definition model
- `TierRequirementsSchema`: Requirements to achieve tier (orders, value, activity)
- `TierBenefitsSchema`: Benefits provided by tier (discounts, perks)
- `UserTierProgressSchema`: User's progress towards next tier
- `TierEvaluationSchema`: Tier evaluation results and recommendations
- Complete CRUD models for tier management

#### Other Model Files
- `src/api/auth/models.py`: Authentication-related models
- `src/api/categories/models.py`: Product category models
- `src/api/admin/models.py`: Admin models
- `src/api/orders/models.py`: Order management models
- `src/api/inventory/models.py`: Inventory tracking models
- `src/api/stores/models.py`: Physical store models

### 5. API Routes (Domain-Specific `src/api/{domain}/routes.py`)

Each route module handles a specific domain of functionality:

#### `src/api/auth/routes.py` ⭐ **Enhanced**
- User registration with Firebase
- Profile management
- Development token generation
- User registration with explicit tier defaults
- Firebase Auth integration
- Automatic role and tier assignment

#### `src/api/users/routes.py` ⭐ **Enhanced**
- User profile CRUD operations
- Cart management (add, update, remove, get)
- Wishlist management (add, remove, get)
- Role-based access control
- Enhanced user management with tier support

#### `src/api/products/routes.py` ⭐ **Enhanced**
- Enhanced product CRUD operations
- Smart pricing with automatic tier detection
- Cursor-based pagination (default: 20, max: 100)
- Legacy endpoints for backward compatibility
- Advanced filtering and querying
- Admin-only creation/modification

#### `src/api/pricing/routes.py` ⭐ **New**
- Complete price list management (Admin only)
- Price list line CRUD operations
- Price calculation endpoints (single and bulk)
- User-specific pricing endpoints
- Comprehensive OpenAPI documentation

#### `src/api/tiers/routes.py` ⭐ **NEW**
- Customer tier CRUD operations (Admin only)
- User tier information and progress tracking
- Automatic tier evaluation and updates
- Tier benefits and requirements management
- Public tier information endpoints

#### `src/api/orders/routes.py`
- Order creation and management
- Status updates
- User-specific order retrieval

#### `src/api/admin/routes.py` ⭐ **New** (Development Only)
- Development token generation
- Database management tools
- Collection browsing and data insertion
- Test data creation utilities

#### Other Route Modules
- `src/api/categories/routes.py`: Product categorization
- `src/api/inventory/routes.py`: Stock tracking
- `src/api/stores/routes.py`: Physical store management
- `src/api/tiers/routes.py`: Customer tier management

### 6. Business Logic (Domain-Specific `src/api/{domain}/service.py`)

Service classes containing business logic, organized by domain:

#### `src/api/pricing/service.py` ⭐ **New**
- Advanced pricing calculation engine
- Tier-based price list discovery and application
- Global price list management with `is_global` field
- Bulk pricing optimization for product listings
- UTC timezone handling for price list validity

#### `src/api/products/service.py` ⭐ **Enhanced**
- Enhanced product service with cursor-based pagination
- Integration with pricing service for bulk calculations
- `get_products_with_pagination()` for efficient listings
- Legacy compatibility with existing methods

#### `src/api/users/service.py` ⭐ **Enhanced**
- Database-backed tier storage and retrieval
- Explicit role and tier defaults during user creation
- Enhanced cart and wishlist functionality
- User tier management integration

#### `src/api/tiers/service.py` ⭐ **NEW**
- Comprehensive tier management and evaluation system
- User statistics calculation for tier evaluation
- Automatic tier progression and updates
- Tier requirements validation and progress tracking
- Default tier initialization and management

#### Other Service Modules
- `src/api/orders/service.py`: Order management logic
- `src/api/categories/service.py`: Category management logic
- `src/api/inventory/service.py`: Inventory management logic
- `src/api/stores/service.py`: Store management logic
- `src/api/admin/service.py`: Admin and development utilities

#### General Service Patterns
- Separation of concerns between routes and business logic
- Database operations and data transformation
- Cross-domain operations and validation
- Error handling with graceful fallbacks

### 7. Configuration & Utilities (`src/config/` and `src/shared/`)

#### `src/config/constants.py` ⭐ **Enhanced**
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
- `stores/`: Physical store locations
- `price_lists/`: ⭐ **NEW** Price list definitions
- `price_list_lines/`: ⭐ **NEW** Individual pricing rules
- `customer_tiers/`: ⭐ **NEW** Customer tier definitions and requirements

### Data Relationships
- Users have carts, wishlists, and customer tiers (embedded/fields)
- Products belong to categories (reference)
- Orders contain product references
- Inventory tracks product stock levels
- Price lists contain multiple price list lines (reference)
- Price list lines target products, categories, or all products
- Customer tiers determine applicable price lists
- Customer tiers have requirements and benefits (embedded)
- Users are assigned customer tiers based on activity evaluation

## Development Workflow

### 1. Adding New Features
1. Create new domain module in `src/api/{domain}/`
2. Define data models in `src/api/{domain}/models.py`
3. Create service layer in `src/api/{domain}/service.py`
4. Implement routes in `src/api/{domain}/routes.py`
5. Add router to `main.py`
6. Update documentation

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
4. **Notifications**: Push notifications for price changes
5. **Analytics**: User behavior, pricing effectiveness, and sales analytics
6. **Testing**: Comprehensive test suite for pricing calculations
7. **Advanced Pricing**: Time-based pricing, geographic pricing, bulk tier pricing
8. **Inventory Integration**: Real-time inventory with pricing synchronization

### Scalability Considerations
- Microservices architecture migration (pricing service separation)
- Database sharding strategies for product and pricing data
- API rate limiting for pricing calculations
- Price calculation caching strategies
- Load balancing for high-traffic product listings
- Container orchestration for pricing service scaling

This enhanced architecture provides a comprehensive foundation for a production-ready e-commerce API with advanced pricing capabilities, smart tier management, and efficient performance optimization.