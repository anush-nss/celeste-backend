# Celeste E-Commerce Platform - Development Memory

## <� Task Execution Process

### Step 1: Requirements Review
- **ALWAYS** read `docs/PROJECT_REQUIREMENTS.md` first to understand target architecture
- Check existing implementation in relevant domain modules (`src/api/{domain}/`)
- Identify if task aligns with planned Phase 1 (Core), Phase 2 (Advanced), or Phase 3 (Real-time)

### Step 2: Implementation Approach
- Follow modular domain-driven architecture in `src/api/{domain}/` structure
- Use established patterns: `models.py`, `routes.py`, `service.py` per domain
- Maintain backward compatibility with current API endpoints
- Implement database schema changes according to migration strategy
- Use proper service layer abstraction for business logic

### Step 3: Code Standards & Architecture
- Follow patterns in `docs/DEVELOPMENT_GUIDELINES.md`
- **NEVER HARDCODE**: Use constants from `src/config/constants.py` (UserRole, OrderStatus, DiscountType, CustomerTier)
- Use proper error handling with custom exceptions from `src/shared/exceptions.py`
- Import models from domain-specific locations: `src/api/{domain}/models.py`
- Use AuthService for authentication logic, not direct Firebase calls in routes
- Add type hints and validation with Pydantic
- Implement role-based access control using `RoleChecker` dependency
- Keep routes thin - business logic belongs in service classes

### Step 4: Documentation Updates (MANDATORY)
- Update `docs/PROJECT_REQUIREMENTS.md` with implementation progress
- Update `docs/API_DOCUMENTATION.md` for any API changes
- Update `docs/PROJECT_STRUCTURE.md` for architectural changes
- Update `README.md` if setup/features change

### Step 5: Testing & Validation
- Test all endpoints locally
- Verify authentication/authorization works
- Check error handling
- Ensure no breaking changes to existing functionality

## =� Database Schema Priority
1. **Phase 1 Collections**: products, users, orders, brands, stock, customer_tiers
2. **Phase 2 Collections**: price_lists, bundles, product_options
3. **Phase 3 Collections**: active_deliveries, rider_presence (Real-time DB)

## =' Key Commands
- **Dev Server**: `uvicorn main:app --reload --port 8000`
- **API Docs**: `http://localhost:8000/docs`
- **Firebase**: Service account in `service-account.json` (gitignored)
- **Dev Token**: `POST /dev/auth/token?uid={user_uid}` (requires FIREBASE_WEB_API_KEY)

## =� Quick Reference
- **Current Tech**: FastAPI + Firebase + Firestore + JWT Auth
- **Target**: Full e-commerce platform with pricing, bundles, delivery tracking
- **Integration**: Odoo ERP for inventory, orders, accounting
- **Performance**: <200ms product queries, <3s checkout, 99.9% uptime

## 🏗️ Current Architecture Overview
- **Modular Structure**: Domain-driven API modules in `src/api/{domain}/`
- **Service Layer**: Business logic separated from route handlers
- **Auth Service**: Centralized authentication logic in `src/api/auth/service.py`
- **Shared Components**: Utilities, exceptions, responses in `src/shared/`
- **Configuration**: Constants and settings in `src/config/`
- **Dependencies**: Auth and other DI in `src/dependencies/`
- **Middleware**: Request timing, logging in `src/middleware/`

## 📁 Domain Modules Available
- `src/api/auth/` - Authentication and user registration
- `src/api/users/` - User management, profiles, cart, wishlist
- `src/api/products/` - Product catalog with smart pricing
- `src/api/pricing/` - Price lists and tier-based pricing
- `src/api/orders/` - Order management
- `src/api/categories/` - Product categorization
- `src/api/inventory/` - Stock management
- `src/api/stores/` - Physical store management
- `src/api/admin/` - Admin utilities and dev tools

## 🎯 Import Patterns
```python
# Domain models and services
from src.api.{domain}.models import {Model}
from src.api.{domain}.service import {Service}

# Shared utilities
from src.config.constants import UserRole, CustomerTier, OrderStatus
from src.shared.exceptions import ResourceNotFoundException
from src.shared.responses import success_response
from src.dependencies.auth import get_current_user, RoleChecker

# Example: User routes pattern
from src.api.users.models import UserSchema, CreateUserSchema
from src.api.users.service import UserService
from src.api.auth.models import DecodedToken
```