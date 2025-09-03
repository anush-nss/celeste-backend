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

#### 1. Products Collection

```
products/{sku}
{
  name: string,
  description: string,
  brand: object,              // Reference to brand document
  price: number,
  images: string[],
  category_ids: string[],
  dietary_tags: string[],     // ["vegetarian", "gluten-free", "halal"]

  // Availability per fulfillment center (not exact stock)
  availability: {
    FC001: "in_stock",        // "in_stock", "low_stock", "out_of_stock"
    FC002: "out_of_stock"
  },

  active: boolean,

  // Metadata
  created_at: timestamp,
  updated_at: timestamp,
  last_sync: timestamp        // Last Odoo sync
}
```

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

#### 3. Categories Collection

```
categories/{categoryId}
{
  name: string,
  slug: string,
  parent_id: string | null,   // For hierarchical categories
  image_url: string,
  display_order: number,
  active: boolean
}
```

#### 4. Brands Collection

```
brands/{brandId}
{
  name: string,
  image_url: string,
  description: string,
  active: boolean
}
```

#### 5. Price Lists Collection

```
price_lists/{priceListId}
{
  name: string,               // "Regular", "VIP", "Gold Member"
  priority: number,           // Order of application
  active: boolean,
  valid_from: timestamp,
  valid_until: timestamp | null
}
```

#### 6. Price List Lines Collection

```
price_list_lines/{priceListLinesId}
{
  price_list_id: object,      // Reference to price_list
  type: string,               // "product", "category", "all"
  product_id: object | null,  // If type="product"
  category_id: object | null, // If type="category"
  discount_type: string,      // "flat", "percentage"
  amount: number,
  min_product_qty: number,
  max_product_qty: number | null
}
```

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

#### 10. Enhanced Users Collection

```
users/{userId}
{
  // Profile data (existing + enhanced)
  name: string,
  phone: string,
  email: string,

  // Enhanced pricing features
  price_list_id: string,
  customer_tier: string,      // "bronze", "silver", "gold", "platinum"

  // Customer statistics
  total_orders: number,
  lifetime_value: number,

  // Existing fields
  address: string,
  role: UserRole,
  createdAt: timestamp,
  wishlist: string[],
  cart: CartItemSchema[],

  // New metadata
  last_order_at: timestamp,

  // Subcollections
  addresses: [{             // Enhanced address management
    addressId: string,
    label: string,
    formatted_address: string,
    location: geopoint,
    instructions: string,
    default: boolean
  }]
}
```

#### 11. Enhanced Orders Collection

```
orders/{orderId}
{
  order_number: string,       // Human-readable
  user_id: string,
  status: string,            // "pending", "confirmed", "preparing", "dispatched", "delivered"

  items: [{
    sku: string,
    name: string,
    quantity: number,
    price: number,

    // Enhanced pricing breakdown
    original_price: number,
    discount_percent: number,
    discount_amount: number,
    tax_rate: number,
    tax_amount: number,
    subtotal: number,        // (price * qty) - discount + tax

    // Bundle support
    is_bundle: boolean,
    bundle_id: string | null,

    // Customization support
    customizations: {
      [groupId]: string[]    // Selected option SKUs
    },
    customization_price: number
  }],

  // Applied promotions tracking
  applied_promotions: [{
    promo_id: string,
    promo_name: string,
    discount_amount: number
  }],

  // Enhanced delivery information
  delivery: {
    address: object,
    fc_id: string,           // Fulfillment center
    type: string,            // "delivery", "pickup"
    slot: string,
    rider_id: string | null,

    // Tracking information
    tracking_id: string,
    eta: timestamp
  },

  // Financial breakdown
  totals: {
    items_total: number,
    delivery_fee: number,
    total_discount: number,
    total_tax: number,
    grand_total: number
  },

  // Payment information
  payment: {
    method: string,          // "card", "wallet", "cod"
    status: string,          // "pending", "paid", "failed"
    transaction_id: string
  },

  // Enhanced timestamps
  timestamps: {
    created: timestamp,
    confirmed: timestamp,
    preparing: timestamp,
    dispatched: timestamp,
    delivered: timestamp,
    cancelled: timestamp | null
  },

  // Metadata
  source: string,            // "app", "web", "uber_eats", "pickme"
  notes: string,

  // Existing fields to maintain
  deliveryAddress: string,
  totalAmount: number,
  createdAt: timestamp
}
```

#### 12. Customer Tiers Collection

```
customer_tiers/{tierId}
{
  name: string,               // "Gold"
  level: number,              // 3

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
  color: string              // "#FFD700"
}
```

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

## 🔄 Migration Strategy from Existing Structure

### Phase 1: Core Enhancement (Priority 1)

1. **Enhance existing collections**:

   - Extend `products` collection with availability, dietary_tags, brand references
   - Extend `users` collection with price_list_id, customer_tier, statistics
   - Extend `orders` collection with detailed pricing breakdown and delivery tracking

2. **Add new core collections**:
   - `brands` - Extract brand information from products
   - `stock` - Detailed inventory management per fulfillment center
   - `customer_tiers` - Loyalty tier management

### Phase 2: Advanced Features (Priority 2)

1. **Add pricing and promotions**:

   - `price_lists` and `price_list_lines` for advanced pricing
   - `promotions` for marketing campaigns
   - `promotion_usage` for usage tracking

2. **Add product enhancements**:
   - `bundles` for product bundles
   - `product_options` for customizable products

### Phase 3: Real-time Features (Priority 3)

1. **Implement delivery tracking**:
   - `active_deliveries` in Realtime Database
   - `rider_presence` for rider management

## 🏗️ Updated Architecture Integration

### Existing Components Integration

- **FastAPI routers** will be extended to support new collections
- **Pydantic models** will be enhanced with new fields and validation
- **Service layer** will implement new business logic for pricing, promotions, and tiers
- **Firebase integration** remains the same with additional collections

### New Components Required

- **Pricing Service**: Handle price lists, tiers, and promotional calculations
- **Promotion Service**: Manage promotion rules and application logic
- **Stock Service**: Manage inventory across fulfillment centers
- **Delivery Service**: Handle real-time tracking and rider management
- **Tier Service**: Manage customer loyalty tiers and benefits

## 📊 Functional Requirements Implementation

### 2.1 Enhanced Product & Catalog Management

- **Existing**: Basic product CRUD with categories
- **Enhanced**: Brand associations, dietary tags, availability per FC, stock management
- **New APIs**:
  - `GET /products?dietary_tags=vegetarian&fc=FC001`
  - `GET /brands/{brandId}/products`
  - `PUT /products/{sku}/availability`

### 2.2 Advanced Categories & Brands

- **Existing**: Flat category structure
- **Enhanced**: Hierarchical categories with parent-child relationships
- **New APIs**:
  - `GET /categories/{categoryId}/children`
  - `GET /categories/tree`
  - `POST /brands`

### 2.3 Pricing & Promotions System

- **New Feature**: Complete pricing and promotion engine
- **APIs**:
  - `POST /price-lists` (Admin)
  - `GET /promotions/applicable?cart_value=100`
  - `POST /promotions/{promoId}/apply`

### 2.4 Enhanced User Management

- **Existing**: Basic user profiles with cart/wishlist
- **Enhanced**: Customer tiers, price lists, multiple addresses
- **New APIs**:
  - `GET /users/me/tier`
  - `POST /users/me/addresses`
  - `GET /users/me/tier-progress`

### 2.5 Advanced Order Processing

- **Existing**: Basic order creation and status
- **Enhanced**: Detailed pricing breakdown, promotion application, delivery tracking
- **New APIs**:
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

## 📈 Success Metrics

### Technical Metrics

- **Uptime**: 99.9% availability
- **Performance**: Product queries < 200ms, checkout < 3s
- **Scalability**: Support 1,000+ concurrent users
- **Data Consistency**: Zero data loss, eventual consistency < 1s

### Business Metrics

- **Conversion Rate**: Order completion percentage
- **Customer Retention**: Repeat purchase rate by tier
- **Promotion Effectiveness**: Usage rates and ROI
- **Delivery Satisfaction**: On-time delivery percentage

This comprehensive requirements document serves as the blueprint for transforming the existing Celeste API into a full-featured e-commerce and delivery platform while maintaining backward compatibility and ensuring scalable growth.
