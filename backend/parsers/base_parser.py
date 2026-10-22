"""
BaseParser — Abstract base class for all language-specific parsers.

Every language parser must subclass BaseParser and implement:
    - parse(source_file) -> list[CodeChunk]
    - get_language() -> str

This module also provides common AST extraction helper methods
(_get_node_text, _get_child_text, _find_child_by_type) to eliminate
duplication across language parsers.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from models.source_file import SourceFile
from models.code_chunk import CodeChunk


class BaseParser(ABC):
    """Abstract base class for Tree-sitter language parsers."""

    @abstractmethod
    def parse(self, source_file: SourceFile) -> List[CodeChunk]:
        """Parse a source file and return structured code chunks."""
        raise NotImplementedError

    @abstractmethod
    def get_language(self) -> str:
        """Return the language name this parser handles (e.g. 'Python')."""
        raise NotImplementedError

    def _make_chunk(
        self,
        source_file: SourceFile,
        chunk_type: str,
        name: str,
        code: str,
        start_line: int,
        end_line: int,
        parent_symbol: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> CodeChunk:
        """Convenience helper to build a CodeChunk with common fields."""
        return CodeChunk(
            file_path=source_file.file_path,
            relative_path=source_file.relative_path,
            language=source_file.language,
            chunk_type=chunk_type,
            name=name,
            code=code,
            start_line=start_line,
            end_line=end_line,
            parent_symbol=parent_symbol,
            metadata=metadata or {},
        )

    # ------------------------------------------------------------------
    # Common AST helpers shared across parsers
    # ------------------------------------------------------------------

    def _get_node_text(self, node, source_lines: List[str]) -> str:
        """Extract the source text corresponding to a Tree-sitter AST node."""
        start_row = node.start_point[0]
        end_row = node.end_point[0]
        start_col = node.start_point[1]
        end_col = node.end_point[1]

        if start_row == end_row:
            return source_lines[start_row][start_col:end_col]

        lines = []
        for i in range(start_row, end_row + 1):
            if i >= len(source_lines):
                break
            line = source_lines[i]
            if i == start_row:
                lines.append(line[start_col:])
            elif i == end_row:
                lines.append(line[:end_col])
            else:
                lines.append(line)
        return "\n".join(lines)

    def _get_child_text(
        self, node, field_name: str, source_lines: List[str]
    ) -> Optional[str]:
        """Get the text of a named child field (e.g. 'name')."""
        child = node.child_by_field_name(field_name)
        if child:
            return self._get_node_text(child, source_lines)
        return None

    def _find_child_by_type(self, node, type_name: str):
        """Find the first child node with the given node type."""
        for child in node.children:
            if child.type == type_name:
                return child
        return None
