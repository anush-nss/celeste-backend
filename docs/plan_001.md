# Implementation Plan 001: Price List & Tier-Based Pricing System

## 📋 Overview

This plan implements the advanced pricing system with customer tiers and price lists as specified in `PROJECT_REQUIREMENTS.md`. The system will enable dynamic pricing based on customer tiers, quantity discounts, and product/category-specific pricing rules.

## 🎯 Objectives

1. **Implement Price Lists**: Create and manage price lists with priority-based application
2. **Implement Customer Tiers**: Customer loyalty tiers with automatic tier assignment
3. **Dynamic Pricing**: Calculate product prices based on customer tier and applicable price lists
4. **Efficient Caching**: Minimize database calls through intelligent caching strategy
5. **Direct Implementation**: Build the complete system from scratch without compatibility constraints

## 🗄️ Database Schema Implementation

### Collections to Implement

1. **price_lists** - Price list definitions
2. **price_list_lines** - Pricing rules and discounts  
3. **customer_tiers** - Tier definitions and benefits

### Enhanced Collections

1. **users** - Add `customer_tier` field only (no direct price_list_id)
2. **products** - Keep base price, show normal price by default, apply tier-based pricing dynamically

## 📊 Current State Analysis

### Existing Structure
- ✅ Basic product pricing (`price` field in products)
- ✅ User roles (`CUSTOMER`, `ADMIN`)  
- ✅ Cart/wishlist functionality
- ✅ Order management with `totalAmount`

### Missing Components
- ❌ Customer tier system
- ❌ Price list management
- ❌ Dynamic pricing calculations
- ❌ Tier-based pricing API

## 🏗️ Implementation Strategy

### Phase 1: Foundation (Constants & Models)
1. **Add new constants** to `src/shared/constants.py`
2. **Create Pydantic models** for price lists, tiers, and enhanced user data
3. **Update existing models** to support pricing fields

### Phase 2: Service Layer
1. **Create PricingService** for price calculations
2. **Create CustomerTierService** for tier management  
3. **Update UserService** for tier assignment
4. **Update ProductService** for dynamic pricing

### Phase 3: API Layer
1. **Create price list routers** (Admin only)
2. **Create customer tier routers** (Admin + User endpoints)
3. **Update product routers** with tier-based pricing
4. **Update user routers** with tier information

### Phase 4: Optimization
1. **Implement caching strategy** for price calculations
2. **Add composite indexes** for efficient queries
3. **Performance testing** and optimization

## 💡 Pricing Calculation Logic

### Priority Order (Highest to Lowest)
1. **Tier-based price list** (from customer tier benefits)
2. **Product-specific price list lines**
3. **Category-specific price list lines**
4. **Global price list lines** (type="all")
5. **Base product price** (default/fallback)

### Calculation Process
```python
def calculate_price(product_id: str, user_tier: str = None, quantity: int = 1):
    base_price = get_product_base_price(product_id)  # Default product price
    
    # If no tier provided, return base price (normal price)
    if not user_tier:
        return base_price
    
    # Get price lists from tier benefits and global price lists
    tier_price_lists = get_tier_price_lists(user_tier)
    global_price_lists = get_global_price_lists()
    
    # Combine and sort by priority
    all_price_lists = tier_price_lists + global_price_lists
    
    # Apply price list lines in priority order
    final_price = base_price
    for price_list in all_price_lists:
        price_lines = get_applicable_price_lines(price_list, product_id, quantity)
        final_price = apply_discount(final_price, price_lines)
    
    return final_price
```

## 🚀 Caching Strategy

### Cache Layers
1. **Price List Cache**: Cache active price lists per tier (15 min TTL)
2. **Product Price Cache**: Cache calculated prices per product-tier combination (5 min TTL)
3. **Tier Cache**: Cache customer tier information (30 min TTL)

### Cache Keys
- `price_lists:tier:{tier_name}`
- `product_price:{product_id}:{tier}:{quantity}`
- `customer_tier:{user_id}`

## 📝 Implementation Steps

### Step 1: Constants & Enums
```python
# Add to src/shared/constants.py
class CustomerTier(str, Enum):
    BRONZE = "bronze"
    SILVER = "silver"  
    GOLD = "gold"
    PLATINUM = "platinum"

class PriceListType(str, Enum):
    PRODUCT = "product"
    CATEGORY = "category"
    ALL = "all"

class Collections(str, Enum):
    PRICE_LISTS = "price_lists"
    PRICE_LIST_LINES = "price_list_lines"
    CUSTOMER_TIERS = "customer_tiers"
```

### Step 2: Pydantic Models
- `src/models/pricing_models.py`
- `src/models/tier_models.py`
- Update `src/models/user_models.py` (add customer_tier field only)
- Keep `src/models/product_models.py` unchanged (base price remains)

### Step 3: Service Layer
- `src/services/pricing_service.py`
- `src/services/customer_tier_service.py`
- Update `src/services/user_service.py`
- Update `src/services/product_service.py`

### Step 4: API Routes  
- `src/routers/pricing_router.py`
- `src/routers/customer_tiers_router.py`
- Update `src/routers/products_router.py`
- Update `src/routers/users_router.py`

### Step 5: Database Setup
- Create default customer tiers
- Create default price lists
- Migration script for existing users

## 🔍 API Endpoints to Implement

### Price Lists (Admin Only)
- `GET /price-lists` - List all price lists
- `POST /price-lists` - Create price list
- `PUT /price-lists/{id}` - Update price list
- `DELETE /price-lists/{id}` - Delete price list
- `GET /price-lists/{id}/lines` - Get price list lines
- `POST /price-lists/{id}/lines` - Add price list line

### Customer Tiers (Admin + User)
- `GET /customer-tiers` - List all tiers (Public)
- `POST /customer-tiers` - Create tier (Admin)
- `PUT /customer-tiers/{id}` - Update tier (Admin)
- `GET /users/me/tier` - Get current user tier
- `GET /users/me/tier-progress` - Get tier progress

### Enhanced Product Endpoints
- `GET /products/{id}` - Get product with base price (default)
- `GET /products/{id}?tier={tier}&quantity={qty}` - Get product with tier pricing
- `POST /products/calculate-price` - Bulk price calculation for cart items
- `GET /products?tier={tier}` - List products with tier pricing
- `GET /products` - List products with base prices (no tier applied)

## 📊 Performance Considerations

### Database Queries Optimization
1. **Composite Indexes**:
   - `(price_list_id, type, active)`
   - `(product_id, customer_tier)`
   - `(category_id, customer_tier)`

2. **Query Batching**: 
   - Batch price calculations for cart items
   - Single query for all applicable price lists

3. **Caching Strategy**:
   - Cache price calculations for 5 minutes
   - Cache tier information for 30 minutes
   - Invalidate cache on price list updates

### Memory Optimization
- Load only necessary fields in pricing queries
- Use pagination for price list management
- Implement lazy loading for tier benefits

## ⚡ Error Handling

### Price Calculation Errors
- **Missing tier**: Default to BRONZE tier
- **Invalid price list**: Skip and continue with next priority
- **Calculation errors**: Fallback to base product price
- **Database errors**: Cache previous calculation, log error

### Data Integrity
- Validate price list date ranges
- Ensure tier requirements are met
- Prevent negative pricing
- Validate discount percentages (0-100%)

## 🧪 Testing Strategy

### Unit Tests
- Price calculation logic
- Tier assignment algorithms
- Cache invalidation
- Edge cases (missing data, invalid inputs)

### Integration Tests  
- End-to-end pricing workflow
- API endpoint functionality
- Database operations
- Cache behavior

### Performance Tests
- Concurrent price calculations
- Large dataset handling
- Cache hit rates
- Response time targets (<200ms)

## 📈 Success Metrics

### Technical Metrics
- **Price calculation time**: <50ms average
- **API response time**: <200ms for product listings
- **Cache hit rate**: >80% for pricing calculations
- **Database queries**: <3 queries per price calculation

### Business Metrics
- **Tier distribution**: Track customer tier adoption
- **Price list usage**: Monitor which price lists are most effective
- **Discount impact**: Measure revenue impact of tier-based pricing

## 🚨 Risk Mitigation

### Data Consistency
- **Atomic operations**: Ensure price list updates are atomic
- **Rollback strategy**: Ability to revert price list changes
- **Data validation**: Strict validation before applying pricing rules

### Performance Risks
- **Cache warming**: Pre-populate cache for popular products
- **Fallback mechanisms**: Always fallback to base price if calculation fails
- **Circuit breaker**: Prevent cascade failures in pricing service

## 📋 Implementation Checklist

### Phase 1: Foundation
- [ ] Add constants to `src/shared/constants.py`
- [ ] Create pricing models in `src/models/pricing_models.py`
- [ ] Create tier models in `src/models/tier_models.py`
- [ ] Update user models with tier fields
- [ ] Update product models if needed

### Phase 2: Services
- [ ] Create `src/services/pricing_service.py`
- [ ] Create `src/services/customer_tier_service.py`
- [ ] Update `src/services/user_service.py` for tier management
- [ ] Update `src/services/product_service.py` for pricing

### Phase 3: API Routes
- [ ] Create `src/routers/pricing_router.py`
- [ ] Create `src/routers/customer_tiers_router.py` 
- [ ] Update `src/routers/products_router.py` with pricing
- [ ] Update `src/routers/users_router.py` with tier info
- [ ] Register all new routers in `main.py`

### Phase 4: Data Setup
- [ ] Create default customer tiers in Firestore
- [ ] Create default price lists
- [ ] Update existing users with default tier
- [ ] Test pricing calculations

### Phase 5: Documentation
- [ ] Update `docs/API_DOCUMENTATION.md` with new endpoints
- [ ] Update `docs/PROJECT_STRUCTURE.md` with new services
- [ ] Update `docs/PROJECT_REQUIREMENTS.md` with implementation status
- [ ] Update `README.md` if needed

This implementation plan ensures a systematic, efficient, and scalable approach to implementing the advanced pricing system for the new development phase.