"""
Unified async database client with connection pooling and Firebase integration
"""
import os
import asyncio
import threading
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

import firebase_admin
from firebase_admin import credentials, auth
from google.cloud import firestore
from dotenv import load_dotenv

load_dotenv()


class AsyncDatabaseClient:
    """
    High-performance async database client for Firestore with Firebase Admin integration
    Manages connection reuse, parallel operations, and authentication
    """
    _instance: Optional['AsyncDatabaseClient'] = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self._initialize_firebase()
        
        # Async Firestore client
        self._async_client: Optional[firestore.AsyncClient] = None
        
        # Sync Firestore client for admin operations
        self._sync_client: Optional[firestore.Client] = None
        
        # Thread pool for sync operations in async context
        self._executor = ThreadPoolExecutor(
            max_workers=20,
            thread_name_prefix="firestore_pool"
        )
        
        # Collection references cache
        self._collections: Dict[str, Any] = {}
        self._async_collections: Dict[str, Any] = {}
    
    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        if not service_account_path:
            raise ValueError("GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
        
        # Initialize Firebase Admin SDK (only if not already initialized)
        if not firebase_admin._apps:
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
    
    async def get_async_client(self) -> firestore.AsyncClient:
        """Get async Firestore client"""
        if self._async_client is None:
            self._async_client = firestore.AsyncClient()
        return self._async_client
    
    def get_sync_client(self) -> firestore.Client:
        """Get sync Firestore client for admin operations"""
        if self._sync_client is None:
            from firebase_admin import firestore as admin_firestore
            self._sync_client = admin_firestore.client()
        return self._sync_client
    
    def get_firebase_auth(self):
        """Get Firebase Auth instance"""
        return auth
    
    async def get_async_collection(self, collection_name: str):
        """Get cached async collection reference"""
        if collection_name not in self._async_collections:
            client = await self.get_async_client()
            self._async_collections[collection_name] = client.collection(collection_name)
        return self._async_collections[collection_name]
    
    def get_sync_collection(self, collection_name: str):
        """Get cached sync collection reference"""
        if collection_name not in self._collections:
            self._collections[collection_name] = self.get_sync_client().collection(collection_name)
        return self._collections[collection_name]
    
    async def batch_get_documents(self, doc_refs: List) -> List:
        """Optimized async batch document retrieval"""
        client = await self.get_async_client()
        return [doc async for doc in client.get_all(doc_refs)]
    
    async def parallel_queries(self, queries: List) -> List:
        """Execute multiple async queries in parallel"""
        tasks = []
        for query in queries:
            tasks.append(self._execute_async_query(query))
        
        return await asyncio.gather(*tasks)
    
    async def _execute_async_query(self, query):
        """Execute a single async query"""
        return [doc async for doc in query.stream()]
    
    async def batch_operations(self, operations: List) -> List:
        """Execute multiple async operations in parallel"""
        return await asyncio.gather(*operations)
    
    async def run_sync_in_executor(self, func, *args):
        """Run sync operations in thread pool"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, func, *args)
    
    async def close(self):
        """Clean shutdown of connections"""
        if self._async_client:
            self._async_client.close()
        
        if self._executor:
            self._executor.shutdown(wait=True)
    
    def __del__(self):
        """Cleanup on deletion"""
        if hasattr(self, '_executor') and self._executor:
            self._executor.shutdown(wait=False)


# Global instance
db_client = AsyncDatabaseClient()


# Async functions (preferred)
async def get_async_db() -> firestore.AsyncClient:
    """Get the async Firestore client"""
    return await db_client.get_async_client()


async def get_async_collection(collection_name: str):
    """Get async collection reference"""
    return await db_client.get_async_collection(collection_name)


# Firebase Auth (sync only)
def get_firebase_auth():
    """Get Firebase Auth instance"""
    return db_client.get_firebase_auth()