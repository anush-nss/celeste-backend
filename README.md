# Celeste E-Commerce API

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Firebase-039BE5?style=for-the-badge&logo=Firebase&logoColor=white" alt="Firebase">
  <img src="https://img.shields.io/badge/JWT-black?style=for-the-badge&logo=JSON%20web%20tokens" alt="JWT">
</p>

A robust, scalable, and feature-rich e-commerce backend API built with **FastAPI**, **Firebase**, and **Firestore**. This API provides comprehensive functionality for managing users, products, orders, inventory, and more in a modern online store environment.

## 🌟 Key Features

- **🔐 Secure Authentication**: JWT-based authentication with Firebase Auth
- **👥 User Management**: Complete user profiles, cart, and wishlist functionality
- **📦 Product Catalog**: Advanced product management with categories and filtering
- **🛍️ Order Processing**: Full order lifecycle management
- **📊 Inventory Tracking**: Real-time inventory management
- **💰 Discount System**: Flexible discount and promotion management
- **🏪 Multi-Store Support**: Physical store location management
- **🛡️ Role-Based Access**: Admin and customer role segregation
- **📝 Comprehensive Logging**: Detailed request/response logging
- **🚀 High Performance**: Optimized with response timing headers

## 🏗️ Architecture

The API follows a clean, modular architecture with clear separation of concerns:

```
📁 Project Structure
├── 📄 main.py                 # Application entry point
├── 📁 src/
│   ├── 📁 auth/              # Authentication & authorization
│   ├── 📁 core/              # Core utilities & configuration
│   ├── 📁 models/            # Pydantic data models
│   ├── 📁 routers/           # API route handlers
│   ├── 📁 services/          # Business logic layer
│   └── 📁 shared/            # Shared constants & utilities
├── 📁 docs/                  # Documentation
└── 📄 requirements.txt       # Dependencies
```

## 🚀 Quick Start

### Prerequisites

- **Python 3.8+**
- **Firebase Project** with Firestore and Authentication enabled
- **Firebase Service Account** credentials

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd celeste
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Firebase Setup

1. **Create Firebase Project:**
   - Go to [Firebase Console](https://console.firebase.google.com/)
   - Create a new project or use existing one

2. **Enable Required Services:**
   - **Authentication**: Enable Email/Password provider
   - **Firestore**: Create database in test/production mode

3. **Generate Service Account:**
   - Go to Project Settings → Service Accounts
   - Click "Generate new private key"
   - Save the JSON file as `service-account.json` in project root
   - **⚠️ Never commit this file to version control**

4. **Get Web API Key (Development only):**
   - Go to Project Settings → General
   - Copy the Web API Key from your app configuration

### Environment Configuration

1. **Create environment file:**
   ```bash
   cp .env.example .env  # Create from example
   # Or create manually:
   touch .env
   ```

2. **Configure environment variables:**
   ```env
   # Firebase Configuration
   GOOGLE_APPLICATION_CREDENTIALS=./service-account.json
   FIREBASE_WEB_API_KEY=your_web_api_key_here
   
   # Application Settings
   ENVIRONMENT=development
   PORT=8000
   ```

### Running the Application

1. **Development mode:**
   ```bash
   uvicorn main:app --reload --port 8000
   ```

2. **Production mode:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

3. **Access the API:**
   - **API Docs**: http://localhost:8000/docs
   - **ReDoc**: http://localhost:8000/redoc
   - **Base API**: http://localhost:8000

## 📚 API Documentation

### Authentication

The API uses **JWT Bearer token** authentication:

```bash
# Example authenticated request
curl -H "Authorization: Bearer <your-jwt-token>" \
     http://localhost:8000/users/me
```

### Core Endpoints

| Endpoint | Method | Description | Auth Required |
|---|---|---|---|
| `/auth/register` | POST | Register new user | ❌ |
| `/users/me` | GET/PUT | Manage current user profile | ✅ |
| `/users/me/addresses` | POST/GET/PUT/DELETE | Manage user addresses | ✅ |
| `/users/me/carts` | POST/GET/PUT/DELETE | Manage user carts | ✅ |
| `/products/` | GET | List products with filtering | ❌ |
| `/products/{id}` | GET | Get a single product | ❌ |
| `/categories/` | GET | List categories | ❌ |
| `/orders/` | GET/POST | Manage orders | ✅ |
| `/stores/` | GET | List stores with location filtering | ❌ |
| `/tiers/` | GET | List customer tiers | ❌ |


### User Roles

- **🛍️ CUSTOMER**: Regular users with shopping capabilities
- **👑 ADMIN**: Administrative users with full access

### Response Format

All API responses follow a consistent format:

```json
{
  "success": true,
  "data": {
    // Response data here
  }
}
```

## 🔧 Development

### Project Structure Details

- **`main.py`**: FastAPI application setup, middleware, and router registration
- **`src/auth/`**: Authentication dependencies and role-based access control
- **`src/core/`**: Firebase config, custom exceptions, logging, and response utilities
- **`src/models/`**: Pydantic models for request/response validation
- **`src/routers/`**: API endpoint definitions grouped by domain
- **`src/services/`**: Business logic and database operations
- **`src/shared/`**: Constants and shared utilities

### Key Technologies

- **[FastAPI](https://fastapi.tiangolo.com/)**: Modern Python web framework
- **[Firebase Admin SDK](https://firebase.google.com/docs/admin/setup)**: Backend Firebase integration
- **[Pydantic](https://pydantic.dev/)**: Data validation and serialization
- **[Uvicorn](https://www.uvicorn.org/)**: ASGI server

### Adding New Features

1. **Define Models**: Create Pydantic models in `src/models/`
2. **Business Logic**: Implement services in `src/services/`
3. **API Routes**: Create router in `src/routers/`
4. **Register Router**: Add to `main.py`
5. **Update Docs**: Document new endpoints

### Testing

```bash
# Install development dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest

# Run with coverage
pytest --cov=src
```

## 📖 Documentation

Comprehensive documentation is available in the `docs/` folder:

- **[📋 Project Requirements](docs/PROJECT_REQUIREMENTS.md)**: Complete feature requirements and implementation roadmap
- **[📄 API Documentation](docs/API_DOCUMENTATION.md)**: Complete API reference and endpoint specifications
- **[🏗️ Project Structure](docs/PROJECT_STRUCTURE.md)**: Architecture, design patterns, and component organization
- **[🛠️ Development Guidelines](docs/DEVELOPMENT_GUIDELINES.md)**: Coding standards and documentation maintenance

## 🔒 Security

- **🔐 JWT Authentication**: Secure token-based authentication
- **🛡️ Role-based Access**: Granular permission control  
- **🔍 Input Validation**: Comprehensive request validation
- **🚫 No Secrets Exposed**: Environment-based configuration
- **📝 Audit Logging**: Complete request/response logging

## 🚀 Deployment

### Docker Deployment

1.  **Create Dockerfile:**
   ```dockerfile
   FROM python:3.12-slim

   WORKDIR /app
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   COPY . .

   CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8080"]
   ```

2. **Build and run:**
   ```bash
   docker build -t celeste-api .
   docker run -p 8000:8000 --env-file .env celeste-api
   ```

### Cloud Deployment

The API is ready for deployment on:
- **Google Cloud Run** (recommended for Firebase integration)
- **AWS Lambda** with Mangum adapter
- **Heroku** with Procfile
- **Azure Container Instances**

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📊 Monitoring

The API includes built-in monitoring features:

- **⏱️ Response Timing**: `X-Process-Time` header on all responses
- **📝 Request Logging**: Structured logging with request details
- **🚨 Error Tracking**: Comprehensive exception handling
- **📈 Performance Metrics**: Built-in performance monitoring

## 🛠️ Troubleshooting

### Common Issues

**Firebase Connection Issues:**
```bash
# Verify service account file
export GOOGLE_APPLICATION_CREDENTIALS="./service-account.json"
python -c "from src.core.firebase import get_firestore_db; print('✅ Firebase connected')"
```

**Token Validation Errors:**
- Ensure Firebase project ID matches
- Verify service account permissions
- Check token expiration

**Development Token Generation:**
```bash
# Use development endpoint
curl -X POST "http://localhost:8000/auth/dev/token" \
     -H "Content-Type: application/json" \
     -d '{"uid": "test-user-id"}'
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🎯 Roadmap

- [ ] **🔍 Advanced Search**: Elasticsearch integration
- [ ] **📧 Email Notifications**: Order status updates
- [ ] **📱 Push Notifications**: Mobile app integration
- [ ] **💳 Payment Gateway**: Stripe/PayPal integration
- [ ] **📊 Analytics Dashboard**: Sales and user analytics
- [ ] **🧪 Testing Suite**: Comprehensive test coverage
- [ ] **🔄 Real-time Updates**: WebSocket support
- [ ] **🌐 Multi-language**: Internationalization support

## 💡 Support

- **📖 Documentation**: Check the `docs/` folder
- **🐛 Bug Reports**: Open an issue on GitHub
- **💬 Discussions**: Use GitHub Discussions
- **📧 Contact**: [Your contact information]

---

<p align="center">
  Made with ❤️ for modern e-commerce
</p>