"""
VectorStore — FAISS vector storage & similarity search engine.

Responsibilities:
    - Manage a local FAISS index (IndexFlatIP for cosine similarity on L2-normalized vectors).
    - Map vector IDs to CodeChunk objects and metadata.
    - Provide fast similarity search.
    - Persist index (.faiss) and metadata (.json) to disk.
    - Load saved index and metadata payloads.
"""

import json
from dataclasses import asdict
import os
from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np

import faiss

from models.code_chunk import CodeChunk


class FAISSVectorStore:
    """Vector store using FAISS for local similarity search."""

    def __init__(self, dimension: Optional[int] = None):
        self.dimension = dimension
        self.index: Optional[faiss.Index] = None
        self.chunks: List[CodeChunk] = []

        if dimension is not None:
            self._init_index(dimension)

    def _init_index(self, dimension: int):
        """Initialize FAISS IndexFlatIP (Inner Product = Cosine Similarity for L2-normalized vectors)."""
        self.dimension = dimension
        self.index = faiss.IndexFlatIP(dimension)

    def add_chunks(self, chunks: List[CodeChunk], embeddings: np.ndarray):
        """Add CodeChunks and their embedding vectors to the FAISS index.

        Args:
            chunks: List of CodeChunk objects.
            embeddings: numpy ndarray of shape (N, dim) with float32 type.
        """
        if not chunks or len(chunks) == 0:
            return

        if embeddings.ndim == 1:
            embeddings = np.expand_dims(embeddings, axis=0)

        num_vectors, dim = embeddings.shape

        if self.index is None:
            self._init_index(dim)

        if dim != self.dimension:
            raise ValueError(f"Embedding dimension {dim} does not match index dimension {self.dimension}")

        # Ensure float32 and C-contiguous array for FAISS
        embeddings_f32 = np.ascontiguousarray(embeddings.astype(np.float32))

        self.index.add(embeddings_f32)
        self.chunks.extend(chunks)

    def search(
        self, query_vector: np.ndarray, top_k: int = 5
    ) -> List[Tuple[CodeChunk, float]]:
        """Search the index for the top-k most similar chunks.

        Args:
            query_vector: 1D or 2D query embedding vector.
            top_k: Number of nearest results to retrieve.

        Returns:
            List of (CodeChunk, similarity_score) tuples, ordered by highest similarity.
        """
        if self.index is None or self.index.ntotal == 0 or len(self.chunks) == 0:
            return []

        if query_vector.ndim == 1:
            query_vector = np.expand_dims(query_vector, axis=0)

        query_f32 = np.ascontiguousarray(query_vector.astype(np.float32))

        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query_f32, k)

        results: List[Tuple[CodeChunk, float]] = []
        for idx, score in zip(indices[0], scores[0]):
            if idx != -1 and idx < len(self.chunks):
                results.append((self.chunks[idx], float(score)))

        return results

    def save(self, dir_path: str):
        """Save the FAISS index and chunk metadata to the specified directory."""
        save_dir = Path(dir_path)
        save_dir.mkdir(parents=True, exist_ok=True)

        index_file = save_dir / "index.faiss"
        metadata_file = save_dir / "metadata.json"

        if self.index is not None:
            faiss.write_index(self.index, str(index_file))

        # Serialize chunks as JSON
        chunk_dicts = [asdict(chunk) for chunk in self.chunks]
        payload = {
            "dimension": self.dimension,
            "total_chunks": len(self.chunks),
            "chunks": chunk_dicts,
        }

        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    @classmethod
    def load(cls, dir_path: str) -> "FAISSVectorStore":
        """Load a FAISSVectorStore instance from disk."""
        load_dir = Path(dir_path)
        index_file = load_dir / "index.faiss"
        metadata_file = load_dir / "metadata.json"

        if not index_file.exists() or not metadata_file.exists():
            raise FileNotFoundError(f"Missing vector store index files in {dir_path}")

        with open(metadata_file, "r", encoding="utf-8") as f:
            payload = json.load(f)

        dimension = payload.get("dimension")
        instance = cls(dimension=dimension)

        instance.index = faiss.read_index(str(index_file))

        chunks_data = payload.get("chunks", [])
        instance.chunks = [CodeChunk(**cd) for cd in chunks_data]

        return instance

    def clear(self):
        """Clear the index and metadata."""
        self.index = None
        self.chunks = []
        self.dimension = None

    @property
    def total_vectors(self) -> int:
        """Total vectors currently in the store."""
        if self.index is None:
            return 0
        return self.index.ntotal
