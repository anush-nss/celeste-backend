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
│   │   └── dependencies.py         # Auth dependencies and role checking
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
│   │   ├── product_models.py       # Product models
│   │   ├── store_models.py         # Store models
│   │   ├── token_models.py         # Token models
│   │   └── user_models.py          # User models
│   ├── routers/                    # API route handlers
│   │   ├── auth_router.py          # Authentication routes
│   │   ├── categories_router.py    # Category routes
│   │   ├── discounts_router.py     # Discount routes
│   │   ├── inventory_router.py     # Inventory routes
│   │   ├── orders_router.py        # Order routes
│   │   ├── products_router.py      # Product routes
│   │   ├── promotions_router.py    # Promotion routes
│   │   ├── stores_router.py        # Store routes
│   │   └── users_router.py         # User routes
│   ├── services/                   # Business logic services
│   │   └── user_service.py         # User service (and others)
│   └── shared/                     # Shared utilities
│       └── constants.py            # Application constants
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
Contains authentication and authorization logic:
- `get_current_user()`: Validates JWT tokens and returns user information
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

#### `user_models.py`
- `UserSchema`: Complete user data model
- `CreateUserSchema`: User creation payload
- `UpdateUserSchema`: User update payload
- `CartItemSchema`: Cart item structure
- `AddToWishlistSchema`, `AddToCartSchema`: Action schemas

#### `product_models.py`
- `ProductSchema`: Complete product data model
- `CreateProductSchema`: Product creation payload
- `UpdateProductSchema`: Product update payload
- `ProductQuerySchema`: Query parameters for product filtering

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

#### `products_router.py`
- Product CRUD operations
- Advanced filtering and querying
- Admin-only creation/modification

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

### 6. Business Logic (`src/services/`)

Service classes containing business logic:
- Separation of concerns between routes and business logic
- Database operations
- Data transformation and validation
- Cross-domain operations

### 7. Shared Components (`src/shared/`)

#### `constants.py`
Application-wide constants:
```python
class UserRole(str, Enum):
    CUSTOMER = "CUSTOMER"
    ADMIN = "ADMIN"

class DiscountType(str, Enum):
    PERCENTAGE = "PERCENTAGE"
    FLAT = "FLAT"

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
- `users/`: User profiles and data
- `products/`: Product catalog
- `categories/`: Product categories
- `orders/`: Order records
- `inventory/`: Stock levels
- `discounts/`: Discount rules
- `stores/`: Physical store locations
- `promotions/`: Marketing campaigns

### Data Relationships
- Users have carts and wishlists (embedded arrays)
- Products belong to categories (reference)
- Orders contain product references
- Inventory tracks product stock levels

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

## Future Enhancements

### Potential Improvements
1. **Caching**: Redis for session and data caching
2. **File Storage**: Cloud storage for product images
3. **Search**: Elasticsearch for advanced product search
4. **Notifications**: Push notifications for orders
5. **Analytics**: User behavior and sales analytics
6. **Testing**: Comprehensive test suite
7. **Documentation**: Interactive API documentation
8. **CI/CD**: Automated deployment pipeline

### Scalability Considerations
- Microservices architecture migration
- Database sharding strategies
- API rate limiting
- Load balancing
- Container orchestration

This architecture provides a solid foundation for a production-ready e-commerce API with room for growth and enhancement.