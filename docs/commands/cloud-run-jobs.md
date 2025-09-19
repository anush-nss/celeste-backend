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
  --args scripts/promote_user.py
```

### Execute the Job
```bash
# Replace TZKU3C493fY2JH9Ftnsdpz5occN2 with the actual user UID
gcloud run jobs execute promote-user-job \
  --args scripts/promote_user.py,TZKU3C493fY2JH9Ftnsdpz5occN2
```

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