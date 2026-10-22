"""
CodeChunk — Represents a meaningful, parsed unit of source code.

Each CodeChunk corresponds to a structural element extracted by Tree-sitter:
a class, function, method, constructor, import, interface, enum, etc.

The chunk retains enough metadata to trace it back to a specific file, line
range, and parent symbol. This is the foundation for embeddings, retrieval,
and the code knowledge graph.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CodeChunk:
    """A structured code unit extracted from a source file."""

    file_path: str                          # Absolute path to the source file
    relative_path: str                      # Path relative to the repository root
    language: str                           # Programming language
    chunk_type: str                         # e.g. "class", "function", "method", "import", "constructor"
    name: str                               # Symbol name (e.g. "UserService", "login")
    code: str                               # Actual source code of this chunk
    start_line: int                         # 1-indexed start line in the file
    end_line: int                           # 1-indexed end line in the file
    parent_symbol: Optional[str] = None     # Enclosing symbol (e.g. class name for a method)
    metadata: dict = field(default_factory=dict)  # Extensible: decorators, annotations, etc.

    def __repr__(self) -> str:
        return (
            f"CodeChunk(type='{self.chunk_type}', name='{self.name}', "
            f"file='{self.relative_path}', lines={self.start_line}-{self.end_line})"
        )

    @property
    def qualified_name(self) -> str:
        """Return a fully-qualified symbol name (e.g. 'UserService.login')."""
        if self.parent_symbol:
            return f"{self.parent_symbol}.{self.name}"
        return self.name

    @property
    def line_count(self) -> int:
        """Number of lines this chunk spans."""
        return self.end_line - self.start_line + 1
