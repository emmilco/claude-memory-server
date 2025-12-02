"""Git history indexing for semantic search over commits and diffs."""

import logging
import os
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, UTC
from pathlib import Path
from dataclasses import dataclass

try:
    import git
    from git import Repo, Commit
    from git.diff import Diff

    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False
    Repo = None
    Commit = None
    Diff = Any  # type: ignore

from src.config import ServerConfig
from src.embeddings.generator import EmbeddingGenerator

logger = logging.getLogger(__name__)


@dataclass
class GitCommitData:
    """Structured data for a git commit."""

    commit_hash: str
    repository_path: str
    author_name: str
    author_email: str
    author_date: datetime
    committer_name: str
    committer_date: datetime
    message: str
    message_embedding: List[float]
    branch_names: List[str]
    tags: List[str]
    parent_hashes: List[str]
    stats: Dict[str, int]  # files_changed, insertions, deletions


@dataclass
class GitFileChangeData:
    """Structured data for a file change in a commit."""

    id: str  # commit_hash + file_path
    commit_hash: str
    file_path: str
    change_type: str  # added|modified|deleted|renamed
    lines_added: int
    lines_deleted: int
    diff_content: Optional[str] = None
    diff_embedding: Optional[List[float]] = None


class GitIndexer:
    """
    Index git history for semantic search.

    Extracts commits, diffs, and metadata for semantic search over
    code history and evolution.
    """

    def __init__(self, config: ServerConfig, embedding_generator: EmbeddingGenerator):
        """
        Initialize git indexer.

        Args:
            config: Server configuration
            embedding_generator: Embedding generator for semantic search

        Raises:
            ImportError: If GitPython is not available
        """
        if not GIT_AVAILABLE:
            raise ImportError(
                "GitPython is required for git indexing. "
                "Install with: pip install GitPython>=3.1.40"
            )

        self.config = config
        self.embedding_generator = embedding_generator

        # Statistics
        self.stats = {
            "repos_indexed": 0,
            "commits_indexed": 0,
            "file_changes_indexed": 0,
            "diffs_embedded": 0,
            "errors": 0,
        }

    async def index_repository(
        self,
        repo_path: str,
        project_name: str,
        num_commits: Optional[int] = None,
        include_diffs: Optional[bool] = None,
    ) -> Tuple[List[GitCommitData], List[GitFileChangeData]]:
        """
        Index a git repository's history.

        Args:
            repo_path: Path to git repository
            project_name: Project name for organization
            num_commits: Number of commits to index (None = use config)
            include_diffs: Whether to index diffs (None = auto-detect)

        Returns:
            Tuple of (commit_data_list, file_change_data_list)

        Raises:
            ValueError: If repo_path is not a git repository
        """
        if not self.config.indexing.git_indexing:
            logger.info("Git indexing is disabled in configuration")
            return [], []

        # Validate repository
        repo_path = Path(repo_path).resolve()
        if not repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")

        try:
            repo = Repo(repo_path)
        except git.InvalidGitRepositoryError:
            raise ValueError(f"Not a git repository: {repo_path}")

        # Determine settings
        num_commits = num_commits or self.config.indexing.git_index_commit_count

        if include_diffs is None:
            # Auto-detect based on repo size
            repo_size_mb = self._get_repo_size_mb(repo_path)
            include_diffs = repo_size_mb < self.config.git_auto_size_threshold_mb
            if not include_diffs:
                logger.info(
                    f"Repository size ({repo_size_mb}MB) exceeds threshold "
                    f"({self.config.git_auto_size_threshold_mb}MB), "
                    "disabling diff indexing for performance"
                )

        logger.info(
            f"Indexing git repository: {repo_path} "
            f"(commits: {num_commits}, diffs: {include_diffs})"
        )

        # Get commits to index
        commits = self._get_commits_to_index(repo, num_commits)

        # Extract commit and file change data
        commit_data_list = []
        file_change_data_list = []

        for commit in commits:
            try:
                # Extract commit data
                commit_data = await self._extract_commit_data(
                    commit, str(repo_path), repo
                )
                commit_data_list.append(commit_data)

                # Extract file changes if requested
                if include_diffs:
                    file_changes = await self._extract_file_changes(
                        commit, include_diff_content=True
                    )
                    file_change_data_list.extend(file_changes)

                self.stats["commits_indexed"] += 1

            except Exception as e:
                logger.error(f"Error processing commit {commit.hexsha}: {e}")
                self.stats["errors"] += 1
                continue

        self.stats["repos_indexed"] += 1
        self.stats["file_changes_indexed"] += len(file_change_data_list)

        logger.info(
            f"Indexed {len(commit_data_list)} commits and "
            f"{len(file_change_data_list)} file changes from {repo_path}"
        )

        return commit_data_list, file_change_data_list

    def _get_repo_size_mb(self, repo_path: Path) -> float:
        """Calculate approximate repository size in MB."""
        git_dir = repo_path / ".git"
        if not git_dir.exists():
            return 0.0

        total_size = 0
        for dirpath, dirnames, filenames in os.walk(git_dir):
            for filename in filenames:
                filepath = Path(dirpath) / filename
                try:
                    total_size += filepath.stat().st_size
                except OSError:
                    continue

        return total_size / (1024 * 1024)  # Convert to MB

    def _get_commits_to_index(self, repo: Repo, num_commits: int) -> List[Commit]:
        """
        Get commits to index based on configuration.

        Args:
            repo: Git repository
            num_commits: Maximum number of commits

        Returns:
            List of commits to index
        """
        try:
            # Get current branch
            if self.config.indexing.git_index_branches == "current":
                # Index current branch only
                commits = list(repo.iter_commits(max_count=num_commits))
            else:
                # Index all branches
                commits = list(repo.iter_commits("--all", max_count=num_commits))

            logger.debug(f"Found {len(commits)} commits to index")
            return commits

        except Exception as e:
            logger.error(f"Error getting commits: {e}")
            return []

    async def _extract_commit_data(
        self, commit: Commit, repo_path: str, repo: Repo
    ) -> GitCommitData:
        """
        Extract structured data from a git commit.

        Args:
            commit: Git commit object
            repo_path: Repository path
            repo: Git repository

        Returns:
            Structured commit data
        """
        # Extract basic metadata
        commit_hash = commit.hexsha
        author_name = commit.author.name
        author_email = commit.author.email
        author_date = datetime.fromtimestamp(commit.authored_date, UTC)
        committer_name = commit.committer.name
        committer_date = datetime.fromtimestamp(commit.committed_date, UTC)
        message = commit.message.strip()

        # Get branch names containing this commit
        branch_names = []
        try:
            branches = repo.git.branch("--contains", commit_hash).split("\n")
            branch_names = [b.strip().lstrip("* ") for b in branches if b.strip()]
        except Exception as e:
            logger.debug(f"Could not get branches for commit {commit_hash}: {e}")

        # Get tags pointing to this commit
        tags = []
        try:
            for tag in repo.tags:
                if tag.commit == commit:
                    tags.append(tag.name)
        except Exception as e:
            logger.debug(f"Could not get tags for commit {commit_hash}: {e}")

        # Get parent hashes
        parent_hashes = [p.hexsha for p in commit.parents]

        # Get commit stats
        stats = {
            "files_changed": len(commit.stats.files),
            "insertions": commit.stats.total["insertions"],
            "deletions": commit.stats.total["deletions"],
        }

        # Generate embedding for commit message
        message_embedding = await self.embedding_generator.generate(message)

        return GitCommitData(
            commit_hash=commit_hash,
            repository_path=repo_path,
            author_name=author_name,
            author_email=author_email,
            author_date=author_date,
            committer_name=committer_name,
            committer_date=committer_date,
            message=message,
            message_embedding=message_embedding,
            branch_names=branch_names,
            tags=tags,
            parent_hashes=parent_hashes,
            stats=stats,
        )

    async def _extract_file_changes(
        self, commit: Commit, include_diff_content: bool = True
    ) -> List[GitFileChangeData]:
        """
        Extract file changes from a commit.

        Args:
            commit: Git commit object
            include_diff_content: Whether to include diff content

        Returns:
            List of file change data
        """
        file_changes = []

        # Get parent commit for diff
        if not commit.parents:
            # Initial commit - compare against empty tree
            parent = None
        else:
            parent = commit.parents[0]

        try:
            # Get diff between parent and commit
            if parent:
                diffs = parent.diff(commit, create_patch=include_diff_content)
            else:
                # Initial commit
                diffs = commit.diff(None, create_patch=include_diff_content)

            for diff_item in diffs:
                try:
                    file_change = await self._process_diff_item(
                        diff_item, commit.hexsha, include_diff_content
                    )
                    if file_change:
                        file_changes.append(file_change)
                except Exception as e:
                    logger.debug(f"Error processing diff item: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error getting diffs for commit {commit.hexsha}: {e}")

        return file_changes

    async def _process_diff_item(
        self, diff_item: Diff, commit_hash: str, include_diff_content: bool
    ) -> Optional[GitFileChangeData]:
        """
        Process a single diff item.

        Args:
            diff_item: Git diff item
            commit_hash: Commit hash
            include_diff_content: Whether to include diff content

        Returns:
            File change data or None if skipped
        """
        # Determine file path and change type
        if diff_item.new_file:
            file_path = diff_item.b_path
            change_type = "added"
        elif diff_item.deleted_file:
            file_path = diff_item.a_path
            change_type = "deleted"
        elif diff_item.renamed_file:
            file_path = diff_item.b_path
            change_type = "renamed"
        else:
            file_path = diff_item.b_path or diff_item.a_path
            change_type = "modified"

        # Skip if no file path
        if not file_path:
            return None

        # Count lines changed
        lines_added = 0
        lines_deleted = 0

        if hasattr(diff_item, "diff") and diff_item.diff:
            try:
                diff_text = diff_item.diff.decode("utf-8", errors="ignore")
                for line in diff_text.split("\n"):
                    if line.startswith("+") and not line.startswith("+++"):
                        lines_added += 1
                    elif line.startswith("-") and not line.startswith("---"):
                        lines_deleted += 1
            except Exception as e:
                logger.debug(f"Could not count lines for {file_path}: {e}")

        # Extract diff content if requested
        diff_content = None
        diff_embedding = None

        if include_diff_content and hasattr(diff_item, "diff") and diff_item.diff:
            try:
                diff_text = diff_item.diff.decode("utf-8", errors="ignore")

                # Check size limit
                diff_size_kb = len(diff_text) / 1024
                if diff_size_kb > self.config.git_diff_size_limit_kb:
                    logger.debug(
                        f"Skipping diff for {file_path} "
                        f"(size: {diff_size_kb:.1f}KB exceeds limit)"
                    )
                else:
                    diff_content = diff_text
                    # Generate embedding for diff
                    diff_embedding = await self.embedding_generator.generate(diff_text)
                    self.stats["diffs_embedded"] += 1

            except Exception as e:
                logger.debug(f"Could not extract diff content for {file_path}: {e}")

        # Create unique ID
        file_change_id = f"{commit_hash}:{file_path}"

        return GitFileChangeData(
            id=file_change_id,
            commit_hash=commit_hash,
            file_path=file_path,
            change_type=change_type,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            diff_content=diff_content,
            diff_embedding=diff_embedding,
        )

    def get_stats(self) -> Dict[str, int]:
        """Get indexing statistics."""
        return self.stats.copy()
