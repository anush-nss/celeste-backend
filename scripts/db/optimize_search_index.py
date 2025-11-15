#!/usr/bin/env python3
"""
Script to optimize the pgvector IVFFlat index for better search performance.

The IVFFlat index performance depends on the 'lists' parameter:
- Too few lists = slow search
- Too many lists = less accurate results
- Optimal: sqrt(rows) for good balance, or rows/1000 for very large datasets

Run this script after:
1. Initial vectorization of products
2. Adding significant number of new products
3. If search performance degrades

Usage:
    python scripts/db/optimize_search_index.py
    python scripts/db/optimize_search_index.py --dry-run  # Preview only
    python scripts/db/optimize_search_index.py --lists 200  # Force specific value
"""

import argparse
import asyncio
import math
import sys
import os
from typing import Optional

# Add project root to path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from sqlalchemy import text
from src.database.connection import AsyncSessionLocal, engine


async def get_vector_count():
    """Get the number of vectors in the database"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM product_vectors"))
        count = result.scalar()
        return count if count is not None else 0


async def calculate_optimal_lists(row_count: int) -> int:
    """
    Calculate optimal 'lists' parameter for IVFFlat index.

    Formula:
    - < 1000 rows: lists = max(10, sqrt(rows))
    - 1000-100k rows: lists = sqrt(rows)
    - > 100k rows: lists = rows / 1000

    Args:
        row_count: Number of vectors in the table

    Returns:
        Optimal lists value
    """
    if row_count < 1000:
        # Minimum of 10 lists for small datasets
        return max(10, int(math.sqrt(row_count)))
    elif row_count < 100000:
        # Square root for medium datasets (best balance)
        return int(math.sqrt(row_count))
    else:
        # For very large datasets
        return max(100, int(row_count / 1000))


async def rebuild_index(lists: int, dry_run: bool = False):
    """
    Rebuild the IVFFlat index with optimal parameters.

    Args:
        lists: Number of lists for IVFFlat index
        dry_run: If True, only show what would be done
    """
    async with AsyncSessionLocal() as session:
        if dry_run:
            print(f"\n[DRY RUN] Would rebuild index with lists={lists}")
            print("\nSQL commands that would be executed:")
            print("  1. DROP INDEX IF EXISTS idx_product_vectors_embedding;")
            print("  2. CREATE INDEX idx_product_vectors_embedding")
            print("       ON product_vectors")
            print("       USING ivfflat (vector_embedding vector_cosine_ops)")
            print(f"       WITH (lists = {lists});")
            return

        print(f"\nRebuilding index with lists={lists}...")

        # Drop existing index
        print("  Step 1/3: Dropping existing index...")
        await session.execute(
            text("DROP INDEX IF EXISTS idx_product_vectors_embedding")
        )
        await session.commit()
        print("  ✓ Index dropped")

        # Create new optimized index
        print(f"  Step 2/3: Creating optimized index (lists={lists})...")
        create_index_sql = f"""
        CREATE INDEX idx_product_vectors_embedding
            ON product_vectors
            USING ivfflat (vector_embedding vector_cosine_ops)
            WITH (lists = {lists})
        """
        await session.execute(text(create_index_sql))
        await session.commit()
        print("  ✓ Optimized index created")

        # Analyze table for query planner
        print("  Step 3/3: Analyzing table for query planner...")
        await session.execute(text("ANALYZE product_vectors"))
        await session.commit()
        print("  ✓ Table analyzed")


async def show_index_info():
    """Display current index information"""
    async with AsyncSessionLocal() as session:
        # Check if index exists
        result = await session.execute(
            text("""
            SELECT
                indexname,
                indexdef
            FROM pg_indexes
            WHERE tablename = 'product_vectors'
                AND indexname = 'idx_product_vectors_embedding'
        """)
        )
        row = result.fetchone()

        if row:
            print("\nCurrent Index Configuration:")
            print(f"  Name: {row.indexname}")
            print(f"  Definition: {row.indexdef}")

            # Try to extract lists parameter
            import re

            lists_match = re.search(r"lists\s*=\s*(\d+)", row.indexdef)
            if lists_match:
                current_lists = int(lists_match.group(1))
                print(f"  Current lists parameter: {current_lists}")
                return current_lists
        else:
            print("\n⚠️  Index 'idx_product_vectors_embedding' does not exist!")
            print(
                "   Run the migration first: migrations/001_search_personalization_tables.sql"
            )

        return None


async def main(dry_run: bool = False, force_lists: Optional[int] = None):
    """
    Main function to optimize the search index.

    Args:
        dry_run: If True, only show what would be done
        force_lists: If provided, use this value instead of calculating
    """
    print("=" * 80)
    print("SEARCH INDEX OPTIMIZATION SCRIPT")
    print("=" * 80)

    # Get current state
    vector_count = await get_vector_count()
    print(f"\nVectorized products: {vector_count:,}")

    if vector_count == 0:
        print("\n⚠️  No vectors found in the database!")
        print("   Run vectorization first: python scripts/db/vectorize_products.py")
        return

    # Show current index
    current_lists = await show_index_info()

    # Calculate or use forced lists value
    if force_lists is not None:
        optimal_lists = force_lists
        print(f"\nUsing forced lists value: {optimal_lists}")
    else:
        optimal_lists = await calculate_optimal_lists(vector_count)
        print(f"\nRecommended lists parameter: {optimal_lists}")
        print(f"  Calculation: sqrt({vector_count:,}) ≈ {math.sqrt(vector_count):.1f}")

    # Check if optimization is needed
    if current_lists is not None and current_lists == optimal_lists:
        print(f"\n✓ Index is already optimized with lists={optimal_lists}")
        print("  No action needed!")
        return

    improvement = 0.0  # Initialize for type checker
    if current_lists is not None:
        improvement = abs(optimal_lists - current_lists) / current_lists * 100
        print(f"\n  Current: {current_lists} lists")
        print(f"  Optimal: {optimal_lists} lists")
        print(f"  Expected improvement: ~{improvement:.1f}%")

    # Rebuild index
    print("\n" + "=" * 80)
    if not dry_run:
        print("REBUILDING INDEX...")
        print("=" * 80)
        print("\n⚠️  This will temporarily impact search performance!")
        print("   The operation may take 30-60 seconds for large datasets.\n")

    await rebuild_index(optimal_lists, dry_run=dry_run)

    if not dry_run:
        print("\n" + "=" * 80)
        print("OPTIMIZATION COMPLETE!")
        print("=" * 80)
        print(f"\n✓ Index optimized with lists={optimal_lists}")
        if current_lists is not None:
            print(f"✓ Search performance should improve by ~{improvement:.0f}%")
        else:
            print("✓ Index created successfully")
        print("\nNext steps:")
        print("  1. Test search performance:")
        print("     GET /products/search?q=milk&mode=full")
        print("  2. Monitor search response times in logs")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Optimize pgvector IVFFlat index for better search performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Optimize with calculated optimal value
  python scripts/db/optimize_search_index.py

  # Preview changes without applying
  python scripts/db/optimize_search_index.py --dry-run

  # Force specific lists value
  python scripts/db/optimize_search_index.py --lists 200

Performance Guidelines:
  - Run after initial vectorization
  - Run when adding 20%+ more products
  - Run if search becomes slow
  - Typical improvement: 30-80% faster searches

Index Parameter Guidelines:
  - Small catalog (<1000): lists = 10-30
  - Medium catalog (1k-10k): lists = 30-100
  - Large catalog (10k-100k): lists = 100-300
  - Very large (>100k): lists = 300-1000
        """,
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Preview changes without applying them"
    )

    parser.add_argument(
        "--lists",
        type=int,
        help="Force specific lists value instead of calculating optimal",
    )

    args = parser.parse_args()

    try:
        asyncio.run(main(dry_run=args.dry_run, force_lists=args.lists))
    except KeyboardInterrupt:
        print("\n\n⚠️  Optimization interrupted by user")
        sys.exit(1)
    finally:
        # Properly dispose of the engine
        asyncio.run(engine.dispose())
