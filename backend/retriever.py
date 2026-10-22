"""
HybridRetriever — Multi-strategy code retrieval engine.

Combines:
    1. Semantic retrieval: Vector similarity via FAISS + BGE-M3 embeddings.
    2. Keyword / Lexical retrieval: Exact identifier, file path, symbol name, and term matching.
    3. Structural filtering: AST metadata, chunk types, parent symbols, line ranges.
    4. Reciprocal Rank Fusion (RRF): Blends semantic and keyword rank lists cleanly.

Responsibilities:
    - Provide a unified retrieval interface for RAG context building.
    - Ensure robust performance even when query is purely keyword-focused or conceptual.
"""

import re
import difflib
from typing import Dict, List, Optional, Tuple, Set, Iterable
import numpy as np

from backend.embedding import embed_query
from backend.graph.symbol_graph import SymbolGraph
from backend.vector_store import FAISSVectorStore
from models.code_chunk import CodeChunk


class HybridRetriever:
    """Hybrid Retriever combining Semantic, Keyword, and Structural search with RRF."""

    def __init__(
        self,
        vector_store: Optional[FAISSVectorStore] = None,
        chunks: Optional[List[CodeChunk]] = None,
        rrf_k: int = 60,
        symbol_graph: Optional[SymbolGraph] = None,
    ):
        self.vector_store = vector_store
        self.chunks = chunks or (vector_store.chunks if vector_store else [])
        self.rrf_k = rrf_k
        self.symbol_graph = symbol_graph

    _SOURCE_EXTENSIONS = {
        ".py", ".pyi", ".js", ".jsx", ".ts", ".tsx", ".java", ".go",
        ".rs", ".c", ".h", ".cpp", ".hpp", ".cs", ".rb", ".php",
        ".swift", ".kt", ".kts", ".scala", ".sh", ".sql", ".html",
        ".css", ".scss", ".vue", ".svelte",
    }
    _SOURCE_LANGUAGES = {
        "python", "javascript", "typescript", "java", "go", "rust",
        "c", "c++", "c#", "ruby", "php", "swift", "kotlin", "scala",
        "shell", "sql", "html", "css",
    }

    def search(
        self,
        query: str,
        top_k: int = 5,
        chunk_type_filter: Optional[str] = None,
        language_filter: Optional[str] = None,
        semantic_weight: float = 0.5,
        keyword_weight: float = 0.5,
        excluded_paths: Optional[Iterable[str]] = None,
        source_code_only: Optional[bool] = None,
    ) -> List[Tuple[CodeChunk, float]]:
        """Perform hybrid retrieval using RRF to blend semantic and keyword rankings.

        Args:
            query: Natural language or code search query.
            top_k: Number of final results to return.
            chunk_type_filter: Optional filter by chunk_type (e.g. 'class', 'method').
            language_filter: Optional filter by language.
            semantic_weight: Multiplier weight for semantic RRF score.
            keyword_weight: Multiplier weight for keyword RRF score.

        Returns:
            List of (CodeChunk, hybrid_score) tuples ordered by highest hybrid score.
        """
        if not self.chunks:
            return []

        constraints = self._parse_constraints(query, excluded_paths, source_code_only)
        query_profile = self._query_profile(query)
        resolved_paths, unresolved_paths = self._resolve_paths(query_profile[0])
        if query_profile[0] and unresolved_paths:
            return []
        query_profile = (resolved_paths, query_profile[1])

        # Candidate pool filtering happens before either retrieval strategy.
        candidate_chunks = [
            chunk for chunk in self.chunks
            if self._allowed_chunk(chunk, constraints)
        ]
        if chunk_type_filter:
            candidate_chunks = [c for c in candidate_chunks if c.chunk_type == chunk_type_filter]
        if language_filter:
            candidate_chunks = [c for c in candidate_chunks if c.language == language_filter]

        if not candidate_chunks:
            return []

        fetch_k = min(len(candidate_chunks), top_k * 4)

        # 1. Semantic Search
        semantic_results = self._semantic_search(query, candidate_chunks, top_k=fetch_k)

        # 2. Keyword Search
        keyword_results = self._keyword_search(query, candidate_chunks, top_k=fetch_k)

        # 3. Reciprocal Rank Fusion (RRF)
        hybrid_results = self._reciprocal_rank_fusion(
            semantic_results,
            keyword_results,
            top_k=fetch_k,
            sem_weight=semantic_weight,
            kw_weight=keyword_weight,
        )

        return self._prioritize_results(hybrid_results, query_profile, top_k)

    def resolve_requested_paths(self, query: str) -> Tuple[List[str], List[str], List[str]]:
        """Resolve explicit query paths against indexed chunks.

        Returns requested paths, resolved repository paths, and close suggestions.
        Resolution is intentionally conservative: only exact paths and the common
        Python ``init.py``/``__init__.py`` alias are accepted.
        """
        requested_paths, _ = self._query_profile(query)
        resolved, unresolved = self._resolve_paths(requested_paths)
        suggestions: List[str] = []
        actual_paths = sorted({self._normalize_path(chunk.relative_path) for chunk in self.chunks})
        for path in unresolved:
            suggestions.extend(
                difflib.get_close_matches(path, actual_paths, n=2, cutoff=0.6)
            )
        return sorted(requested_paths), sorted(resolved), sorted(set(suggestions))

    def _resolve_paths(self, requested_paths: Set[str]) -> Tuple[Set[str], Set[str]]:
        actual_paths = {
            self._normalize_path(chunk.relative_path) for chunk in self.chunks
        }
        resolved: Set[str] = set()
        unresolved: Set[str] = set()
        for path in requested_paths:
            if path in actual_paths:
                resolved.add(path)
                continue
            if path.endswith("/init.py"):
                alias = f"{path[:-len('/init.py')]}/__init__.py"
                if alias in actual_paths:
                    resolved.add(alias)
                    continue
            unresolved.add(path)
        return resolved, unresolved

    def _semantic_search(
        self, query: str, candidates: List[CodeChunk], top_k: int
    ) -> List[Tuple[CodeChunk, float]]:
        """Run FAISS vector search if vector store is populated."""
        if not self.vector_store or self.vector_store.total_vectors == 0:
            return []

        try:
            query_vector = embed_query(query)
            candidate_keys = {self._chunk_key(chunk) for chunk in candidates}
            results = self.vector_store.search(query_vector, top_k=top_k)
            return [
                result for result in results
                if self._chunk_key(result[0]) in candidate_keys
            ]
        except Exception:
            return []

    @staticmethod
    def _parse_constraints(
        query: str,
        excluded_paths: Optional[Iterable[str]],
        source_code_only: Optional[bool],
    ) -> Tuple[Set[str], bool]:
        excluded = {HybridRetriever._normalize_path(path) for path in (excluded_paths or [])}
        query_lower = query.lower()
        source_only = source_code_only is True or bool(
            re.search(r"\b(?:use|show|search|look at)\s+only\s+(?:actual\s+)?source\s+code\b", query_lower)
            or re.search(r"\bsource\s+code\s+only\b", query_lower)
        )

        for match in re.finditer(r"\b(?:ignore|exclude|excluding)\s+([^\n]+)", query_lower):
            for item in re.split(r"\s*(?:,|and)\s*", match.group(1)):
                item = item.strip(" `\"'").rstrip("!?;,")
                if item:
                    excluded.add(HybridRetriever._normalize_path(item))
        return excluded, source_only

    @staticmethod
    def _normalize_path(path: str) -> str:
        return path.strip().replace("\\", "/").strip("/").lower()

    def _allowed_chunk(self, chunk: CodeChunk, constraints: Tuple[Set[str], bool]) -> bool:
        excluded, source_only = constraints
        path = self._normalize_path(chunk.relative_path)
        basename = path.rsplit("/", 1)[-1]
        if any(path == item or basename == item.rsplit("/", 1)[-1] for item in excluded):
            return False
        if source_only:
            extension = "." + path.rsplit(".", 1)[-1] if "." in basename else ""
            language = chunk.language.lower()
            if extension not in self._SOURCE_EXTENSIONS and language not in self._SOURCE_LANGUAGES:
                return False
        return True

    @staticmethod
    def _query_profile(query: str) -> Tuple[Set[str], Set[str]]:
        paths = {
            HybridRetriever._normalize_path(match)
            for match in re.findall(r"(?<!\w)(?:[\w.-]+[\\/])*[\w.-]+\.[A-Za-z0-9]+", query)
        }
        symbols = {
            match.lower()
            for match in re.findall(r"(?<![\w.])([A-Za-z_]\w*)(?:\s*\(\s*\))?", query)
            if match.lower() not in {"explain", "describe", "what", "where", "how", "why", "use", "only"}
        }
        return paths, symbols

    def _prioritize_results(
        self,
        results: List[Tuple[CodeChunk, float]],
        query_profile: Tuple[Set[str], Set[str]],
        top_k: int,
    ) -> List[Tuple[CodeChunk, float]]:
        paths, symbols = query_profile
        related_paths: Set[str] = set()
        related_symbols: Set[str] = set()
        for symbol in symbols:
            node = self.symbol_graph.find_node(symbol) if self.symbol_graph else None
            if not node:
                continue
            related_symbols.add(node.qualified_name.lower())
            related_paths.add(self._normalize_path(node.relative_path))
            relationships = (
                self.symbol_graph.get_callers(node.qualified_name)
                + self.symbol_graph.get_callees(node.qualified_name)
            )
            for related_node, _ in relationships:
                related_symbols.add(related_node.qualified_name.lower())
                related_paths.add(self._normalize_path(related_node.relative_path))

        def priority(item: Tuple[CodeChunk, float]) -> Tuple[float, float]:
            chunk, score = item
            path = self._normalize_path(chunk.relative_path)
            symbol = chunk.qualified_name.lower()
            exact_path = 1 if path in paths else 0
            exact_symbol = 1 if symbol in symbols or chunk.name.lower() in symbols else 0
            related = 1 if path in related_paths or symbol in related_symbols else 0
            source = 1 if path.rsplit("/", 1)[-1].rsplit(".", 1)[-1] in {
                ext.lstrip(".") for ext in self._SOURCE_EXTENSIONS
            } else 0
            documentation = 1 if path.endswith((".md", ".rst", ".txt")) else 0
            boost = exact_path * 100 + exact_symbol * 80 + related * 30 + source * 5 - documentation * 5
            return boost, score

        return sorted(results, key=priority, reverse=True)[:top_k]

    def _keyword_search(
        self, query: str, candidates: List[CodeChunk], top_k: int
    ) -> List[Tuple[CodeChunk, float]]:
        """Lexical & keyword search scoring exact identifier, path, and symbol matches."""
        terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 1]
        if not terms:
            return []

        scored_chunks: List[Tuple[CodeChunk, float]] = []

        for chunk in candidates:
            score = 0.0
            name_lower = chunk.name.lower()
            path_lower = chunk.relative_path.lower()
            code_lower = chunk.code.lower()
            parent_lower = (chunk.parent_symbol or "").lower()

            for term in terms:
                # Direct symbol name match (highest score boost)
                if term == name_lower:
                    score += 10.0
                elif term in name_lower:
                    score += 5.0

                # Parent symbol match
                if term == parent_lower:
                    score += 4.0

                # File path match
                if term in path_lower:
                    score += 3.0

                # Code content occurrence count
                matches = code_lower.count(term)
                if matches > 0:
                    score += min(matches * 0.5, 5.0)

            if score > 0:
                scored_chunks.append((chunk, score))

        scored_chunks.sort(key=lambda x: x[1], reverse=True)
        return scored_chunks[:top_k]

    def _reciprocal_rank_fusion(
        self,
        semantic_list: List[Tuple[CodeChunk, float]],
        keyword_list: List[Tuple[CodeChunk, float]],
        top_k: int,
        sem_weight: float = 0.5,
        kw_weight: float = 0.5,
    ) -> List[Tuple[CodeChunk, float]]:
        """Combine two rank lists using Reciprocal Rank Fusion (RRF).

        RRF_Score = sum(weight / (k_rrf + rank))
        """
        chunk_scores: Dict[str, float] = {}
        chunk_map: Dict[str, CodeChunk] = {}

        # Process semantic ranks
        for rank, (chunk, _) in enumerate(semantic_list, 1):
            key = self._chunk_key(chunk)
            chunk_map[key] = chunk
            rrf_score = sem_weight * (1.0 / (self.rrf_k + rank))
            chunk_scores[key] = chunk_scores.get(key, 0.0) + rrf_score

        # Process keyword ranks
        for rank, (chunk, _) in enumerate(keyword_list, 1):
            key = self._chunk_key(chunk)
            chunk_map[key] = chunk
            rrf_score = kw_weight * (1.0 / (self.rrf_k + rank))
            chunk_scores[key] = chunk_scores.get(key, 0.0) + rrf_score

        # Sort merged candidates by highest RRF score
        sorted_keys = sorted(chunk_scores.keys(), key=lambda k: chunk_scores[k], reverse=True)

        results: List[Tuple[CodeChunk, float]] = []
        for key in sorted_keys[:top_k]:
            results.append((chunk_map[key], chunk_scores[key]))

        return results

    @staticmethod
    def _chunk_key(chunk: CodeChunk) -> str:
        return f"{chunk.relative_path}:{chunk.start_line}-{chunk.end_line}:{chunk.name}"
