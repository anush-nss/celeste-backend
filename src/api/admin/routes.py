from datetime import datetime
from typing import Any, Dict, List, Union

from fastapi import APIRouter, HTTPException, status
from google.cloud.firestore import SERVER_TIMESTAMP

from src.api.auth.service import AuthService
from src.integrations.odoo import OdooService, OdooTestRequest, OdooTestResponse, OdooConnectionResponse, OdooProductResponse
from src.integrations.odoo.models import OdooCustomerResponse
from src.shared.database import get_async_db
from src.shared.responses import success_response

dev_router = APIRouter(prefix="/dev", tags=["Development"])
auth_service = AuthService()
odoo_service = OdooService()


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
                products=OdooProductResponse(**product_result) if product_result else None,
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
                customer=OdooCustomerResponse(**customer_result) if customer_result else None,
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
