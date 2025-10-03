# Celeste E-Commerce API - Project Structure & Architecture

## Project Overview

Celeste is a FastAPI-based e-commerce backend API that provides comprehensive functionality for managing users, products, orders, inventory, and more. The application uses Firebase for authentication, PostgreSQL for the primary database, and Redis for caching.

## Technology Stack

### Core Technologies
- **FastAPI**: Modern Python web framework for building APIs
- **Python**: Primary programming language
- **Firebase Admin SDK**: For Firebase integration
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server for running the application
- **Redis**: In-memory data store for caching
- **SQLAlchemy**: ORM for PostgreSQL

### Database & Authentication
- **PostgreSQL**: Relational database
- **Firebase Auth**: Authentication and user management
- **JWT**: JSON Web Tokens for secure API access

### Development Tools
- **Python-dotenv**: Environment variable management
- **Alembic**: Database migration tool

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
│   │   │   └── routes.py           # Admin routes (dev tools)
│   │   ├── auth/                   # Authentication module
│   │   │   ├── routes.py           # Authentication routes
│   │   │   ├── models.py           # Authentication models
│   │   │   └── service.py          # Authentication service
│   │   ├── carts/                  # Cart management
│   │   │   └── service.py          # Cart service
│   │   ├── categories/             # Category management
│   │   │   ├── routes.py, models.py, service.py, cache.py
│   │   ├── ecommerce_categories/   # Ecommerce Category management
│   │   │   ├── routes.py, models.py, service.py
│   │   ├── inventory/              # Inventory management
│   │   │   ├── routes.py, models.py, service.py
│   │   ├── orders/                 # Order management
│   │   │   ├── routes.py, models.py, service.py
│   │   ├── pricing/                # Pricing management
│   │   │   ├── routes.py, models.py, service.py, cache.py
│   │   ├── products/               # Product management
│   │   │   ├── routes.py, models.py, service.py, cache.py
│   │   ├── stores/                 # Store management
│   │   │   ├── routes.py, models.py, service.py, cache.py
│   │   ├── tags/                   # Tag management
│   │   │   ├── routes.py, models.py, service.py
│   │   ├── tiers/                  # Customer tier management
│   │   │   ├── routes.py, models.py, service.py, cache.py
│   │   └── users/                  # User management
│   │       ├── routes.py, models.py, service.py
│   ├── config/                     # Configuration management
│   │   ├── constants.py, settings.py, cache_config.py
│   ├── database/                   # Database configuration and models
│   │   ├── connection.py, base.py, performance_config.py
│   │   └── models/                 # SQLAlchemy models
│   ├── dependencies/               # Dependency injection
│   │   ├── auth.py, tiers.py
│   ├── middleware/                 # Middleware components
│   │   ├── error.py, timing.py
│   └── shared/                     # Shared utilities
│       ├── db_client.py, core_cache.py, cache_invalidation.py, geo_utils.py, etc.
├── main.py                         # Application entry point
├── requirements.txt                # Python dependencies
├── pyproject.toml                  # Project configuration
├── alembic.ini                     # Alembic configuration
├── migrations/                     # Database migrations
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

### 3. Caching Layer (`src/api/{domain}/cache.py`)

To ensure high performance and reduce database load, the application uses a Redis-based caching layer.

- **`src/shared/core_cache.py`**: Provides the core Redis connection and basic cache operations.
- **`src/api/{domain}/cache.py`**: Each domain has its own cache module that defines domain-specific caching logic.
- **`src/shared/cache_invalidation.py`**: A centralized manager for handling cross-domain cache invalidation.

### 4. API Routes (Domain-Specific `src/api/{domain}/routes.py`)

Each route module handles a specific domain of functionality. All route handlers are `async` and `await` calls to the service layer.

### 5. Data Models (Domain-Specific `src/api/{domain}/models.py`)

Pydantic models are used for data validation, serialization, and documentation. They are organized by domain and define the shape of the API data.

### 6. Dependencies (`src/dependencies/`)

FastAPI's dependency injection system is used for:
- **Authentication & Authorization:** (`auth.py`) Validating JWTs and checking user roles.
- **Tier Detection:** (`tiers.py`) Getting the customer tier for the current user.

### 7. Shared Components (`src/shared/`)

- **`database/connection.py`**: Initializes the asynchronous SQLAlchemy session.
- **`shared/geo_utils.py`**: Geospatial utilities for distance calculations.
- **`shared/exceptions.py`**: Defines custom exception classes.
- **`shared/responses.py`**: Standardizes API response formats.