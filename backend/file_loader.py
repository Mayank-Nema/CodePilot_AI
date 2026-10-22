"""
FileLoader — Recursively load source files from a cloned repository.

Responsibilities:
    - Walk the repository directory tree.
    - Filter out ignored directories and extensions.
    - Detect programming language from file extension.
    - Read file content safely (handle encoding errors).
    - Normalize relative paths to POSIX format (/) across platforms.
    - Return a list of SourceFile objects.
"""

import os
from pathlib import Path
from typing import List, Optional

from backend.config import (
    IGNORED_DIRS,
    IGNORED_EXTENSIONS,
    SUPPORTED_LANGUAGES,
    MAX_FILE_SIZE_BYTES,
)
from models.source_file import SourceFile


def load_files(repo_path: str) -> List[SourceFile]:
    """Load all source files from a repository.

    Args:
        repo_path: Absolute path to the cloned repository root.

    Returns:
        List of SourceFile objects for every loadable source file.
    """
    repo_path = Path(repo_path)
    source_files: List[SourceFile] = []

    for dirpath, dirnames, filenames in os.walk(repo_path):
        # Filter ignored directories in-place so os.walk skips them
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            ext = filepath.suffix.lower()

            # Skip ignored extensions
            if ext in IGNORED_EXTENSIONS:
                continue

            # Skip files with no known language
            language = SUPPORTED_LANGUAGES.get(ext)
            if not language:
                continue

            # Skip very large files
            try:
                size = filepath.stat().st_size
            except OSError:
                continue

            if size > MAX_FILE_SIZE_BYTES:
                continue

            # Read file content safely
            content = _read_file_safe(filepath)
            if content is None:
                continue

            # Normalize to POSIX format (uses '/' on all OS platforms)
            relative_path = filepath.relative_to(repo_path).as_posix()

            source_files.append(
                SourceFile(
                    file_path=str(filepath),
                    relative_path=relative_path,
                    language=language,
                    content=content,
                    size_bytes=size,
                )
            )

    return source_files


def _read_file_safe(filepath: Path) -> Optional[str]:
    """Read a file as text, returning None if it cannot be decoded."""
    encodings = ["utf-8", "latin-1"]
    for encoding in encodings:
        try:
            return filepath.read_text(encoding=encoding)
        except (UnicodeDecodeError, OSError):
            continue
    return None
