"""Tests for CodeIndexingService - Code search, indexing, and dependency analysis.

This test suite covers:
- Code search with semantic and hybrid modes
- Finding similar code snippets
- Indexing codebases
- Re-indexing projects
- Getting indexed files and units
- File dependency analysis
- Dependency path finding
- Dependency statistics
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.code_indexing_service import CodeIndexingService
from src.config import ServerConfig
from src.core.exceptions import (
    StorageError,
    ValidationError,
    ReadOnlyError,
    RetrievalError,
)
from tests.conftest import mock_embedding


class TestCodeIndexingServiceInit:
    """Test CodeIndexingService initialization."""

    def test_initialization_with_required_dependencies(self):
        """Test service initializes with required dependencies."""
        store = MagicMock()
        embedding_generator = MagicMock()
        embedding_cache = MagicMock()
        config = ServerConfig()

        service = CodeIndexingService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=embedding_cache,
            config=config,
        )

        assert service.store == store
        assert service.embedding_generator == embedding_generator
        assert service.embedding_cache == embedding_cache
        assert service.config == config

    def test_initialization_with_all_optional_dependencies(self):
        """Test service initializes with all optional dependencies."""
        store = MagicMock()
        embedding_generator = MagicMock()
        embedding_cache = MagicMock()
        config = ServerConfig()
        hybrid_searcher = MagicMock()
        metrics_collector = MagicMock()
        duplicate_detector = MagicMock()
        quality_analyzer = MagicMock()

        service = CodeIndexingService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=embedding_cache,
            config=config,
            hybrid_searcher=hybrid_searcher,
            metrics_collector=metrics_collector,
            duplicate_detector=duplicate_detector,
            quality_analyzer=quality_analyzer,
            project_name="test-project",
        )

        assert service.hybrid_searcher == hybrid_searcher
        assert service.metrics_collector == metrics_collector
        assert service.duplicate_detector == duplicate_detector
        assert service.quality_analyzer == quality_analyzer
        assert service.project_name == "test-project"

    def test_initial_stats_are_zero(self):
        """Test service stats start at zero."""
        service = CodeIndexingService(
            store=MagicMock(),
            embedding_generator=MagicMock(),
            embedding_cache=MagicMock(),
            config=ServerConfig(),
        )

        stats = service.get_stats()
        assert stats["searches_performed"] == 0
        assert stats["files_indexed"] == 0
        assert stats["units_indexed"] == 0
        assert stats["similar_code_searches"] == 0


class TestConfidenceLabels:
    """Test confidence label generation."""

    @pytest.fixture
    def service(self):
        """Create service instance for label tests."""
        return CodeIndexingService(
            store=MagicMock(),
            embedding_generator=MagicMock(),
            embedding_cache=MagicMock(),
            config=ServerConfig(),
        )

    def test_excellent_confidence(self, service):
        """Test scores above 0.8 yield excellent."""
        assert service._get_confidence_label(0.85) == "excellent"
        assert service._get_confidence_label(0.95) == "excellent"
        assert service._get_confidence_label(1.0) == "excellent"

    def test_good_confidence(self, service):
        """Test scores 0.6-0.8 yield good."""
        assert service._get_confidence_label(0.6) == "good"
        assert service._get_confidence_label(0.7) == "good"
        assert service._get_confidence_label(0.8) == "good"

    def test_weak_confidence(self, service):
        """Test scores below 0.6 yield weak."""
        assert service._get_confidence_label(0.3) == "weak"
        assert service._get_confidence_label(0.5) == "weak"
        assert service._get_confidence_label(0.59) == "weak"


class TestSearchQualityAnalysis:
    """Test search quality analysis."""

    @pytest.fixture
    def service(self):
        """Create service instance for quality analysis tests."""
        return CodeIndexingService(
            store=MagicMock(),
            embedding_generator=MagicMock(),
            embedding_cache=MagicMock(),
            config=ServerConfig(),
        )

    def test_no_results_quality(self, service):
        """Test quality analysis with no results."""
        result = service._analyze_search_quality([], "test query", "project")

        assert result["quality"] == "no_results"
        assert result["confidence"] == "none"
        assert len(result["suggestions"]) > 0

    def test_excellent_quality(self, service):
        """Test quality analysis with excellent results."""
        results = [
            {"relevance_score": 0.90, "code": "def test(): pass"},
            {"relevance_score": 0.85, "code": "def test2(): pass"},
        ]

        result = service._analyze_search_quality(results, "test", "project")

        assert result["quality"] == "excellent"
        assert result["confidence"] == "high"

    def test_good_quality(self, service):
        """Test quality analysis with good results."""
        results = [
            {"relevance_score": 0.75, "code": "def func(): pass"},
        ]

        result = service._analyze_search_quality(results, "func", "project")

        assert result["quality"] == "good"
        assert result["confidence"] == "medium"

    def test_fair_quality(self, service):
        """Test quality analysis with fair results."""
        results = [
            {"relevance_score": 0.55, "code": "def something(): pass"},
        ]

        result = service._analyze_search_quality(results, "something", "project")

        assert result["quality"] == "fair"
        assert result["confidence"] == "low"

    def test_poor_quality(self, service):
        """Test quality analysis with poor results."""
        results = [
            {"relevance_score": 0.3, "code": "def unrelated(): pass"},
        ]

        result = service._analyze_search_quality(results, "search term", "project")

        assert result["quality"] == "poor"
        assert result["confidence"] == "very_low"

    def test_keyword_matching(self, service):
        """Test keyword matching in quality analysis."""
        results = [
            {"relevance_score": 0.7, "code": "def authenticate_user(): pass"},
        ]

        result = service._analyze_search_quality(
            results, "authenticate user", "project"
        )

        assert (
            "authenticate" in result["matched_keywords"]
            or "user" in result["matched_keywords"]
        )


class TestSearchCode:
    """Test code search operations."""

    @pytest.fixture
    def service(self):
        """Create service instance with mocked dependencies."""
        mock_memory = MagicMock()
        mock_memory.id = "code_123"
        mock_memory.content = "def authenticate(user): pass"
        mock_memory.metadata = {
            "file_path": "/project/auth.py",
            "language": "python",
            "unit_name": "authenticate",
            "unit_type": "function",
            "start_line": 10,
            "end_line": 15,
            "signature": "def authenticate(user)",
        }

        store = AsyncMock()
        store.retrieve = AsyncMock(return_value=[(mock_memory, 0.85)])

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=mock_embedding(value=0.1))

        embedding_cache = AsyncMock()
        embedding_cache.get = AsyncMock(return_value=None)
        embedding_cache.set = AsyncMock()

        config = ServerConfig()

        return CodeIndexingService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=embedding_cache,
            config=config,
            project_name="test-project",
        )

    @pytest.mark.asyncio
    async def test_search_code_success(self, service):
        """Test searching code successfully."""
        result = await service.search_code(
            query="authentication function",
            limit=5,
        )

        assert result["status"] == "success"
        assert "results" in result
        assert "query_time_ms" in result
        assert result["total_found"] == 1

    @pytest.mark.asyncio
    async def test_search_code_empty_query(self, service):
        """Test searching with empty query returns empty results."""
        result = await service.search_code(query="", limit=5)

        assert result["status"] == "success"
        assert result["total_found"] == 0
        assert result["quality"] == "poor"

    @pytest.mark.asyncio
    async def test_search_code_invalid_mode_raises(self, service):
        """Test invalid search mode raises RetrievalError."""
        with pytest.raises(RetrievalError):
            await service.search_code(
                query="test",
                search_mode="invalid_mode",
            )

    @pytest.mark.asyncio
    async def test_search_code_with_filters(self, service):
        """Test code search with file and language filters."""
        result = await service.search_code(
            query="auth",
            file_pattern="auth",
            language="python",
        )

        assert result["status"] == "success"
        assert len(result["results"]) == 1

    @pytest.mark.asyncio
    async def test_search_code_filters_by_file_pattern(self, service):
        """Test file pattern filtering."""
        # Set up memory that doesn't match pattern
        mock_memory = MagicMock()
        mock_memory.id = "code_456"
        mock_memory.content = "def other(): pass"
        mock_memory.metadata = {
            "file_path": "/project/utils.py",  # Won't match "auth" pattern
            "language": "python",
            "unit_name": "other",
            "start_line": 1,
        }
        service.store.retrieve = AsyncMock(return_value=[(mock_memory, 0.7)])

        result = await service.search_code(
            query="function",
            file_pattern="nonexistent",  # Won't match
        )

        assert result["total_found"] == 0

    @pytest.mark.asyncio
    async def test_search_code_increments_stats(self, service):
        """Test search increments statistics."""
        initial_stats = service.get_stats()
        await service.search_code(query="test")

        stats = service.get_stats()
        assert stats["searches_performed"] == initial_stats["searches_performed"] + 1

    @pytest.mark.asyncio
    async def test_search_code_hybrid_mode_without_searcher(self, service):
        """Test hybrid mode falls back to semantic when searcher not available."""
        service.hybrid_searcher = None

        result = await service.search_code(
            query="test",
            search_mode="hybrid",
        )

        assert result["search_mode"] == "semantic"  # Falls back

    @pytest.mark.asyncio
    async def test_search_code_hybrid_mode_with_searcher(self, service):
        """Test hybrid search mode with hybrid searcher."""
        hybrid_searcher = MagicMock()
        hybrid_searcher.index_documents = MagicMock()

        mock_result = MagicMock()
        mock_result.memory = MagicMock()
        mock_result.memory.id = "code_123"
        mock_result.memory.content = "def test(): pass"
        mock_result.memory.metadata = {
            "file_path": "/test.py",
            "language": "python",
            "unit_name": "test",
            "start_line": 1,
        }
        mock_result.total_score = 0.9

        hybrid_searcher.hybrid_search = MagicMock(return_value=[mock_result])

        service.hybrid_searcher = hybrid_searcher

        result = await service.search_code(
            query="test function",
            search_mode="hybrid",
        )

        assert result["search_mode"] == "hybrid"
        hybrid_searcher.index_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_code_with_quality_metrics(self, service):
        """Test code search with quality metrics enabled."""
        duplicate_detector = AsyncMock()
        duplicate_detector.calculate_duplication_score = AsyncMock(return_value=0.1)

        quality_analyzer = MagicMock()
        quality_metrics = MagicMock()
        quality_metrics.cyclomatic_complexity = 5
        quality_metrics.line_count = 20
        quality_metrics.nesting_depth = 2
        quality_metrics.parameter_count = 2
        quality_metrics.has_documentation = True
        quality_metrics.duplication_score = 0.1
        quality_metrics.maintainability_index = 75
        quality_metrics.quality_flags = []
        quality_analyzer.calculate_quality_metrics = MagicMock(
            return_value=quality_metrics
        )

        service.duplicate_detector = duplicate_detector
        service.quality_analyzer = quality_analyzer

        result = await service.search_code(
            query="test",
            include_quality_metrics=True,
        )

        assert result["status"] == "success"
        if result["results"]:
            assert "quality_metrics" in result["results"][0]


class TestFindSimilarCode:
    """Test finding similar code snippets."""

    @pytest.fixture
    def service(self):
        """Create service instance for similar code tests."""
        mock_memory = MagicMock()
        mock_memory.id = "code_123"
        mock_memory.content = "def similar_function(): pass"
        mock_memory.metadata = {
            "file_path": "/project/similar.py",
            "language": "python",
            "unit_name": "similar_function",
            "start_line": 1,
            "end_line": 2,
        }

        store = AsyncMock()
        store.retrieve = AsyncMock(return_value=[(mock_memory, 0.92)])

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=mock_embedding(value=0.1))

        embedding_cache = AsyncMock()
        embedding_cache.get = AsyncMock(return_value=None)
        embedding_cache.set = AsyncMock()

        return CodeIndexingService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=embedding_cache,
            config=ServerConfig(),
            project_name="test-project",
        )

    @pytest.mark.asyncio
    async def test_find_similar_code_success(self, service):
        """Test finding similar code successfully."""
        result = await service.find_similar_code(
            code_snippet="def my_function(): pass",
            limit=10,
        )

        assert "results" in result
        assert "total_found" in result
        assert result["total_found"] == 1

    @pytest.mark.asyncio
    async def test_find_similar_code_empty_snippet_raises(self, service):
        """Test empty snippet raises ValidationError."""
        with pytest.raises(ValidationError):
            await service.find_similar_code(code_snippet="")

    @pytest.mark.asyncio
    async def test_find_similar_code_with_filters(self, service):
        """Test finding similar code with filters."""
        result = await service.find_similar_code(
            code_snippet="def test(): pass",
            file_pattern="similar",
            language="python",
        )

        assert result["total_found"] == 1

    @pytest.mark.asyncio
    async def test_find_similar_code_increments_stats(self, service):
        """Test similar code search increments statistics."""
        initial_stats = service.get_stats()
        await service.find_similar_code(code_snippet="def test(): pass")

        stats = service.get_stats()
        assert (
            stats["similar_code_searches"] == initial_stats["similar_code_searches"] + 1
        )

    @pytest.mark.asyncio
    async def test_find_similar_code_interpretation_duplicates(self, service):
        """Test interpretation for likely duplicates."""
        mock_memory = MagicMock()
        mock_memory.id = "code_123"
        mock_memory.content = "def test(): pass"
        mock_memory.metadata = {
            "file_path": "/test.py",
            "language": "python",
            "unit_name": "test",
            "start_line": 1,
        }
        service.store.retrieve = AsyncMock(return_value=[(mock_memory, 0.98)])

        result = await service.find_similar_code(code_snippet="def test(): pass")

        assert "duplicate" in result["interpretation"].lower()


class TestIndexCodebase:
    """Test codebase indexing operations."""

    @pytest.fixture
    def service(self):
        """Create service instance for indexing tests."""
        store = AsyncMock()

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=mock_embedding(value=0.1))

        return CodeIndexingService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_index_codebase_success(self, service, tmp_path):
        """Test indexing a codebase successfully."""
        # Create test file
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")

        with patch("src.memory.incremental_indexer.IncrementalIndexer") as MockIndexer:
            mock_indexer = AsyncMock()
            mock_indexer.initialize = AsyncMock()
            mock_indexer.index_directory = AsyncMock(
                return_value={
                    "indexed_files": 1,
                    "total_units": 1,
                    "languages": {"python": 1},
                }
            )
            MockIndexer.return_value = mock_indexer

            result = await service.index_codebase(
                directory_path=str(tmp_path),
                project_name="test-project",
            )

            assert result["status"] == "success"
            assert result["files_indexed"] == 1
            assert result["units_indexed"] == 1

    @pytest.mark.asyncio
    async def test_index_codebase_nonexistent_directory_raises(self, service):
        """Test indexing non-existent directory raises."""
        with pytest.raises((ValueError, StorageError)):
            await service.index_codebase(
                directory_path="/nonexistent/directory",
            )

    @pytest.mark.asyncio
    async def test_index_codebase_file_instead_of_directory_raises(
        self, service, tmp_path
    ):
        """Test indexing a file instead of directory raises."""
        test_file = tmp_path / "test.py"
        test_file.write_text("test")

        with pytest.raises((ValueError, StorageError)):
            await service.index_codebase(directory_path=str(test_file))

    @pytest.mark.asyncio
    async def test_index_codebase_read_only_mode_raises(self, service, tmp_path):
        """Test indexing in read-only mode raises."""
        service.config.advanced.read_only_mode = True

        with pytest.raises(ReadOnlyError):
            await service.index_codebase(directory_path=str(tmp_path))


class TestReindexProject:
    """Test project re-indexing operations."""

    @pytest.fixture
    def service(self):
        """Create service instance for reindex tests."""
        store = AsyncMock()
        store.delete_code_units_by_project = AsyncMock(return_value=10)

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=mock_embedding(value=0.1))

        return CodeIndexingService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_reindex_project_success(self, service, tmp_path):
        """Test reindexing a project successfully."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")

        with patch("src.memory.incremental_indexer.IncrementalIndexer") as MockIndexer:
            mock_indexer = AsyncMock()
            mock_indexer.index_directory = AsyncMock(
                return_value={
                    "indexed_files": 1,
                    "total_units": 1,
                    "languages": {"python": 1},
                }
            )
            MockIndexer.return_value = mock_indexer

            result = await service.reindex_project(
                project_name="test-project",
                directory_path=str(tmp_path),
                clear_existing=True,
            )

            assert result["status"] == "success"
            assert result["index_cleared"] is True
            assert result["units_deleted"] == 10

    @pytest.mark.asyncio
    async def test_reindex_project_without_clearing(self, service, tmp_path):
        """Test reindexing without clearing existing index."""
        test_file = tmp_path / "test.py"
        test_file.write_text("def test(): pass")

        with patch("src.memory.incremental_indexer.IncrementalIndexer") as MockIndexer:
            mock_indexer = AsyncMock()
            mock_indexer.index_directory = AsyncMock(
                return_value={
                    "indexed_files": 1,
                    "total_units": 1,
                    "languages": {},
                }
            )
            MockIndexer.return_value = mock_indexer

            result = await service.reindex_project(
                project_name="test-project",
                directory_path=str(tmp_path),
                clear_existing=False,
            )

            assert result["index_cleared"] is False
            assert result["units_deleted"] == 0

    @pytest.mark.asyncio
    async def test_reindex_project_read_only_raises(self, service, tmp_path):
        """Test reindexing in read-only mode raises."""
        service.config.advanced.read_only_mode = True

        with pytest.raises(ReadOnlyError):
            await service.reindex_project(
                project_name="test",
                directory_path=str(tmp_path),
            )


class TestGetIndexedFiles:
    """Test getting indexed files."""

    @pytest.fixture
    def service(self):
        """Create service instance for indexed files tests."""
        store = AsyncMock()
        store.get_indexed_files = AsyncMock(
            return_value={
                "files": [{"file_path": "/test.py", "language": "python"}],
                "total": 1,
                "offset": 0,
            }
        )

        return CodeIndexingService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_get_indexed_files_success(self, service):
        """Test getting indexed files successfully."""
        result = await service.get_indexed_files(
            project_name="test-project",
            limit=50,
        )

        assert "files" in result
        assert "total" in result
        assert "has_more" in result

    @pytest.mark.asyncio
    async def test_get_indexed_files_pagination(self, service):
        """Test indexed files pagination."""
        await service.get_indexed_files(
            limit=10,
            offset=5,
        )

        service.store.get_indexed_files.assert_called_with(
            project_name=None,
            limit=10,
            offset=5,
        )


class TestListIndexedUnits:
    """Test listing indexed code units."""

    @pytest.fixture
    def service(self):
        """Create service instance for list units tests."""
        store = AsyncMock()
        store.list_indexed_units = AsyncMock(
            return_value={
                "units": [{"unit_name": "test", "unit_type": "function"}],
                "total": 1,
                "offset": 0,
            }
        )

        return CodeIndexingService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_list_indexed_units_success(self, service):
        """Test listing indexed units successfully."""
        result = await service.list_indexed_units(
            project_name="test-project",
            language="python",
            unit_type="function",
        )

        assert "units" in result
        assert "total" in result
        assert "has_more" in result


class TestFileDependencies:
    """Test file dependency operations."""

    @pytest.fixture
    def service(self):
        """Create service instance for dependency tests."""
        store = AsyncMock()
        store.retrieve = AsyncMock(return_value=[])

        return CodeIndexingService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
            project_name="test-project",
        )

    @pytest.mark.asyncio
    async def test_get_file_dependencies(self, service, tmp_path):
        """Test getting file dependencies."""
        test_file = tmp_path / "test.py"
        test_file.write_text("")

        with patch("src.memory.dependency_graph.DependencyGraph") as MockGraph:
            mock_graph = MagicMock()
            mock_graph.get_dependencies.return_value = set()
            mock_graph.get_all_dependencies.return_value = set()
            mock_graph.get_import_details.return_value = []
            MockGraph.return_value = mock_graph

            result = await service.get_file_dependencies(
                file_path=str(test_file),
            )

            assert "file" in result
            assert "dependencies" in result
            assert "dependency_count" in result

    @pytest.mark.asyncio
    async def test_get_file_dependents(self, service, tmp_path):
        """Test getting file dependents."""
        test_file = tmp_path / "test.py"
        test_file.write_text("")

        with patch("src.memory.dependency_graph.DependencyGraph") as MockGraph:
            mock_graph = MagicMock()
            mock_graph.get_dependents.return_value = set()
            mock_graph.get_all_dependents.return_value = set()
            MockGraph.return_value = mock_graph

            result = await service.get_file_dependents(
                file_path=str(test_file),
            )

            assert "file" in result
            assert "dependents" in result
            assert "dependent_count" in result


class TestFindDependencyPath:
    """Test finding dependency paths."""

    @pytest.fixture
    def service(self):
        """Create service instance for path finding tests."""
        store = AsyncMock()
        store.retrieve = AsyncMock(return_value=[])

        return CodeIndexingService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_find_dependency_path_found(self, service, tmp_path):
        """Test finding dependency path between files."""
        source = tmp_path / "source.py"
        target = tmp_path / "target.py"
        source.write_text("")
        target.write_text("")

        with patch("src.memory.dependency_graph.DependencyGraph") as MockGraph:
            mock_graph = MagicMock()
            mock_graph.find_path.return_value = [str(source), str(target)]
            mock_graph.get_import_details.return_value = []
            MockGraph.return_value = mock_graph

            result = await service.find_dependency_path(
                source_file=str(source),
                target_file=str(target),
            )

            assert result["path_found"] is True
            assert len(result["path"]) == 2

    @pytest.mark.asyncio
    async def test_find_dependency_path_not_found(self, service, tmp_path):
        """Test when no dependency path exists."""
        source = tmp_path / "source.py"
        target = tmp_path / "target.py"
        source.write_text("")
        target.write_text("")

        with patch("src.memory.dependency_graph.DependencyGraph") as MockGraph:
            mock_graph = MagicMock()
            mock_graph.find_path.return_value = None
            MockGraph.return_value = mock_graph

            result = await service.find_dependency_path(
                source_file=str(source),
                target_file=str(target),
            )

            assert result["path_found"] is False


class TestDependencyStats:
    """Test dependency statistics."""

    @pytest.fixture
    def service(self):
        """Create service instance for stats tests."""
        store = AsyncMock()
        store.retrieve = AsyncMock(return_value=[])

        return CodeIndexingService(
            store=store,
            embedding_generator=AsyncMock(),
            embedding_cache=AsyncMock(),
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_get_dependency_stats(self, service):
        """Test getting dependency statistics."""
        with patch("src.memory.dependency_graph.DependencyGraph") as MockGraph:
            mock_graph = MagicMock()
            mock_graph.get_statistics.return_value = {
                "total_files": 10,
                "total_edges": 25,
            }
            mock_graph.detect_circular_dependencies.return_value = []
            MockGraph.return_value = mock_graph

            result = await service.get_dependency_stats()

            assert "statistics" in result
            assert "circular_dependencies" in result


class TestEmbeddingCaching:
    """Test embedding cache behavior in code indexing service."""

    @pytest.fixture
    def service(self):
        """Create service instance for cache tests."""
        embedding_cache = AsyncMock()
        embedding_cache.get = AsyncMock(return_value=None)
        embedding_cache.set = AsyncMock()

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=mock_embedding(value=0.1))

        return CodeIndexingService(
            store=AsyncMock(),
            embedding_generator=embedding_generator,
            embedding_cache=embedding_cache,
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_cache_miss_generates_and_caches(self, service):
        """Test cache miss generates embedding and stores in cache."""
        await service._get_embedding("test code")

        service.embedding_cache.get.assert_called_once()
        service.embedding_generator.generate.assert_called_once()
        service.embedding_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached(self, service):
        """Test cache hit returns cached embedding."""
        cached_embedding = mock_embedding(value=0.2)
        service.embedding_cache.get = AsyncMock(return_value=cached_embedding)

        result = await service._get_embedding("cached code")

        service.embedding_cache.get.assert_called_once()
        service.embedding_generator.generate.assert_not_called()
        assert result == cached_embedding


class TestMetricsCollection:
    """Test metrics collection in code indexing service."""

    @pytest.fixture
    def service(self):
        """Create service with metrics collector."""
        mock_memory = MagicMock()
        mock_memory.id = "code_123"
        mock_memory.content = "def test(): pass"
        mock_memory.metadata = {
            "file_path": "/test.py",
            "language": "python",
            "unit_name": "test",
            "start_line": 1,
        }

        store = AsyncMock()
        store.retrieve = AsyncMock(return_value=[(mock_memory, 0.85)])

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=mock_embedding(value=0.1))

        embedding_cache = AsyncMock()
        embedding_cache.get = AsyncMock(return_value=None)
        embedding_cache.set = AsyncMock()

        metrics_collector = MagicMock()
        metrics_collector.log_query = MagicMock()

        return CodeIndexingService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=embedding_cache,
            config=ServerConfig(),
            metrics_collector=metrics_collector,
        )

    @pytest.mark.asyncio
    async def test_search_logs_metrics(self, service):
        """Test that search operations log metrics."""
        await service.search_code(query="test function")

        service.metrics_collector.log_query.assert_called_once()

    @pytest.mark.asyncio
    async def test_similar_code_logs_metrics(self, service):
        """Test that similar code search logs metrics."""
        await service.find_similar_code(code_snippet="def test(): pass")

        service.metrics_collector.log_query.assert_called_once()


class TestDeduplication:
    """Test result deduplication in code search."""

    @pytest.fixture
    def service(self):
        """Create service instance for deduplication tests."""
        # Create two memories that would create duplicates
        mock_memory1 = MagicMock()
        mock_memory1.id = "code_1"
        mock_memory1.content = "def test(): pass"
        mock_memory1.metadata = {
            "file_path": "/test.py",
            "language": "python",
            "unit_name": "test",
            "start_line": 1,
        }

        mock_memory2 = MagicMock()
        mock_memory2.id = "code_2"
        mock_memory2.content = "def test(): pass"
        mock_memory2.metadata = {
            "file_path": "/test.py",
            "language": "python",
            "unit_name": "test",
            "start_line": 1,  # Same location - should be deduped
        }

        store = AsyncMock()
        store.retrieve = AsyncMock(
            return_value=[
                (mock_memory1, 0.9),
                (mock_memory2, 0.85),
            ]
        )

        embedding_generator = AsyncMock()
        embedding_generator.generate = AsyncMock(return_value=mock_embedding(value=0.1))

        embedding_cache = AsyncMock()
        embedding_cache.get = AsyncMock(return_value=None)
        embedding_cache.set = AsyncMock()

        return CodeIndexingService(
            store=store,
            embedding_generator=embedding_generator,
            embedding_cache=embedding_cache,
            config=ServerConfig(),
        )

    @pytest.mark.asyncio
    async def test_deduplicates_by_location(self, service):
        """Test that results are deduplicated by file location."""
        result = await service.search_code(query="test")

        # Should only have 1 result despite 2 memories with same location
        assert result["total_found"] == 1
