# Local Development Commands

This document provides the necessary commands to set up and run the Celeste E-Commerce API on a local machine.

## Prerequisites

- Python 3.8+
- Firebase Project with Firestore and Authentication enabled
- Firebase Service Account credentials

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd celeste
    ```

2.  **Create and activate virtual environment:**
    ```bash
    python -m venv venv
    
    # Windows
    venv\Scripts\activate
    
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Firebase Setup

1.  **Create Firebase Project:**
    - Go to [Firebase Console](https://console.firebase.google.com/)
    - Create a new project or use an existing one

2.  **Enable Required Services:**
    - **Authentication**: Enable Email/Password provider
    - **Firestore**: Create a database in test/production mode

3.  **Generate Service Account:**
    - Go to Project Settings → Service Accounts
    - Click "Generate new private key"
    - Save the JSON file as `service-account.json` in the project root
    - **⚠️ Never commit this file to version control**

4.  **Get Web API Key (for development token generation):**
    - Go to Project Settings → General
    - Copy the Web API Key from your app configuration

## Environment Configuration

1.  **Create environment file:**
    ```bash
    cp .env.example .env  # Create from example
    # Or create manually:
    touch .env
    ```

2.  **Configure environment variables:**
    ```env
    # Firebase Configuration
    GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
    FIREBASE_WEB_API_KEY=your_web_api_key_here
    
    # Application Settings
    ENVIRONMENT=development
    PORT=8000
    
    # Database URL (PostgreSQL)
    DATABASE_URL=postgresql+asyncpg://user:password@host:port/dbname
    ```

## Database Migrations

- **Initialize Alembic (if not already done):**
  ```bash
  alembic init migrations
  ```

- **Generate a new migration:**
  ```bash
  alembic revision --autogenerate -m "Your migration message"
  ```

- **Apply migrations:**
  ```bash
  alembic upgrade head
  ```

## Running the Application

1.  **Development mode:**
    ```bash
    uvicorn main:app --reload --port 8000
    ```

2.  **Production mode:**
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8000
    ```

3.  **Access the API:**
    - **API Docs**: http://localhost:8000/docs
    - **ReDoc**: http://localhost:8000/redoc
    - **Base API**: http://localhost:8000

## Testing

```bash
# Install development dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest

# Run with coverage
pytest --cov=src
```
