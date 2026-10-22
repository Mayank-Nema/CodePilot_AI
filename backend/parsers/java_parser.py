"""
JavaParser — Extract structural elements from Java source files.

Uses Tree-sitter with the tree-sitter-language-pack to parse Java code
and extract:
    - Classes
    - Interfaces
    - Enums
    - Methods
    - Constructors
    - Fields
    - Imports
    - Annotations
    - Inheritance / implements information (stored in metadata)

Each extracted element becomes a CodeChunk with proper chunk_type, name,
line range, parent_symbol, and metadata.
"""

from typing import List, Optional

from tree_sitter_language_pack import get_language, get_parser

from backend.parsers.base_parser import BaseParser
from models.source_file import SourceFile
from models.code_chunk import CodeChunk


class JavaParser(BaseParser):
    """Tree-sitter-based parser for Java source files."""

    def __init__(self):
        self._language = get_language("java")
        self._parser = get_parser("java")

    def get_language(self) -> str:
        return "Java"

    def parse(self, source_file: SourceFile) -> List[CodeChunk]:
        """Parse a Java source file and return code chunks."""
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

        if node.type == "class_declaration":
            self._extract_class(node, source_file, source_lines, chunks, "class")
            return

        if node.type == "interface_declaration":
            self._extract_class(node, source_file, source_lines, chunks, "interface")
            return

        if node.type == "enum_declaration":
            self._extract_class(node, source_file, source_lines, chunks, "enum")
            return

        if node.type == "method_declaration":
            self._extract_method(node, source_file, source_lines, chunks, parent_class)
            return

        if node.type == "constructor_declaration":
            self._extract_constructor(
                node, source_file, source_lines, chunks, parent_class
            )
            return

        if node.type == "field_declaration":
            self._extract_field(node, source_file, source_lines, chunks, parent_class)
            return

        if node.type == "import_declaration":
            self._extract_import(node, source_file, source_lines, chunks)
            return

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
        chunk_type: str,
    ) -> None:
        """Extract a class, interface, or enum declaration."""
        name = self._get_child_text(node, "name", source_lines) or "<anonymous>"

        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        code = self._get_node_text(node, source_lines)

        metadata: dict = {}

        annotations = self._get_annotations(node, source_lines)
        if annotations:
            metadata["annotations"] = annotations

        modifiers = self._get_modifiers(node, source_lines)
        if modifiers:
            metadata["modifiers"] = modifiers

        superclass = self._get_superclass(node, source_lines)
        if superclass:
            metadata["extends"] = superclass

        interfaces = self._get_interfaces(node, source_lines)
        if interfaces:
            metadata["implements"] = interfaces

        chunks.append(
            self._make_chunk(
                source_file,
                chunk_type=chunk_type,
                name=name,
                code=code,
                start_line=start_line,
                end_line=end_line,
                metadata=metadata,
            )
        )

        body = node.child_by_field_name("body")
        if body:
            for child in body.children:
                self._walk(child, source_file, source_lines, chunks, parent_class=name)

    def _extract_method(
        self,
        node,
        source_file: SourceFile,
        source_lines: List[str],
        chunks: List[CodeChunk],
        parent_class: Optional[str],
    ) -> None:
        """Extract a method declaration."""
        name = self._get_child_text(node, "name", source_lines) or "<anonymous_method>"

        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        code = self._get_node_text(node, source_lines)

        metadata: dict = {}

        annotations = self._get_annotations(node, source_lines)
        if annotations:
            metadata["annotations"] = annotations

        modifiers = self._get_modifiers(node, source_lines)
        if modifiers:
            metadata["modifiers"] = modifiers

        return_type = self._get_child_text(node, "type", source_lines)
        if return_type:
            metadata["return_type"] = return_type

        params = self._get_parameters(node, source_lines)
        if params:
            metadata["parameters"] = params

        chunks.append(
            self._make_chunk(
                source_file,
                chunk_type="method",
                name=name,
                code=code,
                start_line=start_line,
                end_line=end_line,
                parent_symbol=parent_class,
                metadata=metadata,
            )
        )

    def _extract_constructor(
        self,
        node,
        source_file: SourceFile,
        source_lines: List[str],
        chunks: List[CodeChunk],
        parent_class: Optional[str],
    ) -> None:
        """Extract a constructor declaration."""
        name = self._get_child_text(node, "name", source_lines) or parent_class or "<constructor>"

        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        code = self._get_node_text(node, source_lines)

        metadata: dict = {}

        annotations = self._get_annotations(node, source_lines)
        if annotations:
            metadata["annotations"] = annotations

        modifiers = self._get_modifiers(node, source_lines)
        if modifiers:
            metadata["modifiers"] = modifiers

        params = self._get_parameters(node, source_lines)
        if params:
            metadata["parameters"] = params

        chunks.append(
            self._make_chunk(
                source_file,
                chunk_type="constructor",
                name=name,
                code=code,
                start_line=start_line,
                end_line=end_line,
                parent_symbol=parent_class,
                metadata=metadata,
            )
        )

    def _extract_field(
        self,
        node,
        source_file: SourceFile,
        source_lines: List[str],
        chunks: List[CodeChunk],
        parent_class: Optional[str],
    ) -> None:
        """Extract a field declaration."""
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        code = self._get_node_text(node, source_lines)

        name = "<field>"
        declarator = self._find_child_by_type(node, "variable_declarator")
        if declarator:
            name_node = declarator.child_by_field_name("name")
            if name_node:
                name = self._get_node_text(name_node, source_lines)

        metadata: dict = {}

        field_type = self._get_child_text(node, "type", source_lines)
        if field_type:
            metadata["field_type"] = field_type

        annotations = self._get_annotations(node, source_lines)
        if annotations:
            metadata["annotations"] = annotations

        modifiers = self._get_modifiers(node, source_lines)
        if modifiers:
            metadata["modifiers"] = modifiers

        chunks.append(
            self._make_chunk(
                source_file,
                chunk_type="field",
                name=name,
                code=code,
                start_line=start_line,
                end_line=end_line,
                parent_symbol=parent_class,
                metadata=metadata,
            )
        )

    def _extract_import(
        self,
        node,
        source_file: SourceFile,
        source_lines: List[str],
        chunks: List[CodeChunk],
    ) -> None:
        """Extract an import declaration."""
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        code = self._get_node_text(node, source_lines)
        name = code.strip().rstrip(";")

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
    # Java-specific AST helpers
    # ------------------------------------------------------------------

    def _get_annotations(self, node, source_lines: List[str]) -> List[str]:
        """Collect annotation text from sibling or child annotation nodes."""
        annotations = []
        parent = node.parent
        if parent:
            found_self = False
            for child in reversed(parent.children):
                if child == node:
                    found_self = True
                    continue
                if found_self and child.type in ("marker_annotation", "annotation"):
                    text = self._get_node_text(child, source_lines).strip()
                    annotations.insert(0, text)
                elif found_self and child.type not in ("marker_annotation", "annotation"):
                    break

        for child in node.children:
            if child.type in ("marker_annotation", "annotation"):
                text = self._get_node_text(child, source_lines).strip()
                annotations.append(text)
        return annotations

    def _get_modifiers(self, node, source_lines: List[str]) -> List[str]:
        """Extract modifier keywords (public, private, static, etc.)."""
        modifiers = []
        for child in node.children:
            if child.type == "modifiers":
                for mod_child in child.children:
                    if mod_child.type in ("marker_annotation", "annotation"):
                        continue
                    text = self._get_node_text(mod_child, source_lines).strip()
                    if text:
                        modifiers.append(text)
        return modifiers

    def _get_superclass(self, node, source_lines: List[str]) -> Optional[str]:
        """Get the superclass from an 'extends' clause."""
        superclass = node.child_by_field_name("superclass")
        if superclass:
            return self._get_node_text(superclass, source_lines)
        return None

    def _get_interfaces(self, node, source_lines: List[str]) -> List[str]:
        """Get implemented interfaces from an 'implements' clause."""
        interfaces = []
        interfaces_node = node.child_by_field_name("interfaces")
        if interfaces_node:
            for child in interfaces_node.children:
                if child.type == "type_list":
                    for type_child in child.children:
                        if type_child.type not in (",",):
                            text = self._get_node_text(type_child, source_lines).strip()
                            if text:
                                interfaces.append(text)
                elif child.type not in ("implements",):
                    text = self._get_node_text(child, source_lines).strip()
                    if text and text != "implements":
                        interfaces.append(text)
        return interfaces

    def _get_parameters(self, node, source_lines: List[str]) -> List[str]:
        """Extract parameter type-name pairs from a method/constructor."""
        params = []
        parameters_node = node.child_by_field_name("parameters")
        if parameters_node:
            for child in parameters_node.children:
                if child.type == "formal_parameter":
                    param_text = self._get_node_text(child, source_lines).strip()
                    params.append(param_text)
                elif child.type == "spread_parameter":
                    param_text = self._get_node_text(child, source_lines).strip()
                    params.append(param_text)
        return params
