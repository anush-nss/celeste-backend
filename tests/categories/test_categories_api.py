import asyncio
import os
import sys
from unittest import mock

import pytest
import pytest_asyncio
from httpx import AsyncClient

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.config.constants import UserRole
from tests.constants import ADMIN_UID, BASE_URL, CUSTOMER_UID
from tests.get_dev_token import get_dev_token


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
@mock.patch("src.dependencies.firebase.auth", create=True)
@mock.patch("firebase_admin.initialize_app")
class TestCategoriesAPI:
    """Test suite for the Categories API, including RBAC. All tests are independent."""

    async def test_get_all_categories(
        self,
        mock_initialize_app,
        mock_auth,
        customer_client: AsyncClient,
        admin_client: AsyncClient,
        anonymous_client: AsyncClient,
    ):
        """Tests GET /categories for both customer and admin roles, and anonymous users."""
        mock_auth.verify_id_token.return_value = {
            "uid": CUSTOMER_UID,
            "role": UserRole.CUSTOMER,
        }
        for client in [customer_client, admin_client, anonymous_client]:
            response = await client.get("/categories/")
            assert response.status_code == 200
            data = response.json()
            assert "data" in data
            assert isinstance(data["data"], list)

    async def test_customer_cannot_create_category(
        self, mock_initialize_app, mock_auth, customer_client: AsyncClient
    ):
        """Tests that a customer cannot create a category."""
        mock_auth.verify_id_token.return_value = {
            "uid": CUSTOMER_UID,
            "role": UserRole.CUSTOMER,
        }
        category_data = {
            "name": "Customer Category",
            "description": "Test category created by customer",
            "order": 1,
        }
        response = await customer_client.post("/categories/", json=category_data)
        assert response.status_code == 403

    async def test_anonymous_cannot_modify_category(
        self,
        mock_initialize_app,
        mock_auth,
        admin_client: AsyncClient,
        anonymous_client: AsyncClient,
    ):
        """Tests that an anonymous user cannot create, update, or delete a category."""
        # 1. ARRANGE: Create a category as an admin
        mock_auth.verify_id_token.return_value = {
            "uid": ADMIN_UID,
            "role": UserRole.ADMIN,
        }
        category_data = {
            "name": "Category for Anonymous Test",
            "description": "Test category for anonymous user tests",
            "order": 99,
        }
        response = await admin_client.post("/categories/", json=category_data)
        assert response.status_code == 201
        category_id = response.json()["data"]["id"]

        # 2. ACT & ASSERT: As an anonymous user, attempt to create a category
        response = await anonymous_client.post("/categories/", json=category_data)
        assert response.status_code == 403  # Forbidden

        # 3. ACT & ASSERT: As an anonymous user, attempt to update the category
        update_data = {"description": "Updated by anonymous user"}
        response = await anonymous_client.put(
            f"/categories/{category_id}", json=update_data
        )
        assert response.status_code == 403  # Forbidden

        # 4. ACT & ASSERT: As an anonymous user, attempt to delete the category
        response = await anonymous_client.delete(f"/categories/{category_id}")
        assert response.status_code == 403  # Forbidden

        # 5. CLEANUP: Delete the category as an admin
        response = await admin_client.delete(f"/categories/{category_id}")
        assert response.status_code == 200

    async def test_customer_cannot_modify_category(
        self,
        mock_initialize_app,
        mock_auth,
        admin_client: AsyncClient,
        customer_client: AsyncClient,
    ):
        """Tests that a customer cannot update or delete a category created by an admin."""
        # 1. ARRANGE: Create a category as an admin
        mock_auth.verify_id_token.return_value = {
            "uid": ADMIN_UID,
            "role": UserRole.ADMIN,
        }
        category_data = {
            "name": "Category for Modify Test",
            "description": "Test category for customer modification tests",
            "order": 98,
        }
        response = await admin_client.post("/categories/", json=category_data)
        assert response.status_code == 201
        category_id = response.json()["data"]["id"]

        # 2. ACT & ASSERT: As a customer, attempt to update the category
        mock_auth.verify_id_token.return_value = {
            "uid": CUSTOMER_UID,
            "role": UserRole.CUSTOMER,
        }
        update_data = {"description": "Updated by customer"}
        response = await customer_client.put(
            f"/categories/{category_id}", json=update_data
        )
        assert response.status_code == 403

        # 3. ACT & ASSERT: As a customer, attempt to delete the category
        response = await customer_client.delete(f"/categories/{category_id}")
        assert response.status_code == 403

        # 4. CLEANUP: Delete the category as an admin to leave the system clean
        mock_auth.verify_id_token.return_value = {
            "uid": ADMIN_UID,
            "role": UserRole.ADMIN,
        }
        response = await admin_client.delete(f"/categories/{category_id}")
        assert response.status_code == 200

    async def test_admin_can_manage_category_lifecycle(
        self, mock_initialize_app, mock_auth, admin_client: AsyncClient
    ):
        """Tests the full CRUD lifecycle for a category as an admin."""
        mock_auth.verify_id_token.return_value = {
            "uid": ADMIN_UID,
            "role": UserRole.ADMIN,
        }
        create_data = {
            "name": "Admin Lifecycle Category",
            "description": "Category for testing full lifecycle management",
            "order": 97,
        }
        category_id = None

        # 1. CREATE
        response = await admin_client.post("/categories/", json=create_data)
        assert response.status_code == 201
        category = response.json()["data"]
        category_id = category["id"]
        assert category["name"] == create_data["name"]
        assert category["description"] == create_data["description"]
        assert category["order"] == create_data["order"]

        # 2. READ
        response = await admin_client.get(f"/categories/{category_id}")
        assert response.status_code == 200
        fetched_category = response.json()["data"]
        assert fetched_category["id"] == category_id
        assert fetched_category["name"] == create_data["name"]

        # 3. UPDATE
        update_data = {
            "name": "Updated Admin Category",
            "description": "Updated description",
            "order": 96,
        }
        response = await admin_client.put(
            f"/categories/{category_id}", json=update_data
        )
        assert response.status_code == 200
        updated_category = response.json()["data"]
        assert updated_category["name"] == update_data["name"]
        assert updated_category["description"] == update_data["description"]
        assert updated_category["order"] == update_data["order"]

        # 4. DELETE
        response = await admin_client.delete(f"/categories/{category_id}")
        assert response.status_code == 200

        # 5. VERIFY DELETION
        response = await admin_client.get(f"/categories/{category_id}")
        assert response.status_code == 404

    async def test_get_category_by_id_for_all_roles(
        self,
        mock_initialize_app,
        mock_auth,
        admin_client: AsyncClient,
        customer_client: AsyncClient,
        anonymous_client: AsyncClient,
    ):
        """Tests that all users can read a single category by ID."""
        # 1. ARRANGE: Create a category as an admin
        mock_auth.verify_id_token.return_value = {
            "uid": ADMIN_UID,
            "role": UserRole.ADMIN,
        }
        category_data = {
            "name": "Public Read Test Category",
            "description": "Category for testing read access",
            "order": 95,
        }
        response = await admin_client.post("/categories/", json=category_data)
        assert response.status_code == 201
        category_id = response.json()["data"]["id"]

        # 2. ACT & ASSERT: Test read access for all user types
        mock_auth.verify_id_token.return_value = {
            "uid": CUSTOMER_UID,
            "role": UserRole.CUSTOMER,
        }
        for client in [admin_client, customer_client, anonymous_client]:
            response = await client.get(f"/categories/{category_id}")
            assert response.status_code == 200
            category = response.json()["data"]
            assert category["id"] == category_id
            assert category["name"] == category_data["name"]

        # 3. CLEANUP: Delete the category as an admin
        mock_auth.verify_id_token.return_value = {
            "uid": ADMIN_UID,
            "role": UserRole.ADMIN,
        }
        response = await admin_client.delete(f"/categories/{category_id}")
        assert response.status_code == 200

    async def test_get_nonexistent_category(
        self, mock_initialize_app, mock_auth, admin_client: AsyncClient
    ):
        """Tests that requesting a non-existent category returns 404."""
        mock_auth.verify_id_token.return_value = {
            "uid": ADMIN_UID,
            "role": UserRole.ADMIN,
        }
        nonexistent_id = "nonexistent-category-id"
        response = await admin_client.get(f"/categories/{nonexistent_id}")
        assert response.status_code == 404

    async def test_admin_cannot_update_nonexistent_category(
        self, mock_initialize_app, mock_auth, admin_client: AsyncClient
    ):
        """Tests that updating a non-existent category returns 404."""
        mock_auth.verify_id_token.return_value = {
            "uid": ADMIN_UID,
            "role": UserRole.ADMIN,
        }
        nonexistent_id = "nonexistent-category-id"
        update_data = {"name": "Updated Name"}
        response = await admin_client.put(
            f"/categories/{nonexistent_id}", json=update_data
        )
        assert response.status_code == 404

    async def test_admin_cannot_delete_nonexistent_category(
        self, mock_initialize_app, mock_auth, admin_client: AsyncClient
    ):
        """Tests that deleting a non-existent category returns 404."""
        mock_auth.verify_id_token.return_value = {
            "uid": ADMIN_UID,
            "role": UserRole.ADMIN,
        }
        nonexistent_id = "nonexistent-category-id"
        response = await admin_client.delete(f"/categories/{nonexistent_id}")
        assert response.status_code == 404

    async def test_create_category_with_parent(
        self, mock_initialize_app, mock_auth, admin_client: AsyncClient
    ):
        """Tests creating a category with a parent category."""
        mock_auth.verify_id_token.return_value = {
            "uid": ADMIN_UID,
            "role": UserRole.ADMIN,
        }
        # 1. Create parent category
        parent_data = {
            "name": "Parent Category",
            "description": "Parent category for hierarchy test",
            "order": 1,
        }
        response = await admin_client.post("/categories/", json=parent_data)
        assert response.status_code == 201
        parent_id = response.json()["data"]["id"]

        # 2. Create child category
        child_data = {
            "name": "Child Category",
            "description": "Child category for hierarchy test",
            "order": 2,
            "parentCategoryId": parent_id,
        }
        response = await admin_client.post("/categories/", json=child_data)
        assert response.status_code == 201
        child_category = response.json()["data"]
        assert child_category["parentCategoryId"] == parent_id

        # 3. CLEANUP: Delete both categories
        child_id = child_category["id"]
        await admin_client.delete(f"/categories/{child_id}")
        await admin_client.delete(f"/categories/{parent_id}")

    async def test_create_category_validation(
        self, mock_initialize_app, mock_auth, admin_client: AsyncClient
    ):
        """Tests validation when creating categories with invalid data."""
        mock_auth.verify_id_token.return_value = {
            "uid": ADMIN_UID,
            "role": UserRole.ADMIN,
        }
        # Test with missing required field (name)
        invalid_data = {"description": "Category without name", "order": 1}
        response = await admin_client.post("/categories/", json=invalid_data)
        assert response.status_code == 422  # Validation error

        # Test with empty name
        invalid_data = {
            "name": "",
            "description": "Category with empty name",
            "order": 1,
        }
        response = await admin_client.post("/categories/", json=invalid_data)
        assert response.status_code == 422  # Validation error
