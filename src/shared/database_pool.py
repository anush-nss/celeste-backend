"""
Optimized database connection manager with pooling for high-performance operations
"""
import asyncio
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from firebase_admin import firestore
import threading

class DatabasePool:
    """
    High-performance database connection pool for Firestore
    Manages connection reuse and parallel operations
    """
    _instance: Optional['DatabasePool'] = None
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
        self._db: Optional[firestore.client] = None
        
        # Thread pool for parallel operations
        self._executor = ThreadPoolExecutor(
            max_workers=20,
            thread_name_prefix="firestore_pool"
        )
        
        # Collection references cache
        self._collections: Dict[str, Any] = {}
    
    def get_client(self):
        """Get optimized Firestore client with connection reuse"""
        if self._db is None:
            # Use the same initialization as the existing database module
            self._db = firestore.client()
            
        return self._db
    
    def get_collection(self, collection_name: str):
        """Get cached collection reference"""
        if collection_name not in self._collections:
            self._collections[collection_name] = self.get_client().collection(collection_name)
        return self._collections[collection_name]
    
    async def batch_get_documents(self, doc_refs: list) -> list:
        """Optimized batch document retrieval"""
        loop = asyncio.get_event_loop()
        
        def _batch_get():
            return list(self.get_client().get_all(doc_refs))
        
        return await loop.run_in_executor(self._executor, _batch_get)
    
    async def parallel_queries(self, queries: list) -> list:
        """Execute multiple queries in parallel"""
        loop = asyncio.get_event_loop()
        
        def _execute_query(query):
            return list(query.stream())
        
        tasks = [
            loop.run_in_executor(self._executor, _execute_query, query)
            for query in queries
        ]
        
        return await asyncio.gather(*tasks)
    
    async def batch_operations(self, operations: list) -> list:
        """Execute multiple operations in parallel"""
        loop = asyncio.get_event_loop()
        
        tasks = [
            loop.run_in_executor(self._executor, op)
            for op in operations
        ]
        
        return await asyncio.gather(*tasks)
    
    def close(self):
        """Clean shutdown of connections"""
        if self._executor:
            self._executor.shutdown(wait=True)

# Global instance
db_pool = DatabasePool()

def get_optimized_db():
    """Get the optimized database connection"""
    return db_pool.get_client()

def get_optimized_collection(collection_name: str):
    """Get cached collection reference"""
    return db_pool.get_collection(collection_name)