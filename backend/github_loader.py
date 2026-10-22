"""
GitHubLoader — Clone a GitHub repository to local storage.

Responsibilities:
    - Validate the GitHub repository URL.
    - Extract and sanitize repository names safely (preventing path traversal).
    - Ensure cloned paths stay strictly within the configured storage directory.
    - Clone the repository using GitPython.
    - Handle errors (invalid URL, clone failure, already-cloned repos, path traversal).
"""

import os
import re
import shutil
from pathlib import Path

from git import Repo, GitCommandError

from backend.config import REPO_STORAGE_DIR


# Matches HTTPS GitHub URLs like https://github.com/user/repo or
# https://github.com/user/repo.git
_GITHUB_URL_PATTERN = re.compile(
    r"^https?://github\.com/[\w.\-]+/[\w.\-]+(\.git)?/?$"
)


def validate_github_url(url: str) -> bool:
    """Return True if *url* looks like a valid GitHub repository URL."""
    return bool(_GITHUB_URL_PATTERN.match(url.strip()))


def extract_repo_name(url: str) -> str:
    """Extract and sanitize the repository name from a GitHub URL.

    Example:
        https://github.com/user/my-repo.git  ->  my-repo
    """
    url = url.strip().rstrip("/")
    name = url.split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]

    # Sanitize name to prevent path traversal
    name = re.sub(r"[^\w.\-]", "_", name)
    if name in (".", "..") or ".." in name:
        name = "repository"

    return name


def clone_repository(url: str, force_reclone: bool = False) -> str:
    """Clone a GitHub repository and return the local directory path.

    Args:
        url: HTTPS GitHub URL.
        force_reclone: If True, delete any existing clone and re-clone.

    Returns:
        Absolute path to the cloned repository.

    Raises:
        ValueError: If the URL is invalid or attempts path traversal.
        RuntimeError: If cloning fails.
    """
    url = url.strip()

    if not validate_github_url(url):
        raise ValueError(
            f"Invalid GitHub URL: {url}\n"
            "Expected format: https://github.com/user/repository"
        )

    repo_name = extract_repo_name(url)

    # Ensure storage directory exists
    storage_dir = REPO_STORAGE_DIR.resolve()
    storage_dir.mkdir(parents=True, exist_ok=True)

    local_path = (REPO_STORAGE_DIR / repo_name).resolve()

    # Security Check: Verify local_path is strictly inside storage_dir
    try:
        local_path.relative_to(storage_dir)
    except ValueError:
        raise ValueError(
            f"Security Error: Repository path '{repo_name}' escapes storage directory '{storage_dir}'."
        )

    # Handle already-cloned repos
    if local_path.exists():
        if force_reclone:
            shutil.rmtree(local_path)
        else:
            # Verify it is a valid git repo
            if (local_path / ".git").is_dir():
                return str(local_path)
            else:
                # Directory exists but is not a git repo — remove and re-clone
                shutil.rmtree(local_path)

    try:
        Repo.clone_from(url, str(local_path))
    except GitCommandError as exc:
        raise RuntimeError(f"Failed to clone repository: {exc}") from exc

    return str(local_path)
