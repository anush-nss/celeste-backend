# Deploying to Google Cloud Run

This document provides instructions on how to deploy the Celeste API to Google Cloud Run.

## Prerequisites

1.  **Google Cloud SDK:** Ensure you have the `gcloud` CLI installed and authenticated.

    - Install the SDK [here](https://cloud.google.com/sdk/docs/install).
    - Authenticate your account: `gcloud auth login`
    - Set your project configuration: `gcloud config set project [YOUR_PROJECT_ID]`

2.  **Required Files:** Make sure the `Dockerfile` and `cloudbuild.yaml` files are present in the root of the project.

## Deployment Steps

The deployment process is automated using Google Cloud Build.

1.  **Sync requirements.txt:**
    Before submitting the build, ensure `requirements.txt` is up-to-date:

    ```bash
    uv export --format requirements-txt > requirements.txt
    ```

    This exports dependencies from `uv.lock` to `requirements.txt` for cloud deployment compatibility.

2.  **Review Configuration (Optional):**
    The `cloudbuild.yaml` file is pre-configured with default values. You can open this file to change the service name or region:

    ```yaml
    substitutions:
      _SERVICE_NAME: "celeste-api"
      _REGION: "us-central1" # Change to your desired region
    ```

3.  **Submit the Build:**
    Run the following command from the root directory of the project:

    ```bash
    gcloud builds submit --config cloudbuild.yaml
    ```

    **Alternative build commands:**

    - For a unique timestamp tag: `gcloud builds submit --config cloudbuild.yaml --substitutions=_TAG=$(date +%Y%m%d-%H%M%S)`
    - To override the default tag: `gcloud builds submit --config cloudbuild.yaml --substitutions=_TAG=v1.0.0`

This command will:

- Upload your code to Google Cloud Build.
- Build the Docker container image based on the `Dockerfile`.
- Push the container image to Google Container Registry (GCR).
- Deploy the image to Google Cloud Run with the specified service name and region.

## Troubleshooting

### Common Issues

1.  **Invalid image name error:**

    ```
    ERROR: invalid image name "gcr.io/project-id/service-name:": could not parse reference
    ```

    This occurs when the image tag is empty. The `cloudbuild.yaml` is configured with a default `_TAG: 'latest'` substitution to prevent this issue.

2.  **Files not included in upload:**
    Some files may be excluded due to `.gcloudignore`. Check the gcloud log file mentioned in the output to see which files were excluded.

3.  **Permission errors:**
    Ensure your Google Cloud account has the necessary permissions:
    - Cloud Build Editor
    - Cloud Run Admin
    - Storage Admin (for Container Registry)

### Build Configuration

The `cloudbuild.yaml` uses the following substitutions:

```yaml
substitutions:
  _SERVICE_NAME: "celeste-api"
  _REGION: "us-central1"
  _TAG: "latest" # Default tag when COMMIT_SHA is not available
```

The build process uses `${_TAG}` for consistent image tagging across all build steps.

## Local Development

Due to system differences, the command to run the server locally is different from the one used in the Docker container.

- **For local development on Windows or macOS**, use `uvicorn` for live reloading:

  ```bash
  uv run uvicorn main:app --reload
  ```

- The **Docker container** uses `gunicorn` for production, as defined in the `Dockerfile`. This is handled automatically by Cloud Run and does not require any action from you.
