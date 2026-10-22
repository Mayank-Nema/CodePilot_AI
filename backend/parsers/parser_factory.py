"""
ParserFactory — Map language names to their parser implementations.

Usage:
    parser = get_parser("Python")
    if parser:
        chunks = parser.parse(source_file)

Returns None for unsupported languages so callers can skip gracefully.
"""

from typing import Optional

from backend.parsers.base_parser import BaseParser
from backend.parsers.python_parser import PythonParser
from backend.parsers.java_parser import JavaParser


# Lazily-instantiated parser singletons (one per language)
_parser_cache: dict[str, BaseParser] = {}

# Registry: language name -> parser class
_PARSER_REGISTRY: dict[str, type] = {
    "Python": PythonParser,
    "Java": JavaParser,
}


def get_parser(language: str) -> Optional[BaseParser]:
    """Return a parser instance for the given language, or None if unsupported.

    Parser instances are cached (singletons) since they are stateless
    and Tree-sitter parser objects can be reused.

    Args:
        language: Language name (e.g. "Python", "Java").

    Returns:
        A BaseParser subclass instance, or None.
    """
    if language not in _PARSER_REGISTRY:
        return None

    if language not in _parser_cache:
        _parser_cache[language] = _PARSER_REGISTRY[language]()

    return _parser_cache[language]


def get_supported_languages() -> list[str]:
    """Return a list of languages that have parser support."""
    return list(_PARSER_REGISTRY.keys())
