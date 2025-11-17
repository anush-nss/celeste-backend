#!/usr/bin/env python3
"""
Script to create vector embeddings for products.

Default behavior: Only creates embeddings for products that are missing them.
Use the --force flag to update embeddings for all products.

This script uses sentence-transformers for semantic search functionality.
"""

import argparse
import asyncio
import os
import sys
from typing import Optional

# Add the project root to the Python path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from src.api.products.services.vector_service import VectorService
from src.database.connection import engine


async def vectorize_all(force: bool = False, batch_size: int = 8):
    """
    Vectorize products in the database.

    Args:
        force: If True, re-vectorize all products. Otherwise, only vectorize
               products that are missing a vector.
        batch_size: Number of products to process in each batch.
    """
    print("=" * 80)
    print("PRODUCT VECTORIZATION SCRIPT")
    print("=" * 80)
    print()

    only_missing = not force
    if only_missing:
        print("MODE: Vectorizing products missing an embedding.")
    else:
        print("⚠️  FORCE MODE: Vectorizing all products.")

    print(f"Batch size: {batch_size} products")
    print(f"Memory optimization: {'ENABLED' if batch_size <= 8 else 'DISABLED'}")
    print()

    vector_service = VectorService()

    try:
        # Vectorize products based on the selected mode
        results = await vector_service.vectorize_all_products(
            version=1, only_missing=only_missing
        )

        # Display results
        print()
        print("=" * 80)
        print("VECTORIZATION RESULTS")
        print("=" * 80)
        print(f"✅ Successfully vectorized: {results['success']} products")
        print(f"❌ Failed to vectorize:    {results['failed']} products")
        print(f"⏭️  Skipped (no text):      {results['skipped']} products")
        print()

        total = results["success"] + results["failed"] + results["skipped"]
        if total > 0:
            success_rate = (results["success"] / total) * 100
            print(f"Success rate: {success_rate:.1f}%")
        print()

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


async def vectorize_product(product_id: int):
    """
    Vectorize a specific product.

    Args:
        product_id: Product ID to vectorize
    """
    print("=" * 80)
    print(f"VECTORIZING PRODUCT ID: {product_id}")
    print("=" * 80)
    print()

    vector_service = VectorService()

    try:
        success = await vector_service.vectorize_product(product_id, version=1)

        print()
        if success:
            print(f"✅ Successfully vectorized product {product_id}")
        else:
            print(f"❌ Failed to vectorize product {product_id}")
            sys.exit(1)

    except Exception as e:
        print(f"❌ ERROR: {e}")
        sys.exit(1)


async def main(
    force: bool = False,
    product_id: Optional[int] = None,
    batch_size: int = 8,
):
    """
    Main function that runs vectorization.

    Args:
        force: If True, re-vectorize all products.
        product_id: Vectorize a specific product ID.
        batch_size: Batch size for processing.
    """
    try:
        if product_id is not None:
            # Vectorize specific product
            await vectorize_product(product_id)
        else:
            # Vectorize products (either all or just missing)
            await vectorize_all(force=force, batch_size=batch_size)

        print("=" * 80)
        print("VECTORIZATION COMPLETE")
        print("=" * 80)
        print()
        print("Next steps:")
        print("  1. Verify vectors were created:")
        print("     SELECT COUNT(*) FROM product_vectors;")
        print()
        print("  2. Test search functionality:")
        print("     GET /products/search?q=organic&mode=full")
        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  Vectorization interrupted by user")
        sys.exit(1)

    finally:
        # Properly dispose of the engine to close all connections
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create and update vector embeddings for products.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Vectorize only products that are missing an embedding (default behavior)
  python scripts/db/vectorize_products.py

  # Re-vectorize ALL products, updating existing ones
  python scripts/db/vectorize_products.py --force

  # Vectorize a specific product by its ID
  python scripts/db/vectorize_products.py --product-id 123

  # Use a custom batch size (e.g., if you have more memory available)
  python scripts/db/vectorize_products.py --batch-size 16

Notes:
  - The default behavior is the most efficient for regular updates.
  - Use --force after significant changes to product text generation logic.
  - First run may take several minutes for large product catalogs.
  - Requires sentence-transformers package (model is pre-cached in Docker image).
        """,
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-vectorize all products, updating existing embeddings. Default is to only create for missing.",
    )

    parser.add_argument(
        "--product-id",
        type=int,
        help="Vectorize a specific product by ID, ignoring other modes.",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=8,
        help="Batch size for vectorization (default: 8, optimized for 1GB RAM).",
    )

    args = parser.parse_args()

    # Run vectorization
    asyncio.run(
        main(force=args.force, product_id=args.product_id, batch_size=args.batch_size)
    )
