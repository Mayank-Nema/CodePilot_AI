"""
RelationshipBuilder — Extract structural & invocation relationships from CodeChunks.

Populates SymbolGraph with:
    - contains: Parent class/module -> child method/function/field
    - extends: Subclass -> Base class
    - implements: Class -> Interface
    - imports: File -> Imported module/symbol
    - calls / uses: Method/Function -> Target method call (text-based heuristic)
"""

import re
from typing import List, Set

from backend.graph.symbol_graph import SymbolGraph, SymbolNode
from models.code_chunk import CodeChunk


def build_symbol_graph(chunks: List[CodeChunk]) -> SymbolGraph:
    """Build an in-memory SymbolGraph from a list of CodeChunks.

    Args:
        chunks: List of parsed CodeChunk objects.

    Returns:
        Populated SymbolGraph object.
    """
    graph = SymbolGraph()

    if not chunks:
        return graph

    # Step 1: Add all chunks as SymbolNodes
    all_symbol_names: Set[str] = set()

    for chunk in chunks:
        node = SymbolNode(
            qualified_name=chunk.qualified_name,
            name=chunk.name,
            chunk_type=chunk.chunk_type,
            file_path=chunk.file_path,
            relative_path=chunk.relative_path,
            language=chunk.language,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            parent_symbol=chunk.parent_symbol,
            metadata=chunk.metadata,
        )
        graph.add_node(node)
        all_symbol_names.add(chunk.name)
        all_symbol_names.add(chunk.qualified_name)

    # Step 2: Build Relationships
    for chunk in chunks:
        source_name = chunk.qualified_name

        # 2a. Parent-Child ('contains')
        if chunk.parent_symbol:
            graph.add_edge(
                source=chunk.parent_symbol,
                target=source_name,
                relation_type="contains",
                metadata={"type": "hierarchy"},
            )

        # 2b. Inheritance ('extends')
        if "bases" in chunk.metadata:
            for base in chunk.metadata["bases"]:
                graph.add_edge(source=source_name, target=base, relation_type="extends")
        if "extends" in chunk.metadata:
            base = chunk.metadata["extends"]
            if base:
                graph.add_edge(source=source_name, target=base, relation_type="extends")

        # 2c. Interface Implementation ('implements')
        if "implements" in chunk.metadata:
            for iface in chunk.metadata["implements"]:
                graph.add_edge(source=source_name, target=iface, relation_type="implements")

        # 2d. Module Imports ('imports')
        if chunk.chunk_type == "import":
            target_import = chunk.name.replace("import ", "").replace("from ", "").strip()
            graph.add_edge(
                source=chunk.relative_path,
                target=target_import,
                relation_type="imports",
            )

        # 2e. Function/Method Call Detection (text-based heuristic)
        if chunk.chunk_type in ("method", "function", "constructor"):
            called_symbols = _detect_method_call_lines(chunk.code, chunk.name, all_symbol_names)
            for target, call_lines in called_symbols.items():
                graph.add_edge(
                    source=source_name,
                    target=target,
                    relation_type="calls",
                    metadata={
                        "detection": "text_based_heuristic",
                        "call_start_line": chunk.start_line + call_lines[0] - 1,
                        "call_end_line": chunk.start_line + call_lines[-1] - 1,
                    },
                )

    return graph


def _detect_method_calls(
    code: str,
    self_name: str,
    known_symbols: Set[str],
) -> Set[str]:
    """Conservative text-based call extraction heuristic.

    Matches identifier(...) call patterns in source code text and checks against known symbols.
    """
    calls: Set[str] = set()

    # Match method call syntax: identifier(...) or object.method(...)
    pattern = r"\b([a-zA-Z_]\w*)\s*\("
    matches = re.findall(pattern, code)

    keywords_to_skip = {
        "if", "while", "for", "switch", "catch", "return", "sizeof",
        "super", "this", "print", "len", "range", "str", "int", "list", "dict", "set",
        "self", "def", "class", "public", "private", "protected", "void", "new"
    }

    for identifier in matches:
        if identifier == self_name or identifier in keywords_to_skip:
            continue
        if identifier in known_symbols:
            calls.add(identifier)

    return calls


def _detect_method_call_lines(
    code: str,
    self_name: str,
    known_symbols: Set[str],
) -> dict:
    """Return detected symbols and their 1-indexed lines within ``code``."""
    calls = {}
    keywords_to_skip = {
        "if", "while", "for", "switch", "catch", "return", "sizeof",
        "super", "this", "print", "len", "range", "str", "int", "list", "dict", "set",
        "self", "def", "class", "public", "private", "protected", "void", "new"
    }
    pattern = re.compile(r"\b([a-zA-Z_]\w*)\s*\(")
    for line_number, line in enumerate(code.splitlines(), 1):
        for identifier in pattern.findall(line):
            if identifier == self_name or identifier in keywords_to_skip:
                continue
            if identifier in known_symbols:
                calls.setdefault(identifier, []).append(line_number)
    return calls
