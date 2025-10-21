# Future Work & Optimization Roadmap

## Background Task Optimizations

### Current Implementation Gaps

While the API has been optimized for N+1 query elimination and bulk operations, there are several opportunities for background task optimization to improve user experience and system performance.

### 1. Vector Embedding Generation

**Current State:**
- Vector embeddings are generated synchronously during product creation/update
- Uses sentence-transformers model (all-MiniLM-L6-v2)
- Blocks the response until embedding is complete

**Future Improvement:**
```python
# Current (Blocking)
@product_router.post("/")
async def create_product(product_data):
    product = await product_service.create(product_data)
    embedding = generate_embedding(product.name + product.description)  # ❌ Blocks
    await save_embedding(product.id, embedding)
    return product

# Proposed (Background Task)
@product_router.post("/")
async def create_product(product_data, background_tasks: BackgroundTasks):
    product = await product_service.create(product_data)
    background_tasks.add_task(
        generate_and_save_embedding,
        product.id,
        product.name,
        product.description
    )  # ✅ Non-blocking
    return product  # Immediate response
```

**Benefits:**
- Faster API responses (~200-500ms saved per product creation)
- Better user experience
- Decoupled embedding generation from CRUD operations

**Implementation Priority:** High

---

### 2. Order Enrichment Pre-caching

**Current State:**
- Order lists fetch related data on-demand (products, stores, addresses)
- Even with bulk queries, there's latency when users request full details

**Future Improvement:**
```python
# Background task to pre-populate order cache after order confirmation
async def precache_order_details(order_id: int):
    """
    Pre-fetch and cache order details in background.
    Triggered after payment confirmation.
    """
    order = await order_service.get_order_by_id(
        order_id,
        include_products=True,
        include_stores=True,
        include_addresses=True
    )

    # Cache enriched order for fast retrieval
    await cache_service.set(
        f"order:{order_id}:enriched",
        order.model_dump(mode="json"),
        ttl=3600  # 1 hour
    )

# In payment callback handler
background_tasks.add_task(precache_order_details, order.id)
```

**Benefits:**
- Instant order detail pages after payment
- Reduced database load for frequently accessed orders
- Better mobile app performance

**Implementation Priority:** Medium

---

### 3. Bulk Notification System

**Current State:**
- No notification system implemented
- Order status updates not communicated to users

**Future Improvement:**
```python
# Background notification dispatcher
async def dispatch_order_notifications(
    order_id: int,
    event_type: str,  # "confirmed", "shipped", "delivered"
    user_id: str
):
    """
    Send multi-channel notifications in background.
    """
    tasks = [
        send_push_notification(user_id, event_type, order_id),
        send_email_notification(user_id, event_type, order_id),
        update_notification_center(user_id, event_type, order_id),
    ]
    await asyncio.gather(*tasks)

# In order status update
background_tasks.add_task(
    dispatch_order_notifications,
    order.id,
    "shipped",
    order.user_id
)
```

**Benefits:**
- User engagement
- Real-time order tracking
- No performance impact on API responses

**Implementation Priority:** High

---

### 4. Analytics & Metrics Aggregation

**Current State:**
- Product interactions tracked synchronously
- Popularity scores recalculated on each query

**Future Improvement:**
```python
# Batch process product metrics every 5 minutes
@background_scheduler.scheduled_task(interval=300)  # 5 minutes
async def aggregate_product_metrics():
    """
    Background aggregation of product popularity, views, orders.
    """
    # Aggregate last 5 minutes of interactions
    await popularity_service.batch_update_scores(
        time_window_seconds=300
    )

    # Update trending products cache
    await cache_service.set(
        "trending:products",
        await popularity_service.get_trending(limit=100),
        ttl=300
    )

# Individual interaction tracking remains lightweight
async def track_product_view(product_id: int, user_id: str):
    # Just write to queue/log
    await interaction_queue.add({
        "type": "view",
        "product_id": product_id,
        "user_id": user_id,
        "timestamp": datetime.utcnow()
    })
```

**Benefits:**
- Faster product listing endpoints
- More sophisticated analytics without performance impact
- Scalable to high traffic

**Implementation Priority:** Medium

---

### 5. Image Processing Pipeline

**Current State:**
- Product images stored as-is
- No thumbnail generation or optimization

**Future Improvement:**
```python
async def process_product_images(product_id: int, image_urls: List[str]):
    """
    Background image processing:
    - Generate thumbnails (small, medium, large)
    - Optimize for web (compress, format conversion)
    - Upload to CDN
    - Update product with optimized URLs
    """
    optimized_urls = []
    for url in image_urls:
        # Download, process, upload
        thumbnails = await generate_thumbnails(url)
        cdn_urls = await upload_to_cdn(thumbnails)
        optimized_urls.append(cdn_urls)

    await product_service.update_image_urls(product_id, optimized_urls)

# On product creation
background_tasks.add_task(
    process_product_images,
    product.id,
    product.image_urls
)
```

**Benefits:**
- Faster page loads (optimized images)
- Better mobile experience
- CDN distribution

**Implementation Priority:** Low

---

### 6. Inventory Sync with Odoo

**Current State:**
- Odoo sync happens synchronously in some places
- Can block API responses

**Future Improvement:**
```python
# Queue-based Odoo sync
async def sync_inventory_to_odoo(inventory_updates: List[dict]):
    """
    Background sync of inventory changes to Odoo ERP.
    """
    try:
        await odoo_client.bulk_update_inventory(inventory_updates)
    except OdooError as e:
        # Retry logic
        await retry_queue.add(inventory_updates, retry_count=3)

# On inventory adjustment
background_tasks.add_task(
    sync_inventory_to_odoo,
    [{"product_id": 123, "quantity": 50, "store_id": 1}]
)
```

**Benefits:**
- Non-blocking inventory updates
- Retry mechanism for failed syncs
- Better error handling

**Implementation Priority:** High (already partially implemented)

---

## Implementation Strategy

### Phase 1: Critical Background Tasks (Q1 2026)
1. ✅ Odoo order sync (Already implemented)
2. 🔄 Vector embedding generation
3. 🔄 Notification system

### Phase 2: Performance Enhancements (Q2 2026)
4. Order enrichment pre-caching
5. Analytics aggregation
6. Search index updates

### Phase 3: Additional Features (Q3 2026)
7. Image processing pipeline
8. Bulk email campaigns
9. Report generation

---

## Technical Stack Recommendations

### Task Queue Options
1. **Celery** (Recommended)
   - Mature, well-tested
   - Redis/RabbitMQ backend
   - Retry and error handling built-in
   - Monitoring with Flower

2. **ARQ** (Alternative)
   - Async-native (FastAPI friendly)
   - Redis-based
   - Simpler than Celery
   - Good for smaller scale

3. **FastAPI BackgroundTasks** (Current)
   - Simple, no extra dependencies
   - Good for quick, non-critical tasks
   - Limited to single process
   - No retry or monitoring

### Recommendation
Start with **Celery + Redis** for production workloads:
- Proven at scale
- Rich ecosystem
- Distributed task execution
- Comprehensive monitoring

---

## Performance Impact Estimation

| Task | Current Blocking Time | After Background | User Impact |
|------|----------------------|------------------|-------------|
| Product creation with embedding | 800ms | 200ms | ⭐⭐⭐⭐⭐ High |
| Order enrichment | 300ms (cached) | 50ms (pre-cached) | ⭐⭐⭐ Medium |
| Notification sending | N/A | 0ms | ⭐⭐⭐⭐ High |
| Image optimization | N/A | 0ms | ⭐⭐⭐ Medium |
| Analytics updates | 150ms | 20ms | ⭐⭐ Low |

**Total Expected Improvement:**
- API response times: **30-60% faster**
- User perceived performance: **50-80% better**
- System scalability: **3-5x increase in capacity**

---

## Monitoring & Observability

### Task Monitoring Requirements
1. **Task Queue Metrics**
   - Queue depth
   - Processing rate
   - Error rate
   - Retry count

2. **Performance Metrics**
   - Task execution time
   - Success/failure ratio
   - Resource usage (CPU, memory)

3. **Business Metrics**
   - Notification delivery rate
   - Embedding generation lag
   - Cache hit ratio

### Recommended Tools
- **Celery Flower**: Task monitoring UI
- **Prometheus + Grafana**: Metrics and dashboards
- **Sentry**: Error tracking
- **CloudWatch/Stackdriver**: Cloud-native monitoring

---

## Migration Path

### Step 1: Infrastructure Setup
```bash
# Add Celery to dependencies
pip install celery[redis]

# Configure Redis
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

### Step 2: Create Task Module
```python
# src/background_tasks/celery_app.py
from celery import Celery

celery_app = Celery(
    "celeste",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
```

### Step 3: Convert Existing BackgroundTasks
```python
# Before
background_tasks.add_task(send_notification, user_id)

# After
from src.background_tasks.notifications import send_notification_task
send_notification_task.delay(user_id)
```

### Step 4: Deploy Worker
```bash
# Start Celery worker
celery -A src.background_tasks.celery_app worker --loglevel=info

# Start Flower monitoring
celery -A src.background_tasks.celery_app flower
```

---

## Security Considerations

### Task Data
- Sanitize user input before queuing
- Encrypt sensitive data (passwords, payment info)
- Use task signatures for tamper prevention

### Rate Limiting
- Implement per-user task limits
- Prevent notification spam
- Queue depth limits

### Resource Limits
- Task timeout limits (e.g., 5 minutes max)
- Memory limits per task
- Concurrent task limits

---

## Testing Strategy

### Unit Tests
```python
@pytest.mark.asyncio
async def test_embedding_generation_task():
    """Test embedding generation in isolation"""
    result = await generate_and_save_embedding(
        product_id=123,
        name="Test Product",
        description="Test Description"
    )
    assert result["success"] is True
    assert result["embedding_dim"] == 384
```

### Integration Tests
```python
@pytest.mark.asyncio
async def test_order_notification_flow():
    """Test complete notification flow"""
    order = await create_test_order()

    # Trigger notification task
    task = dispatch_order_notifications.delay(
        order.id,
        "confirmed",
        order.user_id
    )

    # Wait for task completion
    result = task.get(timeout=10)

    assert result["email_sent"] is True
    assert result["push_sent"] is True
```

---

## Rollback Plan

If background tasks cause issues:

1. **Feature Flag**: Disable specific task types
2. **Graceful Degradation**: Fall back to synchronous execution
3. **Queue Drain**: Process pending tasks before shutdown
4. **Monitoring Alerts**: Automated rollback on error threshold

---

## Documentation Requirements

### Developer Documentation
- Task registration guide
- Testing guidelines
- Monitoring dashboard access
- Troubleshooting guide

### Operations Documentation
- Worker deployment guide
- Scaling guidelines
- Incident response procedures
- Performance tuning guide

---

## Next Steps

1. **Proof of Concept** (1 week)
   - Set up Celery with Redis
   - Implement vector embedding task
   - Measure performance improvement

2. **Production Rollout** (2 weeks)
   - Deploy workers to staging
   - Load testing
   - Production deployment with feature flags

3. **Iteration** (Ongoing)
   - Monitor metrics
   - Optimize task execution
   - Add new background tasks as needed

---

**Last Updated:** 2025-10-22
**Status:** Planning Phase
**Owner:** Backend Team
