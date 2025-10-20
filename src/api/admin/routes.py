from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from fastapi import APIRouter, HTTPException, status
from google.cloud.firestore import SERVER_TIMESTAMP
from pydantic import BaseModel, Field

from src.api.auth.service import AuthService
from src.api.interactions.service import InteractionService
from src.api.personalization.service import PersonalizationService
from src.api.products.services.popularity_service import PopularityService
from src.config.constants import InteractionType
from src.integrations.odoo import (
    OdooService,
    OdooTestRequest,
    OdooTestResponse,
    OdooConnectionResponse,
    OdooProductResponse,
)
from src.integrations.odoo.models import OdooCustomerResponse
from src.shared.database import get_async_db
from src.shared.responses import success_response

dev_router = APIRouter(prefix="/dev", tags=["Development"])
auth_service = AuthService()
odoo_service = OdooService()
interaction_service = InteractionService()
popularity_service = PopularityService()
personalization_service = PersonalizationService()


class TriggerRequest(BaseModel):
    """Request body for manual triggers"""

    action: str = Field(
        ...,
        description="Action to perform: update_popularity, update_preferences, track_interaction, update_all_popularity",
    )
    user_id: Optional[str] = Field(
        None, description="Firebase UID (for preferences/interactions)"
    )
    product_id: Optional[int] = Field(
        None, description="Product ID (for popularity/interactions)"
    )
    interaction_type: Optional[str] = Field(
        None, description="Interaction type: view, cart_add, order, etc."
    )
    quantity: Optional[int] = Field(1, description="Quantity (for cart_add)")
    order_id: Optional[int] = Field(None, description="Order ID (for order tracking)")


@dev_router.post("/auth/token", summary="Generate dev ID token for existing user")
async def create_dev_token(uid: str):
    """
    Generate an ID token for an existing Firebase user for testing purposes.
    This creates a proper ID token that can be used with verify_id_token().

    The user with the given UID must already exist in Firebase Auth.
    """
    try:
        result = auth_service.generate_development_id_token(uid)
        return success_response(result)
    except Exception as e:
        if "not found in Firebase Auth" in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        elif "FIREBASE_WEB_API_KEY" in str(e):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"{str(e)}. Add it to your .env file.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
            )


@dev_router.post(
    "/triggers", summary="Manual trigger for search/personalization updates"
)
async def manual_trigger(request: TriggerRequest):
    """
    Manual triggers for testing search & personalization features.

    **Actions:**

    1. **update_popularity** - Update popularity scores for a product
       - Required: `product_id`
       ```json
       {"action": "update_popularity", "product_id": 123}
       ```

    2. **update_all_popularity** - Update popularity for all products (slow!)
       ```json
       {"action": "update_all_popularity"}
       ```

    3. **update_preferences** - Update user preferences
       - Required: `user_id`
       ```json
       {"action": "update_preferences", "user_id": "firebase_uid"}
       ```

    4. **track_interaction** - Manually track an interaction
       - Required: `user_id`, `product_id`, `interaction_type`
       - Optional: `quantity`, `order_id`
       ```json
       {
         "action": "track_interaction",
         "user_id": "firebase_uid",
         "product_id": 123,
         "interaction_type": "cart_add",
         "quantity": 2
       }
       ```

       Available interaction types: `view`, `cart_add`, `wishlist_add`, `order`, `search_click`
    """
    try:
        action = request.action.lower()

        # Action: Update popularity for a single product
        if action == "update_popularity":
            if not request.product_id:
                raise HTTPException(
                    status_code=400,
                    detail="product_id is required for update_popularity",
                )

            success = await popularity_service.update_product_popularity(
                request.product_id
            )

            if success:
                # Get updated metrics
                metrics = await popularity_service.get_popularity_metrics(
                    request.product_id
                )
                return success_response(
                    {
                        "action": "update_popularity",
                        "product_id": request.product_id,
                        "success": True,
                        "metrics": metrics,
                    }
                )
            else:
                return success_response(
                    {
                        "action": "update_popularity",
                        "product_id": request.product_id,
                        "success": False,
                        "message": "No interactions found for this product",
                    }
                )

        # Action: Update popularity for all products
        elif action == "update_all_popularity":
            results = await popularity_service.update_all_popularity_scores()
            return success_response(
                {
                    "action": "update_all_popularity",
                    "results": results,
                    "message": f"Updated {results['success']} products, {results['failed']} failed",
                }
            )

        # Action: Update user preferences
        elif action == "update_preferences":
            if not request.user_id:
                raise HTTPException(
                    status_code=400, detail="user_id is required for update_preferences"
                )

            success = await personalization_service.update_user_preferences(
                request.user_id
            )

            if success:
                # Get updated preferences
                preferences = await personalization_service.get_user_preferences(
                    request.user_id
                )
                return success_response(
                    {
                        "action": "update_preferences",
                        "user_id": request.user_id,
                        "success": True,
                        "preferences": {
                            "total_interactions": preferences.total_interactions
                            if preferences
                            else 0,
                            "category_scores": preferences.category_scores
                            if preferences
                            else {},
                            "brand_scores": preferences.brand_scores
                            if preferences
                            else {},
                            "search_keywords": preferences.search_keywords
                            if preferences
                            else {},
                        },
                    }
                )
            else:
                return success_response(
                    {
                        "action": "update_preferences",
                        "user_id": request.user_id,
                        "success": False,
                        "message": "Not enough interactions (minimum 5 required)",
                    }
                )

        # Action: Track interaction
        elif action == "track_interaction":
            if (
                not request.user_id
                or not request.product_id
                or not request.interaction_type
            ):
                raise HTTPException(
                    status_code=400,
                    detail="user_id, product_id, and interaction_type are required for track_interaction",
                )

            # Validate interaction type
            try:
                interaction_type = InteractionType(request.interaction_type.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid interaction_type. Must be one of: {[t.value for t in InteractionType]}",
                )

            # Track the interaction
            if interaction_type == InteractionType.CART_ADD:
                success = await interaction_service.track_cart_add(
                    user_id=request.user_id,
                    product_id=request.product_id,
                    quantity=request.quantity or 1,
                    auto_update=True,
                )
            elif interaction_type == InteractionType.ORDER:
                if not request.order_id:
                    raise HTTPException(
                        status_code=400,
                        detail="order_id is required for order interaction",
                    )
                success = await interaction_service.track_order(
                    user_id=request.user_id,
                    product_id=request.product_id,
                    order_id=request.order_id,
                    quantity=request.quantity or 1,
                    auto_update=True,
                )
            elif interaction_type == InteractionType.WISHLIST_ADD:
                success = await interaction_service.track_wishlist_add(
                    user_id=request.user_id,
                    product_id=request.product_id,
                    auto_update=True,
                )
            elif interaction_type == InteractionType.VIEW:
                success = await interaction_service.track_view(
                    user_id=request.user_id,
                    product_id=request.product_id,
                    auto_update=False,
                )
            else:
                success = await interaction_service.track_interaction(
                    user_id=request.user_id,
                    product_id=request.product_id,
                    interaction_type=interaction_type,
                    auto_update_popularity=True,
                    auto_update_preferences=False,
                )

            return success_response(
                {
                    "action": "track_interaction",
                    "user_id": request.user_id,
                    "product_id": request.product_id,
                    "interaction_type": request.interaction_type,
                    "success": success,
                    "message": "Interaction tracked (popularity/preferences updating in background)",
                }
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid action: {action}. Must be one of: update_popularity, update_all_popularity, update_preferences, track_interaction",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error executing trigger: {str(e)}"
        )


@dev_router.post("/db/add", summary="Add data to database collection")
async def add_data_to_collection(
    collection: str, data: Union[Dict[str, Any], List[Dict[str, Any]]]
):
    """
    Add data to a specified Firestore collection.

    - **collection**: Name of the collection to add data to
    - **data**: Single document (dict) or list of documents to add
    """
    try:
        db = await get_async_db()
        collection_ref = db.collection(collection)

        added_documents = []

        if isinstance(data, dict):
            # Single document
            doc_ref = collection_ref.document()
            # Add server timestamps
            doc_data = data.copy()
            doc_data.update(
                {"created_at": SERVER_TIMESTAMP, "updated_at": SERVER_TIMESTAMP}
            )
            await doc_ref.set(doc_data)
            added_documents.append(
                {
                    "id": doc_ref.id,
                    "data": data,  # Return original data without server timestamp placeholders
                }
            )
        elif isinstance(data, list):
            # Multiple documents
            for item_data in data:
                if isinstance(item_data, dict):
                    doc_ref = collection_ref.document()
                    # Add server timestamps
                    doc_data = item_data.copy()
                    doc_data.update(
                        {"created_at": SERVER_TIMESTAMP, "updated_at": SERVER_TIMESTAMP}
                    )
                    await doc_ref.set(doc_data)
                    added_documents.append(
                        {
                            "id": doc_ref.id,
                            "data": item_data,  # Return original data without server timestamp placeholders
                        }
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="All items in the list must be dictionaries",
                    )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Data must be a dictionary or a list of dictionaries",
            )

        return success_response(
            {
                "collection": collection,
                "documents_added": len(added_documents),
                "documents": added_documents,
                "message": f"Successfully added {len(added_documents)} document(s) to {collection}",
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add data to collection: {str(e)}",
        )


@dev_router.get("/db/collections", summary="List all collections")
async def list_collections():
    """
    List all collections in the database.
    """
    try:
        db = await get_async_db()
        collections = db.collections()
        collection_names = [collection.id async for collection in collections]

        return success_response(
            {"collections": collection_names, "count": len(collection_names)}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list collections: {str(e)}",
        )


@dev_router.get("/db/{collection}", summary="Get all documents from a collection")
async def get_collection_data(collection: str, limit: int = 100):
    """
    Get all documents from a specified collection.

    - **collection**: Name of the collection
    - **limit**: Maximum number of documents to return (default: 100)
    """
    try:
        db = await get_async_db()
        collection_ref = db.collection(collection)
        docs = collection_ref.limit(limit).stream()

        documents = []
        async for doc in docs:
            doc_data = doc.to_dict()
            if doc_data:
                # Convert DatetimeWithNanoseconds to ISO format strings
                for key, value in doc_data.items():
                    if hasattr(value, "timestamp"):  # DatetimeWithNanoseconds object
                        doc_data[key] = value.isoformat()
                documents.append({"id": doc.id, "data": doc_data})

        return success_response(
            {"collection": collection, "documents": documents, "count": len(documents)}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get collection data: {str(e)}",
        )


@dev_router.delete("/db/{collection}", summary="Clear all documents from a collection")
async def clear_collection(collection: str):
    """
    Delete all documents from a specified collection.
    WARNING: This will permanently delete all data in the collection!

    - **collection**: Name of the collection to clear
    """
    try:
        db = await get_async_db()
        collection_ref = db.collection(collection)
        docs = collection_ref.stream()

        deleted_count = 0
        async for doc in docs:
            await doc.reference.delete()
            deleted_count += 1

        return success_response(
            {
                "collection": collection,
                "deleted_documents": deleted_count,
                "message": f"Successfully deleted {deleted_count} document(s) from {collection}",
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear collection: {str(e)}",
        )


@dev_router.post("/odoo/test", summary="Test Odoo ERP connection and read product")
async def test_odoo_connection(request: OdooTestRequest):
    """
    Test connection to Odoo ERP and optionally read product data.

    Test Types:
    - **connection**: Test connection and authentication only
    - **product**: Test connection and read product(s)

    Example request bodies:

    Connection test:
    ```json
    {
        "test_type": "connection"
    }
    ```

    Product test (first product):
    ```json
    {
        "test_type": "product",
        "limit": 1
    }
    ```

    Product test (specific product):
    ```json
    {
        "test_type": "product",
        "product_id": 123
    }
    ```

    Customer creation test:
    ```json
    {
        "test_type": "customer",
        "customer_data": {
            "name": "John Doe",
            "email": "john.doe@example.com",
            "phone": "+94771234567",
            "mobile": "+94771234567",
            "street": "123 Main Street",
            "city": "Colombo",
            "zip": "00100"
        }
    }
    ```
    """
    try:
        timestamp = datetime.utcnow().isoformat()

        if request.test_type == "connection":
            # Test connection only
            connection_result = odoo_service.test_connection()

            response = OdooTestResponse(
                test_type="connection",
                connection=OdooConnectionResponse(**connection_result),
                products=None,
                customer=None,
                timestamp=timestamp,
                success=connection_result["status"] == "success",
            )

            return success_response(response.model_dump())

        elif request.test_type == "product":
            # Test connection and read product
            connection_result = odoo_service.test_connection()

            if connection_result["status"] != "success":
                # Connection failed, return connection error
                response = OdooTestResponse(
                    test_type="product",
                    connection=OdooConnectionResponse(**connection_result),
                    products=None,
                    customer=None,
                    timestamp=timestamp,
                    success=False,
                )
                return success_response(response.model_dump())

            # Connection successful, read product
            product_result = odoo_service.read_product(
                product_id=request.product_id, limit=request.limit
            )

            response = OdooTestResponse(
                test_type="product",
                connection=OdooConnectionResponse(**connection_result),
                products=OdooProductResponse(**product_result)
                if product_result
                else None,
                customer=None,
                timestamp=timestamp,
                success=(
                    connection_result["status"] == "success"
                    and product_result["status"] == "success"
                ),
            )

            return success_response(response.model_dump())

        elif request.test_type == "customer":
            # Test connection and create customer
            connection_result = odoo_service.test_connection()

            if connection_result["status"] != "success":
                # Connection failed, return connection error
                response = OdooTestResponse(
                    test_type="customer",
                    connection=OdooConnectionResponse(**connection_result),
                    products=None,
                    customer=None,
                    timestamp=timestamp,
                    success=False,
                )
                return success_response(response.model_dump())

            # Connection successful, validate customer_data
            if not request.customer_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="customer_data is required for customer test type",
                )

            # Create customer
            customer_result = odoo_service.create_customer(
                request.customer_data.model_dump()
            )

            response = OdooTestResponse(
                test_type="customer",
                connection=OdooConnectionResponse(**connection_result),
                products=None,
                customer=OdooCustomerResponse(**customer_result)
                if customer_result
                else None,
                timestamp=timestamp,
                success=(
                    connection_result["status"] == "success"
                    and customer_result["status"] == "success"
                ),
            )

            return success_response(response.model_dump())

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid test_type: {request.test_type}. Use 'connection', 'product', or 'customer'",
            )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Odoo test failed: {str(e)}",
        )
