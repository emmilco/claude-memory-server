"""Git repository detection and metadata extraction (FEAT-017)."""

import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def is_git_repository(path: Path) -> bool:
    """
    Check if a directory is a git repository.

    Args:
        path: Directory path to check

    Returns:
        True if directory contains a .git folder or is within a git repo
    """
    try:
        path = Path(path).resolve()

        # Check for .git directory
        git_dir = path / ".git"
        if git_dir.exists():
            return True

        # Check if we're inside a git repository (even if not at root)
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=2,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.warning(f"Git command timed out checking if {path} is git repo")
        return False
    except Exception as e:
        logger.debug(f"Error checking if {path} is git repo: {e}")
        return False


def get_git_root(path: Path) -> Optional[Path]:
    """
    Get the root directory of a git repository.

    Args:
        path: Any path within a git repository

    Returns:
        Path to repository root, or None if not in a git repo
    """
    try:
        path = Path(path).resolve()

        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=2,
        )

        if result.returncode == 0:
            return Path(result.stdout.strip())
        return None
    except subprocess.TimeoutExpired:
        logger.warning(f"Git command timed out getting root for {path}")
        return None
    except Exception as e:
        logger.debug(f"Error getting git root for {path}: {e}")
        return None


def get_git_metadata(path: Path) -> Optional[Dict[str, Any]]:
    """
    Extract git metadata from a repository.

    Args:
        path: Path to git repository (or any path within it)

    Returns:
        Dictionary with git metadata:
        - root: Repository root path
        - remote_url: Primary remote URL (origin)
        - current_branch: Current branch name
        - commit_hash: Current commit SHA
        - is_dirty: Whether there are uncommitted changes

        Returns None if not a git repository
    """
    if not is_git_repository(path):
        return None

    try:
        path = Path(path).resolve()
        metadata: Dict[str, Any] = {}

        # Get repository root
        root = get_git_root(path)
        if root:
            metadata["root"] = str(root)
        else:
            return None

        # Get remote URL (origin)
        try:
            result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                metadata["remote_url"] = result.stdout.strip()
            else:
                metadata["remote_url"] = None
        except subprocess.TimeoutExpired:
            logger.warning(f"Git command timed out getting remote URL for {path}")
            metadata["remote_url"] = None
        except Exception as e:
            logger.debug(f"Could not get remote URL: {e}")
            metadata["remote_url"] = None

        # Get current branch
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                metadata["current_branch"] = result.stdout.strip() or None
            else:
                metadata["current_branch"] = None
        except subprocess.TimeoutExpired:
            logger.warning(f"Git command timed out getting current branch for {path}")
            metadata["current_branch"] = None
        except Exception as e:
            logger.debug(f"Could not get current branch: {e}")
            metadata["current_branch"] = None

        # Get current commit hash
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                metadata["commit_hash"] = result.stdout.strip()
            else:
                metadata["commit_hash"] = None
        except subprocess.TimeoutExpired:
            logger.warning(f"Git command timed out getting commit hash for {path}")
            metadata["commit_hash"] = None
        except Exception as e:
            logger.debug(f"Could not get commit hash: {e}")
            metadata["commit_hash"] = None

        # Check for uncommitted changes
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                metadata["is_dirty"] = bool(result.stdout.strip())
            else:
                metadata["is_dirty"] = None
        except subprocess.TimeoutExpired:
            logger.warning(f"Git command timed out checking status for {path}")
            metadata["is_dirty"] = None
        except Exception as e:
            logger.debug(f"Could not check git status: {e}")
            metadata["is_dirty"] = None

        logger.info(
            f"Extracted git metadata for {path}: {metadata.get('remote_url', 'local')}"
        )
        return metadata

    except Exception as e:
        logger.error(f"Error extracting git metadata from {path}: {e}")
        return None


def get_repository_name(metadata: Dict[str, Any]) -> str:
    """
    Derive a repository name from git metadata.

    Args:
        metadata: Git metadata dictionary from get_git_metadata()

    Returns:
        Repository name (derived from remote URL or root path)
    """
    # Try to extract from remote URL first
    remote_url = metadata.get("remote_url")
    if remote_url:
        # Handle different URL formats:
        # - https://github.com/user/repo.git
        # - git@github.com:user/repo.git
        # - /path/to/repo

        # Remove .git suffix
        if remote_url.endswith(".git"):
            remote_url = remote_url[:-4]

        # Extract repo name from URL
        parts = remote_url.replace(":", "/").split("/")
        if len(parts) >= 2:
            return parts[-1]  # Just the repo name

    # Fallback to directory name from root path
    root = metadata.get("root")
    if root:
        return Path(root).name

    return "unknown"
