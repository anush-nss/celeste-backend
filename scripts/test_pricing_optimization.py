#!/usr/bin/env python3
"""
Performance test for optimized product pricing queries
"""
import asyncio
import time
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.products.service import ProductService
from src.api.products.models import ProductQuerySchema

async def test_optimized_vs_original():
    """Test the performance difference between optimized and original implementations"""
    product_service = ProductService()
    
    # Test with a simple query
    query_params = ProductQuerySchema(
        limit=50,
        include_pricing=True,
        cursor=None,
        include_categories=True
    )
    
    print("Testing optimized implementation...")
    start_time = time.time()
    try:
        result_optimized = await product_service.get_products_with_pagination_optimized(
            query_params=query_params,
            customer_tier=1  # Bronze tier
        )
        print(f"Optimized implementation returned {len(result_optimized.products)} products")
        print(f"Execution time: {time.time() - start_time:.4f} seconds")
    except Exception as e:
        print(f"Optimized implementation error: {e}")
        return

if __name__ == "__main__":
    asyncio.run(test_optimized_vs_original())
