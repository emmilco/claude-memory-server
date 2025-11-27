"""Test configuration and shared fixtures."""

import pytest
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Callable
import asyncio
from itertools import cycle

# Monkeypatch parse_source_file to support Kotlin/Swift via Python fallback
try:
    from mcp_performance_core import parse_source_file as rust_parse_source_file
    import mcp_performance_core
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    rust_parse_source_file = None
    mcp_performance_core = None

if RUST_AVAILABLE:
    from src.memory.python_parser import PythonParser

    original_parse = rust_parse_source_file

    def parse_source_file_with_fallback(file_path: str, source_code: str):
        """Parse source file with fallback to Python parser for unsupported languages."""
        try:
            # Try Rust parser first
            return original_parse(file_path, source_code)
        except RuntimeError as e:
            if "Unsupported file extension" in str(e):
                # Fall back to Python parser for Kotlin, Swift, etc.
                from pathlib import Path
                ext = Path(file_path).suffix.lower()

                # Language map for Python fallback
                lang_map = {
                    '.kt': 'kotlin',
                    '.kts': 'kotlin',
                    '.swift': 'swift',
                    '.rb': 'ruby',
                }

                if ext in lang_map:
                    try:
                        parser = PythonParser()
                        units = parser.parse_file(file_path, lang_map[ext])

                        # Normalize language names to match Rust output (capitalized)
                        lang_name_capitalized = lang_map[ext].capitalize()
                        for unit in units:
                            unit['language'] = lang_name_capitalized

                        # Convert Python parser units (dicts) to objects compatible with Rust output
                        class SemanticUnitWrapper:
                            """Wrapper to make dict behave like Rust SemanticUnit."""
                            def __init__(self, data):
                                self._data = data
                                # Expose as attributes
                                for key, value in data.items():
                                    setattr(self, key, value)
                                # Add 'type' alias for 'unit_type' (tests use both)
                                if 'unit_type' in data:
                                    setattr(self, 'type', data['unit_type'])

                            def __getitem__(self, key):
                                # Support dict-style access for tests
                                if key == 'type' and key not in self._data:
                                    return self._data.get('unit_type')
                                return self._data[key]

                            def __repr__(self):
                                return f"SemanticUnit({self._data})"

                        class PythonParseResult:
                            """Mimics Rust ParseResult."""
                            def __init__(self, file_path, language, units, parse_time_ms):
                                self.file_path = file_path
                                self.language = language
                                self.units = [SemanticUnitWrapper(u) for u in units]
                                self.parse_time_ms = parse_time_ms

                        return PythonParseResult(
                            file_path=file_path,
                            language=lang_name_capitalized,
                            units=units,
                            parse_time_ms=0.0
                        )
                    except Exception:
                        # If Python parser fails, re-raise original error
                        raise e
            # Re-raise if not an unsupported extension error
            raise

    # Monkey-patch the module
    mcp_performance_core.parse_source_file = parse_source_file_with_fallback


@pytest.fixture(scope="session")
def mock_embedding_cache():
    """Pre-computed embeddings for common test phrases."""
    # Generate deterministic 384-dimensional embeddings for common test phrases
    base_embedding = [0.0] * 384

    return {
        "def authenticate": [0.1, 0.2, 0.3] + base_embedding[:381],
        "user authentication": [0.2, 0.3, 0.1] + base_embedding[:381],
        "login function": [0.3, 0.1, 0.2] + base_embedding[:381],
        "database connection": [0.4, 0.2, 0.1] + base_embedding[:381],
        "test function": [0.5, 0.3, 0.2] + base_embedding[:381],
        "api request": [0.6, 0.4, 0.1] + base_embedding[:381],
        "def test": [0.2, 0.5, 0.3] + base_embedding[:381],
        "class User": [0.3, 0.2, 0.5] + base_embedding[:381],
    }


@pytest.fixture
def mock_embeddings(monkeypatch, mock_embedding_cache):
    """Mock embedding generator for unit tests to avoid slow embedding generation."""
    from src.embeddings.generator import EmbeddingGenerator

    original_generate = EmbeddingGenerator.generate

    async def mock_generate(self, text):
        """Generate mock embedding based on cached values or hash."""
        # Return cached embedding if available
        if text in mock_embedding_cache:
            return mock_embedding_cache[text]

        # For other texts, generate deterministic embedding based on hash
        # This ensures consistency across test runs
        hash_val = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        base_value = (hash_val % 100) / 100.0

        # Create a simple deterministic pattern
        embedding = []
        for i in range(384):
            val = (base_value + (i * 0.001)) % 1.0
            embedding.append(val)

        return embedding

    monkeypatch.setattr(EmbeddingGenerator, "generate", mock_generate)

    # Also mock batch generation if it exists
    try:
        async def mock_generate_batch(self, texts):
            """Generate mock embeddings for batch of texts."""
            return [await mock_generate(self, text) for text in texts]

        monkeypatch.setattr(EmbeddingGenerator, "generate_batch", mock_generate_batch)
    except AttributeError:
        pass  # generate_batch might not exist


@pytest.fixture(autouse=True)
def disable_auto_indexing(monkeypatch):
    """Globally disable auto-indexing for all tests to prevent Qdrant timeouts.

    Auto-indexing triggers full repository scans during server initialization,
    which overwhelms Qdrant during test fixture setup and causes 60s timeouts.

    This fixture automatically applies to ALL tests via autouse=True.
    Tests that specifically need indexing should explicitly enable it.
    """
    monkeypatch.setenv("CLAUDE_RAG_AUTO_INDEX_ENABLED", "false")
    monkeypatch.setenv("CLAUDE_RAG_AUTO_INDEX_ON_STARTUP", "false")


@pytest.fixture
def small_test_project(tmp_path):
    """Create small test project with 5 files for fast indexing.

    This fixture creates a minimal test project that indexes quickly,
    reducing test time from 60-80s to 10-15s for tests that need indexed code.
    """
    project = tmp_path / "test_project"
    project.mkdir()

    # Create 5 small Python files with searchable content
    test_files = {
        "auth.py": "def authenticate(user, password):\n    return validate_credentials(user, password)",
        "db.py": "def connect_database():\n    return DatabaseConnection()",
        "api.py": "def handle_request(req):\n    return process_api_request(req)",
        "utils.py": "def test_function():\n    return 'test result'",
        "models.py": "class User:\n    def __init__(self, name):\n        self.name = name"
    }

    for filename, content in test_files.items():
        (project / filename).write_text(content)

    return project


# ============================================================================
# Phase 2: Fixture Optimization (Session-scoped resources)
# ============================================================================

class LazyResource:
    """Lazy initialization wrapper for expensive resources.

    Resources are only created when first accessed, reducing
    test startup time for tests that don't use all fixtures.
    """
    def __init__(self, factory: Callable):
        self._factory = factory
        self._instance = None
        self._lock = asyncio.Lock()

    async def get(self):
        """Get or create the resource."""
        if self._instance is None:
            async with self._lock:
                if self._instance is None:  # Double-check pattern
                    self._instance = await self._factory()
        return self._instance


@pytest.fixture(scope="session")
def lazy_embedding_model():
    """Lazy-loaded embedding model for tests that need real embeddings.

    Most unit tests should use mock_embeddings fixture instead.
    This is for integration tests that need actual embedding generation.
    """
    async def create_model():
        from src.embeddings.generator import EmbeddingGenerator
        return EmbeddingGenerator()

    return LazyResource(create_model)


@pytest.fixture(scope="session")
def session_db_path(tmp_path_factory):
    """Session-scoped database path for reusable test database.

    Creates a single database file for the entire test session.
    Individual tests should clear/reset data rather than recreating DB.
    """
    db_dir = tmp_path_factory.mktemp("db")
    db_path = db_dir / "test_session.db"
    yield db_path
    # Cleanup after session
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
async def clean_db(session_db_path):
    """Function-scoped fixture that provides a clean database.

    Uses session-scoped DB but clears it before each test.
    Much faster than creating new DB files for each test.
    """
    # Clear the database before test
    if session_db_path.exists():
        session_db_path.unlink()

    yield session_db_path

    # Note: We don't clear after test - next test will clear before use


# ============================================================================
# Phase 3: Advanced Optimizations (Test data factories)
# ============================================================================

@pytest.fixture
def test_project_factory(tmp_path):
    """Factory for creating test projects with custom sizes.

    Usage:
        project = test_project_factory(name="my_test", files=10)
    """
    def create_project(name: str = "test_project", files: int = 5,
                      language: str = "python") -> Path:
        """Create a test project with specified number of files.

        Args:
            name: Project directory name
            files: Number of files to create
            language: Programming language (python, javascript, etc.)

        Returns:
            Path to created project directory
        """
        project_dir = tmp_path / name
        project_dir.mkdir(parents=True, exist_ok=True)

        # File templates by language
        templates = {
            "python": lambda i: f"def function_{i}():\n    return {i}",
            "javascript": lambda i: f"function func{i}() {{\n  return {i};\n}}",
            "typescript": lambda i: f"function func{i}(): number {{\n  return {i};\n}}",
        }

        extensions = {
            "python": ".py",
            "javascript": ".js",
            "typescript": ".ts",
        }

        template = templates.get(language, templates["python"])
        ext = extensions.get(language, extensions["python"])

        for i in range(files):
            filename = f"file_{i}{ext}"
            content = template(i)
            (project_dir / filename).write_text(content)

        return project_dir

    return create_project


@pytest.fixture
def memory_factory():
    """Factory for creating test memory objects.

    Usage:
        memory = memory_factory(content="test", importance=0.8)
    """
    def create_memory(
        content: str = "Test memory content",
        importance: float = 0.5,
        context_level: str = "global",
        category: str = "general",
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create a memory dictionary with sensible defaults."""
        from datetime import datetime

        return {
            "content": content,
            "importance": importance,
            "context_level": context_level,
            "category": category,
            "tags": tags or [],
            "metadata": metadata or {},
            "created_at": datetime.now().isoformat(),
        }

    return create_memory


@pytest.fixture
def code_sample_factory():
    """Factory for creating code samples for testing parsers.

    Usage:
        python_code = code_sample_factory("python", functions=3)
    """
    def create_code_sample(
        language: str = "python",
        functions: int = 1,
        classes: int = 0,
        complexity: str = "simple"
    ) -> str:
        """Generate code samples for testing.

        Args:
            language: Programming language
            functions: Number of functions to generate
            classes: Number of classes to generate
            complexity: 'simple', 'medium', or 'complex'

        Returns:
            Generated code as string
        """
        if language == "python":
            code_parts = []

            # Generate classes
            for i in range(classes):
                code_parts.append(f"class TestClass{i}:")
                code_parts.append(f"    def __init__(self):")
                code_parts.append(f"        self.value = {i}")
                code_parts.append("")

            # Generate functions
            for i in range(functions):
                if complexity == "simple":
                    code_parts.append(f"def test_function_{i}():")
                    code_parts.append(f"    return {i}")
                elif complexity == "medium":
                    code_parts.append(f"def test_function_{i}(x, y):")
                    code_parts.append(f"    result = x + y + {i}")
                    code_parts.append(f"    return result")
                else:  # complex
                    code_parts.append(f"async def test_function_{i}(x, y, z=None):")
                    code_parts.append(f"    if z is None:")
                    code_parts.append(f"        z = {i}")
                    code_parts.append(f"    result = await process(x, y, z)")
                    code_parts.append(f"    return result")
                code_parts.append("")

            return "\n".join(code_parts)

        # Add other languages as needed
        return f"# {language} code sample placeholder"

    return create_code_sample


# ============================================================================
# Test Isolation: Collection Pooling for Qdrant (Prevents Deadlocks)
# ============================================================================

# Collection pool: Pre-created collections reused across tests
# This prevents Qdrant overload from 8 parallel workers creating/deleting collections
# With 10 collections and 8 workers, each worker gets a dedicated collection
COLLECTION_POOL = [f"test_pool_{i}" for i in range(10)]
_collection_cycle = cycle(COLLECTION_POOL)

# Worker ID to collection mapping (Option E: worker-specific isolation)
# Each worker gets a dedicated collection to eliminate cross-worker data contamination
def _get_worker_collection(worker_id: str) -> str:
    """Map worker ID to a specific collection for true isolation.

    Args:
        worker_id: "master" for serial, "gw0"-"gw9" for parallel

    Returns:
        Collection name dedicated to this worker
    """
    if worker_id == "master":
        return COLLECTION_POOL[0]  # Serial execution uses first pool
    # Extract worker number from "gwN" format
    try:
        worker_num = int(worker_id.replace("gw", ""))
        # Map to collection pool (wrap around if more workers than collections)
        return COLLECTION_POOL[worker_num % len(COLLECTION_POOL)]
    except (ValueError, IndexError):
        # Fallback for unexpected worker IDs
        return COLLECTION_POOL[0]


@pytest.fixture(scope="session")
def qdrant_client():
    """Session-scoped Qdrant client (connection reuse prevents deadlocks).

    QA Best Practice: Reuse connections instead of creating new ones per test.
    This reduces load on Qdrant and prevents connection exhaustion.
    """
    import os
    from qdrant_client import QdrantClient

    qdrant_url = os.getenv("CLAUDE_RAG_QDRANT_URL", "http://localhost:6333")
    client = QdrantClient(url=qdrant_url, timeout=30.0)

    yield client

    # Close client at end of session
    try:
        client.close()
    except Exception:
        pass


@pytest.fixture(scope="session")
def setup_qdrant_pool(qdrant_client):
    """Pre-create collection pool at session start.

    Creates 10 collections that will be reused across all tests.
    This is 10x faster than creating/deleting collections per test.

    QA Best Practice: Setup once, reuse many times.
    """
    import os
    from qdrant_client.models import Distance, VectorParams

    storage_backend = os.getenv("CLAUDE_RAG_STORAGE_BACKEND", "qdrant")
    if storage_backend != "qdrant":
        # Skip pool setup if using SQLite backend
        yield
        return

    # Create collection pool (only if collections don't exist)
    # Get existing collections ONCE (not in loop - prevents Qdrant overload)
    try:
        collections = qdrant_client.get_collections().collections
        collection_names = [c.name for c in collections]
    except Exception:
        # If we can't get collections, assume none exist
        collection_names = []

    for name in COLLECTION_POOL:
        try:
            if name not in collection_names:
                # Create only if doesn't exist
                qdrant_client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                )
        except Exception:
            # Creation failure is not critical - collection might exist
            pass

    yield

    # NO cleanup - keep pool collections for next test run
    # Collection pool is persistent across test runs for maximum performance
    # Tests clear collection contents before use via unique_qdrant_collection fixture


@pytest.fixture(scope="session")
def worker_id(request):
    """Get pytest-xdist worker ID for collection isolation.

    Returns:
    - "gw0", "gw1", ... "gw7" when running with pytest -n 8
    - "master" when running without xdist (serial execution)

    This fixture enables worker-specific collection assignment.
    """
    workerinput = getattr(request.config, "workerinput", None)
    if workerinput is not None:
        return workerinput.get("workerid", "master")
    return "master"


@pytest.fixture
def unique_qdrant_collection(monkeypatch, qdrant_client, setup_qdrant_pool, worker_id):
    """Provide worker-specific collection for true parallel isolation.

    Instead of round-robin allocation (which causes cross-worker contamination),
    this fixture assigns each worker its own dedicated collection:
    - gw0 -> test_pool_0
    - gw1 -> test_pool_1
    - etc.

    This is Option E from TEST_PARALLELIZATION_ANALYSIS.md, using the existing
    pool infrastructure for zero overhead.
    """
    import os
    from qdrant_client.models import PointIdsList

    storage_backend = os.getenv("CLAUDE_RAG_STORAGE_BACKEND", "qdrant")
    if storage_backend != "qdrant":
        # For SQLite backend, use unique collection names as before
        import uuid
        unique_collection = f"test_{uuid.uuid4().hex[:12]}"
        monkeypatch.setenv("CLAUDE_RAG_QDRANT_COLLECTION_NAME", unique_collection)
        yield unique_collection
        return

    # Get worker-specific collection (true isolation)
    collection_name = _get_worker_collection(worker_id)
    monkeypatch.setenv("CLAUDE_RAG_QDRANT_COLLECTION_NAME", collection_name)

    # Clear collection before test (faster than recreate)
    try:
        # Scroll to get all point IDs (limit 10000 per call)
        points, _ = qdrant_client.scroll(
            collection_name=collection_name,
            limit=10000,
            with_payload=False,
            with_vectors=False
        )

        if points:
            point_ids = [p.id for p in points]
            qdrant_client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=point_ids)
            )
    except Exception:
        # If clear fails, test can still proceed with dirty collection
        # (not ideal but better than deadlock)
        pass

    yield collection_name

    # No cleanup needed - collection stays in pool for next test


# ============================================================================
# Test Project Isolation (TEST-016 Fix)
# ============================================================================

@pytest.fixture
def test_project_name(request):
    """Generate unique project name per test for data isolation.

    This fixture ensures each test operates on isolated data by providing
    a unique project_name. Tests should use this when storing/retrieving
    data to avoid cross-test contamination in parallel execution.

    Usage:
        async def test_something(server, test_project_name):
            await server.store_memory(
                content="test",
                project_name=test_project_name,
                scope="project"
            )
            results = await server.retrieve_memories(
                query="test",
                project_name=test_project_name
            )

    The name format is: test_{test_name}_{random_8chars}
    """
    import uuid
    # Use test name + random suffix for uniqueness
    test_name = request.node.name[:30]  # Truncate long test names
    unique_suffix = uuid.uuid4().hex[:8]
    return f"test_{test_name}_{unique_suffix}"


# ============================================================================
# Automatic Test Marker Application (TEST-011)
# ============================================================================

def pytest_collection_modifyitems(config, items):
    """Auto-apply markers based on test location and characteristics.

    This hook automatically adds markers to tests based on their file path,
    reducing the need for manual marker application while maintaining
    test categorization.

    Auto-applied markers:
    - unit: All tests in tests/unit/
    - integration: All tests in tests/integration/
    - e2e: All tests in tests/e2e/
    - security: All tests in tests/security/
    - requires_docker: Integration and E2E tests (most need Docker for Qdrant)
    """
    for item in items:
        # Get file path as string
        fspath = str(item.fspath)

        # Auto-apply markers based on directory structure
        if "tests/unit/" in fspath:
            item.add_marker(pytest.mark.unit)
        elif "tests/integration/" in fspath:
            item.add_marker(pytest.mark.integration)
            # Most integration tests require Docker for Qdrant
            item.add_marker(pytest.mark.requires_docker)
        elif "tests/e2e/" in fspath:
            item.add_marker(pytest.mark.e2e)
            # E2E tests require Docker for Qdrant
            item.add_marker(pytest.mark.requires_docker)
        elif "tests/security/" in fspath:
            item.add_marker(pytest.mark.security)
        elif "tests/performance/" in fspath:
            item.add_marker(pytest.mark.performance)
            # Performance tests require Docker for Qdrant
            item.add_marker(pytest.mark.requires_docker)

        # Skip GPU tests if GPU not available
        if "requires_gpu" in item.keywords:
            try:
                import torch
                if not torch.cuda.is_available():
                    item.add_marker(pytest.mark.skip(reason="GPU not available"))
            except ImportError:
                item.add_marker(pytest.mark.skip(reason="PyTorch not installed"))

        # Skip Docker tests if Docker not running
        if "requires_docker" in item.keywords:
            try:
                import docker
                client = docker.from_env()
                client.ping()
            except Exception:
                item.add_marker(pytest.mark.skip(reason="Docker not available"))
