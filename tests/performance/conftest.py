"""Performance test fixtures and utilities."""

import pytest
import pytest_asyncio
import time
import statistics
import asyncio
from pathlib import Path
from typing import List

from src.core.server import MemoryRAGServer
from src.config import get_config


@pytest.fixture
def performance_tracker():
    """Track performance metrics across test runs."""

    class Tracker:
        def __init__(self):
            self.measurements = []

        def record(self, value: float):
            """Record a measurement."""
            self.measurements.append(value)

        @property
        def p50(self) -> float:
            """50th percentile (median)."""
            if not self.measurements:
                return 0.0
            return statistics.median(self.measurements)

        @property
        def p95(self) -> float:
            """95th percentile."""
            if not self.measurements:
                return 0.0
            sorted_vals = sorted(self.measurements)
            idx = int(len(sorted_vals) * 0.95)
            return sorted_vals[idx]

        @property
        def p99(self) -> float:
            """99th percentile."""
            if not self.measurements:
                return 0.0
            sorted_vals = sorted(self.measurements)
            idx = int(len(sorted_vals) * 0.99)
            return sorted_vals[idx]

        @property
        def mean(self) -> float:
            """Mean (average)."""
            if not self.measurements:
                return 0.0
            return statistics.mean(self.measurements)

        @property
        def min(self) -> float:
            """Minimum value."""
            if not self.measurements:
                return 0.0
            return min(self.measurements)

        @property
        def max(self) -> float:
            """Maximum value."""
            if not self.measurements:
                return 0.0
            return max(self.measurements)

    return Tracker()


@pytest_asyncio.fixture
async def indexed_test_project(tmp_path, unique_qdrant_collection, mock_embeddings):
    """Pre-indexed project for performance testing.

    Creates a small test project with 20 Python files and indexes it.
    This provides a realistic but fast test environment for performance tests.
    """
    # Create test project directory
    project_dir = tmp_path / "perf_test_project"
    project_dir.mkdir()

    # Create 20 Python files with searchable content
    for i in range(20):
        file_content = f'''"""Module {i} with test functions."""

def function_{i}_authenticate(username, password):
    """Authenticate user {i}."""
    return validate_credentials_{i}(username, password)

def function_{i}_process(data):
    """Process data for module {i}."""
    result = compute_{i}(data)
    return result

class Service{i}:
    """Service class {i}."""

    def __init__(self):
        self.id = {i}

    def execute(self, request):
        """Execute request in service {i}."""
        return self.handle_request_{i}(request)
'''
        (project_dir / f"module_{i}.py").write_text(file_content)

    # Create server and index project
    config = get_config()
    server = MemoryRAGServer(config)
    await server.initialize()

    # Index the project
    await server.index_codebase(
        directory_path=str(project_dir),
        project_name="perf_test",
        recursive=True
    )

    yield server

    # Cleanup
    await server.close()


@pytest_asyncio.fixture
async def server_with_memories(tmp_path, unique_qdrant_collection, mock_embeddings):
    """Server with pre-populated memories for performance testing."""
    config = get_config()
    server = MemoryRAGServer(config)
    await server.initialize()

    # Store 100 test memories
    for i in range(100):
        await server.store_memory(
            content=f"Test memory {i}: User prefers {['vim', 'emacs', 'vscode'][i % 3]} editor",
            category="preference",
            importance=0.5 + (i % 5) * 0.1,
            tags=[f"tag_{i % 10}", "test"],
        )

    yield server

    # Cleanup
    await server.close()


@pytest.fixture
def temp_code_directory(tmp_path):
    """Create a temporary directory with test code files.

    Creates specified number of Python files for indexing performance tests.
    """
    def create_files(count: int = 100) -> Path:
        """Create test files.

        Args:
            count: Number of files to create

        Returns:
            Path to directory containing files
        """
        code_dir = tmp_path / "code_perf"
        code_dir.mkdir(exist_ok=True)

        for i in range(count):
            file_content = f'''def test_function_{i}():
    """Test function {i}."""
    return {i}

class TestClass{i}:
    """Test class {i}."""
    value = {i}
'''
            (code_dir / f"file_{i}.py").write_text(file_content)

        return code_dir

    return create_files


@pytest_asyncio.fixture
async def fresh_server(unique_qdrant_collection, mock_embeddings):
    """Fresh server instance for performance testing."""
    config = get_config()
    server = MemoryRAGServer(config)
    await server.initialize()

    yield server

    # Cleanup
    await server.close()
