# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download sentence-transformers model to avoid runtime downloads
# This prevents HuggingFace rate limiting issues
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy the rest of the application's source code from the current directory to the working directory
COPY . .

# Command to run the application
# Gunicorn will listen on the port specified by the PORT environment variable, which is required by Cloud Run.
# We use 8080 as a default port.
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8080"]
