# Cloud Run Jobs Commands

This document contains commands for creating and executing Cloud Run jobs for database operations and administrative tasks.

## Database Initialization Job

### Create the Job
```bash
gcloud run jobs create db-init-job \
  --image gcr.io/celeste-470811/celeste-api:latest \
  --command python \
  --args scripts/db/db_init.py \
  --set-env-vars DATABASE_URL="postgresql+asyncpg://test:asdASD123-@/celeste?host=/cloudsql/celeste-470811:asia-south1:sql-primary" \
  --set-cloudsql-instances celeste-470811:asia-south1:sql-primary
```

### Execute the Job
```bash
# Normal initialization (create tables only)
gcloud run jobs execute db-init-job \
  --args scripts/db/db_init.py

# Drop and recreate all tables
gcloud run jobs execute db-init-job \
  --args scripts/db/db_init.py,--drop
```

## User Promotion Job

### Create the Job
```bash
gcloud run jobs create promote-user-job \
  --image gcr.io/celeste-470811/celeste-api:latest \
  --command python \
  --args scripts/promote_user.py \
  --set-env-vars DATABASE_URL="postgresql+asyncpg://test:asdASD123-@/celeste?host=/cloudsql/celeste-470811:asia-south1:sql-primary" \
  --set-cloudsql-instances celeste-470811:asia-south1:sql-primary
```

### Execute the Job
```bash
# Replace TZKU3C493fY2JH9Ftnsdpz5occN2 with the actual user UID
gcloud run jobs execute promote-user-job \
  --args scripts/promote_user.py,TZKU3C493fY2JH9Ftnsdpz5occN2
```

## Product Vectorization Job

### Create the Job
```bash
gcloud run jobs create vectorize-products-job \
  --image gcr.io/celeste-470811/celeste-api:latest \
  --command python \
  --args scripts/db/vectorize_products.py \
  --set-env-vars DATABASE_URL="postgresql+asyncpg://test:asdASD123-@/celeste?host=/cloudsql/celeste-470811:asia-south1:sql-primary" \
  --set-cloudsql-instances celeste-470811:asia-south1:sql-primary \
  --memory 2Gi \
  --cpu 2 \
  --task-timeout 2h
```

### Execute the Job
```bash
# Vectorize all products (optimized for low memory)
gcloud run jobs execute vectorize-products-job \
  --args scripts/db/vectorize_products.py

# Vectorize with custom batch size (if more memory available)
gcloud run jobs execute vectorize-products-job \
  --args scripts/db/vectorize_products.py,--batch-size,16

# Re-vectorize all products (force update)
gcloud run jobs execute vectorize-products-job \
  --args scripts/db/vectorize_products.py,--force

# Vectorize a specific product
gcloud run jobs execute vectorize-products-job \
  --args scripts/db/vectorize_products.py,--product-id,123

# Vectorize with smaller batch (if memory issues)
gcloud run jobs execute vectorize-products-job \
  --args scripts/db/vectorize_products.py,--batch-size,4
```

### Notes
- **Memory**: 2GB recommended for faster processing. Use 1GB with `--batch-size 4` if needed
- **Duration**: ~30-60 seconds per 100 products with batch size 8
- **First Run**: Downloads sentence-transformers model (~400MB) from container cache
- **Run After**: Product imports, bulk product updates, or when search returns no results

## Search Index Optimization Job

### Create the Job
```bash
gcloud run jobs create optimize-search-index-job \
  --image gcr.io/celeste-470811/celeste-api:latest \
  --command python \
  --args scripts/db/optimize_search_index.py \
  --set-env-vars DATABASE_URL="postgresql+asyncpg://test:asdASD123-@/celeste?host=/cloudsql/celeste-470811:asia-south1:sql-primary" \
  --set-cloudsql-instances celeste-470811:asia-south1:sql-primary \
  --memory 1Gi \
  --task-timeout 5m
```

### Execute the Job
```bash
# Optimize with auto-calculated optimal value (recommended)
gcloud run jobs execute optimize-search-index-job \
  --args scripts/db/optimize_search_index.py

# Preview optimization without applying (dry run)
gcloud run jobs execute optimize-search-index-job \
  --args scripts/db/optimize_search_index.py,--dry-run

# Force specific lists value (advanced)
gcloud run jobs execute optimize-search-index-job \
  --args scripts/db/optimize_search_index.py,--lists,200
```

### Notes
- **Duration**: 30-60 seconds (rebuilds pgvector IVFFlat index)
- **Performance Impact**: Temporary search slowdown during rebuild (~30s)
- **Run After**: Initial vectorization, adding 20%+ more products, or monthly maintenance
- **Expected Improvement**: 2-5x faster search queries (30-80% improvement)
- **Formula**: Calculates optimal `lists` parameter as sqrt(product_count)

## Job Management Commands

### List Jobs
```bash
gcloud run jobs list
```

### Describe a Job
```bash
gcloud run jobs describe JOB_NAME
```

### Delete a Job
```bash
gcloud run jobs delete JOB_NAME
```

### View Job Execution Logs
```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=JOB_NAME" --limit 50
```

## Notes

- **Environment Variables**: Jobs automatically inherit Cloud Run environment variables including `DEPLOYMENT` (defaults to "cloud")
- **Authentication**: Jobs use Application Default Credentials (ADC) in Cloud Run environment
- **Database Connection**: Uses Cloud SQL Proxy connection via `--set-cloudsql-instances`
- **Image**: Make sure to update the image tag if using a specific version instead of `:latest`
- **Timeouts**: Cloud Run jobs have a default timeout of 1 hour, which can be increased if needed

## Troubleshooting

### View Recent Job Executions
```bash
gcloud run jobs executions list --job=JOB_NAME
```

### Get Execution Details
```bash
gcloud run jobs executions describe EXECUTION_NAME --job=JOB_NAME
```

### Common Issues
1. **SQLAlchemy Relationship Errors**: Ensure all database models are imported in the script
2. **Authentication Errors**: Verify the job has proper IAM permissions for Firebase and Cloud SQL
3. **Database Connection**: Check Cloud SQL instance name and database URL format
4. **Vectorization Memory Errors**: Reduce batch size with `--batch-size 4` or increase job memory to 2Gi
5. **HuggingFace Rate Limiting**: Model should load from container cache (check Dockerfile pre-download step)
6. **Index Optimization Timeout**: Increase task-timeout if optimizing very large datasets (>100k products)
7. **Search Returns No Results**: Run vectorization job first to create embeddings

## Recommended Workflows

### Initial Search Setup (First Time)
1. Deploy application with search tables (migrations)
2. Create and run `vectorize-products-job` (vectorize all products)
3. Create and run `optimize-search-index-job` (optimize for current product count)
4. Test search: `GET /products/search?q=milk&mode=full`

### Adding New Products (Bulk Import)
1. Import products to database
2. Run `vectorize-products-job` (vectorize new products only or use `--force` for all)
3. If added 20%+ more products, run `optimize-search-index-job`
4. Verify search includes new products

### Monthly Maintenance
1. Run `optimize-search-index-job` to maintain optimal performance
2. Check search logs for any performance degradation
3. Consider re-vectorizing if product descriptions changed significantly

### Performance Issues
1. Check search response times in Cloud Run logs
2. Run `optimize-search-index-job --dry-run` to preview optimization
3. Apply optimization if recommended lists value differs
4. Monitor improvement in subsequent searches