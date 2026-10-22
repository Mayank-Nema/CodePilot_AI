"""
EmbeddingGenerator — Generate dense vector embeddings for code chunks.

Uses BAAI/bge-m3 via sentence-transformers as the primary embedding model.

Responsibilities:
    - Load the embedding model lazily and efficiently.
    - Format CodeChunk objects into enriched textual representation.
    - Generate batched L2-normalized embeddings for code chunks.
    - Embed text queries for similarity search.
"""

import os
from typing import List, Optional
import numpy as np

# Default embedding model per README section 8
DEFAULT_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")

_model_instance = None


def get_embedding_model(model_name: str = DEFAULT_EMBEDDING_MODEL):
    """Lazily load and return the SentenceTransformer embedding model."""
    global _model_instance
    if _model_instance is None:
        from sentence_transformers import SentenceTransformer

        # Load SentenceTransformer model
        _model_instance = SentenceTransformer(model_name)
    return _model_instance


def format_chunk_for_embedding(chunk) -> str:
    """Format a CodeChunk into a rich textual representation for embedding."""
    header_lines = [
        f"File: {chunk.relative_path}",
        f"Language: {chunk.language}",
        f"Type: {chunk.chunk_type}",
        f"Symbol: {chunk.qualified_name}",
    ]

    if chunk.parent_symbol:
        header_lines.append(f"Parent: {chunk.parent_symbol}")

    if chunk.metadata:
        if "decorators" in chunk.metadata:
            header_lines.append(f"Decorators: {', '.join(chunk.metadata['decorators'])}")
        if "annotations" in chunk.metadata:
            header_lines.append(f"Annotations: {', '.join(chunk.metadata['annotations'])}")
        if "bases" in chunk.metadata:
            header_lines.append(f"Extends: {', '.join(chunk.metadata['bases'])}")

    header = "\n".join(header_lines)
    return f"{header}\n\nCode:\n{chunk.code}"


def embed_chunks(
    chunks: List,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    batch_size: int = 32,
    show_progress: bool = False,
) -> np.ndarray:
    """Generate dense vector embeddings for a list of CodeChunk objects.

    Args:
        chunks: List of CodeChunk objects.
        model_name: HuggingFace model identifier (default BAAI/bge-m3).
        batch_size: Batch size for model inference.
        show_progress: Show progress bar during generation.

    Returns:
        numpy.ndarray of shape (len(chunks), vector_dim) with dtype float32, L2-normalized.
    """
    if not chunks:
        return np.empty((0, 0), dtype=np.float32)

    model = get_embedding_model(model_name)

    texts = [format_chunk_for_embedding(c) for c in chunks]

    # Generate embeddings normalized with L2 norm for cosine similarity
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    return embeddings.astype(np.float32)


def embed_query(query: str, model_name: str = DEFAULT_EMBEDDING_MODEL) -> np.ndarray:
    """Embed a single query string into an L2-normalized float32 vector."""
    model = get_embedding_model(model_name)
    embedding = model.encode(
        query,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return embedding.astype(np.float32)
