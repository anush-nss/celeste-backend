"""Shared Firestore client for connection reuse"""
from google.cloud import firestore
from functools import lru_cache

@lru_cache(maxsize=1)
def get_firestore_client():
    """Get a cached Firestore client instance"""
    return firestore.Client()

# Global client instance
db_client = get_firestore_client()