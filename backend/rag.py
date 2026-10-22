"""
RepositoryRAG — RAG pipeline for grounded repository question-answering.

Orchestrates:
    1. Hybrid retrieval (semantic + keyword + structural) via HybridRetriever.
    2. Optional Code Knowledge Graph context enrichment (callers, callees, impact analysis).
    3. Grounded context formatting with line range citations (path/to/file:L10-L45).
    4. LLM invocation via OllamaLLM with strict system prompt avoiding hallucination.
    5. Diagnostic fallback handling when Ollama is unavailable.
"""

import re
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from backend.graph.symbol_graph import SymbolGraph
from backend.llm import OllamaLLM, DEFAULT_OLLAMA_MODEL
from backend.retriever import HybridRetriever
from models.code_chunk import CodeChunk


@dataclass
class RAGResponse:
    """Structured response from the Repository RAG pipeline."""

    query: str
    answer: str
    retrieved_chunks: List[Tuple[CodeChunk, float]] = field(default_factory=list)
    cited_sources: List[str] = field(default_factory=list)
    llm_success: bool = False
    llm_model: str = ""
    graph_context: Optional[str] = None


SYSTEM_PROMPT = """You are CodePilot AI, an expert software engineering assistant.
Your task is to answer the user's question about the repository based ONLY on the provided source code snippets and structural graph relationships.

CRITICAL RULES:
1. Treat the section labeled SOURCE CODE EVIDENCE as authoritative evidence. Ground every claim strictly in that provided retrieved evidence and the explicitly labeled structural metadata.
2. For implementation questions, inspect the relevant source function or method body line by line.
3. Distinguish the function signature, docstring, executable statements, and inferred or intended purpose. If an executable statement is present, describe its observable behavior.
4. If source contains a call, print, assignment, return, mutation, or other executable statement, acknowledge it accurately. Never say the behavior is unavailable when it is visibly present in SOURCE CODE EVIDENCE.
5. Do NOT infer implementation details. Never reconstruct, invent, or replace retrieved source code with inferred code, `pass`, an empty implementation, return values, or statements that are not present.
6. For code questions, actual source code takes priority over graph metadata, README/documentation, imports, names, project metadata, and unstated conventions.
7. Respect every user-specified source restriction (for example, ignored files or "source code only").
8. ALWAYS cite the exact retrieved file path and line numbers (e.g., `src/auth/UserService.java:42-68`) when discussing code.
9. If the requested implementation is genuinely absent from the retrieved evidence, explicitly say that it cannot be determined. Do not use that response when the exact implementation is visible.
10. Graph metadata may identify relationships, but use retrieved source text for exact implementation and call-site claims. If a relationship has no exact location, say that the location is absent.
11. Quote only the necessary short source fragment when helpful, and keep explanations technical and precise.
"""


class RepositoryRAG:
    """Repository RAG pipeline service."""

    def __init__(
        self,
        retriever: HybridRetriever,
        symbol_graph: Optional[SymbolGraph] = None,
        llm: Optional[OllamaLLM] = None,
    ):
        self.retriever = retriever
        self.symbol_graph = symbol_graph
        if self.retriever.symbol_graph is None:
            self.retriever.symbol_graph = symbol_graph
        self.llm = llm or OllamaLLM()

    def ask(
        self,
        query: str,
        top_k: int = 5,
        llm_model: Optional[str] = None,
    ) -> RAGResponse:
        """Process a developer query through hybrid retrieval, graph enrichment, and LLM generation."""
        if llm_model:
            self.llm.model = llm_model

        requested_paths, resolved_paths, suggestions = self.retriever.resolve_requested_paths(query)
        if requested_paths and not resolved_paths:
            suggestion_text = (
                f" Closest repository path: {suggestions[0]}."
                if suggestions else ""
            )
            return RAGResponse(
                query=query,
                answer=(
                    f"The requested file `{requested_paths[0]}` was not found in the repository."
                    f"{suggestion_text} No source code was retrieved, so I cannot determine its contents."
                ),
                llm_model=self.llm.model,
            )

        # 1. Retrieve candidate code chunks via Hybrid Retriever
        retrieved_chunks = self.retriever.search(query, top_k=top_k)

        # 2. Enrich with SymbolGraph Context if available
        graph_text = self._build_graph_context(query)

        # Collect cited source references
        cited_sources = [
            f"{c.relative_path}:{c.start_line}-{c.end_line}"
            for c, _ in retrieved_chunks
        ]

        if not retrieved_chunks and not graph_text:
            return RAGResponse(
                query=query,
                answer="No relevant code chunks or symbol relationships found in the repository for this query.",
                retrieved_chunks=[],
                cited_sources=[],
                llm_success=False,
                llm_model=self.llm.model,
            )

        # 3. Format Context for LLM
        code_context = self._build_context_text(retrieved_chunks)
        full_context = (
            "SOURCE CODE EVIDENCE (authoritative; actual retrieved source text):\n"
            f"{code_context}"
        )
        if graph_text:
            full_context += (
                "\n\nSTRUCTURAL GRAPH METADATA (relationship evidence, not source code):\n"
                f"{graph_text}"
            )

        user_prompt = f"Question: {query}\n\nRepository Context:\n{full_context}\n\nAnswer:"

        # 4. Call LLM
        answer, success = self.llm.generate(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT,
        )

        return RAGResponse(
            query=query,
            answer=answer,
            retrieved_chunks=retrieved_chunks,
            cited_sources=cited_sources,
            llm_success=success,
            llm_model=self.llm.model,
            graph_context=graph_text,
        )

    def _build_graph_context(self, query: str) -> Optional[str]:
        """Extract relationship graph insights for terms in the query if symbol_graph exists."""
        if not self.symbol_graph or self.symbol_graph.total_nodes == 0:
            return None

        terms = re.findall(r"\w+", query)
        insights = []

        for term in terms:
            if len(term) < 3:
                continue
            node = self.symbol_graph.find_node(term)
            if node:
                callers = self.symbol_graph.get_callers(node.qualified_name)
                callees = self.symbol_graph.get_callees(node.qualified_name)
                impact = self.symbol_graph.get_impact_analysis(node.qualified_name, max_depth=2)

                lines = [f"Symbol: {node.qualified_name} ({node.relative_path}:{node.start_line}-{node.end_line})"]
                if callers:
                    lines.append("  - Called by:")
                    for caller, relationship in callers[:5]:
                        lines.append(self._format_relationship_evidence(caller, relationship))
                if callees:
                    lines.append("  - Calls:")
                    for callee, relationship in callees[:5]:
                        lines.append(self._format_relationship_evidence(callee, relationship))
                if impact:
                    impact_str = ", ".join([imp["qualified_name"] for imp in impact[:5]])
                    lines.append(f"  - Change Impact (dependent code): {impact_str}")

                insights.append("\n".join(lines))

        return "\n".join(insights) if insights else None

    def _format_relationship_evidence(self, node, relationship) -> str:
        """Format relationship metadata together with matching source text."""
        location = f"{node.relative_path}:{node.start_line}-{node.end_line}"
        call_start = relationship.metadata.get("call_start_line")
        call_end = relationship.metadata.get("call_end_line")
        call_location = (
            f"{node.relative_path}:{call_start}-{call_end}"
            if call_start is not None and call_end is not None
            else f"{node.relative_path}:location absent"
        )
        source = next(
            (
                chunk.code
                for chunk in self.retriever.chunks
                if chunk.qualified_name == node.qualified_name
                and chunk.relative_path == node.relative_path
            ),
            None,
        )
        evidence = (
            f"    - {node.qualified_name} in {location}; "
            f"call site: {call_location}"
        )
        if source:
            evidence += f"\n      Source ({location}):\n      {source}"
        return evidence

    @staticmethod
    def _build_context_text(retrieved_chunks: List[Tuple[CodeChunk, float]]) -> str:
        """Format retrieved code chunks into structured context blocks with line references."""
        blocks = []
        for rank, (chunk, score) in enumerate(retrieved_chunks, 1):
            header = (
                f"--- [CHUNK {rank}] ---\n"
                f"File: {chunk.relative_path} (Lines {chunk.start_line}-{chunk.end_line})\n"
                f"Symbol: {chunk.qualified_name} (Type: {chunk.chunk_type}, Language: {chunk.language})\n"
            )
            if chunk.parent_symbol:
                header += f"Parent: {chunk.parent_symbol}\n"

            source_lines = chunk.code.splitlines()
            numbered_source = "\n".join(
                f"{chunk.start_line + offset}: {line}"
                for offset, line in enumerate(source_lines)
            )
            code_block = (
                "SOURCE TEXT (authoritative; line-numbered):\n"
                f"```{chunk.language.lower()}\n{numbered_source}\n```"
            )
            blocks.append(f"{header}{code_block}")

        return "\n\n".join(blocks)
