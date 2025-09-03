from fastapi import APIRouter, HTTPException, status
from typing import Dict, List, Union, Any
from src.core.firebase import get_firestore_db
from src.core.responses import success_response
import firebase_admin
from firebase_admin import auth
from google.cloud.firestore import SERVER_TIMESTAMP

dev_router = APIRouter(prefix="/dev", tags=["Development"])

@dev_router.post("/auth/token", summary="Generate dev token for testing")
async def create_dev_token(uid: str):
    """
    Generate a custom token for testing purposes.
    """
    try:
        custom_token = auth.create_custom_token(uid)
        return success_response({
            "token": custom_token.decode('utf-8'),
            "uid": uid,
            "message": "Development token created successfully"
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create token: {str(e)}"
        )

@dev_router.post("/db/add", summary="Add data to database collection")
async def add_data_to_collection(
    collection: str,
    data: Union[Dict[str, Any], List[Dict[str, Any]]]
):
    """
    Add data to a specified Firestore collection.
    
    - **collection**: Name of the collection to add data to
    - **data**: Single document (dict) or list of documents to add
    """
    try:
        db = get_firestore_db()
        collection_ref = db.collection(collection)
        
        added_documents = []
        
        if isinstance(data, dict):
            # Single document
            doc_ref = collection_ref.document()
            # Add server timestamps
            doc_data = data.copy()
            doc_data.update({
                'created_at': SERVER_TIMESTAMP,
                'updated_at': SERVER_TIMESTAMP
            })
            doc_ref.set(doc_data)
            added_documents.append({
                "id": doc_ref.id,
                "data": data  # Return original data without server timestamp placeholders
            })
        elif isinstance(data, list):
            # Multiple documents
            for item_data in data:
                if isinstance(item_data, dict):
                    doc_ref = collection_ref.document()
                    # Add server timestamps
                    doc_data = item_data.copy()
                    doc_data.update({
                        'created_at': SERVER_TIMESTAMP,
                        'updated_at': SERVER_TIMESTAMP
                    })
                    doc_ref.set(doc_data)
                    added_documents.append({
                        "id": doc_ref.id,
                        "data": item_data  # Return original data without server timestamp placeholders
                    })
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="All items in the list must be dictionaries"
                    )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Data must be a dictionary or a list of dictionaries"
            )
        
        return success_response({
            "collection": collection,
            "documents_added": len(added_documents),
            "documents": added_documents,
            "message": f"Successfully added {len(added_documents)} document(s) to {collection}"
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add data to collection: {str(e)}"
        )

@dev_router.get("/db/collections", summary="List all collections")
async def list_collections():
    """
    List all collections in the database.
    """
    try:
        db = get_firestore_db()
        collections = db.collections()
        collection_names = [collection.id for collection in collections]
        
        return success_response({
            "collections": collection_names,
            "count": len(collection_names)
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list collections: {str(e)}"
        )

@dev_router.get("/db/{collection}", summary="Get all documents from a collection")
async def get_collection_data(collection: str, limit: int = 100):
    """
    Get all documents from a specified collection.
    
    - **collection**: Name of the collection
    - **limit**: Maximum number of documents to return (default: 100)
    """
    try:
        db = get_firestore_db()
        collection_ref = db.collection(collection)
        docs = collection_ref.limit(limit).stream()
        
        documents = []
        for doc in docs:
            doc_data = doc.to_dict()
            if doc_data:
                documents.append({
                    "id": doc.id,
                    "data": doc_data
                })
        
        return success_response({
            "collection": collection,
            "documents": documents,
            "count": len(documents)
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get collection data: {str(e)}"
        )

@dev_router.delete("/db/{collection}", summary="Clear all documents from a collection")
async def clear_collection(collection: str):
    """
    Delete all documents from a specified collection.
    WARNING: This will permanently delete all data in the collection!
    
    - **collection**: Name of the collection to clear
    """
    try:
        db = get_firestore_db()
        collection_ref = db.collection(collection)
        docs = collection_ref.stream()
        
        deleted_count = 0
        for doc in docs:
            doc.reference.delete()
            deleted_count += 1
        
        return success_response({
            "collection": collection,
            "deleted_documents": deleted_count,
            "message": f"Successfully deleted {deleted_count} document(s) from {collection}"
        })
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear collection: {str(e)}"
        )