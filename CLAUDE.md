# Celeste E-Commerce Platform - Development Memory

## <� Task Execution Process

### Step 1: Requirements Review
- **ALWAYS** read `docs/PROJECT_REQUIREMENTS.md` first to understand target architecture
- Check existing implementation in relevant files (`src/models/`, `src/routers/`, `src/services/`)
- Identify if task aligns with planned Phase 1 (Core), Phase 2 (Advanced), or Phase 3 (Real-time)

### Step 2: Implementation Approach
- Follow existing code patterns in `src/` structure
- Use established Pydantic models, FastAPI routers, service layer patterns
- Maintain backward compatibility with current API endpoints
- Implement database schema changes according to migration strategy

### Step 3: Code Standards
- Follow patterns in `docs/DEVELOPMENT_GUIDELINES.md`
- **NEVER HARDCODE**: Use constants from `src/shared/constants.py` (UserRole, OrderStatus, DiscountType)
- Use proper error handling with custom exceptions
- Add type hints and validation with Pydantic
- Implement role-based access control where needed
- Add proper docstrings and comments

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
2. **Phase 2 Collections**: price_lists, promotions, bundles, product_options
3. **Phase 3 Collections**: active_deliveries, rider_presence (Real-time DB)

## =' Key Commands
- **Dev Server**: `uvicorn main:app --reload --port 8000`
- **API Docs**: `http://localhost:8000/docs`
- **Firebase**: Service account in `service-account.json` (gitignored)

## =� Quick Reference
- **Current Tech**: FastAPI + Firebase + Firestore + JWT Auth
- **Target**: Full e-commerce platform with pricing, promotions, delivery tracking
- **Integration**: Odoo ERP for inventory, orders, accounting
- **Performance**: <200ms product queries, <3s checkout, 99.9% uptime