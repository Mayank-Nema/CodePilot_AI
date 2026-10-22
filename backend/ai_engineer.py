"""
AIEngineerService — AI Software Engineer core services.

Provides higher-level developer assistance capabilities:
    1. Structural Code Explanation (with symbol metadata, line ranges, callers/callees).
    2. LLM-Assisted Code Review (evaluating modularity, readability, and edge cases).
    3. Bug Investigation Helper (grounded evidence-based inspection).
    4. Automated Documentation Generation (README, Architecture Overview, API Reference).
"""

from typing import Dict, List, Optional, Any

from backend.graph.symbol_graph import SymbolGraph
from backend.llm import OllamaLLM
from backend.rag import RepositoryRAG, RAGResponse
from backend.retriever import HybridRetriever
from models.code_chunk import CodeChunk
from models.repository import RepositoryInfo


class AIEngineerService:
    """Service providing AI Software Engineer tasks using existing RAG, Graph, and LLM services."""

    def __init__(
        self,
        rag: RepositoryRAG,
        symbol_graph: Optional[SymbolGraph] = None,
        llm: Optional[OllamaLLM] = None,
    ):
        self.rag = rag
        self.symbol_graph = symbol_graph or rag.symbol_graph
        self.llm = llm or rag.llm

    def explain_symbol(self, symbol_name: str, chunks: List[CodeChunk]) -> Dict[str, Any]:
        """Generate a structural explanation of a code symbol with callers and callees."""
        node = self.symbol_graph.find_node(symbol_name) if self.symbol_graph else None

        matched_chunks = [c for c in chunks if c.qualified_name.lower() == symbol_name.lower() or c.name.lower() == symbol_name.lower()]
        target_chunk = matched_chunks[0] if matched_chunks else None

        if not node and not target_chunk:
            return {
                "symbol_name": symbol_name,
                "explanation": f"Symbol `{symbol_name}` was not found in the parsed repository symbols.",
                "llm_success": False,
            }

        # Gather callers and callees from SymbolGraph if available
        callers = self.symbol_graph.get_callers(node.qualified_name if node else symbol_name) if self.symbol_graph else []
        callees = self.symbol_graph.get_callees(node.qualified_name if node else symbol_name) if self.symbol_graph else []

        code_text = target_chunk.code if target_chunk else (node.qualified_name if node else "")
        file_path = target_chunk.relative_path if target_chunk else (node.relative_path if node else "Unknown")
        line_range = f"{target_chunk.start_line}-{target_chunk.end_line}" if target_chunk else (f"{node.start_line}-{node.end_line}" if node else "Unknown")

        caller_str = ", ".join([c[0].qualified_name for c in callers[:5]]) if callers else "None detected"
        callee_str = ", ".join([c[0].qualified_name for c in callees[:5]]) if callees else "None detected"

        prompt = f"""Explain the following code symbol structurally and conceptually.

Symbol Name: {symbol_name}
File Path: {file_path} (Lines {line_range})
Callers (who calls this): {caller_str}
Callees (what this calls): {callee_str}

Source Code:
```
{code_text}
```

Provide a clear summary of what this code does, its responsibilities, how it fits into the repository structure, and explain key parameters or logic. Cite {file_path}:{line_range} in your explanation.
"""

        system_prompt = "You are CodePilot AI. Provide a clear, technical, grounded code explanation citing exact line ranges."
        explanation, success = self.llm.generate(prompt=prompt, system_prompt=system_prompt)

        return {
            "symbol_name": symbol_name,
            "file_path": file_path,
            "line_range": line_range,
            "chunk_type": target_chunk.chunk_type if target_chunk else (node.chunk_type if node else "symbol"),
            "code": code_text,
            "callers": [c[0].qualified_name for c in callers],
            "callees": [c[0].qualified_name for c in callees],
            "explanation": explanation,
            "llm_success": success,
        }

    def review_code(self, relative_path: str, chunks: List[CodeChunk]) -> Dict[str, Any]:
        """Perform an LLM-assisted code review for a specific source file.

        Note: LLM-assisted code review evaluates modularity, readability, error handling,
        and edge cases based on code context and AST structure. It complements, but does not replace,
        deterministic static analysis tools.
        """
        file_chunks = [c for c in chunks if c.relative_path == relative_path]

        if not file_chunks:
            return {
                "file_path": relative_path,
                "review": f"No parsed code chunks found for file `{relative_path}`.",
                "llm_success": False,
            }

        # Combine code text from file chunks
        code_blocks = [f"// Lines {c.start_line}-{c.end_line} ({c.chunk_type}: {c.qualified_name})\n{c.code}" for c in file_chunks[:10]]
        combined_code = "\n\n".join(code_blocks)

        prompt = f"""Perform an LLM-assisted code review for the source file `{relative_path}`.

File Code Snippets:
{combined_code}

Format your review into 4 structured sections:
1. 📋 **Overview & Purpose**: Summary of the file's responsibilities.
2. ✅ **Strengths**: Positive architectural practices, clean code usage, or modularity.
3. ⚠️ **Opportunities for Improvement**: Refactoring recommendations, error handling enhancements, or clarity improvements.
4. 💡 **Suggested Actionable Refactorings**: Specific code improvement ideas with line citations.
"""

        system_prompt = "You are CodePilot AI. Perform a thorough, grounded LLM-assisted code review. Cite file paths and line numbers."
        review_text, success = self.llm.generate(prompt=prompt, system_prompt=system_prompt)

        return {
            "file_path": relative_path,
            "chunk_count": len(file_chunks),
            "review": review_text,
            "llm_success": success,
        }

    def investigate_bugs(self, query: str, top_k: int = 5) -> RAGResponse:
        """Perform a targeted bug investigation searching for edge cases or unhandled logic."""
        bug_query = f"Investigate potential bugs, edge cases, missing error handling, or suspicious logic related to: {query}"
        return self.rag.ask(bug_query, top_k=top_k)

    def generate_documentation(
        self,
        doc_type: str,
        repo_info: Optional[RepositoryInfo],
        chunks: List[CodeChunk],
    ) -> Dict[str, Any]:
        """Generate structured documentation (README, Architecture Overview, API Reference)."""
        repo_name = repo_info.name if repo_info else "Repository"
        primary_lang = repo_info.primary_language if repo_info else "Unknown"

        # Summarize key classes and methods from chunks
        top_classes = [c.qualified_name for c in chunks if c.chunk_type in ("class", "interface")][:10]
        top_functions = [c.qualified_name for c in chunks if c.chunk_type in ("function", "method")][:15]

        classes_str = ", ".join(top_classes) if top_classes else "None"
        functions_str = ", ".join(top_functions) if top_functions else "None"

        graph_summary = ""
        if self.symbol_graph:
            graph_summary = f"Total Nodes: {self.symbol_graph.total_nodes}, Total Directed Relationships: {self.symbol_graph.total_edges}"

        if doc_type == "readme":
            prompt = f"""Generate a comprehensive, professional project README.md for the repository `{repo_name}`.

Repository Metadata:
- Name: {repo_name}
- Primary Language: {primary_lang}
- Key Classes/Components: {classes_str}
- Key Functions/Methods: {functions_str}

Include:
- Project Title & Overview
- Key Features & Capabilities
- Architecture Overview
- Core Components & Symbol Reference
- Installation & Usage Guidance
"""
            title = f"README.md — {repo_name}"

        elif doc_type == "architecture":
            prompt = f"""Generate an Architecture Overview document for the repository `{repo_name}`.

Repository Structure:
- Primary Language: {primary_lang}
- System Knowledge Graph Stats: {graph_summary}
- Main Classes/Modules: {classes_str}
- Main Functions: {functions_str}

Include:
- System Architecture Summary
- High-level Data Flow
- Component Responsibilities & Symbol Map
- Architectural Strengths & Key Patterns
"""
            title = f"Architecture Overview — {repo_name}"

        else:  # API / Module Reference
            prompt = f"""Generate an API & Module Reference guide for the repository `{repo_name}`.

Key Symbols in Repository:
- Classes & Interfaces: {classes_str}
- Methods & Functions: {functions_str}

Include:
- Module Breakdown
- Class & Interface Specifications (with responsibilities)
- Key Function Signatures & Descriptions
- Line Range Citations
"""
            title = f"API Reference — {repo_name}"

        system_prompt = "You are CodePilot AI. Generate clean, well-structured GitHub-flavored Markdown documentation based on the provided repository context."
        doc_content, success = self.llm.generate(prompt=prompt, system_prompt=system_prompt)

        return {
            "doc_type": doc_type,
            "title": title,
            "content": doc_content,
            "llm_success": success,
        }
