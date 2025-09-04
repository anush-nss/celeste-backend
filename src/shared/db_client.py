"""Shared Firestore client for connection reuse"""
from google.cloud import firestore

# Global async client instance
db_client = firestore.AsyncClient()