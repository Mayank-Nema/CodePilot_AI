"""
PythonParser — Extract structural elements from Python source files.

Uses Tree-sitter with the tree-sitter-language-pack to parse Python code
and extract:
    - Classes (with decorators and base classes)
    - Module-level functions
    - Methods (inside classes, with parameters and return types)
    - Imports (import / from ... import)

Each extracted element becomes a CodeChunk with proper chunk_type, name,
line range, parent_symbol, and metadata.
"""

from typing import List, Optional

from tree_sitter_language_pack import get_language, get_parser

from backend.parsers.base_parser import BaseParser
from models.source_file import SourceFile
from models.code_chunk import CodeChunk


class PythonParser(BaseParser):
    """Tree-sitter-based parser for Python source files."""

    def __init__(self):
        self._language = get_language("python")
        self._parser = get_parser("python")

    def get_language(self) -> str:
        return "Python"

    def parse(self, source_file: SourceFile) -> List[CodeChunk]:
        """Parse a Python source file and return code chunks."""
        code_bytes = source_file.content.encode("utf-8")
        tree = self._parser.parse(code_bytes)
        root = tree.root_node

        chunks: List[CodeChunk] = []
        source_lines = source_file.content.split("\n")

        self._walk(root, source_file, source_lines, chunks, parent_class=None)

        return chunks

    # ------------------------------------------------------------------
    # Private traversal
    # ------------------------------------------------------------------

    def _walk(
        self,
        node,
        source_file: SourceFile,
        source_lines: List[str],
        chunks: List[CodeChunk],
        parent_class: Optional[str],
    ) -> None:
        """Recursively walk the AST and extract structural elements."""

        if node.type == "class_definition":
            self._extract_class(node, source_file, source_lines, chunks)
            return  # Children are handled inside _extract_class

        if node.type == "function_definition":
            self._extract_function(
                node, source_file, source_lines, chunks, parent_class
            )
            return

        if node.type == "decorated_definition":
            self._extract_decorated(
                node, source_file, source_lines, chunks, parent_class
            )
            return

        if node.type in ("import_statement", "import_from_statement"):
            self._extract_import(node, source_file, source_lines, chunks)

        # Recurse into children
        for child in node.children:
            self._walk(child, source_file, source_lines, chunks, parent_class)

    # ------------------------------------------------------------------
    # Extractors
    # ------------------------------------------------------------------

    def _extract_class(
        self,
        node,
        source_file: SourceFile,
        source_lines: List[str],
        chunks: List[CodeChunk],
    ) -> None:
        """Extract a class definition and then walk its body for methods."""
        name = self._get_child_text(node, "name", source_lines) or "<anonymous_class>"

        start_line = node.start_point[0] + 1  # 1-indexed
        end_line = node.end_point[0] + 1
        code = self._get_node_text(node, source_lines)

        decorators = self._get_decorators_from_parent(node, source_lines)
        bases = self._get_bases(node, source_lines)

        metadata = {}
        if decorators:
            metadata["decorators"] = decorators
        if bases:
            metadata["bases"] = bases

        chunks.append(
            self._make_chunk(
                source_file,
                chunk_type="class",
                name=name,
                code=code,
                start_line=start_line,
                end_line=end_line,
                metadata=metadata,
            )
        )

        body = self._find_child_by_type(node, "block")
        if body:
            for child in body.children:
                self._walk(child, source_file, source_lines, chunks, parent_class=name)

    def _extract_function(
        self,
        node,
        source_file: SourceFile,
        source_lines: List[str],
        chunks: List[CodeChunk],
        parent_class: Optional[str],
    ) -> None:
        """Extract a function or method definition."""
        name = self._get_child_text(node, "name", source_lines) or "<anonymous_function>"

        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        code = self._get_node_text(node, source_lines)

        chunk_type = "method" if parent_class else "function"

        decorators = self._get_decorators_from_parent(node, source_lines)
        params = self._get_parameters(node, source_lines)
        return_type = self._get_return_type(node, source_lines)

        metadata = {}
        if decorators:
            metadata["decorators"] = decorators
        if params:
            metadata["parameters"] = params
        if return_type:
            metadata["return_type"] = return_type

        chunks.append(
            self._make_chunk(
                source_file,
                chunk_type=chunk_type,
                name=name,
                code=code,
                start_line=start_line,
                end_line=end_line,
                parent_symbol=parent_class,
                metadata=metadata,
            )
        )

    def _extract_decorated(
        self,
        node,
        source_file: SourceFile,
        source_lines: List[str],
        chunks: List[CodeChunk],
        parent_class: Optional[str],
    ) -> None:
        """Handle a decorated_definition by extracting the inner definition."""
        for child in node.children:
            if child.type == "class_definition":
                self._extract_class(child, source_file, source_lines, chunks)
                return
            if child.type == "function_definition":
                self._extract_function(
                    child, source_file, source_lines, chunks, parent_class
                )
                return

    def _extract_import(
        self,
        node,
        source_file: SourceFile,
        source_lines: List[str],
        chunks: List[CodeChunk],
    ) -> None:
        """Extract an import statement."""
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        code = self._get_node_text(node, source_lines)
        name = code.strip()

        chunks.append(
            self._make_chunk(
                source_file,
                chunk_type="import",
                name=name,
                code=code,
                start_line=start_line,
                end_line=end_line,
            )
        )

    # ------------------------------------------------------------------
    # Python-specific AST helpers
    # ------------------------------------------------------------------

    def _get_decorators_from_parent(
        self, node, source_lines: List[str]
    ) -> List[str]:
        """Collect decorator names from a decorated_definition parent."""
        decorators = []
        parent = node.parent
        if parent and parent.type == "decorated_definition":
            for child in parent.children:
                if child.type == "decorator":
                    dec_text = self._get_node_text(child, source_lines).strip()
                    decorators.append(dec_text)
        return decorators

    def _get_bases(self, node, source_lines: List[str]) -> List[str]:
        """Extract base class names from a class definition."""
        bases = []
        arg_list = node.child_by_field_name("superclasses")
        if arg_list:
            for child in arg_list.children:
                if child.type in ("identifier", "attribute"):
                    bases.append(self._get_node_text(child, source_lines))
        return bases

    def _get_parameters(self, node, source_lines: List[str]) -> List[str]:
        """Extract parameter names from a function definition."""
        params = []
        parameters_node = node.child_by_field_name("parameters")
        if parameters_node:
            for child in parameters_node.children:
                if child.type == "identifier":
                    params.append(self._get_node_text(child, source_lines))
                elif child.type in (
                    "default_parameter",
                    "typed_parameter",
                    "typed_default_parameter",
                ):
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        params.append(self._get_node_text(name_node, source_lines))
                elif child.type in ("list_splat_pattern", "dictionary_splat_pattern"):
                    for sub in child.children:
                        if sub.type == "identifier":
                            prefix = "*" if child.type == "list_splat_pattern" else "**"
                            params.append(prefix + self._get_node_text(sub, source_lines))
        return params

    def _get_return_type(self, node, source_lines: List[str]) -> Optional[str]:
        """Extract the return type annotation if present."""
        return_type = node.child_by_field_name("return_type")
        if return_type:
            return self._get_node_text(return_type, source_lines)
        return None
