# Development Guidelines & Documentation Maintenance

## 📋 Overview

This document provides essential guidelines for maintaining code quality, following established patterns, and keeping documentation up-to-date when making modifications to the Celeste e-commerce API.

### 📚 Required Reading Before Development

Before starting any development work, developers MUST review these documents:

1. **[📋 Project Requirements](PROJECT_REQUIREMENTS.md)**: Complete feature requirements, database schema, and implementation roadmap
2. **[🏗️ Project Structure](PROJECT_STRUCTURE.md)**: Architecture, design patterns, and component organization  
3. **[📖 API Documentation](API_DOCUMENTATION.md)**: Complete API reference and endpoint specifications

**⚠️ CRITICAL**: All new features and modifications must align with the specifications in `PROJECT_REQUIREMENTS.md`. This document defines the target architecture and feature set that the platform is evolving towards.

## 🔄 Documentation Update Requirements

### ⚠️ CRITICAL: When Making ANY Modifications

**Every code change MUST be accompanied by corresponding documentation updates. This is not optional.**

### 1. API Endpoint Changes

When adding, modifying, or removing API endpoints:

#### Update `docs/API_DOCUMENTATION.md`:
- ✅ Add new endpoint sections with complete details
- ✅ Update existing endpoint descriptions if modified
- ✅ Remove deprecated endpoint documentation
- ✅ Update request/response examples
- ✅ Update authentication requirements
- ✅ Update query parameters and path parameters
- ✅ Update error responses and status codes

#### Update `README.md`:
- ✅ Update the Core Endpoints table if new public endpoints added
- ✅ Update feature list if new major functionality added
- ✅ Update technology stack if new dependencies introduced

#### Example Documentation Template for New Endpoints:
```markdown
#### POST `/new-endpoint`
Brief description of what this endpoint does.

**Headers:** `Authorization: Bearer <token>` (if auth required)

**Request Body:**
```json
{
  "field": "type and description"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "result": "expected response structure"
  }
}
```

**Errors:**
- `400`: Bad Request - Invalid input data
- `401`: Unauthorized - Invalid or missing token
- `404`: Not Found - Resource not found
```

### 2. Data Model Changes

When adding or modifying Pydantic models in `src/api/{domain}/models.py`:

#### Update `docs/API_DOCUMENTATION.md`:
- ✅ Update Data Models section with new model definitions
- ✅ Update all endpoint documentation that uses modified models
- ✅ Add field descriptions and validation rules
- ✅ Update example request/response bodies

#### Update `docs/PROJECT_STRUCTURE.md`:
- ✅ Update Database Schema section if Firestore collections change
- ✅ Update Data Relationships section for new model relationships

### 3. Authentication & Authorization Changes

When modifying auth logic or adding new roles:

#### Update `docs/API_DOCUMENTATION.md`:
- ✅ Update Authentication section
- ✅ Update User Roles section
- ✅ Update Security Scheme if changed
- ✅ Update all affected endpoint auth requirements

#### Update `README.md`:
- ✅ Update Security section
- ✅ Update User Roles section

### 4. New Router/Service/Core Component

When adding new major components:

#### Update `docs/PROJECT_STRUCTURE.md`:
- ✅ Add new component to Architecture Components section
- ✅ Update Project Structure diagram
- ✅ Document new patterns or principles if introduced
- ✅ Update Database Schema if new collections added

#### Update `README.md`:
- ✅ Update Project Structure diagram
- ✅ Update Key Features if significant functionality added

### 5. Configuration & Environment Changes

When adding new environment variables or config:

#### Update `README.md`:
- ✅ Update Environment Configuration section
- ✅ Update example .env file content
- ✅ Update Firebase Setup if needed
- ✅ Update Troubleshooting section if new issues possible

### 6. Technology Stack Changes

When adding new dependencies or changing core technologies:

#### Update `README.md`:
- ✅ Update technology badges at the top
- ✅ Update Key Technologies section
- ✅ Update Installation section if new setup steps required
- ✅ Update requirements.txt

#### Update `docs/PROJECT_STRUCTURE.md`:
- ✅ Update Technology Stack section
- ✅ Update Architecture Components if affected
- ✅ Update Development Workflow if changed

#### Update `docs/PROJECT_REQUIREMENTS.md`:
- ✅ Update Technical Implementation Plan if architecture changes
- ✅ Update Integration Requirements if new external services
- ✅ Update Performance & Scalability section if optimization changes

### 7. Feature Implementation Changes

When implementing new features from the requirements document:

#### Update `docs/PROJECT_REQUIREMENTS.md`:
- ✅ Mark features as "In Progress" or "Completed" in implementation plan
- ✅ Update migration steps if database changes implemented
- ✅ Update API enhancement strategy with actual implementation details
- ✅ Document any deviations from planned implementation

#### Update `docs/API_DOCUMENTATION.md`:
- ✅ Add complete documentation for implemented features
- ✅ Update existing endpoints that are enhanced
- ✅ Update data models with new schema fields

#### Update `docs/PROJECT_STRUCTURE.md`:
- ✅ Document new services, components, or architectural changes
- ✅ Update database schema section with implemented changes

## 🛠️ Technical Standards & Coding Practices

### Code Organization

#### 1. Follow Established Patterns
```python
# ✅ CORRECT: Follow existing modular structure
from fastapi import APIRouter, Depends, status
from typing import Annotated, List
from src.api.{domain}.models import {Schema}
from src.api.{domain}.service import {Service}
from src.dependencies.auth import get_current_user, RoleChecker
from src.config.constants import UserRole
from src.shared.exceptions import ResourceNotFoundException
from src.shared.responses import success_response

{domain}_router = APIRouter(prefix="/{domain}", tags=["{Domain}"])
{domain}_service = {Service}()

@{domain}_router.get("/", summary="Get all {domain}")
async def get_all_{domain}():
    # Implementation here
    return success_response(data)
```

#### 2. Modular Structure Organization
- ✅ Create domain-specific modules: `src/api/{domain}/`
- ✅ Models: `src/api/{domain}/models.py`
- ✅ Routes: `src/api/{domain}/routes.py`
- ✅ Services: `src/api/{domain}/service.py`
- ✅ Use snake_case for files and functions
- ✅ Use PascalCase for classes

#### 3. Import Organization
```python
# ✅ CORRECT: Import order
# 1. Standard library imports
from datetime import datetime
from typing import List, Optional

# 2. Third-party imports
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

# 3. Local imports
from src.models.user_models import UserSchema
from src.services.user_service import UserService
from src.core.responses import success_response
```

### Data Models (Pydantic)

#### 1. Model Structure
```python
# ✅ CORRECT: Complete model definition
class UserSchema(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, description="User's full name")
    email: Optional[EmailStr] = Field(None, description="User's email address")
    createdAt: Optional[datetime] = Field(None, description="Account creation timestamp")
    
class CreateUserSchema(BaseModel):
    name: str = Field(..., min_length=1, description="User's full name")
    email: Optional[EmailStr] = Field(None, description="User's email address")
    
class UpdateUserSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=1, description="Updated name")
    email: Optional[EmailStr] = Field(None, description="Updated email")
```

#### 2. Field Validation
- ✅ Use `Field()` for validation and descriptions
- ✅ Set appropriate constraints (min_length, ge, gt, etc.)
- ✅ Provide clear descriptions for API documentation
- ✅ Use Optional for nullable fields

### API Router Patterns

#### 1. Route Definitions
```python
# ✅ CORRECT: Complete route definition
@router.post("/", 
    summary="Create a new resource",
    response_model=ResourceSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def create_resource(resource_data: CreateResourceSchema):
    """
    Create a new resource with the provided data.
    
    - **name**: Resource name (required)
    - **description**: Resource description (optional)
    """
    new_resource = await resource_service.create_resource(resource_data)
    return success_response(new_resource.model_dump(), status_code=status.HTTP_201_CREATED)
```

#### 2. Response Handling
```python
# ✅ CORRECT: Consistent response format
return success_response(data.model_dump())

# ✅ CORRECT: Error handling
if not resource:
    raise ResourceNotFoundException(detail=f"Resource with ID {id} not found")
```

### Authentication & Authorization

#### 1. Protected Routes
```python
# ✅ CORRECT: User authentication
@router.get("/me")
async def get_profile(current_user: Annotated[DecodedToken, Depends(get_current_user)]):
    return success_response(current_user.model_dump())

# ✅ CORRECT: Role-based access
@router.post("/", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
async def admin_only_endpoint():
    pass
```

#### 2. Permission Checks
```python
# ✅ CORRECT: Resource ownership validation
if current_user.get("role") != UserRole.ADMIN.value and resource.userId != user_id:
    raise ForbiddenException("You do not have permission to access this resource.")
```

### Service Layer Patterns

#### 1. Service Structure
```python
# ✅ CORRECT: Service class pattern
class ResourceService:
    def __init__(self):
        self.db = get_firestore_db()
        self.collection = self.db.collection('resources')
    
    async def create_resource(self, resource_data: CreateResourceSchema) -> ResourceSchema:
        # Implementation
        pass
        
    async def get_resource_by_id(self, resource_id: str) -> Optional[ResourceSchema]:
        # Implementation
        pass
```

### Error Handling

#### 1. Custom Exceptions
```python
# ✅ CORRECT: Use custom exceptions
from src.core.exceptions import ResourceNotFoundException, ForbiddenException

if not resource:
    raise ResourceNotFoundException(detail="Resource not found")
    
if not authorized:
    raise ForbiddenException(detail="Access denied")
```

#### 2. Validation Errors
```python
# ✅ CORRECT: Let FastAPI handle validation
# Pydantic models automatically validate - no need for manual checks
```

### Database Operations (Firestore)

#### 1. Collection Access
```python
# ✅ CORRECT: Service-level database access
class UserService:
    def __init__(self):
        self.db = get_firestore_db()
        self.users_collection = self.db.collection('users')
```

#### 2. Document Operations
```python
# ✅ CORRECT: Firestore operations
# Create
doc_ref = self.users_collection.document()
doc_ref.set(user_data)

# Read
doc = self.users_collection.document(user_id).get()
if doc.exists:
    return UserSchema(**doc.to_dict(), id=doc.id)

# Update
self.users_collection.document(user_id).update(update_data)

# Delete
self.users_collection.document(user_id).delete()
```

### Environment & Configuration

#### 1. Environment Variables
```python
# ✅ CORRECT: Environment variable usage
import os
from dotenv import load_dotenv

load_dotenv()

SERVICE_ACCOUNT_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if not SERVICE_ACCOUNT_PATH:
    raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
```

#### 2. Configuration Validation
- ✅ Always validate required environment variables
- ✅ Provide clear error messages for missing config
- ✅ Use type hints for configuration values

### Constants & Hardcoding Prevention

#### 1. NEVER Hardcode Values
```python
# ❌ WRONG: Hardcoded strings
if user.role == "ADMIN":
    pass
if order.status == "pending":
    pass
if discount.type == "percentage":
    pass

# ✅ CORRECT: Use constants from src/config/constants.py
from src.shared.constants import UserRole, OrderStatus, DiscountType

if user.role == UserRole.ADMIN:
    pass
if order.status == OrderStatus.PENDING:
    pass
if discount.type == DiscountType.PERCENTAGE:
    pass
```

#### 2. Adding New Constants
```python
# ✅ CORRECT: Add new constants to src/config/constants.py
class PaymentMethod(str, Enum):
    CARD = "card"
    WALLET = "wallet"
    COD = "cod"

class DeliveryType(str, Enum):
    DELIVERY = "delivery"
    PICKUP = "pickup"

class FulfillmentCenter(str, Enum):
    FC001 = "FC001"
    FC002 = "FC002"
```

#### 3. Environment-Specific Values
```python
# ❌ WRONG: Hardcoded URLs/paths
FIREBASE_URL = "https://celeste-prod.firebaseio.com"
API_BASE_URL = "https://api.celeste.com"

# ✅ CORRECT: Environment-based configuration
FIREBASE_URL = os.getenv("FIREBASE_URL", "https://celeste-dev.firebaseio.com")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
```

#### 4. Database Collection Names
```python
# ❌ WRONG: Hardcoded collection names
users_collection = db.collection('users')
products_collection = db.collection('products')

# ✅ CORRECT: Use constants
class Collections(str, Enum):
    USERS = "users"
    PRODUCTS = "products"
    ORDERS = "orders"
    CATEGORIES = "categories"

users_collection = db.collection(Collections.USERS)
products_collection = db.collection(Collections.PRODUCTS)
```

### Testing Standards

#### 1. Test Structure (Future Implementation)
```python
# ✅ CORRECT: Test file structure
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

class TestUserEndpoints:
    def test_get_user_profile_success(self):
        # Test implementation
        pass
        
    def test_get_user_profile_unauthorized(self):
        # Test implementation
        pass
```

### Documentation Standards

#### 1. Code Documentation
```python
# ✅ CORRECT: Function docstrings
async def create_user(user_data: CreateUserSchema, uid: str) -> UserSchema:
    """
    Create a new user in Firestore.
    
    Args:
        user_data: User information to store
        uid: Firebase user ID
        
    Returns:
        Created user schema
        
    Raises:
        HTTPException: If user creation fails
    """
```

#### 2. API Documentation
- ✅ Use `summary` parameter in route decorators
- ✅ Add docstrings to route functions
- ✅ Use `response_model` for type hints
- ✅ Document query parameters with descriptions

## 🚨 Pre-Commit Checklist

Before committing any changes, ensure:

### Requirements Alignment
- [ ] ✅ Changes align with `PROJECT_REQUIREMENTS.md` specifications
- [ ] ✅ Database schema changes follow the planned migration strategy
- [ ] ✅ New features implement the exact functionality specified
- [ ] ✅ API endpoints match the planned enhancement strategy

### Code Quality
- [ ] ✅ Code follows established patterns
- [ ] ✅ All imports are properly organized
- [ ] ✅ Error handling is implemented
- [ ] ✅ Type hints are used consistently
- [ ] ✅ Docstrings are added where appropriate

### Testing
- [ ] ✅ Code has been tested locally
- [ ] ✅ API endpoints return expected responses
- [ ] ✅ Authentication/authorization works correctly
- [ ] ✅ Error cases are handled properly

### Documentation Updates
- [ ] ✅ `docs/PROJECT_REQUIREMENTS.md` updated with implementation progress
- [ ] ✅ `docs/API_DOCUMENTATION.md` updated if API changes
- [ ] ✅ `docs/PROJECT_STRUCTURE.md` updated if architecture changes
- [ ] ✅ `README.md` updated if setup/features change
- [ ] ✅ Code comments updated if logic changes
- [ ] ✅ Environment variables documented if config changes

### Deployment Readiness
- [ ] ✅ No hardcoded values or secrets in code
- [ ] ✅ Environment variables properly configured
- [ ] ✅ Requirements.txt updated if dependencies changed
- [ ] ✅ Firebase configuration still valid

## 📝 Documentation Templates

### New Feature Documentation Template
```markdown
## {Feature Name}

### Overview
Brief description of the feature and its purpose.

### Endpoints
List of new/modified endpoints with full documentation.

### Data Models
Any new or modified Pydantic models.

### Authentication
Authentication requirements and role permissions.

### Examples
Request/response examples and use cases.

### Integration
How this feature integrates with existing functionality.
```

### Bug Fix Documentation Template
```markdown
## Bug Fix: {Issue Description}

### Problem
Description of the bug that was fixed.

### Solution
Explanation of how the bug was resolved.

### Changes Made
- Modified files list
- API changes (if any)
- Breaking changes (if any)

### Testing
How the fix was tested and validated.
```

## 🎯 Best Practices Summary

### DO's
- ✅ Follow existing code patterns and structure
- ✅ Update documentation with every change
- ✅ Use constants from `src/config/constants.py` for all string values
- ✅ Use type hints and proper validation
- ✅ Implement proper error handling
- ✅ Test changes thoroughly
- ✅ Use consistent naming conventions
- ✅ Add meaningful docstrings and comments
- ✅ Validate environment configuration

### DON'Ts
- ❌ Skip documentation updates
- ❌ **NEVER HARDCODE**: strings, URLs, collection names, status values
- ❌ Hardcode sensitive values or environment-specific data
- ❌ Break existing API contracts without versioning
- ❌ Ignore error cases
- ❌ Use inconsistent patterns
- ❌ Commit incomplete features
- ❌ Leave TODO comments in production code
- ❌ Ignore security best practices

## 🔄 Review Process

### Self-Review Checklist
1. **Functionality**: Does the code work as expected?
2. **Patterns**: Does it follow established patterns?
3. **Security**: Are there any security concerns?
4. **Performance**: Any performance implications?
5. **Documentation**: Is documentation updated?
6. **Testing**: Has it been properly tested?

### Code Review Guidelines
- Focus on architecture and patterns
- Check documentation completeness
- Verify security implementations
- Ensure consistency with existing code
- Test the changes locally if possible

---

## 📞 Support

For questions about development guidelines:
1. Check existing code patterns first
2. Review this documentation
3. Consult the project maintainers
4. Create detailed issues for clarification

Remember: **Consistent, well-documented code is maintainable code!**