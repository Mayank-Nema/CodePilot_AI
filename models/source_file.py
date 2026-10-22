"""
SourceFile — Represents a single source file loaded from a repository.

Each SourceFile holds the file's content, path information, detected language,
and size. This is the primary input to the parser layer.
"""

from dataclasses import dataclass


@dataclass
class SourceFile:
    """A source file loaded from a cloned repository."""

    file_path: str          # Absolute path on disk
    relative_path: str      # Path relative to the repository root
    language: str           # Detected programming language (e.g. "Python", "Java")
    content: str            # Full source-code content
    size_bytes: int         # File size in bytes

    def __repr__(self) -> str:
        return (
            f"SourceFile(relative_path='{self.relative_path}', "
            f"language='{self.language}', size={self.size_bytes})"
        )
