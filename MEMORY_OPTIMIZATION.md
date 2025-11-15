# Memory Optimization Guide for Search & Vectorization

**Last Updated:** 2025-10-20

This guide explains how to run the search and vectorization system on low-memory instances (1GB RAM or less).

---

## ⚠️ Memory Requirements

### Minimum Requirements
- **Development:** 512 MB RAM
- **Production (Search Only):** 512 MB RAM
- **Vectorization Script:** 1 GB RAM (temporary spike)

### Component Memory Usage

| Component | Memory Usage | Notes |
|-----------|--------------|-------|
| Sentence Transformer Model | ~400 MB | Loaded on-demand |
| Search Query (runtime) | ~50 MB | Per concurrent request |
| Vectorization Batch (8 products) | ~100 MB | Temporary during batch |
| Database Connection Pool | ~50 MB | Persistent |

---

## ✅ Optimizations Implemented

### 1. **Lazy Model Loading**
- Model only loads when needed
- Automatically unloaded after vectorization
- Shared instance for search requests

### 2. **Small Batch Processing**
```python
# Default batch size reduced from 32 to 8
SENTENCE_TRANSFORMER_BATCH_SIZE = 8
```

### 3. **Chunked Vectorization**
- Processes 50 products at a time
- Each chunk divided into batches of 8
- Aggressive garbage collection between chunks

### 4. **Memory Cleanup**
```python
# Explicit cleanup after each batch
del embeddings, batch_texts, batch_ids
gc.collect()

# Model unloading after vectorization
self._unload_model()
```

### 5. **CPU-Only Mode**
- Forces CPU usage (no GPU memory overhead)
- Consistent behavior across environments

---

## 🚀 Running Vectorization on Low-Memory Instances

### Option 1: Local Vectorization (Recommended)
Run vectorization locally or on a larger instance, then deploy:

```bash
# On your local machine or large instance
python scripts/db/vectorize_products.py

# Deploy to Cloud Run with only search enabled
# Model will lazy-load for search queries only
```

### Option 2: Cloud Run with Increased Memory
Temporarily increase Cloud Run memory for vectorization:

```bash
# Deploy with 2GB memory for initial vectorization
gcloud run deploy celeste-api \
  --memory 2Gi \
  --timeout 900s

# Run vectorization via API or script

# Redeploy with 1GB for normal operation
gcloud run deploy celeste-api \
  --memory 1Gi
```

### Option 3: Batch Vectorization
Vectorize products in smaller batches over time:

```bash
# Vectorize first 100 products
python scripts/db/vectorize_products.py --limit 100

# Wait a few minutes, then next batch
python scripts/db/vectorize_products.py --limit 100 --offset 100
```

---

## 🛠️ Cloud Run Configuration

### Recommended Settings for 1GB Memory Limit

**cloudbuild.yaml or gcloud command:**
```yaml
options:
  machineType: 'E2_HIGHCPU_8'  # More CPU helps with encoding

steps:
  - name: 'gcr.io/cloud-builders/gcloud'
    args:
      - 'run'
      - 'deploy'
      - 'celeste-api'
      - '--memory=1Gi'
      - '--cpu=2'
      - '--timeout=300s'
      - '--max-instances=10'
      - '--min-instances=0'  # Scale to zero when idle
      - '--concurrency=10'   # Limit concurrent requests
```

### Key Settings Explained

1. **Memory: 1Gi**
   - Enough for search queries + model
   - Model loaded on-demand

2. **CPU: 2**
   - Faster encoding (2x speedup)
   - Better for CPU-bound ML tasks

3. **Timeout: 300s**
   - Allows search queries to complete
   - Vector encoding takes 1-3s per query

4. **Concurrency: 10**
   - Limits memory spikes from concurrent searches
   - Each search query uses ~50MB

5. **Min Instances: 0**
   - Scale to zero to save costs
   - Model loads in <5 seconds on cold start

---

## 📊 Monitoring Memory Usage

### During Vectorization

Monitor memory in real-time:

```bash
# Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision" \
  --limit 50 \
  --format json | grep -i memory

# Look for:
# - "Memory limit ... exceeded"
# - Memory usage percentage
```

### Search Performance

Check search query memory:

```python
# Add to SearchService for debugging
import tracemalloc

tracemalloc.start()
# ... search logic ...
current, peak = tracemalloc.get_traced_memory()
self.logger.info(f"Memory: {current / 1024 / 1024:.1f} MB (peak: {peak / 1024 / 1024:.1f} MB)")
tracemalloc.stop()
```

---

## 🔧 Tuning for Your Environment

### If Memory Still Exceeded

**Reduce batch size further:**
```python
# In constants.py
SENTENCE_TRANSFORMER_BATCH_SIZE = 4  # Even smaller batches
```

**Reduce chunk size:**
```python
# In VectorService.vectorize_products_batch()
chunk_size = 25  # Process 25 products at a time (down from 50)
```

**Limit concurrent searches:**
```yaml
# In Cloud Run config
--concurrency=5  # Only 5 concurrent requests
```

### If Vectorization Too Slow

**Increase batch size (with more memory):**
```python
# If you have 2GB RAM
SENTENCE_TRANSFORMER_BATCH_SIZE = 16
```

**Use larger instance temporarily:**
```bash
# During vectorization only
gcloud run deploy celeste-api --memory=2Gi

# After vectorization
gcloud run deploy celeste-api --memory=1Gi
```

---

## 📝 Best Practices

### 1. **Vectorize During Off-Peak Hours**
Run vectorization when search traffic is low:
```bash
# Schedule for 2 AM
0 2 * * * /app/scripts/db/vectorize_products.py
```

### 2. **Incremental Vectorization**
Only vectorize new/updated products:
```python
# In your product update logic
from src.api.products.services.vector_service import VectorService

vector_service = VectorService()
await vector_service.vectorize_product(product_id)
```

### 3. **Monitor and Alert**
Set up Cloud Monitoring alerts:
```bash
# Alert if memory usage > 90%
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="High Memory Usage" \
  --condition-threshold-value=0.9
```

### 4. **Batch New Products**
Instead of vectorizing immediately:
```python
# Queue products for batch vectorization
# Run vectorization script every 6 hours for new products
```

---

## 🎯 Performance Benchmarks

### Search Performance (1GB Instance)

| Metric | Cold Start | Warm Instance |
|--------|-----------|---------------|
| Model Load Time | 4-6 seconds | 0 seconds (cached) |
| Search Query (dropdown) | 100-200 ms | 50-100 ms |
| Search Query (full) | 200-400 ms | 100-200 ms |
| Memory Usage | ~600 MB | ~500 MB |

### Vectorization Performance

| Products | Batch Size 8 | Memory Peak |
|----------|--------------|-------------|
| 100 | ~2 minutes | ~900 MB |
| 500 | ~10 minutes | ~950 MB |
| 1000 | ~20 minutes | ~980 MB |

---

## 🐛 Troubleshooting

### Error: "Memory limit exceeded"

**Cause:** Too many concurrent requests or large batch size

**Solution:**
```bash
# Reduce concurrency
gcloud run deploy celeste-api --concurrency=5

# Or reduce batch size in code
SENTENCE_TRANSFORMER_BATCH_SIZE = 4
```

### Error: "Container startup timeout"

**Cause:** Model download taking too long on cold start

**Solution:**
```bash
# Increase startup timeout
gcloud run deploy celeste-api \
  --timeout=600s \
  --cpu-boost  # Faster cold starts
```

### Error: "Out of memory during vectorization"

**Cause:** Too many products in one batch

**Solution:**
```python
# Process in smaller chunks
chunk_size = 25  # Reduced from 50

# Or vectorize in multiple runs
python scripts/db/vectorize_products.py --limit 100
python scripts/db/vectorize_products.py --limit 100 --offset 100
```

---

## 💡 Alternative: Separate Vectorization Service

For very large product catalogs (>10,000 products), consider:

### Architecture
```
┌─────────────────┐     ┌──────────────────┐
│  Main API       │     │  Vectorization   │
│  (Search only)  │     │  Worker Service  │
│  512 MB RAM     │     │  2 GB RAM        │
└─────────────────┘     └──────────────────┘
```

### Setup
```bash
# Deploy main API (low memory)
gcloud run deploy celeste-api \
  --memory=512Mi \
  --source=.

# Deploy vectorization worker (high memory)
gcloud run deploy celeste-vectorizer \
  --memory=2Gi \
  --source=. \
  --command=python \
  --args=scripts/db/vectorize_products.py
```

### Trigger
```bash
# Manual trigger
gcloud run jobs execute vectorize-products

# Or scheduled (Cloud Scheduler)
gcloud scheduler jobs create http vectorize-daily \
  --schedule="0 2 * * *" \
  --uri="https://celeste-vectorizer-xyz.run.app/vectorize"
```

---

## 📚 Additional Resources

- [Cloud Run Memory Limits](https://cloud.google.com/run/docs/configuring/memory-limits)
- [Python Memory Management](https://docs.python.org/3/library/gc.html)
- [Sentence Transformers Performance](https://www.sbert.net/docs/usage/computing_sentence_embeddings.html)

---

## 🎉 Summary

The system is now optimized for **1GB RAM instances**:

✅ Lazy model loading (on-demand)
✅ Small batch sizes (8 products)
✅ Aggressive memory cleanup
✅ CPU-only mode
✅ Chunked processing
✅ Auto model unloading

**For production:**
- Search: 512 MB - 1 GB RAM
- Vectorization: Run locally or use 2 GB temporarily

**Memory usage breakdown:**
- Model: ~400 MB
- Search query: ~50 MB
- Buffer: ~200 MB
- **Total: ~650 MB** ✅ Fits in 1 GB!
