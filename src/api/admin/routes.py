from fastapi import APIRouter, HTTPException, status
from typing import Dict, List, Union, Any
from src.shared.database import get_async_db, get_async_collection
from src.shared.responses import success_response
from src.api.auth.service import AuthService
from google.cloud.firestore import SERVER_TIMESTAMP
from datetime import datetime

dev_router = APIRouter(prefix="/dev", tags=["Development"])
auth_service = AuthService()


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
                    if hasattr(value, 'timestamp'):  # DatetimeWithNanoseconds object
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
