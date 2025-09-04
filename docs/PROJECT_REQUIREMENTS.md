# Celeste E-Commerce & Delivery Platform - Project Requirements

## 📋 Project Overview

The Celeste platform is a comprehensive, scalable e-commerce system that enables customers to browse products, apply promotions, place orders, and complete payments. The system integrates with Odoo ERP for order management, stock synchronization, and financial reconciliation, while providing real-time delivery tracking capabilities.

### Key Objectives

- **High Concurrency**: Support 100,000+ concurrent customers and thousands of riders
- **Reliable Payments**: Secure payment processing with multiple gateways
- **Real-time Tracking**: Live delivery tracking with rider presence management
- **ERP Integration**: Seamless integration with Odoo for business operations
- **Scalable Architecture**: Built on Firebase with performance optimization

## 🗄️ Database Schema Design

### Core Collections (Firestore)

#### 1. Products Collection ✅ **Implemented**

```
products/{productId}
{
  name: string,
  description: string | null,
  price: number,              // Base price for the product
  unit: string,               // "kg", "g", "piece", etc.
  categoryId: string,         // Single category reference
  imageUrl: string | null,    // Single product image URL

  // Metadata
  createdAt: timestamp,
  updatedAt: timestamp,

  // Future fields (not yet implemented)
  // brand: object,           // Reference to brand document
  // dietary_tags: string[],  // ["vegetarian", "gluten-free", "halal"]
  // availability: object,    // Availability per fulfillment center
  // active: boolean,         // Product active status
  // last_sync: timestamp     // Last Odoo sync
}
```

**Current Implementation Status:**
- ✅ Basic product CRUD operations
- ✅ Category association (single category)
- ✅ Base pricing structure
- ✅ Image URL support
- ✅ Metadata tracking
- 🔄 **Enhanced with Smart Pricing**: Products automatically calculate tier-based pricing when requested

#### 2. Stock Collection

```
stock/{recordId}
{
  store_id: object,           // Reference to FC/store
  sku_id: object,            // Reference to product
  quantity: number,
  reserved_quantity: number,  // For pending orders
  updated_at: timestamp
}
```

#### 3. Categories Collection ✅ **Implemented**

```
categories/{categoryId}
{
  id: string | null,          // Category document ID
  name: string,               // Category name
  description: string | null, // Category description
  imageUrl: string | null,    // Category image URL
  parentCategoryId: string | null, // For hierarchical categories

  // Future fields (not yet implemented)
  // slug: string,             // URL-friendly slug
  // display_order: number,    // Sort order
  // active: boolean           // Category active status
}
```

**Current Implementation Status:**
- ✅ Complete category CRUD operations
- ✅ Hierarchical category support (parentCategoryId)
- ✅ Category images support
- ✅ Category-product associations
- ✅ Category-based product filtering
- 🔄 **Integrated with Pricing**: Categories can have specific pricing rules via price list lines

#### 4. Brands Collection 🔄 **Planned (Not Yet Implemented)**

```
brands/{brandId}
{
  name: string,
  image_url: string,
  description: string,
  active: boolean
}
```

#### 5. Price Lists Collection ✅ **Implemented**

```
price_lists/{priceListId}
{
  name: string,               // "Gold Customer Discounts", "VIP Pricing"
  priority: number,           // Order of application (1 = highest priority)
  active: boolean,
  valid_from: timestamp,
  valid_until: timestamp | null,
  is_global: boolean | null,  // NEW: Determines if this is a global price list
  
  // Metadata
  created_at: timestamp,
  updated_at: timestamp
}
```

**Current Implementation Status:**
- ✅ Complete CRUD operations for price lists
- ✅ Priority-based application logic
- ✅ Date-based validity checking
- ✅ Global vs tier-specific price list control
- ✅ Admin-only access control

#### 6. Price List Lines Collection ✅ **Implemented**

```
price_list_lines/{priceListLineId}
{
  price_list_id: string,      // Reference to price_list document ID
  type: string,               // "product", "category", "all"
  product_id: string | null,  // If type="product"
  category_id: string | null, // If type="category"
  discount_type: string,      // "percentage", "flat"
  amount: number,             // Discount amount
  min_product_qty: number,    // Minimum quantity required
  max_product_qty: number | null, // Maximum quantity allowed
  
  // Metadata
  created_at: timestamp,
  updated_at: timestamp
}
```

**Current Implementation Status:**
- ✅ Complete CRUD operations for price list lines
- ✅ Product-specific, category-specific, and global discounts
- ✅ Quantity-based discount rules
- ✅ Percentage and flat discount types
- ✅ Integration with price calculation engine

#### 7. Bundles Collection

```
bundles/{bundleId}
{
  name: string,
  sku: string,                // Bundle SKU
  bundle_type: string,        // "fixed", "dynamic"
  bundle_price: number,
  savings: number,

  items: [{
    sku: string,
    quantity: number,
    name: string,
    can_substitute: boolean
  }],

  active: boolean,
  valid_from: timestamp,
  valid_until: timestamp
}
```

#### 8. Promotions Collection

```
promotions/{promoId}
{
  name: string,
  type: string,               // "buy_x_get_y", "cart_discount", "category_discount"

  conditions: {
    // For buy_x_get_y
    buy_quantity: number,
    buy_products: string[],   // SKUs
    buy_categories: string[], // Category IDs

    // For cart discounts
    min_cart_value: number,
    max_cart_value: number,

    // General conditions
    customer_tiers: string[], // Eligible tiers
    payment_methods: string[] // Eligible payment methods
  },

  rewards: {
    // For buy_x_get_y
    get_quantity: number,
    get_products: string[],
    discount_percent: number,

    // For cart/category discounts
    discount_type: string,    // "flat", "percentage"
    discount_amount: number,
    max_discount: number
  },

  usage_limit: number | null,
  usage_limit_per_customer: number,

  active: boolean,
  valid_from: timestamp,
  valid_until: timestamp
}
```

#### 9. Product Options Collection

```
product_options/{productId}
{
  base_sku: string,
  name: string,
  base_price: number,

  option_groups: [{
    id: string,
    name: string,
    required: boolean,
    min_select: number,
    max_select: number,

    options: [{
      sku: string,
      name: string,
      price_modifier: number,  // Add/subtract from base
      image: string,
      available: boolean
    }]
  }]
}
```

#### 10. Enhanced Users Collection ✅ **Implemented**

```
users/{userId}
{
  // Core profile data
  id: string,                 // User document ID
  name: string,
  phone: string | null,
  email: string | null,
  address: string | null,

  // Role and tier management
  role: string,               // "CUSTOMER", "ADMIN"
  customer_tier: string,      // "bronze", "silver", "gold", "platinum"

  // Customer statistics
  total_orders: number,       // Default: 0
  lifetime_value: number,     // Default: 0.0

  // Metadata
  createdAt: timestamp,
  last_order_at: timestamp | null,

  // Cart and wishlist
  wishlist: string[] | null,  // Array of product IDs
  cart: [{                   // Array of cart items
    productId: string,
    quantity: number
  }] | null,

  // Future fields (not yet implemented)
  // price_list_id: string,   // Direct price list assignment
  // addresses: object[]      // Multiple address management
}
```

**Current Implementation Status:**
- ✅ Complete user CRUD operations
- ✅ Customer tier management with BRONZE default
- ✅ Role-based access control
- ✅ Cart and wishlist functionality
- ✅ Customer statistics tracking
- ✅ Database-backed tier detection for pricing
- ✅ Automatic tier assignment during registration

#### 11. Enhanced Orders Collection ✅ **Partially Implemented**

```
orders/{orderId}
{
  // Core order information
  id: string,                // Order document ID
  userId: string,            // Reference to user
  status: string,            // "pending", "processing", "shipped", "delivered", "cancelled"

  // Order items
  items: [{
    productId: string,
    quantity: number,
    price: number            // Price at time of order
  }],

  // Delivery information
  deliveryAddress: string,   // Delivery address
  totalAmount: number,       // Total order amount

  // Metadata
  createdAt: timestamp,

  // Future enhanced fields (not yet implemented)
  // order_number: string,    // Human-readable order number
  // applied_promotions: [],  // Promotion tracking
  // delivery: object,        // Enhanced delivery info
  // totals: object,          // Detailed financial breakdown
  // payment: object,         // Payment information
  // timestamps: object,      // Enhanced timestamp tracking
  // source: string,          // Order source
  // notes: string            // Order notes
}
```

**Current Implementation Status:**
- ✅ Basic order CRUD operations
- ✅ Order-user association
- ✅ Basic order status management
- ✅ Order items with pricing
- ✅ Delivery address support
- 🔄 **Ready for Enhancement**: Foundation exists for detailed pricing breakdown and tracking

#### 12. Customer Tiers Collection 🔄 **Planned (Logic Implemented)**

```
customer_tiers/{tierId}
{
  name: string,               // "Bronze", "Silver", "Gold", "Platinum"
  level: number,              // 1, 2, 3, 4

  requirements: {
    min_orders: number,
    min_lifetime_value: number,
    min_monthly_orders: number
  },

  benefits: {
    price_list_id: string,
    delivery_discount: number, // Percentage
    priority_support: boolean,
    early_access: boolean
  },

  icon_url: string,
  color: string              // "#CD7F32", "#C0C0C0", "#FFD700", "#E5E4E2"
}
```

**Current Implementation Status:**
- ✅ **Tier Logic Implemented**: Four tiers (Bronze, Silver, Gold, Platinum) defined in constants
- ✅ **Database Integration**: User tiers stored in users collection
- ✅ **Automatic Detection**: Tier-based pricing calculations work seamlessly
- ✅ **Default Assignment**: New users automatically get Bronze tier
- 🔄 **Collection Creation**: Tier definitions can be stored in dedicated collection for admin management
- 🔄 **Benefits System**: Ready for tier-specific benefits implementation

#### 13. Promotion Usage Collection

```
promotion_usage/{userId}_{promoId}
{
  count: number,
  last_used: timestamp,
  total_savings: number
}
```

### Real-time Database Collections (Lower Priority)

#### Active Deliveries

```
active_deliveries/{deliveryId}
{
  order_id: string,
  rider_id: string,

  location: {
    lat: number,
    lng: number,
    heading: number,         // 0-360 degrees
    speed: number,           // km/h
    accuracy: number,        // meters
    timestamp: number
  },

  status: string,            // "assigned", "heading_to_pickup", "at_pickup", "heading_to_customer", "arrived"

  route: {
    pickup_location: { lat: number, lng: number },
    delivery_location: { lat: number, lng: number },
    distance_remaining: number, // meters
    time_remaining: number      // seconds
  },

  eta: number,               // timestamp

  checkpoints: [{
    status: string,
    timestamp: number,
    location: { lat: number, lng: number }
  }]
}
```

#### Rider Presence

```
rider_presence/{riderId}
{
  online: boolean,
  last_seen: number,

  status: string,            // "available", "busy", "offline"
  active_delivery: string | null,

  stats: {
    deliveries_today: number,
    active_time: number,     // minutes
    current_zone: string
  },

  device: {
    battery: number,         // percentage
    network: string          // "wifi", "4g", "3g"
  }
}
```

## 🔄 Migration Strategy and Implementation Status

### ✅ Phase 1: Core Enhancement - **COMPLETED**

1. **✅ Enhanced existing collections**:
   - ✅ Extended `products` collection with enhanced pricing integration
   - ✅ Extended `users` collection with customer_tier, total_orders, lifetime_value
   - ✅ Enhanced `orders` collection foundation (ready for detailed breakdown)

2. **✅ Added new core collections**:
   - ✅ `price_lists` - Advanced pricing management
   - ✅ `price_list_lines` - Detailed pricing rules
   - 🔄 `customer_tiers` - Logic implemented, collection optional
   - 🔄 `brands` - Planned for future implementation
   - 🔄 `stock` - Planned for inventory management

### ✅ Phase 2: Advanced Pricing Features - **COMPLETED**

1. **✅ Implemented pricing and tier system**:
   - ✅ Complete `price_lists` and `price_list_lines` system
   - ✅ Database-backed customer tier management
   - ✅ Smart pricing calculations with tier detection
   - ✅ Bulk pricing optimization for performance
   - ✅ Global vs tier-specific price list control

2. **🔄 Product enhancements (planned)**:
   - 🔄 `bundles` for product bundles
   - 🔄 `product_options` for customizable products
   - 🔄 `promotions` for marketing campaigns
   - 🔄 `promotion_usage` for usage tracking

### 🔄 Phase 3: Real-time Features (Future)

1. **Planned delivery tracking**:
   - 🔄 `active_deliveries` in Realtime Database
   - 🔄 `rider_presence` for rider management

## 🏗️ Updated Architecture Integration

### Existing Components Integration

- **FastAPI routers** will be extended to support new collections
- **Pydantic models** will be enhanced with new fields and validation
- **Service layer** will implement new business logic for pricing, promotions, and tiers
- **Firebase integration** remains the same with additional collections

### ✅ New Components Implemented

- ✅ **Pricing Service**: Complete price lists, tiers, and pricing calculations
- ✅ **Enhanced Product Service**: Cursor-based pagination and smart pricing integration
- ✅ **Enhanced User Service**: Database-backed tier management
- ✅ **Enhanced Authentication**: Bearer token tier detection

### 🔄 Future Components Planned

- 🔄 **Promotion Service**: Manage promotion rules and application logic
- 🔄 **Stock Service**: Manage inventory across fulfillment centers  
- 🔄 **Delivery Service**: Handle real-time tracking and rider management
- 🔄 **Tier Service**: Advanced tier progression and benefits management

## 📊 Functional Requirements Implementation

### ✅ 2.1 Enhanced Product & Catalog Management - **IMPLEMENTED**

- **✅ Existing**: Basic product CRUD with categories
- **✅ Implemented**: Smart pricing integration, cursor-based pagination, tier-aware responses
- **✅ Current APIs**:
  - `GET /products` - Enhanced with smart pricing and pagination
  - `GET /products/{id}` - Enhanced with automatic tier pricing
  - `GET /products/legacy` - Backward compatibility
- **🔄 Future APIs**:
  - `GET /products?dietary_tags=vegetarian&fc=FC001`
  - `GET /brands/{brandId}/products`
  - `PUT /products/{sku}/availability`

### 🔄 2.2 Advanced Categories & Brands - **PLANNED**

- **✅ Existing**: Flat category structure with basic CRUD
- **🔄 Planned**: Hierarchical categories with parent-child relationships
- **🔄 Future APIs**:
  - `GET /categories/{categoryId}/children`
  - `GET /categories/tree`
  - `POST /brands`

### ✅ 2.3 Pricing & Tier System - **IMPLEMENTED**

- **✅ Implemented**: Complete pricing engine with tier-based calculations
- **✅ Current APIs**:
  - `POST /pricing/price-lists` (Admin)
  - `GET /pricing/price-lists` (Admin)
  - `POST /pricing/calculate-price`
  - `POST /pricing/calculate-bulk-prices`
  - `GET /pricing/my-price/{product_id}`
- **🔄 Future Promotions APIs**:
  - `GET /promotions/applicable?cart_value=100`
  - `POST /promotions/{promoId}/apply`

### ✅ 2.4 Enhanced User Management - **IMPLEMENTED**

- **✅ Existing**: Basic user profiles with cart/wishlist
- **✅ Implemented**: Customer tiers, automatic tier assignment, tier-based pricing
- **✅ Current APIs**:
  - `GET /users/me` - Includes tier information
  - `PUT /users/me` - Enhanced profile management
  - `POST /auth/register` - Automatic tier assignment
- **🔄 Future APIs**:
  - `POST /users/me/addresses`
  - `GET /users/me/tier-progress`

### ✅ 2.5 Enhanced Order Processing - **FOUNDATION IMPLEMENTED**

- **✅ Existing**: Basic order creation and status management
- **✅ Ready for Enhancement**: Foundation exists for pricing breakdown integration
- **✅ Current APIs**:
  - `GET /orders` - Basic order management
  - `POST /orders` - Order creation
  - `PUT /orders/{id}` - Order updates
- **🔄 Future APIs**:
  - `GET /orders/{orderId}/pricing-breakdown`
  - `GET /orders/{orderId}/tracking`
  - `PUT /orders/{orderId}/delivery-status`

### 2.6 Payment Integration

- **Enhanced**: Multiple payment methods, transaction tracking
- **New APIs**:
  - `POST /payments/process`
  - `GET /payments/{transactionId}/status`
  - `POST /payments/webhooks`

### 2.7 Delivery & Real-time Tracking (Future)

- **New Feature**: Complete delivery management system
- **APIs**:
  - `GET /deliveries/{deliveryId}/track`
  - `PUT /deliveries/{deliveryId}/location`
  - `GET /riders/{riderId}/status`

## 🔧 Technical Implementation Plan

### Database Migration Steps

1. **Backup Existing Data**

   ```bash
   # Export existing Firestore data
   gcloud firestore export gs://backup-bucket/backup-$(date +%Y%m%d)
   ```

2. **Schema Evolution**

   ```python
   # Add new fields to existing documents
   async def migrate_products():
       products = await product_service.get_all_products()
       for product in products:
           await product_service.update_product(product.id, {
               'availability': {'FC001': 'in_stock'},
               'dietary_tags': [],
               'brand': None,
               'last_sync': datetime.now()
           })
   ```

3. **Data Population**
   ```python
   # Create customer tiers
   default_tiers = [
       {'name': 'Bronze', 'level': 1, 'requirements': {'min_orders': 0}},
       {'name': 'Silver', 'level': 2, 'requirements': {'min_orders': 10}},
       {'name': 'Gold', 'level': 3, 'requirements': {'min_orders': 50}},
       {'name': 'Platinum', 'level': 4, 'requirements': {'min_orders': 100}}
   ]
   ```

### API Enhancement Strategy

1. **Backward Compatibility**

   - Maintain existing API endpoints
   - Add optional parameters to existing endpoints
   - Create new versioned endpoints for major changes

2. **Gradual Feature Rollout**

   - Phase 1: Core enhancements (products, users, orders)
   - Phase 2: Pricing and promotions
   - Phase 3: Real-time features

3. **Testing Strategy**
   - Unit tests for new services
   - Integration tests for enhanced workflows
   - Performance tests for high-concurrency scenarios

## 🚀 Performance & Scalability

### Database Optimization

- **Composite Indexes**: For complex queries (category + price range + dietary tags)
- **Partitioning**: Orders and stock by fulfillment center
- **Caching**: Redis for frequently accessed data (price lists, promotions)

### API Optimization

- **Response Caching**: CDN for product catalogs and static content
- **Query Optimization**: Limit results, pagination, field selection
- **Async Processing**: Background jobs for Odoo sync, analytics

### Monitoring & Observability

- **Performance Metrics**: Response times, throughput, error rates
- **Business Metrics**: Order conversion, promotion usage, tier distribution
- **Real-time Dashboards**: Admin panel for operations monitoring

## 🔌 Integration Requirements

### Odoo ERP Integration

- **Orders**: Sync confirmed orders to Odoo Sales
- **Inventory**: Pull stock updates from Odoo to Firestore
- **Accounting**: Push payment data to Odoo financial modules
- **Customers**: Sync customer profiles and tier information
- **Deliveries**: Update delivery status and costs

### External Services

- **Payment Gateways**: Stripe, PayPal, local payment providers
- **SMS/Email**: Notifications for order updates and promotions
- **Push Notifications**: Mobile app integration for real-time updates
- **Analytics**: Google Analytics, custom event tracking

## 🎯 Current Implementation Achievements

### ✅ **Smart Pricing System**
- **Tier-Based Pricing**: Automatic tier detection from Bearer tokens
- **Bulk Optimization**: Efficient pricing calculations for product listings
- **Global Price Lists**: Enhanced control with `is_global` field support
- **Database Integration**: Customer tiers stored in Firestore with BRONZE defaults
- **Performance Optimized**: Cursor-based pagination with 20/100 limits

### ✅ **Enhanced Product Management**
- **Smart Product Listings**: Automatic tier-based pricing integration  
- **Cursor-Based Pagination**: High-performance pagination using Firebase `startAt`
- **Legacy Compatibility**: Backward-compatible endpoints for existing integrations
- **Future-Ready Structure**: Inventory placeholders for future expansion

### ✅ **Advanced Authentication & User Management**
- **Database-Backed Tiers**: User tiers stored and managed in Firestore
- **Silent Token Extraction**: Optional Bearer token authentication
- **Automatic Defaults**: New users get CUSTOMER role and BRONZE tier automatically
- **Enhanced Profiles**: User statistics and tier information included

### ✅ **Development & Management Tools**
- **Admin Price Management**: Complete CRUD operations for pricing rules
- **Development Endpoints**: Database management and token generation tools
- **Error Resilience**: Graceful fallbacks and comprehensive error handling
- **Query Optimization**: Firestore queries optimized to avoid composite indexes

## 📈 Success Metrics

### ✅ **Technical Achievements**

- **✅ Performance**: Product queries optimized with bulk pricing calculations
- **✅ Scalability**: Cursor-based pagination supports large product catalogs
- **✅ Data Consistency**: UTC timezone handling and proper datetime comparisons
- **✅ Error Handling**: Graceful fallbacks for missing data and failed operations
- **✅ Query Efficiency**: Memory-based filtering to avoid composite indexes

### 🔄 **Future Technical Goals**

- **Uptime**: 99.9% availability target
- **Performance**: Product queries < 200ms, checkout < 3s
- **Scalability**: Support 1,000+ concurrent users
- **Caching**: Redis implementation for pricing calculations

### ✅ **Business Foundation Established**

- **✅ Customer Segmentation**: Four-tier system (Bronze, Silver, Gold, Platinum)
- **✅ Pricing Flexibility**: Dynamic pricing based on customer tiers
- **✅ Admin Control**: Complete price list management system
- **✅ User Experience**: Seamless tier-based pricing without authentication friction

### 🔄 **Future Business Goals**

- **Conversion Rate**: Order completion percentage tracking
- **Customer Retention**: Repeat purchase rate by tier analysis
- **Promotion Effectiveness**: Usage rates and ROI measurement
- **Tier Progression**: Automatic tier upgrades based on customer behavior

## 🚀 **Implementation Status Summary**

The Celeste API has successfully implemented **Phase 1 and Phase 2** of the comprehensive e-commerce platform requirements:

- **✅ Core Enhancement**: Products, Users, Orders with enhanced features
- **✅ Advanced Pricing**: Complete tier-based pricing system with smart calculations
- **✅ Performance Optimization**: Efficient querying and bulk processing
- **✅ Admin Management**: Full CRUD operations for pricing rules
- **✅ Developer Tools**: Testing and development utilities

The platform now provides a solid foundation for **Phase 3** real-time features and advanced e-commerce capabilities while maintaining backward compatibility and ensuring scalable growth.
