# Deploying to Google Cloud Run

This document provides instructions on how to deploy the Celeste API to Google Cloud Run.

## Prerequisites

1.  **Google Cloud SDK:** Ensure you have the `gcloud` CLI installed and authenticated.
    *   Install the SDK [here](https://cloud.google.com/sdk/docs/install).
    *   Authenticate your account: `gcloud auth login`
    *   Set your project configuration: `gcloud config set project [YOUR_PROJECT_ID]`

2.  **Required Files:** Make sure the `Dockerfile` and `cloudbuild.yaml` files are present in the root of the project.

## Deployment Steps

The deployment process is automated using Google Cloud Build.

1.  **Review Configuration (Optional):**
    The `cloudbuild.yaml` file is pre-configured with default values. You can open this file to change the service name or region:
    ```yaml
    substitutions:
      _SERVICE_NAME: 'celeste-api'
      _REGION: 'us-central1' # Change to your desired region
    ```

2.  **Submit the Build:**
    Run the following command from the root directory of the project:
    ```bash
    gcloud builds submit --config cloudbuild.yaml
    ```

This command will:
*   Upload your code to Google Cloud Build.
*   Build the Docker container image based on the `Dockerfile`.
*   Push the container image to Google Container Registry (GCR).
*   Deploy the image to Google Cloud Run with the specified service name and region.

## Local Development

Due to system differences, the command to run the server locally is different from the one used in the Docker container.

*   **For local development on Windows or macOS**, use `uvicorn` for live reloading:
    ```bash
    uvicorn main:app --reload
    ```

*   The **Docker container** uses `gunicorn` for production, as defined in the `Dockerfile`. This is handled automatically by Cloud Run and does not require any action from you.
