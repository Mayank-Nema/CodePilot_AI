"""
RepositoryInfo — Holds analysis results for a cloned repository.

This model is produced by the RepositoryAnalyzer and consumed by the
Streamlit UI to display the repository dashboard.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class RepositoryInfo:
    """Analysis results for a single repository."""

    name: str                                       # Repository name
    local_path: str                                 # Absolute path to the cloned repo
    total_files: int = 0                            # Total source files (after filtering)
    languages: Dict[str, int] = field(default_factory=dict)   # Language -> file count
    folders: List[str] = field(default_factory=list)          # Discovered folder paths
    largest_files: List[Tuple[str, int]] = field(default_factory=list)  # (path, size) pairs
    total_size_bytes: int = 0                       # Sum of all source-file sizes

    @property
    def primary_language(self) -> str:
        """Return the language with the most files, or 'Unknown'."""
        if not self.languages:
            return "Unknown"
        return max(self.languages, key=self.languages.get)

    def __repr__(self) -> str:
        return (
            f"RepositoryInfo(name='{self.name}', files={self.total_files}, "
            f"primary_language='{self.primary_language}')"
        )
