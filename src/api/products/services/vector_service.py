import gc
import json
import logging
from typing import List, Optional

from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sqlalchemy import text
from sqlalchemy.future import select

from src.config.constants import (
    NEXT_DAY_DELIVERY_ONLY_TAG_ID,
    SEARCH_TFIDF_MAX_FEATURES,
    SEARCH_VECTOR_DIM,
    SENTENCE_TRANSFORMER_MODEL,
)
from src.database.connection import AsyncSessionLocal
from src.database.models.product import Product
from src.database.models.product_vector import ProductVector
from src.shared.error_handler import ErrorHandler


class VectorService:
    """
    Service for creating and managing product vector embeddings.

    Handles:
    - Sentence transformer embeddings (semantic search)
    - TF-IDF vectorization (keyword search)
    - Batch processing for efficiency
    - Text preprocessing and combination
    - Memory-optimized for low-resource environments
    """

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)
        self._model: Optional[SentenceTransformer] = None
        self._tfidf_vectorizer: Optional[TfidfVectorizer] = None
        self.logger = logging.getLogger(__name__)

    def _load_model(self):
        """Lazy load the sentence transformer model with memory optimization"""
        if self._model is None:
            self.logger.info(
                f"Loading sentence transformer model: {SENTENCE_TRANSFORMER_MODEL}"
            )
            # Load model from local cache (no HuggingFace API calls)
            # local_files_only=True prevents any internet access to HuggingFace Hub
            self._model = SentenceTransformer(
                SENTENCE_TRANSFORMER_MODEL,
                device="cpu",  # Force CPU to avoid GPU memory issues
                cache_folder=None,  # Use default cache (~/.cache/huggingface or container cache)
                local_files_only=True,  # CRITICAL: Never contact HuggingFace API
            )
            self.logger.info("Model loaded successfully from local cache")
        return self._model

    def _unload_model(self):
        """Unload model from memory to free resources"""
        if self._model is not None:
            self.logger.info("Unloading model to free memory")
            del self._model
            self._model = None
            # Force garbage collection
            gc.collect()
            self.logger.info("Model unloaded")

    def _get_tfidf_vectorizer(self):
        """Get or create TF-IDF vectorizer"""
        if self._tfidf_vectorizer is None:
            self._tfidf_vectorizer = TfidfVectorizer(
                max_features=SEARCH_TFIDF_MAX_FEATURES,
                stop_words="english",
                ngram_range=(1, 2),  # Unigrams and bigrams
                min_df=2,  # Ignore terms that appear in less than 2 documents
            )
        return self._tfidf_vectorizer

    async def _build_product_text(self, product_id: int, session) -> Optional[str]:
        """
        Build comprehensive searchable text for a product.

        Combines: name, description, brand, category names, tag names
        Excludes: NEXT_DAY_DELIVERY_ONLY tag
        """
        query = text("""
            SELECT
                p.name,
                p.description,
                p.brand,
                STRING_AGG(DISTINCT c.name, ' ') as category_names,
                STRING_AGG(DISTINCT c.description, ' ') as category_descriptions,
                STRING_AGG(DISTINCT t.name, ' ') FILTER (WHERE t.id != :excluded_tag_id) as tag_names
            FROM products p
            LEFT JOIN product_categories pc ON p.id = pc.product_id
            LEFT JOIN categories c ON pc.category_id = c.id
            LEFT JOIN product_tags pt ON p.id = pt.product_id
            LEFT JOIN tags t ON pt.tag_id = t.id
            WHERE p.id = :product_id
            GROUP BY p.id, p.name, p.description, p.brand
        """)

        result = await session.execute(
            query,
            {
                "product_id": product_id,
                "excluded_tag_id": NEXT_DAY_DELIVERY_ONLY_TAG_ID,
            },
        )
        row = result.fetchone()

        if not row:
            return None

        # Combine all text fields
        text_parts = []

        # Name is most important (weight it by repeating)
        if row.name:
            text_parts.extend([row.name] * 3)

        # Description
        if row.description:
            text_parts.append(row.description)

        # Brand
        if row.brand:
            text_parts.extend([row.brand] * 2)

        # Category names
        if row.category_names:
            text_parts.extend([row.category_names] * 2)

        # Category descriptions
        if row.category_descriptions:
            text_parts.append(row.category_descriptions)

        # Tag names
        if row.tag_names:
            text_parts.append(row.tag_names)

        # Join and clean
        combined_text = " ".join(text_parts)
        # Remove extra whitespace
        combined_text = " ".join(combined_text.split())

        return combined_text if combined_text else None

    async def vectorize_product(self, product_id: int, version: int = 1) -> bool:
        """
        Create or update vector embedding for a single product.

        Args:
            product_id: Product ID to vectorize
            version: Embedding model version

        Returns:
            True if successful, False otherwise
        """
        try:
            async with AsyncSessionLocal() as session:
                # Build searchable text
                text_content = await self._build_product_text(product_id, session)

                if not text_content:
                    self.logger.warning(
                        f"No text content found for product {product_id}"
                    )
                    return False

                # Load model
                model = self._load_model()

                # Generate embedding
                embedding = model.encode(text_content, convert_to_numpy=True)

                # Verify embedding dimensions
                if embedding.shape[0] != SEARCH_VECTOR_DIM:
                    self.logger.error(
                        f"Embedding dimension mismatch: expected {SEARCH_VECTOR_DIM}, got {embedding.shape[0]}"
                    )
                    return False

                # Check if vector already exists
                result = await session.execute(
                    select(ProductVector).where(ProductVector.product_id == product_id)
                )
                existing_vector = result.scalars().first()

                if existing_vector:
                    # Update existing
                    existing_vector.vector_embedding = embedding.tolist()
                    existing_vector.text_content = text_content
                    existing_vector.version = version
                else:
                    # Create new
                    new_vector = ProductVector(
                        product_id=product_id,
                        vector_embedding=embedding.tolist(),
                        text_content=text_content,
                        version=version,
                    )
                    session.add(new_vector)

                await session.commit()
                self.logger.info(f"Vectorized product {product_id}")
                return True

        except Exception as e:
            self.logger.error(f"Error vectorizing product {product_id}: {e}")
            return False

    async def vectorize_products_batch(
        self,
        product_ids: List[int],
        version: int = 1,
        batch_size: int = 8,  # Reduced from 32 for memory efficiency
    ) -> dict:
        """
        Vectorize multiple products in batches for efficiency.
        Optimized for low-memory environments.

        Args:
            product_ids: List of product IDs to vectorize
            version: Embedding model version
            batch_size: Number of products to process at once (default: 8 for low memory)

        Returns:
            dict with success/failure counts
        """
        results = {"success": 0, "failed": 0, "skipped": 0}

        try:
            # Load model once for all batches
            model = self._load_model()

            async with AsyncSessionLocal() as session:
                # Process in smaller chunks to avoid memory issues
                chunk_size = 50  # Process 50 products at a time
                for chunk_start in range(0, len(product_ids), chunk_size):
                    chunk_ids = product_ids[chunk_start : chunk_start + chunk_size]

                    # Build text for chunk
                    text_data = []
                    for product_id in chunk_ids:
                        text_content = await self._build_product_text(
                            product_id, session
                        )
                        if text_content:
                            text_data.append((product_id, text_content))
                        else:
                            results["skipped"] += 1

                    if not text_data:
                        continue

                    # Process chunk in smaller batches
                    for i in range(0, len(text_data), batch_size):
                        batch = text_data[i : i + batch_size]
                        batch_ids = [item[0] for item in batch]
                        batch_texts = [item[1] for item in batch]
                        batch_len = len(batch)  # Store length before potential deletion

                        try:
                            # Generate embeddings for batch
                            embeddings = model.encode(
                                batch_texts,
                                convert_to_numpy=True,
                                show_progress_bar=False,  # Disable for less output
                                batch_size=batch_size,
                                normalize_embeddings=False,  # Skip normalization to save memory
                            )

                            # Store embeddings
                            for product_id, text_content, embedding in zip(
                                batch_ids, batch_texts, embeddings
                            ):
                                try:
                                    # Check if exists
                                    result = await session.execute(
                                        select(ProductVector).where(
                                            ProductVector.product_id == product_id
                                        )
                                    )
                                    existing_vector = result.scalars().first()

                                    if existing_vector:
                                        existing_vector.vector_embedding = (
                                            embedding.tolist()
                                        )
                                        existing_vector.text_content = text_content
                                        existing_vector.version = version
                                    else:
                                        new_vector = ProductVector(
                                            product_id=product_id,
                                            vector_embedding=embedding.tolist(),
                                            text_content=text_content,
                                            version=version,
                                        )
                                        session.add(new_vector)

                                    results["success"] += 1

                                except Exception as e:
                                    self.logger.error(
                                        f"Error storing vector for product {product_id}: {e}"
                                    )
                                    results["failed"] += 1

                            # Commit batch
                            await session.commit()

                            # Clear batch data from memory
                            del embeddings, batch_texts, batch_ids, batch

                            total_processed = results["success"] + results["failed"]
                            if total_processed % 20 == 0:
                                self.logger.info(
                                    f"Processed {total_processed} products..."
                                )
                                # Periodic garbage collection
                                gc.collect()

                        except Exception as e:
                            self.logger.error(f"Error processing batch: {e}")
                            results["failed"] += batch_len
                            await session.rollback()

                    # Clear chunk data
                    del text_data
                    gc.collect()

        except Exception as e:
            self.logger.error(f"Error in batch vectorization: {e}")
        finally:
            # Always unload model to free memory
            self._unload_model()

        self.logger.info(
            f"Vectorization complete: {results['success']} success, "
            f"{results['failed']} failed, {results['skipped']} skipped"
        )
        return results

    async def vectorize_all_products(
        self, version: int = 1, only_missing: bool = False
    ) -> dict:
        """
        Vectorize products in the database.

        Args:
            version: Embedding model version
            only_missing: If True, only vectorize products that don't have a vector yet.
                          If False, process all products.

        Returns:
            dict with success/failure counts
        """
        if only_missing:
            self.logger.info("Starting vectorization for products missing a vector")
        else:
            self.logger.info("Starting vectorization for all products")

        try:
            async with AsyncSessionLocal() as session:
                if only_missing:
                    # Get product IDs that are not in product_vectors
                    query = text("""
                        SELECT p.id
                        FROM products p
                        LEFT JOIN product_vectors pv ON p.id = pv.product_id
                        WHERE pv.product_id IS NULL
                    """)
                    result = await session.execute(query)
                else:
                    # Get all product IDs
                    result = await session.execute(select(Product.id))

                product_ids = [row[0] for row in result.fetchall()]

                if only_missing:
                    self.logger.info(
                        f"Found {len(product_ids)} products missing a vector"
                    )
                else:
                    self.logger.info(
                        f"Found {len(product_ids)} total products to process"
                    )

                if not product_ids:
                    return {"success": 0, "failed": 0, "skipped": 0}

                # Vectorize in batches
                return await self.vectorize_products_batch(product_ids, version)

        except Exception as e:
            self.logger.error(f"Error vectorizing all products: {e}")
            return {"success": 0, "failed": 0, "skipped": 0}

    async def update_product_vector(self, product_id: int) -> bool:
        """
        Update vector for a product (e.g., when product is updated).

        Args:
            product_id: Product ID to update

        Returns:
            True if successful
        """
        return await self.vectorize_product(product_id)

    async def delete_product_vector(self, product_id: int) -> bool:
        """
        Delete vector for a product.

        Args:
            product_id: Product ID

        Returns:
            True if successful
        """
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(ProductVector).where(ProductVector.product_id == product_id)
                )
                vector = result.scalars().first()

                if vector:
                    await session.delete(vector)
                    await session.commit()
                    self.logger.info(f"Deleted vector for product {product_id}")
                    return True
                else:
                    self.logger.warning(f"No vector found for product {product_id}")
                    return False

        except Exception as e:
            self.logger.error(f"Error deleting vector for product {product_id}: {e}")
            return False

    async def find_similar_products(
        self,
        product_id: int,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> List[tuple]:
        """
        Find products similar to a given product using vector similarity.

        Uses cosine similarity with pgvector for efficient similarity search.

        Args:
            product_id: Product ID to find similar products for
            limit: Maximum number of similar products to return
            min_similarity: Minimum similarity threshold (0.0 to 1.0)

        Returns:
            List of tuples: (product_id, similarity_score)
            Sorted by similarity score descending
        """
        try:
            async with AsyncSessionLocal() as session:
                # Get the vector for the source product
                result = await session.execute(
                    select(ProductVector).where(ProductVector.product_id == product_id)
                )
                source_vector = result.scalars().first()

                if not source_vector:
                    self.logger.warning(f"No vector found for product {product_id}")
                    return []

                # Find similar products using cosine similarity
                # <=> is the cosine distance operator (1 - cosine similarity)
                # So we calculate similarity as 1 - distance
                similarity_query = text("""
                    SELECT
                        pv.product_id,
                        1 - (pv.vector_embedding <=> CAST(:query_vector AS vector)) AS similarity
                    FROM product_vectors pv
                    WHERE pv.product_id != :product_id
                        AND (1 - (pv.vector_embedding <=> CAST(:query_vector AS vector))) >= :min_similarity
                    ORDER BY similarity DESC
                    LIMIT :limit
                """)

                # Convert vector to list for JSON serialization
                vector_data = source_vector.vector_embedding
                if hasattr(vector_data, "tolist"):
                    vector_list = vector_data.tolist()  # type: ignore
                else:
                    vector_list = vector_data

                result = await session.execute(
                    similarity_query,
                    {
                        "query_vector": json.dumps(vector_list),
                        "product_id": product_id,
                        "min_similarity": min_similarity,
                        "limit": limit,
                    },
                )

                # Return list of (product_id, similarity_score) tuples
                similar_products = [
                    (row.product_id, float(row.similarity)) for row in result.fetchall()
                ]

                self.logger.info(
                    f"Found {len(similar_products)} similar products for product {product_id}"
                )
                return similar_products

        except Exception as e:
            self.logger.error(
                f"Error finding similar products for product {product_id}: {e}",
                exc_info=True,
            )
            return []
