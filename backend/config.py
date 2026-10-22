"""
Configuration — Centralized project settings.

All configurable values live here. Nothing is hard-coded in business-logic
modules. Values can be overridden via environment variables or a .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

REPO_STORAGE_DIR = Path(
    os.getenv("REPO_STORAGE_DIR", str(PROJECT_ROOT / "repositories"))
)

# ---------------------------------------------------------------------------
# Directories to ignore when scanning repositories
# ---------------------------------------------------------------------------

IGNORED_DIRS: set[str] = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "target",
    ".gradle",
    ".mvn",
    "env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "egg-info",
    ".eggs",
    ".next",
    "out",
    "vendor",
    "bower_components",
}

# ---------------------------------------------------------------------------
# File extensions to ignore (binary / generated / non-source)
# ---------------------------------------------------------------------------

IGNORED_EXTENSIONS: set[str] = {
    # Images
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".svg", ".webp",
    # Compiled / binary
    ".pyc", ".pyo", ".class", ".o", ".so", ".dll", ".exe", ".jar", ".war",
    ".ear", ".whl",
    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".rar", ".7z",
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    # Media
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".flac",
    # Fonts
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # Lock files (large, generated)
    ".lock",
    # Data
    ".sqlite", ".db", ".bin", ".dat",
    # Misc
    ".DS_Store",
}

# ---------------------------------------------------------------------------
# Supported programming languages (extension -> language name)
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES: dict[str, str] = {
    ".py": "Python",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".c": "C",
    ".h": "C",
    ".hpp": "C++",
    ".go": "Go",
    ".rs": "Rust",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".cs": "C#",
    ".php": "PHP",
    ".rb": "Ruby",
    ".swift": "Swift",
    ".scala": "Scala",
    ".r": "R",
    ".R": "R",
    ".m": "Objective-C",
    ".mm": "Objective-C",
    ".lua": "Lua",
    ".pl": "Perl",
    ".pm": "Perl",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".bat": "Batch",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SASS",
    ".less": "LESS",
    ".xml": "XML",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "INI",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
    ".dockerfile": "Dockerfile",
    ".proto": "Protocol Buffers",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
}

# ---------------------------------------------------------------------------
# Languages with Tree-sitter parser support in this project
# ---------------------------------------------------------------------------

PARSEABLE_LANGUAGES: set[str] = {"Python", "Java"}

# ---------------------------------------------------------------------------
# File-size limit (skip very large files during loading)
# ---------------------------------------------------------------------------

MAX_FILE_SIZE_BYTES: int = int(os.getenv("MAX_FILE_SIZE_BYTES", str(5 * 1024 * 1024)))  # 5 MB
