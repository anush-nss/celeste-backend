import pytest
from httpx import AsyncClient

from src.config.constants import OrderStatus


@pytest.mark.asyncio
class TestOrdersAPI:
    async def test_order_lifecycle(
        self, admin_client: AsyncClient, customer_client: AsyncClient
    ):
        # 1. Create a product
        product_data = {
            "name": "Test Product for Order",
            "brand": "TestBrand",
            "base_price": 12.50,
            "unit_measure": "item",
            "category_ids": [],
        }
        response = await admin_client.post("/products/", json=product_data)
        assert response.status_code == 201
        product_id = response.json()["data"]["id"]

        # 2. Create a store
        store_data = {
            "name": "Test Store for Order",
            "address": "456 Test Ave",
            "latitude": 10.0,
            "longitude": 10.0,
        }
        response = await admin_client.post("/stores/", json=store_data)
        assert response.status_code == 201
        store_id = response.json()["data"]["id"]

        # 3. Create inventory for the product in the store
        inventory_data = {
            "product_id": product_id,
            "store_id": store_id,
            "quantity_available": 50,
        }
        response = await admin_client.post("/inventory/", json=inventory_data)
        assert response.status_code == 201
        inventory_id = response.json()["data"]["id"]

        # 4. Create an order as a customer
        order_data = {
            "store_id": store_id,
            "items": [{"product_id": product_id, "quantity": 5}],
        }
        response = await customer_client.post("/orders/", json=order_data)
        assert response.status_code == 201
        order = response.json()["data"]
        order_id = order["id"]
        assert order["status"] == OrderStatus.PENDING.value
        assert order["total_amount"] == 62.50  # 5 * 12.50

        # 5. Check inventory - stock should be on hold
        response = await admin_client.get(f"/inventory/{inventory_id}")
        assert response.status_code == 200
        inventory = response.json()["data"]
        assert inventory["quantity_available"] == 45
        assert inventory["quantity_on_hold"] == 5

        # 6. Admin confirms the order
        update_data = {"status": OrderStatus.CONFIRMED.value}
        response = await admin_client.put(
            f"/orders/{order_id}/status", json=update_data
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == OrderStatus.CONFIRMED.value

        # 7. Check inventory - stock should be reserved
        response = await admin_client.get(f"/inventory/{inventory_id}")
        assert response.status_code == 200
        inventory = response.json()["data"]
        assert inventory["quantity_available"] == 45
        assert inventory["quantity_on_hold"] == 0
        assert inventory["quantity_reserved"] == 5

        # 8. Admin ships the order
        update_data = {"status": OrderStatus.SHIPPED.value}
        response = await admin_client.put(
            f"/orders/{order_id}/status", json=update_data
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == OrderStatus.SHIPPED.value

        # 9. Check inventory - reserved stock should be gone
        response = await admin_client.get(f"/inventory/{inventory_id}")
        assert response.status_code == 200
        inventory = response.json()["data"]
        assert inventory["quantity_available"] == 45
        assert inventory["quantity_on_hold"] == 0
        assert inventory["quantity_reserved"] == 0
