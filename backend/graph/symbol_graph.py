"""
SymbolGraph — In-memory Code Knowledge Graph & Dependency Analysis.

Responsibilities:
    - Maintain nodes (SymbolNode) representing classes, methods, functions, and modules.
    - Store directed relationships (Relationship) for contains, extends, implements, imports, calls, and uses.
    - Provide derived reverse lookup for callers (called_by) without duplicating edge state.
    - Perform recursive Change Impact Analysis to identify all code units affected by changes.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any


@dataclass
class SymbolNode:
    """Represents a structural code element in the Knowledge Graph."""

    qualified_name: str          # e.g. "UserService.login" or "UserService"
    name: str                    # e.g. "login"
    chunk_type: str              # e.g. "class", "method", "function", "interface", "module"
    file_path: str               # Absolute path
    relative_path: str           # Path relative to repository root
    language: str                # Programming language
    start_line: int              # 1-indexed line start
    end_line: int                # 1-indexed line end
    parent_symbol: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"SymbolNode({self.qualified_name} [{self.chunk_type}], {self.relative_path}:{self.start_line}-{self.end_line})"


@dataclass
class Relationship:
    """Directed relationship link between code symbols."""

    source: str                  # Source qualified_name
    target: str                  # Target qualified_name or symbol name
    relation_type: str           # "contains", "extends", "implements", "imports", "calls", "uses"
    metadata: dict = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"Relationship({self.source} -[{self.relation_type}]-> {self.target})"


class SymbolGraph:
    """In-memory Code Knowledge Graph engine."""

    def __init__(self):
        self.nodes: Dict[str, SymbolNode] = {}
        self.edges: List[Relationship] = []
        self._outgoing: Dict[str, List[Relationship]] = {}
        self._incoming: Dict[str, List[Relationship]] = {}
        self._name_index: Dict[str, List[str]] = {}  # short name -> list of qualified_names

    def add_node(self, node: SymbolNode):
        """Add or update a SymbolNode in the graph."""
        self.nodes[node.qualified_name] = node

        # Index by short name for fuzzy lookup
        short_name = node.name.lower()
        if short_name not in self._name_index:
            self._name_index[short_name] = []
        if node.qualified_name not in self._name_index[short_name]:
            self._name_index[short_name].append(node.qualified_name)

    def add_edge(self, source: str, target: str, relation_type: str, metadata: Optional[dict] = None):
        """Add a directed relationship edge to the graph."""
        rel = Relationship(source=source, target=target, relation_type=relation_type, metadata=metadata or {})
        self.edges.append(rel)

        if source not in self._outgoing:
            self._outgoing[source] = []
        self._outgoing[source].append(rel)

        if target not in self._incoming:
            self._incoming[target] = []
        self._incoming[target].append(rel)

    def find_node(self, query_name: str) -> Optional[SymbolNode]:
        """Find a node by exact qualified name or short name."""
        if query_name in self.nodes:
            return self.nodes[query_name]

        short_lower = query_name.lower()
        if short_lower in self._name_index:
            q_name = self._name_index[short_lower][0]
            return self.nodes[q_name]

        # Partial match fallback
        for key, node in self.nodes.items():
            if query_name.lower() in key.lower() or query_name.lower() in node.name.lower():
                return node
        return None

    def get_callees(self, symbol_name: str) -> List[Tuple[SymbolNode, Relationship]]:
        """Get all symbols called or used by the given symbol (outgoing 'calls' or 'uses' edges)."""
        node = self.find_node(symbol_name)
        if not node:
            return []

        results = []
        for rel in self._outgoing.get(node.qualified_name, []):
            if rel.relation_type in ("calls", "uses"):
                target_node = self.find_node(rel.target)
                if target_node:
                    results.append((target_node, rel))
        return results

    def get_callers(self, symbol_name: str) -> List[Tuple[SymbolNode, Relationship]]:
        """Derived reverse lookup of 'calls' or 'uses' edges pointing to the target symbol."""
        node = self.find_node(symbol_name)
        target_keys = {node.qualified_name, node.name} if node else {symbol_name}

        results = []
        for rel in self.edges:
            if rel.relation_type in ("calls", "uses"):
                if rel.target in target_keys or rel.target.lower() == symbol_name.lower():
                    source_node = self.find_node(rel.source)
                    if source_node:
                        results.append((source_node, rel))
        return results

    def get_dependencies(self, symbol_name: str) -> List[Tuple[SymbolNode, str]]:
        """Get direct outgoing dependencies (extends, implements, imports, calls, uses)."""
        node = self.find_node(symbol_name)
        if not node:
            return []

        results = []
        for rel in self._outgoing.get(node.qualified_name, []):
            target_node = self.find_node(rel.target)
            if target_node:
                results.append((target_node, rel.relation_type))
        return results

    def get_impact_analysis(self, symbol_name: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        """Perform recursive reverse dependency traversal (Change Impact Analysis).

        Identifies all symbols and files directly or indirectly dependent on the given symbol.
        """
        start_node = self.find_node(symbol_name)
        if not start_node:
            return []

        target_identifiers = {start_node.qualified_name, start_node.name}

        visited: Set[str] = set()
        queue = deque([(target_identifiers, 0, [start_node.qualified_name])])

        impact_results: List[Dict[str, Any]] = []

        while queue:
            current_targets, depth, chain = queue.popleft()
            if depth >= max_depth:
                continue

            for rel in self.edges:
                # If rel.target matches any of current_targets, rel.source is impacted
                if rel.target in current_targets or any(t.lower() == rel.target.lower() for t in current_targets):
                    source_node = self.find_node(rel.source)
                    if source_node and source_node.qualified_name not in visited:
                        visited.add(source_node.qualified_name)

                        impact_item = {
                            "qualified_name": source_node.qualified_name,
                            "name": source_node.name,
                            "chunk_type": source_node.chunk_type,
                            "relative_path": source_node.relative_path,
                            "line_range": f"{source_node.start_line}-{source_node.end_line}",
                            "relation_type": rel.relation_type,
                            "depth": depth + 1,
                            "dependency_chain": chain + [source_node.qualified_name],
                        }
                        impact_results.append(impact_item)

                        # Recurse on this caller/dependent node
                        next_targets = {source_node.qualified_name, source_node.name}
                        queue.append((next_targets, depth + 1, chain + [source_node.qualified_name]))

        return impact_results

    @property
    def total_nodes(self) -> int:
        return len(self.nodes)

    @property
    def total_edges(self) -> int:
        return len(self.edges)
