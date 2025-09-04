# Celeste E-Commerce API - Project Structure & Architecture

## Project Overview

Celeste is a FastAPI-based e-commerce backend API that provides comprehensive functionality for managing users, products, orders, inventory, and more. The application uses Firebase for authentication, Firestore as the primary database, and Redis for caching.

## Technology Stack

### Core Technologies
- **FastAPI**: Modern Python web framework for building APIs
- **Python**: Primary programming language
- **Firebase Admin SDK**: For Firebase integration
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server for running the application
- **Redis**: In-memory data store for caching

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
│   │   │   └── __init__.py
│   │   ├── auth/                   # Authentication module
│   │   │   ├── routes.py           # Authentication routes
│   │   │   ├── models.py           # Authentication models
│   │   │   └── __init__.py
│   │   ├── categories/             # Category management
│   │   │   ├── routes.py           # Category routes
│   │   │   ├── models.py           # Category models
│   │   │   ├── service.py          # Category services
│   │   │   ├── cache.py            # Category caching
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
│   │   ├── pricing/                # Pricing management
│   │   │   ├── routes.py           # Pricing management routes
│   │   │   ├── models.py           # Pricing and tier models
│   │   │   ├── service.py          # Pricing calculations service
│   │   │   ├── cache.py            # Pricing caching
│   │   │   └── __init__.py
│   │   ├── products/               # Product management
│   │   │   ├── routes.py           # Enhanced products with smart pricing
│   │   │   ├── models.py           # Enhanced product models with pricing
│   │   │   ├── service.py          # Enhanced product service with pagination
│   │   │   ├── cache.py            # Product caching
│   │   │   └── __init__.py
│   │   ├── stores/                 # Store management
│   │   │   ├── routes.py           # Store routes
│   │   │   ├── models.py           # Store models
│   │   │   ├── service.py          # Store services
│   │   │   └── __init__.py
│   │   ├── tiers/                  # Customer tier management
│   │   │   ├── routes.py           # Tier management routes (admin + user)
│   │   │   ├── models.py           # Customer tier models and schemas
│   │   │   ├── service.py          # Tier evaluation and management service
│   │   │   ├── cache.py            # Tier caching
│   │   │   └── __init__.py
│   │   └── users/                  # User management
│   │       ├── routes.py           # User routes with tier support
│   │       ├── models.py           # Enhanced user models with tiers
│   │       ├── service.py          # Enhanced user service with tiers
│   │       └── __init__.py
│   ├── config/                     # Configuration management
│   │   ├── constants.py            # Enhanced constants with tiers and pricing
│   │   ├── settings.py             # Application settings
│   │   └── cache_config.py         # Cache configuration
│   ├── dependencies/               # Dependency injection
│   │   ├── auth.py                 # Auth dependencies and role checking
│   │   ├── tiers.py                # Tier-related dependencies
│   │   └── __init__.py
│   ├── middleware/                 # Middleware components
│   │   ├── timing.py               # Request timing middleware
│   │   └── __init__.py
│   └── shared/                     # Shared utilities
│       ├── db_client.py            # Firestore client initialization
│       ├── core_cache.py           # Core Redis cache connection
│       ├── cache_invalidation.py   # Cross-domain cache invalidation manager
│       ├── exceptions.py           # Custom exceptions
│       └── responses.py            # Response formatting
├── main.py                         # Application entry point
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment variables example
└── README.md                       # Project readme
```

## Architecture Components

### 1. Application Entry Point (`main.py`)

The main application file that:
- Initializes the FastAPI application
- Configures middleware for request logging and timing
- Includes all routers
- Sets up global exception handling

### 2. Asynchronous Services (`src/api/{domain}/service.py`)

All business logic is encapsulated in asynchronous service classes. This ensures that all database operations are non-blocking, leading to higher performance and scalability.

#### General Service Patterns
- **Fully Asynchronous:** All methods that perform I/O are `async`.
- **Separation of Concerns:** Services are responsible for business logic, keeping the route handlers clean and focused on handling HTTP requests.
- **Database Interaction:** All interaction with Firestore is handled within the service layer.

### 3. Caching Layer (`src/api/{domain}/cache.py`)

To ensure high performance and reduce database load, the application uses a Redis-based caching layer.

- **`src/shared/core_cache.py`**: Provides the core Redis connection and basic cache operations (get, set, delete).
- **`src/api/{domain}/cache.py`**: Each domain has its own cache module that defines domain-specific caching logic, keys, and TTLs.
- **`src/shared/cache_invalidation.py`**: A centralized manager for handling cross-domain cache invalidation, ensuring data consistency.

### 4. API Routes (Domain-Specific `src/api/{domain}/routes.py`)

Each route module handles a specific domain of functionality. All route handlers are `async` and `await` calls to the service layer.

### 5. Data Models (Domain-Specific `src/api/{domain}/models.py`)

Pydantic models are used for data validation, serialization, and documentation. They are organized by domain and define the shape of the API data.

### 6. Dependencies (`src/dependencies/`)

FastAPI's dependency injection system is used for:
- **Authentication & Authorization:** (`auth.py`) Validating JWTs and checking user roles.
- **Tier Detection:** (`tiers.py`) Getting the customer tier for the current user.

### 7. Shared Components (`src/shared/`)

- **`db_client.py`**: Initializes the asynchronous Firestore client.
- **`exceptions.py`**: Defines custom exception classes.
- **`responses.py`**: Standardizes API response formats.

## Design Patterns & Principles

- **Separation of Concerns**: Routers, services, and models are kept in separate modules.
- **Asynchronous Everywhere**: The entire application is built on an async-first principle for performance.
- **Dependency Injection**: Used extensively for managing dependencies like authentication and services.
- **Centralized Caching**: A dedicated caching layer with cross-domain invalidation logic.

## Future Enhancements

### Potential Improvements
1. **File Storage**: Cloud storage for product images.
2. **Search**: Elasticsearch for advanced product search.
3. **Notifications**: Push notifications for order status updates and promotions.
4. **Analytics**: User behavior, pricing effectiveness, and sales analytics.
5. **Testing**: A comprehensive test suite for all services and endpoints.
