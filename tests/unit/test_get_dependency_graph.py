"""Tests for get_dependency_graph MCP tool (FEAT-048)."""

import pytest
import pytest_asyncio
import json
from pathlib import Path

from src.store.qdrant_store import QdrantMemoryStore
from src.core.server import MemoryRAGServer
from src.core.exceptions import ValidationError
from src.config import ServerConfig


@pytest_asyncio.fixture
async def qdrant_store():
    """Create a temporary Qdrant store for testing."""
    config = ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name="test_dependency_graph",
    )
    store = QdrantMemoryStore(config)
    await store.initialize()
    yield store
    await store.close()


@pytest_asyncio.fixture
async def sample_dependency_graph(qdrant_store):
    """Create sample indexed code with dependencies for testing."""
    # Store Python files with dependencies
    # File A -> imports B and C
    await qdrant_store.store(
        content="from utils import helper\nfrom models import User",
        embedding=[0.1] * 384,
        metadata={
            "id": "unit-a",
            "category": "context",  # Code is stored as context
            "context_level": "PROJECT_CONTEXT",
            "scope": "project",
            "project_name": "test-project",
            "importance": 0.8,
            "metadata": {
                "unit_name": "main",
                "unit_type": "module",
                "file_path": "/project/main.py",
                "language": "python",
                "start_line": 1,
                "end_line": 10,
                "file_size": 500,
                "last_modified": "2025-11-18T10:00:00",
                "dependencies": ["/project/utils.py", "/project/models.py"],
            },
        },
    )

    # File B (utils.py)
    await qdrant_store.store(
        content="def helper(): pass",
        embedding=[0.2] * 384,
        metadata={
            "id": "unit-b",
            "category": "context",
            "context_level": "PROJECT_CONTEXT",
            "scope": "project",
            "project_name": "test-project",
            "importance": 0.7,
            "metadata": {
                "unit_name": "helper",
                "unit_type": "function",
                "file_path": "/project/utils.py",
                "language": "python",
                "start_line": 1,
                "end_line": 2,
                "file_size": 300,
                "last_modified": "2025-11-18T09:00:00",
                "dependencies": [],
            },
        },
    )

    # File C (models.py)
    await qdrant_store.store(
        content="class User: pass",
        embedding=[0.3] * 384,
        metadata={
            "id": "unit-c",
            "category": "context",
            "context_level": "PROJECT_CONTEXT",
            "scope": "project",
            "project_name": "test-project",
            "importance": 0.7,
            "metadata": {
                "unit_name": "User",
                "unit_type": "class",
                "file_path": "/project/models.py",
                "language": "python",
                "start_line": 1,
                "end_line": 2,
                "file_size": 200,
                "last_modified": "2025-11-18T09:30:00",
                "dependencies": [],
            },
        },
    )

    # File D (JavaScript file for language filtering tests)
    await qdrant_store.store(
        content="const test = require('./lib')",
        embedding=[0.4] * 384,
        metadata={
            "id": "unit-d",
            "category": "context",
            "context_level": "PROJECT_CONTEXT",
            "scope": "project",
            "project_name": "test-project",
            "importance": 0.6,
            "metadata": {
                "unit_name": "test",
                "unit_type": "constant",
                "file_path": "/project/test.js",
                "language": "javascript",
                "start_line": 1,
                "end_line": 1,
                "file_size": 150,
                "last_modified": "2025-11-18T08:00:00",
                "dependencies": ["/project/lib.js"],
            },
        },
    )

    # File E (lib.js)
    await qdrant_store.store(
        content="module.exports = {}",
        embedding=[0.5] * 384,
        metadata={
            "id": "unit-e",
            "category": "context",
            "context_level": "PROJECT_CONTEXT",
            "scope": "project",
            "project_name": "test-project",
            "importance": 0.5,
            "metadata": {
                "unit_name": "exports",
                "unit_type": "module",
                "file_path": "/project/lib.js",
                "language": "javascript",
                "start_line": 1,
                "end_line": 1,
                "file_size": 100,
                "last_modified": "2025-11-18T07:00:00",
                "dependencies": [],
            },
        },
    )

    return sqlite_store


@pytest_asyncio.fixture
async def circular_dependency_graph(sqlite_store):
    """Create sample graph with circular dependencies."""
    # A -> B -> C -> A (circular)
    await qdrant_store.store(
        content="from b import func_b",
        embedding=[0.1] * 384,
        metadata={
            "id": "circ-a",
            "category": "context",
            "context_level": "PROJECT_CONTEXT",
            "scope": "project",
            "project_name": "circular-project",
            "importance": 0.8,
            "metadata": {
                "unit_name": "module_a",
                "unit_type": "module",
                "file_path": "/circ/a.py",
                "language": "python",
                "dependencies": ["/circ/b.py"],
            },
        },
    )

    await qdrant_store.store(
        content="from c import func_c",
        embedding=[0.2] * 384,
        metadata={
            "id": "circ-b",
            "category": "context",
            "context_level": "PROJECT_CONTEXT",
            "scope": "project",
            "project_name": "circular-project",
            "importance": 0.8,
            "metadata": {
                "unit_name": "module_b",
                "unit_type": "module",
                "file_path": "/circ/b.py",
                "language": "python",
                "dependencies": ["/circ/c.py"],
            },
        },
    )

    await qdrant_store.store(
        content="from a import func_a",
        embedding=[0.3] * 384,
        metadata={
            "id": "circ-c",
            "category": "context",
            "context_level": "PROJECT_CONTEXT",
            "scope": "project",
            "project_name": "circular-project",
            "importance": 0.8,
            "metadata": {
                "unit_name": "module_c",
                "unit_type": "module",
                "file_path": "/circ/c.py",
                "language": "python",
                "dependencies": ["/circ/a.py"],
            },
        },
    )

    return sqlite_store


@pytest_asyncio.fixture
async def server_with_graph(sample_dependency_graph):
    """Create server with sample dependency graph."""
    config = ServerConfig(
        storage_backend="sqlite",
        sqlite_path=":memory:",
    )
    server = MemoryRAGServer(config)
    server.store = sample_dependency_graph  # Use pre-populated store
    yield server


@pytest_asyncio.fixture
async def server_with_circular(circular_dependency_graph):
    """Create server with circular dependency graph."""
    config = ServerConfig(
        storage_backend="sqlite",
        sqlite_path=":memory:",
    )
    server = MemoryRAGServer(config)
    server.store = circular_dependency_graph
    yield server


class TestGetDependencyGraphBasics:
    """Test basic dependency graph export."""

    @pytest.mark.asyncio
    async def test_export_as_json(self, server_with_graph):
        """Test exporting graph as JSON."""
        result = await server_with_graph.get_dependency_graph(
            project_name="test-project",
            format="json",
        )

        assert result["format"] == "json"
        assert "graph" in result
        assert "stats" in result

        # Parse JSON graph
        graph_data = json.loads(result["graph"])
        assert "nodes" in graph_data
        assert "links" in graph_data
        assert len(graph_data["nodes"]) >= 3  # At least 3 files

    @pytest.mark.asyncio
    async def test_export_as_dot(self, server_with_graph):
        """Test exporting graph as DOT."""
        result = await server_with_graph.get_dependency_graph(
            project_name="test-project",
            format="dot",
        )

        assert result["format"] == "dot"
        graph_str = result["graph"]
        assert "digraph" in graph_str
        assert "rankdir=LR" in graph_str
        assert graph_str.endswith("}")

    @pytest.mark.asyncio
    async def test_export_as_mermaid(self, server_with_graph):
        """Test exporting graph as Mermaid."""
        result = await server_with_graph.get_dependency_graph(
            project_name="test-project",
            format="mermaid",
        )

        assert result["format"] == "mermaid"
        graph_str = result["graph"]
        assert "graph LR" in graph_str
        assert "-->" in graph_str

    @pytest.mark.asyncio
    async def test_invalid_format_raises_error(self, server_with_graph):
        """Test invalid format raises ValidationError."""
        with pytest.raises(ValidationError, match="Invalid format"):
            await server_with_graph.get_dependency_graph(
                project_name="test-project",
                format="invalid",
            )

    @pytest.mark.asyncio
    async def test_format_case_insensitive(self, server_with_graph):
        """Test format parameter is case-insensitive."""
        result = await server_with_graph.get_dependency_graph(
            project_name="test-project",
            format="JSON",  # Uppercase
        )

        assert result["format"] == "json"

    @pytest.mark.asyncio
    async def test_stats_included(self, server_with_graph):
        """Test statistics are included in result."""
        result = await server_with_graph.get_dependency_graph(
            project_name="test-project",
            format="json",
        )

        stats = result["stats"]
        assert "node_count" in stats
        assert "edge_count" in stats
        assert "circular_dependency_count" in stats
        assert "max_depth" in stats
        assert stats["node_count"] >= 3


class TestGraphFiltering:
    """Test graph filtering options."""

    @pytest.mark.asyncio
    async def test_filter_by_project(self, server_with_graph):
        """Test filtering by project name."""
        result = await server_with_graph.get_dependency_graph(
            project_name="test-project",
            format="json",
        )

        graph_data = json.loads(result["graph"])
        assert len(graph_data["nodes"]) >= 3

    @pytest.mark.asyncio
    async def test_filter_by_language(self, server_with_graph):
        """Test filtering by programming language."""
        result = await server_with_graph.get_dependency_graph(
            project_name="test-project",
            language="python",
            format="json",
        )

        graph_data = json.loads(result["graph"])

        # Should only include Python files
        for node in graph_data["nodes"]:
            assert node["language"].lower() == "python"

    @pytest.mark.asyncio
    async def test_filter_by_file_pattern(self, server_with_graph):
        """Test filtering by file pattern."""
        result = await server_with_graph.get_dependency_graph(
            project_name="test-project",
            file_pattern="*.py",
            format="json",
        )

        graph_data = json.loads(result["graph"])

        # Should only include .py files
        for node in graph_data["nodes"]:
            assert node["id"].endswith(".py")

    @pytest.mark.asyncio
    async def test_filter_by_depth(self, server_with_graph):
        """Test filtering by max depth from root."""
        result = await server_with_graph.get_dependency_graph(
            project_name="test-project",
            root_file="/project/main.py",
            max_depth=1,
            format="json",
        )

        graph_data = json.loads(result["graph"])

        # Should include main.py and its direct dependencies only
        # main.py + utils.py + models.py = 3 nodes max
        assert len(graph_data["nodes"]) <= 3


class TestCircularDependencies:
    """Test circular dependency detection."""

    @pytest.mark.asyncio
    async def test_circular_dependencies_detected(self, server_with_circular):
        """Test circular dependencies are detected."""
        result = await server_with_circular.get_dependency_graph(
            project_name="circular-project",
            format="json",
        )

        # Check stats
        assert result["stats"]["circular_dependency_count"] >= 1

        # Check circular_dependencies list
        assert len(result["circular_dependencies"]) >= 1
        cycle = result["circular_dependencies"][0]
        assert "cycle" in cycle
        assert "length" in cycle
        assert len(cycle["cycle"]) >= 3  # At least 3 files in cycle

    @pytest.mark.asyncio
    async def test_circular_edges_marked_in_json(self, server_with_circular):
        """Test circular edges are marked in JSON output."""
        result = await server_with_circular.get_dependency_graph(
            project_name="circular-project",
            format="json",
        )

        graph_data = json.loads(result["graph"])

        # At least some links should be marked circular
        circular_links = [link for link in graph_data["links"] if link.get("circular")]
        assert len(circular_links) >= 1

    @pytest.mark.asyncio
    async def test_circular_edges_highlighted_in_dot(self, server_with_circular):
        """Test circular edges are highlighted in DOT output."""
        result = await server_with_circular.get_dependency_graph(
            project_name="circular-project",
            format="dot",
        )

        graph_str = result["graph"]
        # Should have red circular edges
        assert "color=red" in graph_str
        assert "circular" in graph_str

    @pytest.mark.asyncio
    async def test_circular_edges_dotted_in_mermaid(self, server_with_circular):
        """Test circular edges use dotted lines in Mermaid."""
        result = await server_with_circular.get_dependency_graph(
            project_name="circular-project",
            format="mermaid",
        )

        graph_str = result["graph"]
        # Should have dotted circular edges
        assert "-.->|circular|" in graph_str


class TestMetadataInclusion:
    """Test metadata inclusion options."""

    @pytest.mark.asyncio
    async def test_include_metadata_true(self, server_with_graph):
        """Test graph includes metadata when enabled."""
        result = await server_with_graph.get_dependency_graph(
            project_name="test-project",
            format="json",
            include_metadata=True,
        )

        graph_data = json.loads(result["graph"])

        # Nodes should have metadata fields
        for node in graph_data["nodes"]:
            if node.get("unit_count", 0) > 0:
                # If unit_count exists, other metadata should too
                assert "file_size" in node or "last_modified" in node

    @pytest.mark.asyncio
    async def test_include_metadata_false(self, server_with_graph):
        """Test graph excludes metadata when disabled."""
        result = await server_with_graph.get_dependency_graph(
            project_name="test-project",
            format="json",
            include_metadata=False,
        )

        graph_data = json.loads(result["graph"])

        # Nodes should only have essential fields
        for node in graph_data["nodes"]:
            # Should always have id and language
            assert "id" in node
            assert "language" in node
