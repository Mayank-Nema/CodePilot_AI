"""
RepositoryAnalyzer — Analyze a cloned repository's structure.

Responsibilities:
    - Detect repository name.
    - Count total source files (after filtering).
    - Detect programming languages from extensions.
    - Calculate file counts by language.
    - Discover folder structure (normalized to POSIX format).
    - Find largest files.
    - Return a RepositoryInfo model.
"""

import os
from pathlib import Path
from typing import List, Tuple

from backend.config import (
    IGNORED_DIRS,
    IGNORED_EXTENSIONS,
    SUPPORTED_LANGUAGES,
    MAX_FILE_SIZE_BYTES,
)
from models.repository import RepositoryInfo


def analyze_repository(repo_path: str) -> RepositoryInfo:
    """Analyze the structure of a cloned repository.

    Args:
        repo_path: Absolute path to the cloned repository.

    Returns:
        A populated RepositoryInfo object.
    """
    repo_path = Path(repo_path)
    repo_name = repo_path.name

    languages: dict[str, int] = {}
    folders: list[str] = []
    file_sizes: list[Tuple[str, int]] = []
    total_size = 0
    total_files = 0

    for dirpath, dirnames, filenames in os.walk(repo_path):
        # Filter out ignored directories (in-place so os.walk skips them)
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]

        dir_p = Path(dirpath)
        if dir_p != repo_path:
            rel_dir = dir_p.relative_to(repo_path).as_posix()
            folders.append(rel_dir)

        for filename in filenames:
            filepath = dir_p / filename
            ext = filepath.suffix.lower()

            # Skip ignored extensions
            if ext in IGNORED_EXTENSIONS:
                continue

            try:
                size = filepath.stat().st_size
            except OSError:
                continue

            # Skip very large files
            if size > MAX_FILE_SIZE_BYTES:
                continue

            total_files += 1
            total_size += size

            # Track POSIX relative path for largest files
            rel_path = filepath.relative_to(repo_path).as_posix()
            file_sizes.append((rel_path, size))

            # Language detection
            language = SUPPORTED_LANGUAGES.get(ext)
            if language:
                languages[language] = languages.get(language, 0) + 1

    # Sort folders alphabetically
    folders.sort()

    # Top-10 largest files
    file_sizes.sort(key=lambda x: x[1], reverse=True)
    largest_files = file_sizes[:10]

    return RepositoryInfo(
        name=repo_name,
        local_path=str(repo_path),
        total_files=total_files,
        languages=dict(sorted(languages.items(), key=lambda x: x[1], reverse=True)),
        folders=folders,
        largest_files=largest_files,
        total_size_bytes=total_size,
    )
