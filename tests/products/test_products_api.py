import pytest
import pytest_asyncio
from httpx import AsyncClient
import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from tests.get_dev_token import get_dev_token
from src.config.constants import UserRole
from tests.constants import BASE_URL, ADMIN_UID, CUSTOMER_UID

@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_test_users():
    """Ensure test users have proper roles assigned before running tests."""
    from src.api.auth.service import AuthService
    
    auth_service = AuthService()
    
    try:
        # Set admin role for admin user
        auth_service.set_user_role(ADMIN_UID, UserRole.ADMIN)
    except Exception as e:
        print(f"Warning: Could not set admin role for {ADMIN_UID}: {e}")
    
    try:
        # Set customer role for customer user
        auth_service.set_user_role(CUSTOMER_UID, UserRole.CUSTOMER)
    except Exception as e:
        print(f"Warning: Could not set customer role for {CUSTOMER_UID}: {e}")

@pytest.fixture(scope="module")
def event_loop():
    """Overrides pytest default event loop to share it across all tests in the module."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="module")
async def admin_token():
    """Fixture to get a JWT token for an admin user."""
    return await get_dev_token(ADMIN_UID)


@pytest_asyncio.fixture(scope="module")
async def customer_token():
    """Fixture to get a JWT token for a customer user."""
    return await get_dev_token(CUSTOMER_UID)


@pytest_asyncio.fixture
async def admin_client(admin_token):
    """Fixture to get an httpx.AsyncClient with admin authentication."""
    async with AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=20,
    ) as client:
        yield client


@pytest_asyncio.fixture
async def customer_client(customer_token):
    """Fixture to get an httpx.AsyncClient with customer authentication."""
    async with AsyncClient(
        base_url=BASE_URL,
        headers={"Authorization": f"Bearer {customer_token}"},
        timeout=20,
    ) as client:
        yield client

@pytest_asyncio.fixture
async def anonymous_client():
    """Fixture to get an httpx.AsyncClient without any authentication."""
    async with AsyncClient(base_url=BASE_URL, timeout=20) as client:
        yield client

@pytest.mark.asyncio
class TestProductsAPI:
    """Test suite for the Products API, including RBAC. All tests are independent."""

    async def test_get_all_products(self, customer_client: AsyncClient, admin_client: AsyncClient, anonymous_client: AsyncClient):
        """Tests GET /products for both customer and admin roles."""
        for client in [customer_client, admin_client, anonymous_client]:
            response = await client.get("/products/")
            assert response.status_code == 200
            data = response.json()
            assert "products" in data["data"]
            assert "pagination" in data["data"]

    async def test_customer_cannot_create_product(self, customer_client: AsyncClient):
        """Tests that a customer cannot create a product."""
        product_data = {"name": "Customer Product", "brand": "CustBrand", "price": 10.0, "unit": "item", "categoryId": "cat1"}
        response = await customer_client.post("/products/", json=product_data)
        assert response.status_code == 403

    async def test_anonymous_cannot_modify_product(self, admin_client: AsyncClient, anonymous_client: AsyncClient):
        """Tests that an anonymous user cannot create, update, or delete a product."""
        # 1. ARRANGE: Create a product as an admin
        product_data = {
            "name": "Product for Anonymous Test",
            "brand": "TestBrand",
            "price": 99.99,
            "unit": "piece",
            "categoryId": "anon-test-category",
        }
        response = await admin_client.post("/products/", json=product_data)
        assert response.status_code == 201
        product_id = response.json()["data"]["id"]

        # 2. ACT & ASSERT: As an anonymous user, attempt to create a product
        response = await anonymous_client.post("/products/", json=product_data)
        assert response.status_code == 403  # Forbidden

        # 3. ACT & ASSERT: As an anonymous user, attempt to update the product
        update_data = {"price": 129.99}
        response = await anonymous_client.put(f"/products/{product_id}", json=update_data)
        assert response.status_code == 403  # Forbidden

        # 4. ACT & ASSERT: As an anonymous user, attempt to delete the product
        response = await anonymous_client.delete(f"/products/{product_id}")
        assert response.status_code == 403  # Forbidden

        # 5. CLEANUP: Delete the product as an admin
        response = await admin_client.delete(f"/products/{product_id}")
        assert response.status_code == 200

    async def test_customer_cannot_modify_product(self, admin_client: AsyncClient, customer_client: AsyncClient):
        """Tests that a customer cannot update or delete a product created by an admin."""
        # 1. ARRANGE: Create a product as an admin
        product_data = {
            "name": "Product for Modify Test",
            "brand": "TestBrand",
            "price": 99.99,
            "unit": "piece",
            "categoryId": "permissions-test-category",
        }
        response = await admin_client.post("/products/", json=product_data)
        assert response.status_code == 201
        product_id = response.json()["data"]["id"]

        # 2. ACT & ASSERT: As a customer, attempt to update the product
        update_data = {"price": 129.99}
        response = await customer_client.put(f"/products/{product_id}", json=update_data)
        assert response.status_code == 403

        # 3. ACT & ASSERT: As a customer, attempt to delete the product
        response = await customer_client.delete(f"/products/{product_id}")
        assert response.status_code == 403

        # 4. CLEANUP: Delete the product as an admin to leave the system clean
        response = await admin_client.delete(f"/products/{product_id}")
        assert response.status_code == 200


    async def test_admin_can_manage_product_lifecycle(self, admin_client: AsyncClient):
        """Tests the full CRUD lifecycle for a product as an admin."""
        create_data = {
            "name": "Admin Lifecycle Product",
            "brand": "AdminBrand",
            "price": 250.00,
            "unit": "piece",
            "categoryId": "lifecycle-category",
        }
        product_id = None
        
        # 1. CREATE
        response = await admin_client.post("/products/", json=create_data)
        assert response.status_code == 201
        product = response.json()["data"]
        product_id = product["id"]
        assert product["name"] == create_data["name"]

        # 2. READ
        response = await admin_client.get(f"/products/{product_id}")
        assert response.status_code == 200
        fetched_product = response.json()["data"]
        assert fetched_product["id"] == product_id

        # 3. UPDATE
        update_data = {"price": 245.50}
        response = await admin_client.put(f"/products/{product_id}", json=update_data)
        assert response.status_code == 200
        updated_product = response.json()["data"]
        assert updated_product["price"] == 245.50

        # 4. DELETE
        response = await admin_client.delete(f"/products/{product_id}")
        assert response.status_code == 200

        # 5. VERIFY DELETION
        response = await admin_client.get(f"/products/{product_id}")
        assert response.status_code == 404
