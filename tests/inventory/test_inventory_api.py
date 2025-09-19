import pytest
from httpx import AsyncClient
from src.config.constants import UserRole

@pytest.mark.asyncio
class TestInventoryAPI:
    async def test_inventory_lifecycle(self, admin_client: AsyncClient):
        # 1. Create a product
        product_data = {
            "name": "Test Product for Inventory",
            "brand": "TestBrand",
            "base_price": 10.0,
            "unit_measure": "kg",
            "category_ids": [],
        }
        response = await admin_client.post("/products/", json=product_data)
        assert response.status_code == 201
        product_id = response.json()["data"]["id"]

        # 2. Create a store
        store_data = {
            "name": "Test Store for Inventory",
            "address": "123 Test St",
            "latitude": 0.0,
            "longitude": 0.0,
        }
        response = await admin_client.post("/stores/", json=store_data)
        assert response.status_code == 201
        store_id = response.json()["data"]["id"]

        # 3. Create inventory
        inventory_data = {
            "product_id": product_id,
            "store_id": store_id,
            "quantity_available": 100,
        }
        response = await admin_client.post("/inventory/", json=inventory_data)
        assert response.status_code == 201
        inventory_id = response.json()["data"]["id"]

        # 4. Get all inventory
        response = await admin_client.get("/inventory/")
        assert response.status_code == 200
        data = response.json()["data"]
        assert isinstance(data, list)
        assert len(data) > 0

        # 5. Get inventory by id
        response = await admin_client.get(f"/inventory/{inventory_id}")
        assert response.status_code == 200
        assert response.json()["data"]["id"] == inventory_id

        # 6. Update inventory
        update_data = {"quantity_available": 150}
        response = await admin_client.put(f"/inventory/{inventory_id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["data"]["quantity_available"] == 150

        # 7. Adjust inventory
        adjustment_data = {
            "product_id": product_id,
            "store_id": store_id,
            "available_change": -10,
            "on_hold_change": 10,
        }
        response = await admin_client.post("/inventory/adjust", json=adjustment_data)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["quantity_available"] == 140
        assert data["quantity_on_hold"] == 10

        # 8. Delete inventory
        response = await admin_client.delete(f"/inventory/{inventory_id}")
        assert response.status_code == 204
