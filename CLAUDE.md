# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚀 Getting Started

### Key Commands
- **Dev Server**: `uvicorn main:app --reload --port 8000`
- **API Docs**: `http://localhost:8000/docs`
- **Code Formatting**: `black .` (configured in pyproject.toml)
- **Python Version**: 3.12+

### Development Setup
1. Install uv: `pip install uv`
2. Create virtual environment: `uv venv`
3. Activate: `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (Linux/Mac)
4. Install dependencies: `uv pip sync uv.lock`
5. Set up Firebase service account as `service-account.json` (gitignored)
6. Configure environment variables (see README.md for details)
7. Before cloud deployment: `uv export --format requirements-txt > requirements.txt`

## 🏗️ Architecture Overview

This is a FastAPI-based e-commerce API with Firebase/Firestore backend following domain-driven architecture.

### Tech Stack
- **FastAPI**: Modern Python web framework
- **Firebase**: Authentication and Firestore NoSQL database
- **Pydantic**: Data validation and serialization
- **Uvicorn**: ASGI server

### Project Structure
```
src/
├── api/                    # Domain-driven API modules
│   ├── auth/              # Authentication & user registration
│   ├── users/             # User management, cart, wishlist
│   ├── products/          # Product catalog with smart pricing
│   ├── pricing/           # Price lists and tier-based pricing
│   ├── orders/            # Order management
│   ├── categories/        # Product categorization
│   ├── inventory/         # Stock management
│   ├── stores/            # Physical store management
│   ├── tiers/             # Customer tier management
│   └── admin/             # Admin utilities and dev tools
├── config/                # Configuration and constants
├── dependencies/          # Dependency injection (auth, tiers)
├── middleware/            # Request timing, logging
└── shared/                # Utilities, exceptions, responses
```

## 🎯 Development Patterns

### Task Execution Process

#### Step 1: Requirements Review
- **ALWAYS** read `docs/PROJECT_REQUIREMENTS.md` first to understand target architecture
- Check existing implementation in relevant domain modules (`src/api/{domain}/`)
- Identify if task aligns with planned Phase 1 (Core), Phase 2 (Advanced), or Phase 3 (Real-time)

#### Step 2: Implementation Approach
- Follow modular domain-driven architecture in `src/api/{domain}/` structure
- Use established patterns: `models.py`, `routes.py`, `service.py` per domain
- Maintain backward compatibility with current API endpoints
- Implement database schema changes according to migration strategy
- Use proper service layer abstraction for business logic

#### Step 3: Code Standards & Architecture
- Follow patterns in `docs/DEVELOPMENT_GUIDELINES.md`
- **NEVER HARDCODE**: Use constants from `src/config/constants.py` (UserRole, OrderStatus, DiscountType, etc.)
- Use proper error handling with custom exceptions from `src/shared/exceptions.py`
- Import models from domain-specific locations: `src/api/{domain}/models.py`
- Add type hints and validation with Pydantic
- Implement role-based access control using `RoleChecker` dependency
- Keep routes thin - business logic belongs in service classes

#### Step 4: Documentation Updates (MANDATORY)
- Update `docs/PROJECT_REQUIREMENTS.md` with implementation progress
- Update `docs/API_DOCUMENTATION.md` for any API changes
- Update `docs/PROJECT_STRUCTURE.md` for architectural changes
- Update `README.md` if setup/features change

#### Step 5: Testing & Validation
- Test all endpoints locally with `uvicorn main:app --reload --port 8000`
- Verify authentication/authorization works
- Check error handling
- Ensure no breaking changes to existing functionality

### Import Patterns
```python
# Domain models and services
from src.api.{domain}.models import {Model}
from src.api.{domain}.service import {Service}

# Shared utilities
from src.config.constants import UserRole, OrderStatus, DiscountType, PriceListType, Collections
from src.shared.exceptions import ResourceNotFoundException
from src.shared.responses import success_response
from src.dependencies.auth import get_current_user, RoleChecker

# Example: User routes pattern
from src.api.users.models import UserSchema, CreateUserSchema
from src.api.users.service import UserService
from src.api.auth.models import DecodedToken
```

## 🔧 Domain Module Structure

Each domain follows this pattern:
- `models.py`: Pydantic schemas for validation
- `routes.py`: FastAPI endpoints with proper auth/validation
- `service.py`: Business logic and database operations
- Router registration in `main.py`

### Key Constants (src/config/constants.py)
- `UserRole`: CUSTOMER, ADMIN
- `OrderStatus`: PENDING, PROCESSING, SHIPPED, DELIVERED, CANCELLED
- `DiscountType`: PERCENTAGE, FLAT  
- `PriceListType`: PRODUCT, CATEGORY, ALL
- `Collections`: All Firestore collection names
- `DEFAULT_FALLBACK_TIER`: "BRONZE"

## 🔐 Authentication & Authorization

### Pattern for Protected Routes
```python
@router.get("/protected")
async def protected_endpoint(
    current_user: Annotated[DecodedToken, Depends(get_current_user)]
):
    # User is authenticated
    pass

@router.post("/admin-only", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def admin_endpoint():
    # Admin only
    pass
```

### Optional Authentication
```python
from src.dependencies.auth import get_optional_user

@router.get("/optional-auth")
async def optional_auth_endpoint(
    current_user: Annotated[Optional[DecodedToken], Depends(get_optional_user)]
):
    # Works with or without Bearer token
    pass
```

## 🗄️ Database Architecture

### Firestore Collections
- `users`: User profiles with customer tiers (BRONZE default)
- `products`: Product catalog with base pricing
- `categories`: Product categories
- `orders`: Order records
- `price_lists`: Pricing rules and tier-based pricing
- `price_list_lines`: Individual pricing rules
- `customer_tiers`: Tier definitions and requirements
- `inventory`: Stock management
- `stores`: Physical store locations

### Database Schema Priorities
1. **Phase 1**: products, users, orders, price_lists (✅ Implemented)
2. **Phase 2**: bundles, product_options, promotions
3. **Phase 3**: active_deliveries, rider_presence (Real-time DB)

## 🎨 Code Standards

### Response Format
All responses use `success_response()`:
```python
from src.shared.responses import success_response

return success_response(data.model_dump(), status_code=201)
```

### Error Handling
```python
from src.shared.exceptions import ResourceNotFoundException, ForbiddenException

if not resource:
    raise ResourceNotFoundException(detail="Resource not found")
```

### Black Code Formatting
- Line length: 88 characters (configured in pyproject.toml)
- Target: Python 3.12
- Run: `black .` to format code

## 🔄 Key Features Implemented

### Smart Pricing System
- Automatic tier detection from Bearer tokens
- Bulk price calculations for product listings  
- Global vs tier-specific price lists
- Database-backed customer tiers with BRONZE defaults

### Enhanced Product Management
- Cursor-based pagination (default: 20, max: 100)
- Smart pricing integration
- Legacy compatibility endpoints

### Development Tools
- Admin endpoints for dev token generation (`/dev/auth/token`)
- Database management utilities
- Development environment detection

## 🎯 Quick Reference

- **Current Tech**: FastAPI + Firebase + Firestore + JWT Auth
- **Target**: Full e-commerce platform with pricing, bundles, delivery tracking
- **Integration**: Odoo ERP for inventory, orders, accounting
- **Performance Goals**: <200ms product queries, <3s checkout, 99.9% uptime

## 🚨 Critical Rules

### Never Hardcode Values
```python
# ❌ WRONG
if user.role == "ADMIN":
    pass

# ✅ CORRECT  
from src.config.constants import UserRole
if user.role == UserRole.ADMIN:
    pass
```

### Always Update Documentation
Every code change MUST include corresponding documentation updates in the `docs/` folder.

### Environment Configuration
- Firebase service account: `service-account.json` (gitignored)
- Environment variables for FIREBASE_WEB_API_KEY (dev only)
- Development endpoints only available when ENVIRONMENT=development

## 📖 Essential Documentation

Before making changes, review:
1. `docs/PROJECT_REQUIREMENTS.md` - Complete feature requirements and roadmap
2. `docs/DEVELOPMENT_GUIDELINES.md` - Coding standards and patterns  
3. `docs/PROJECT_STRUCTURE.md` - Architecture and design patterns
4. `docs/API_DOCUMENTATION.md` - Complete API reference

This codebase implements a sophisticated e-commerce platform with smart pricing, customer tiers, and comprehensive product management. Follow the established patterns and always prioritize backward compatibility.