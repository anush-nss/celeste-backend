# Database Operations Analysis: Firestore vs Cloud SQL PostgreSQL

## Executive Summary

This document provides a detailed operational analysis of Celeste's e-commerce platform with **6,000 orders per day**, focusing on database operations, infrastructure requirements, and technical specifications.

---

## Current Platform Analysis

### Architecture Overview
- **FastAPI-based e-commerce platform** with Firebase/Firestore backend
- **Domain-driven architecture**: Products, Users, Orders, Pricing, Categories, Inventory, Stores
- **Smart pricing system** with tier-based calculations
- **High-concurrency requirements**: 100,000+ concurrent customers planned

### Database Operations Profile

#### Core Collections in Use:
- `products` (✅ Implemented with smart pricing)
- `users` (✅ Enhanced with customer tiers) 
- `orders` (✅ Foundation implemented)
- `categories` (✅ Full CRUD)
- `price_lists` & `price_list_lines` (✅ Advanced pricing)
- `customer_tiers` (✅ Logic implemented)
- `inventory`, `stores` (🔄 Planned)

---

## Detailed Operations Analysis (6,000 orders/day)

### Customer-Facing Operations

#### Product Catalog & Search Operations:
```
Product Listings (GET /products):
- Daily calls: 75,000 requests
- Firestore reads per request: 20-100 documents (pagination)
- Total daily reads: 1,500,000 - 7,500,000
- Peak load: 10x normal (150x during flash sales)

Individual Product Views (GET /products/{id}):
- Daily calls: 45,000 requests  
- Firestore reads per request: 1 product + 3-5 price calculations
- Total daily reads: 180,000 - 225,000
- Cache hit rate: ~60% (reduces actual DB hits)

Category Browsing (GET /categories):
- Daily calls: 25,000 requests
- Firestore reads per request: 10-50 categories
- Total daily reads: 250,000 - 1,250,000
- Hierarchical queries increase complexity

Smart Pricing Calculations:
- Triggered on: Every product view, cart operations, checkout
- Daily calculations: 120,000 pricing operations
- Firestore reads per calculation: 2-8 (price_lists + price_list_lines)
- Total daily reads: 240,000 - 960,000
- Bulk pricing optimization reduces individual calls
```

#### User Management Operations:
```
Authentication & Profile (GET /users/me):
- Daily calls: 180,000 requests (users checking profile)
- Firestore reads per request: 1 user document
- Total daily reads: 180,000

Cart Operations (PUT /users/me/cart):
- Daily calls: 85,000 requests (add/remove/update cart)
- Firestore writes per request: 1 user document update
- Total daily writes: 85,000

Wishlist Operations (PUT /users/me/wishlist):
- Daily calls: 15,000 requests
- Firestore writes per request: 1 user document update
- Total daily writes: 15,000
```

### Order Processing Operations

#### Order Lifecycle:
```
Order Creation (POST /orders):
- Daily orders: 6,000
- Firestore operations per order:
  * 1 write (order document)
  * 1 write (user stats update) 
  * 2-5 writes (inventory adjustments per item)
  * 1-2 reads (user validation, pricing verification)
- Total per order: 5-9 operations
- Daily totals: 30,000-54,000 operations (mixed read/write)

Order Status Updates:
- Status changes per order: ~3 (processing, shipped, delivered)
- Daily status updates: 18,000 writes
- Admin order queries: 2,000 reads/day

Order History Queries (GET /orders):
- Daily requests: 35,000
- Firestore reads per request: 1-20 orders (pagination)
- Total daily reads: 35,000 - 700,000
- User-specific filtering with indexes
```

### Administrative Operations

#### Pricing Management:
```
Price List Updates (Admin):
- Daily price list changes: 150 writes
- Price list line updates: 800 writes  
- Price recalculation triggers: Affects 10,000+ product queries

Product Management:
- Product updates: 500 writes/day
- New products: 50 writes/day
- Bulk product imports: 2-3 operations/week (500-1000 writes each)

Inventory Management:
- Stock level updates: 25,000 writes/day
- Low stock alerts: 500 reads/day
- Bulk inventory sync: 2x daily (5,000 writes each)
```

### Analytics & Reporting Queries

#### Business Intelligence Operations:
```
Daily Reports:
- Order summary queries: 50 complex aggregations/day
- Sales analytics: 100 aggregation queries/day  
- Customer analytics: 75 aggregation queries/day
- Inventory reports: 25 aggregation queries/day

Real-time Dashboards:
- Live order tracking: 500 reads/minute during business hours
- Inventory monitoring: 100 reads/minute
- Customer activity: 200 reads/minute
```

---

## Total Daily Operations Summary

### Firestore Operations (Detailed Breakdown):

```
READS (Document Reads):
├── Product Catalog: 3,000,000 - 9,000,000 (varies by traffic)
├── Pricing Calculations: 240,000 - 960,000
├── User Profiles: 180,000
├── Order Queries: 35,000 - 700,000  
├── Category Browsing: 250,000 - 1,250,000
├── Admin Queries: 5,000
├── Analytics: 15,000
└── Cache Misses: ~40% of above (2,100,000 actual DB reads)

ESTIMATED DAILY READS: 8,000,000 - 15,000,000
ACTUAL DAILY READS (with caching): 3,200,000 - 6,000,000

WRITES (Document Writes):
├── Orders: 30,000
├── Order Status Updates: 18,000
├── Cart Operations: 85,000
├── Wishlist Updates: 15,000
├── User Tier Updates: 2,500
├── Inventory Updates: 35,000
├── Product Updates: 550
├── Pricing Updates: 950
└── Admin Operations: 1,200

TOTAL DAILY WRITES: 188,200

DELETES (Document Deletes):
├── Expired Cart Items: 5,000
├── Old Session Data: 2,000
├── Test Data Cleanup: 500
└── Promotional Cleanup: 200

TOTAL DAILY DELETES: 7,700
```

### Index Operations:
```
Composite Index Reads (Charged Separately):
├── Product filtering (category + price): 500,000 index entries/day
├── Order filtering (user + date): 100,000 index entries/day  
├── User queries (tier + status): 50,000 index entries/day
├── Analytics aggregations: 200,000 index entries/day

TOTAL INDEX ENTRIES READ: 850,000/day
BILLABLE INDEX READS: 850 (per 1000 entries)
```

### Storage Requirements:
```
Document Storage:
├── Products: ~15 GiB (50,000 products with images metadata)
├── Orders: ~25 GiB (order history, growing 500 MB/month)
├── Users: ~8 GiB (user profiles, cart, wishlist data)  
├── Price Lists: ~2 GiB (pricing rules and calculations)
├── Categories: ~1 GiB (category hierarchy and metadata)
├── Analytics Data: ~5 GiB (aggregated reports and metrics)
└── Indexes Overhead: ~20 GiB (composite indexes for queries)

TOTAL STORAGE: ~76 GiB (current)
MONTHLY GROWTH: ~2 GiB (primarily orders and analytics)
PROJECTED YEAR-END: ~100 GiB
```

---

## Cloud SQL PostgreSQL Requirements

### Infrastructure Configuration

#### Database Server Specifications:
```
COMPUTE REQUIREMENTS:
├── vCPUs: 8-12 cores
│   ├── Base load: 4 cores (handles 3,200,000 reads + 188,200 writes daily)  
│   ├── Peak capacity: 8-12 cores (10x traffic spikes)
│   ├── Concurrent connections: 200-500 active
│   └── Query processing: Complex JOIN operations for analytics
│
├── Memory: 32-64 GiB RAM
│   ├── PostgreSQL shared_buffers: 8-16 GiB (25% of RAM)
│   ├── Effective cache: 16-32 GiB (50% of RAM)  
│   ├── Connection buffers: 2-4 GiB
│   └── Working memory: 8-16 GiB for analytics queries
│
└── Storage: 500 GiB - 1 TiB SSD
    ├── Database size: 100 GiB (current data)
    ├── Index space: 50-80 GiB (optimized B-tree indexes)
    ├── WAL logs: 20-30 GiB (Write-Ahead Logging)
    ├── Backups: 150-200 GiB (3x daily backups)
    └── Growth buffer: 200+ GiB (12-month projection)
```

#### Performance Configuration:
```
POSTGRESQL SETTINGS:
├── max_connections: 500
├── shared_buffers: 16GB
├── effective_cache_size: 48GB  
├── work_mem: 256MB
├── maintenance_work_mem: 2GB
├── checkpoint_completion_target: 0.9
├── wal_buffers: 64MB
├── random_page_cost: 1.1 (SSD optimized)
└── effective_io_concurrency: 200

CONNECTION POOLING (PgBouncer):
├── Pool size: 100-150 connections
├── Max client connections: 1000
├── Pool mode: Transaction
└── Memory per connection: ~25MB
```

### Database Schema Design

#### Optimized Table Structure:
```sql
-- Primary Tables (replacing Firestore collections)
Products (50K rows, ~300MB)
├── Indexes: category_id, price_range, search_vector (GIN)
├── Daily operations: 3M reads, 500 writes
└── Partitioning: By category for large-scale queries

Users (100K rows, ~150MB)  
├── Indexes: email, phone, customer_tier
├── Daily operations: 180K reads, 100K writes
└── JSONB cart/wishlist for flexibility

Orders (2M+ rows, ~2GB, growing 500MB/month)
├── Indexes: user_id + created_at, status + created_at
├── Daily operations: 735K reads, 30K writes  
├── Partitioning: By date (monthly partitions)
└── Archiving: Orders >2 years to separate table

Price_Lists & Price_List_Lines (10K rows, ~50MB)
├── Indexes: priority, valid_date_range, product/category refs
├── Daily operations: 960K reads, 950 writes
└── Materialized views for pricing calculations

Analytics Tables (100K+ rows, ~500MB)
├── Daily aggregations: order_stats, product_performance  
├── Partitioning: By date for efficient queries
├── Indexes: date ranges, key metrics
└── Background refresh: Every 15 minutes
```

#### Query Performance Expectations:
```
READ OPERATIONS:
├── Product listings: 5-25ms (with proper indexes)
├── Single product: 1-3ms (primary key lookup)
├── User profile: 1-2ms (indexed by user_id)  
├── Order history: 10-50ms (partitioned by date)
├── Pricing calculations: 5-15ms (materialized views)
└── Analytics queries: 100-500ms (complex aggregations)

WRITE OPERATIONS:
├── Order creation: 5-10ms (single transaction)
├── Cart updates: 2-5ms (JSONB update)
├── Inventory updates: 3-8ms (atomic operations)
├── Bulk operations: 50-200ms (batch processing)
└── Analytics updates: 100-300ms (materialized view refresh)

CONCURRENT PERFORMANCE:
├── 100 concurrent reads: <50ms p95
├── 50 concurrent writes: <100ms p95  
├── Mixed workload: 200 connections sustained
└── Peak traffic handling: 500 req/sec
```

### High Availability & Backup Strategy

#### Production Configuration:
```
HIGH AVAILABILITY:
├── Master-Replica Setup: 1 primary + 2 read replicas
├── Automatic failover: <30 seconds downtime
├── Read traffic distribution: 70% replica, 30% primary
├── Cross-zone replication: Multi-AZ deployment
└── Connection failover: Application-level retry logic

BACKUP STRATEGY:
├── Continuous WAL archiving: Point-in-time recovery
├── Daily full backups: Retained for 30 days
├── Weekly snapshots: Retained for 1 year  
├── Backup verification: Automated restore testing
├── Recovery Time Objective (RTO): <4 hours
└── Recovery Point Objective (RPO): <15 minutes

MONITORING REQUIREMENTS:
├── Query performance: Slow query log analysis
├── Connection monitoring: Pool utilization tracking
├── Disk I/O monitoring: IOPS and throughput metrics
├── Memory usage: Buffer hit ratios and cache efficiency  
├── Replication lag: Real-time replica synchronization
└── Custom metrics: Business KPIs and error rates
```

### Migration Considerations

#### Data Migration Strategy:
```
PHASE 1 - Schema Design (2-3 weeks):
├── Document → Relational mapping
├── Index strategy optimization  
├── Partitioning scheme design
├── Performance testing with sample data
└── Query optimization and tuning

PHASE 2 - Parallel Development (6-8 weeks):
├── Dual-write implementation (Firestore + PostgreSQL)
├── Data consistency validation
├── Performance benchmark comparison
├── Application layer abstraction
└── Comprehensive testing framework

PHASE 3 - Migration Execution (2-3 weeks):
├── Historical data migration (75 GiB transfer)
├── Real-time synchronization cutover
├── DNS/traffic switching
├── Monitoring and validation
└── Rollback preparation

TOTAL ESTIMATED EFFORT: 12-16 weeks
```

---

## Infrastructure Requirements Summary

### Firestore (Current):
- **Zero infrastructure management**
- **Auto-scaling**: Handles traffic spikes automatically  
- **Global distribution**: Multi-region by default
- **Operations**: 3.2-6M reads, 188K writes, 7.7K deletes daily
- **Storage**: 76 GiB current, 2 GiB monthly growth
- **Index overhead**: Managed automatically

### Cloud SQL PostgreSQL:
- **Server**: 8-12 vCPU, 32-64 GiB RAM, 500 GiB-1 TiB SSD
- **Connections**: 500 max, 100-150 pooled  
- **Performance**: <50ms read, <100ms write (p95)
- **Storage**: 100 GiB data + 400 GiB overhead/backups
- **HA Setup**: 1 primary + 2 replicas (cross-zone)
- **Management overhead**: DBA required for optimization

**Document Version**: 1.1  
**Last Updated**: September 2025  
**Focus**: Technical Operations & Infrastructure Requirements