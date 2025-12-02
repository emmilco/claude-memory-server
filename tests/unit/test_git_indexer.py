"""Unit tests for git history indexing."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, UTC

from src.memory.git_indexer import (
    GitIndexer,
    GitCommitData,
    GitFileChangeData,
    GIT_AVAILABLE,
)
from src.config import ServerConfig
from src.embeddings.generator import EmbeddingGenerator
from tests.conftest import mock_embedding

# Git storage feature implemented in FEAT-055
# Tests enabled as of 2025-11-22


@pytest.fixture
def config():
    """Create test configuration."""
    config = ServerConfig(
        indexing={
            "git_indexing": True,
            "git_index_commit_count": 10,
            "git_index_branches": "current",
            "git_index_diffs": True,
        }
    )
    return config


@pytest.fixture
def embedding_generator():
    """Create mock embedding generator."""
    gen = Mock(spec=EmbeddingGenerator)
    gen.generate = AsyncMock(return_value=mock_embedding(value=0.1))
    return gen


@pytest.fixture
def git_indexer(config, embedding_generator):
    """Create GitIndexer instance."""
    if not GIT_AVAILABLE:
        pytest.skip("GitPython not available")
    return GitIndexer(config, embedding_generator)


class TestGitIndexerInitialization:
    """Test GitIndexer initialization."""

    def test_initialization_without_gitpython(self, config, embedding_generator):
        """Test initialization fails gracefully without GitPython."""
        with patch("src.memory.git_indexer.GIT_AVAILABLE", False):
            with pytest.raises(ImportError, match="GitPython is required"):
                GitIndexer(config, embedding_generator)

    def test_initialization_with_gitpython(self, git_indexer, config):
        """Test successful initialization with GitPython."""
        assert git_indexer.config == config
        assert git_indexer.stats["repos_indexed"] == 0
        assert git_indexer.stats["commits_indexed"] == 0
        assert git_indexer.stats["file_changes_indexed"] == 0
        assert git_indexer.stats["diffs_embedded"] == 0
        assert git_indexer.stats["errors"] == 0

    def test_initial_stats(self, git_indexer):
        """Test initial statistics."""
        stats = git_indexer.get_stats()
        assert stats == {
            "repos_indexed": 0,
            "commits_indexed": 0,
            "file_changes_indexed": 0,
            "diffs_embedded": 0,
            "errors": 0,
        }


class TestRepositoryIndexing:
    """Test repository indexing functionality."""

    @pytest.mark.asyncio
    async def test_index_repository_disabled(self, git_indexer):
        """Test indexing returns empty when disabled."""
        git_indexer.config.indexing.git_indexing = False
        commits, changes = await git_indexer.index_repository("/fake/path", "test")
        assert commits == []
        assert changes == []

    @pytest.mark.asyncio
    async def test_index_repository_nonexistent_path(self, git_indexer):
        """Test indexing fails with nonexistent path."""
        with pytest.raises(ValueError, match="does not exist"):
            await git_indexer.index_repository("/nonexistent/path", "test")

    @pytest.mark.asyncio
    async def test_index_repository_not_git_repo(self, git_indexer, tmp_path):
        """Test indexing fails with non-git directory."""
        with pytest.raises(ValueError, match="Not a git repository"):
            await git_indexer.index_repository(str(tmp_path), "test")

    @pytest.mark.asyncio
    async def test_index_repository_auto_disable_diffs(self, git_indexer, tmp_path):
        """Test diffs auto-disabled for large repositories."""
        # Create fake git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        with patch("src.memory.git_indexer.Repo") as mock_repo_class:
            mock_repo = Mock()
            mock_repo_class.return_value = mock_repo
            mock_repo.iter_commits.return_value = []

            # Mock large repo size
            with patch.object(git_indexer, "_get_repo_size_mb", return_value=600):
                commits, changes = await git_indexer.index_repository(
                    str(tmp_path), "test", include_diffs=None
                )
                # Should complete with diffs disabled due to size
                assert commits == []
                assert changes == []

    @pytest.mark.asyncio
    async def test_index_repository_with_commits(self, git_indexer, tmp_path):
        """Test indexing repository with commits."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create mock commit
        mock_commit = Mock()
        mock_commit.hexsha = "abc123"
        mock_commit.author.name = "Test Author"
        mock_commit.author.email = "test@example.com"
        mock_commit.authored_date = 1700000000
        mock_commit.committer.name = "Test Committer"
        mock_commit.committer.email = "committer@example.com"
        mock_commit.committed_date = 1700000000
        mock_commit.message = "Test commit message"
        mock_commit.parents = []
        mock_commit.stats.files = {"file.py": {}}
        mock_commit.stats.total = {"insertions": 10, "deletions": 5}

        with patch("src.memory.git_indexer.Repo") as mock_repo_class:
            mock_repo = Mock()
            mock_repo_class.return_value = mock_repo
            mock_repo.iter_commits.return_value = [mock_commit]
            mock_repo.git.branch.return_value = "main"
            mock_repo.tags = []

            commits, changes = await git_indexer.index_repository(
                str(tmp_path), "test", include_diffs=False
            )

            assert len(commits) == 1
            assert commits[0].commit_hash == "abc123"
            assert commits[0].author_name == "Test Author"
            assert commits[0].message == "Test commit message"
            assert changes == []  # No diffs requested

    @pytest.mark.asyncio
    async def test_index_repository_error_handling(self, git_indexer, tmp_path):
        """Test error handling during commit processing."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create mock commits (one will fail)
        mock_commit1 = Mock()
        mock_commit1.hexsha = "abc123"

        mock_commit2 = Mock()
        mock_commit2.hexsha = "def456"
        mock_commit2.author.name = "Test Author"
        mock_commit2.author.email = "test@example.com"
        mock_commit2.authored_date = 1700000000
        mock_commit2.committer.name = "Test Committer"
        mock_commit2.committer.email = "committer@example.com"
        mock_commit2.committed_date = 1700000000
        mock_commit2.message = "Test commit"
        mock_commit2.parents = []
        mock_commit2.stats.files = {}
        mock_commit2.stats.total = {"insertions": 0, "deletions": 0}

        with patch("src.memory.git_indexer.Repo") as mock_repo_class:
            mock_repo = Mock()
            mock_repo_class.return_value = mock_repo
            mock_repo.iter_commits.return_value = [mock_commit1, mock_commit2]
            mock_repo.git.branch.return_value = "main"
            mock_repo.tags = []

            # Make first commit fail (missing author)
            mock_commit1.author.name = Mock(side_effect=Exception("Test error"))

            commits, changes = await git_indexer.index_repository(
                str(tmp_path), "test", include_diffs=False
            )

            # Should process second commit successfully
            assert len(commits) == 1
            assert commits[0].commit_hash == "def456"
            assert git_indexer.stats["errors"] == 1


class TestCommitExtraction:
    """Test commit data extraction."""

    @pytest.mark.asyncio
    async def test_extract_commit_data(self, git_indexer):
        """Test extracting data from a commit."""
        mock_commit = Mock()
        mock_commit.hexsha = "abc123"
        mock_commit.author.name = "Test Author"
        mock_commit.author.email = "test@example.com"
        mock_commit.authored_date = 1700000000
        mock_commit.committer.name = "Test Committer"
        mock_commit.committer.email = "committer@example.com"
        mock_commit.committed_date = 1700000000
        mock_commit.message = "Test commit\n\nWith description"
        mock_commit.parents = []
        mock_commit.stats.files = {"file1.py": {}, "file2.py": {}}
        mock_commit.stats.total = {"insertions": 15, "deletions": 3}

        mock_repo = Mock()
        mock_repo.git.branch.return_value = "* main\n  develop"
        mock_repo.tags = []

        commit_data = await git_indexer._extract_commit_data(
            mock_commit, "/repo/path", mock_repo
        )

        assert commit_data.commit_hash == "abc123"
        assert commit_data.author_name == "Test Author"
        assert commit_data.author_email == "test@example.com"
        assert commit_data.message == "Test commit\n\nWith description"
        assert commit_data.branch_names == ["main", "develop"]
        assert commit_data.stats["files_changed"] == 2
        assert commit_data.stats["insertions"] == 15
        assert commit_data.stats["deletions"] == 3
        assert len(commit_data.message_embedding) == 768

    @pytest.mark.asyncio
    async def test_extract_commit_with_tags(self, git_indexer):
        """Test extracting commit with tags."""
        mock_commit = Mock()
        mock_commit.hexsha = "abc123"
        mock_commit.author.name = "Test"
        mock_commit.author.email = "test@example.com"
        mock_commit.authored_date = 1700000000
        mock_commit.committer.name = "Test"
        mock_commit.committer.email = "test@example.com"
        mock_commit.committed_date = 1700000000
        mock_commit.message = "Release v1.0"
        mock_commit.parents = []
        mock_commit.stats.files = {}
        mock_commit.stats.total = {"insertions": 0, "deletions": 0}

        # Create mock tag
        mock_tag = Mock()
        mock_tag.name = "v1.0.0"
        mock_tag.commit = mock_commit

        mock_repo = Mock()
        mock_repo.git.branch.return_value = "main"
        mock_repo.tags = [mock_tag]

        commit_data = await git_indexer._extract_commit_data(
            mock_commit, "/repo/path", mock_repo
        )

        assert commit_data.tags == ["v1.0.0"]

    @pytest.mark.asyncio
    async def test_extract_commit_with_parents(self, git_indexer):
        """Test extracting commit with parent commits."""
        mock_parent = Mock()
        mock_parent.hexsha = "parent123"

        mock_commit = Mock()
        mock_commit.hexsha = "abc123"
        mock_commit.author.name = "Test"
        mock_commit.author.email = "test@example.com"
        mock_commit.authored_date = 1700000000
        mock_commit.committer.name = "Test"
        mock_commit.committer.email = "test@example.com"
        mock_commit.committed_date = 1700000000
        mock_commit.message = "Merge commit"
        mock_commit.parents = [mock_parent]
        mock_commit.stats.files = {}
        mock_commit.stats.total = {"insertions": 0, "deletions": 0}

        mock_repo = Mock()
        mock_repo.git.branch.return_value = "main"
        mock_repo.tags = []

        commit_data = await git_indexer._extract_commit_data(
            mock_commit, "/repo/path", mock_repo
        )

        assert commit_data.parent_hashes == ["parent123"]


class TestFileChangeExtraction:
    """Test file change extraction."""

    @pytest.mark.asyncio
    async def test_extract_file_changes_initial_commit(self, git_indexer):
        """Test extracting file changes from initial commit."""
        mock_commit = Mock()
        mock_commit.hexsha = "abc123"
        mock_commit.parents = []

        # Mock diff for initial commit
        mock_diff_item = Mock()
        mock_diff_item.new_file = True
        mock_diff_item.deleted_file = False
        mock_diff_item.renamed_file = False
        mock_diff_item.b_path = "README.md"
        mock_diff_item.diff = b"+# Test Project\n+First line"

        mock_commit.diff.return_value = [mock_diff_item]

        file_changes = await git_indexer._extract_file_changes(
            mock_commit, include_diff_content=False
        )

        assert len(file_changes) == 1
        assert file_changes[0].commit_hash == "abc123"
        assert file_changes[0].file_path == "README.md"
        assert file_changes[0].change_type == "added"
        assert file_changes[0].lines_added == 2
        assert file_changes[0].diff_content is None

    @pytest.mark.asyncio
    async def test_extract_file_changes_with_diff_content(self, git_indexer):
        """Test extracting file changes with diff content."""
        mock_parent = Mock()
        mock_commit = Mock()
        mock_commit.hexsha = "abc123"
        mock_commit.parents = [mock_parent]

        # Mock diff item
        mock_diff_item = Mock()
        mock_diff_item.new_file = False
        mock_diff_item.deleted_file = False
        mock_diff_item.renamed_file = False
        mock_diff_item.b_path = "file.py"
        mock_diff_item.diff = b"+added line\n-removed line"

        mock_parent.diff.return_value = [mock_diff_item]

        file_changes = await git_indexer._extract_file_changes(
            mock_commit, include_diff_content=True
        )

        assert len(file_changes) == 1
        assert file_changes[0].diff_content is not None
        assert file_changes[0].diff_embedding is not None
        assert len(file_changes[0].diff_embedding) == 768

    @pytest.mark.asyncio
    async def test_extract_file_changes_deleted_file(self, git_indexer):
        """Test extracting deleted file change."""
        mock_parent = Mock()
        mock_commit = Mock()
        mock_commit.hexsha = "abc123"
        mock_commit.parents = [mock_parent]

        mock_diff_item = Mock()
        mock_diff_item.new_file = False
        mock_diff_item.deleted_file = True
        mock_diff_item.renamed_file = False
        mock_diff_item.a_path = "old_file.py"
        mock_diff_item.diff = b"-deleted content"

        mock_parent.diff.return_value = [mock_diff_item]

        file_changes = await git_indexer._extract_file_changes(
            mock_commit, include_diff_content=False
        )

        assert len(file_changes) == 1
        assert file_changes[0].file_path == "old_file.py"
        assert file_changes[0].change_type == "deleted"

    @pytest.mark.asyncio
    async def test_extract_file_changes_renamed_file(self, git_indexer):
        """Test extracting renamed file change."""
        mock_parent = Mock()
        mock_commit = Mock()
        mock_commit.hexsha = "abc123"
        mock_commit.parents = [mock_parent]

        mock_diff_item = Mock()
        mock_diff_item.new_file = False
        mock_diff_item.deleted_file = False
        mock_diff_item.renamed_file = True
        mock_diff_item.a_path = "old_name.py"
        mock_diff_item.b_path = "new_name.py"
        mock_diff_item.diff = b""

        mock_parent.diff.return_value = [mock_diff_item]

        file_changes = await git_indexer._extract_file_changes(
            mock_commit, include_diff_content=False
        )

        assert len(file_changes) == 1
        assert file_changes[0].file_path == "new_name.py"
        assert file_changes[0].change_type == "renamed"

    @pytest.mark.asyncio
    async def test_extract_file_changes_size_limit(self, git_indexer):
        """Test diff size limit enforcement."""
        git_indexer.config.git_diff_size_limit_kb = 0.001  # Very small limit

        mock_parent = Mock()
        mock_commit = Mock()
        mock_commit.hexsha = "abc123"
        mock_commit.parents = [mock_parent]

        # Large diff
        large_diff = b"+line\n" * 1000
        mock_diff_item = Mock()
        mock_diff_item.new_file = False
        mock_diff_item.deleted_file = False
        mock_diff_item.renamed_file = False
        mock_diff_item.b_path = "file.py"
        mock_diff_item.diff = large_diff

        mock_parent.diff.return_value = [mock_diff_item]

        file_changes = await git_indexer._extract_file_changes(
            mock_commit, include_diff_content=True
        )

        # Should skip diff due to size
        assert len(file_changes) == 1
        assert file_changes[0].diff_content is None
        assert file_changes[0].diff_embedding is None


class TestDiffProcessing:
    """Test diff item processing."""

    @pytest.mark.asyncio
    async def test_process_diff_item_added_file(self, git_indexer):
        """Test processing added file diff."""
        mock_diff = Mock()
        mock_diff.new_file = True
        mock_diff.deleted_file = False
        mock_diff.renamed_file = False
        mock_diff.b_path = "new_file.py"
        mock_diff.diff = b"+new content"

        result = await git_indexer._process_diff_item(
            mock_diff, "abc123", include_diff_content=True
        )

        assert result is not None
        assert result.id == "abc123:new_file.py"
        assert result.change_type == "added"
        assert result.file_path == "new_file.py"
        assert result.lines_added == 1

    @pytest.mark.asyncio
    async def test_process_diff_item_no_path(self, git_indexer):
        """Test processing diff with no path (should skip)."""
        mock_diff = Mock()
        mock_diff.new_file = False
        mock_diff.deleted_file = False
        mock_diff.renamed_file = False
        mock_diff.a_path = None
        mock_diff.b_path = None

        result = await git_indexer._process_diff_item(
            mock_diff, "abc123", include_diff_content=False
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_process_diff_item_line_counting(self, git_indexer):
        """Test accurate line counting in diffs."""
        mock_diff = Mock()
        mock_diff.new_file = False
        mock_diff.deleted_file = False
        mock_diff.renamed_file = False
        mock_diff.b_path = "file.py"
        mock_diff.diff = b"""--- a/file.py
+++ b/file.py
+added line 1
+added line 2
-removed line 1
 unchanged line
+added line 3
-removed line 2
"""

        result = await git_indexer._process_diff_item(
            mock_diff, "abc123", include_diff_content=False
        )

        assert result is not None
        assert result.lines_added == 3
        assert result.lines_deleted == 2


class TestHelperMethods:
    """Test helper methods."""

    def test_get_repo_size_mb(self, git_indexer, tmp_path):
        """Test repository size calculation."""
        # Create fake .git directory with files
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        # Create some files
        (git_dir / "config").write_text("test config")
        objects_dir = git_dir / "objects"
        objects_dir.mkdir()
        (objects_dir / "pack1").write_bytes(b"x" * 1024 * 100)  # 100KB

        size_mb = git_indexer._get_repo_size_mb(tmp_path)
        assert size_mb > 0
        assert size_mb < 1  # Should be less than 1MB

    def test_get_repo_size_mb_no_git_dir(self, git_indexer, tmp_path):
        """Test size calculation with no .git directory."""
        size_mb = git_indexer._get_repo_size_mb(tmp_path)
        assert size_mb == 0.0

    def test_get_commits_to_index_current_branch(self, git_indexer):
        """Test getting commits from current branch."""
        mock_commit1 = Mock()
        mock_commit2 = Mock()

        mock_repo = Mock()
        mock_repo.iter_commits.return_value = [mock_commit1, mock_commit2]

        git_indexer.config.indexing.git_index_branches = "current"
        commits = git_indexer._get_commits_to_index(mock_repo, 10)

        assert len(commits) == 2
        mock_repo.iter_commits.assert_called_once_with(max_count=10)

    def test_get_commits_to_index_all_branches(self, git_indexer):
        """Test getting commits from all branches."""
        mock_commit1 = Mock()
        mock_commit2 = Mock()
        mock_commit3 = Mock()

        mock_repo = Mock()
        mock_repo.iter_commits.return_value = [mock_commit1, mock_commit2, mock_commit3]

        git_indexer.config.indexing.git_index_branches = "all"
        commits = git_indexer._get_commits_to_index(mock_repo, 10)

        assert len(commits) == 3
        mock_repo.iter_commits.assert_called_once_with("--all", max_count=10)

    def test_get_commits_error_handling(self, git_indexer):
        """Test error handling when getting commits."""
        mock_repo = Mock()
        mock_repo.iter_commits.side_effect = Exception("Git error")

        commits = git_indexer._get_commits_to_index(mock_repo, 10)
        assert commits == []


class TestDataClasses:
    """Test data class structures."""

    def test_git_commit_data_creation(self):
        """Test creating GitCommitData."""
        data = GitCommitData(
            commit_hash="abc123",
            repository_path="/repo",
            author_name="Test Author",
            author_email="test@example.com",
            author_date=datetime.now(UTC),
            committer_name="Test Committer",
            committer_date=datetime.now(UTC),
            message="Test message",
            message_embedding=mock_embedding(value=0.1),
            branch_names=["main"],
            tags=["v1.0"],
            parent_hashes=["parent123"],
            stats={"files_changed": 1, "insertions": 10, "deletions": 5},
        )

        assert data.commit_hash == "abc123"
        assert data.author_name == "Test Author"
        assert len(data.message_embedding) == 768

    def test_git_file_change_data_creation(self):
        """Test creating GitFileChangeData."""
        data = GitFileChangeData(
            id="abc123:file.py",
            commit_hash="abc123",
            file_path="file.py",
            change_type="modified",
            lines_added=5,
            lines_deleted=2,
            diff_content="diff content",
            diff_embedding=mock_embedding(value=0.1),
        )

        assert data.id == "abc123:file.py"
        assert data.change_type == "modified"
        assert data.diff_content == "diff content"


class TestStatistics:
    """Test statistics tracking."""

    def test_initial_statistics(self, git_indexer):
        """Test initial statistics are zero."""
        stats = git_indexer.get_stats()
        assert all(v == 0 for v in stats.values())

    def test_statistics_copy(self, git_indexer):
        """Test get_stats returns a copy."""
        stats1 = git_indexer.get_stats()
        stats1["repos_indexed"] = 999

        stats2 = git_indexer.get_stats()
        assert stats2["repos_indexed"] == 0

    @pytest.mark.asyncio
    async def test_statistics_update_on_indexing(self, git_indexer, tmp_path):
        """Test statistics update during indexing."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()

        mock_commit = Mock()
        mock_commit.hexsha = "abc123"
        mock_commit.author.name = "Test"
        mock_commit.author.email = "test@example.com"
        mock_commit.authored_date = 1700000000
        mock_commit.committer.name = "Test"
        mock_commit.committer.email = "test@example.com"
        mock_commit.committed_date = 1700000000
        mock_commit.message = "Test"
        mock_commit.parents = []
        mock_commit.stats.files = {}
        mock_commit.stats.total = {"insertions": 0, "deletions": 0}

        with patch("src.memory.git_indexer.Repo") as mock_repo_class:
            mock_repo = Mock()
            mock_repo_class.return_value = mock_repo
            mock_repo.iter_commits.return_value = [mock_commit]
            mock_repo.git.branch.return_value = "main"
            mock_repo.tags = []

            await git_indexer.index_repository(
                str(tmp_path), "test", include_diffs=False
            )

            stats = git_indexer.get_stats()
            assert stats["repos_indexed"] == 1
            assert stats["commits_indexed"] == 1
