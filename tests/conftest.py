"""Test configuration and shared fixtures."""

import os
import pytest
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Callable
import asyncio
from itertools import cycle


# =============================================================================
# TEST CONFIGURATION CONSTANTS
# =============================================================================
# These constants allow tests to work with both default and isolated Qdrant instances.
# The isolated test runner sets CLAUDE_RAG_QDRANT_URL to use an ephemeral test instance.
TEST_QDRANT_URL = os.environ.get("CLAUDE_RAG_QDRANT_URL", "http://localhost:6333")

# Test embedding dimension (matches DEFAULT_EMBEDDING_DIM from src.config)
# Use 768-dim for all-mpnet-base-v2 (current default model)
from src.config import DEFAULT_EMBEDDING_DIM
TEST_EMBEDDING_DIM = DEFAULT_EMBEDDING_DIM


def mock_embedding(dim=None, value=0.1):
    """Create a mock embedding vector for testing.

    Args:
        dim: Vector dimension (defaults to TEST_EMBEDDING_DIM = 768)
        value: Fill value for the vector (defaults to 0.1)

    Returns:
        List of floats representing the embedding vector

    Example:
        emb = mock_embedding()  # [0.1] * 768
        emb = mock_embedding(384)  # [0.1] * 384 (legacy tests)
        emb = mock_embedding(value=0.2)  # [0.2] * 768
    """
    return [value] * (dim or TEST_EMBEDDING_DIM)


# =============================================================================
# CRITICAL: Apply embedding mocks at module import time
# =============================================================================
# This ensures mocks are in place BEFORE any fixtures run, preventing the
# 420MB embedding model from being loaded during server.initialize() calls.
# The autouse fixture below provides the actual mock implementations per-test,
# but this early patching prevents any imports from loading the real model.


def _apply_early_patches():
    """Apply critical patches at import time."""
    import os

    # CRITICAL: Disable auto-indexing BEFORE any imports that might trigger it
    os.environ["CLAUDE_RAG_AUTO_INDEX_ENABLED"] = "false"
    os.environ["CLAUDE_RAG_AUTO_INDEX_ON_STARTUP"] = "false"

    # Patch IndexingFeatures defaults to disable auto-indexing in tests
    # This is necessary because ServerConfig may be instantiated before env vars are read
    from src.config import IndexingFeatures
    IndexingFeatures.model_fields['auto_index_enabled'].default = False
    IndexingFeatures.model_fields['auto_index_on_startup'].default = False

    # Apply embedding patches to prevent model loading
    from src.embeddings.generator import EmbeddingGenerator
    from src.embeddings import parallel_generator
    from src.embeddings.parallel_generator import ParallelEmbeddingGenerator

    # Store originals for tests that need them
    EmbeddingGenerator._original_initialize = EmbeddingGenerator.initialize
    ParallelEmbeddingGenerator._original_initialize = ParallelEmbeddingGenerator.initialize

    async def noop_initialize(self):
        """No-op initialize that will be replaced by fixture mock."""
        self.model = "early_patch_placeholder"
        self._initialized = True
        self.embedding_dim = 768

    async def noop_parallel_initialize(self):
        """No-op initialize that will be replaced by fixture mock."""
        self._initialized = True
        self.use_mps = False
        self.executor = None

    # CRITICAL: Patch the module-level worker function to prevent model loading
    # in ProcessPoolExecutor workers (which are separate processes)
    def noop_load_model_in_worker(model_name):
        """No-op model loader for worker processes."""
        return None

    EmbeddingGenerator.initialize = noop_initialize
    ParallelEmbeddingGenerator.initialize = noop_parallel_initialize
    parallel_generator._load_model_in_worker = noop_load_model_in_worker


# Apply patches immediately when conftest is imported
_apply_early_patches()

# Monkeypatch parse_source_file to support Kotlin/Swift via Python fallback
try:
    from mcp_performance_core import parse_source_file as rust_parse_source_file
    import mcp_performance_core
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    rust_parse_source_file = None
    mcp_performance_core = None

# Note: Python parser fallback was removed (it was broken, returned 0 units)
# Rust parser (mcp_performance_core) is now required for all parsing


@pytest.fixture(scope="session")
def mock_embedding_cache():
    """Pre-computed embeddings for common test phrases."""
    # Get vector size from config (matches embedding model)
    from src.config import get_config
    config = get_config()
    model_dims = {"all-MiniLM-L6-v2": 384, "all-MiniLM-L12-v2": 384, "all-mpnet-base-v2": 768}
    dim = model_dims.get(config.embedding_model, 768)

    # Generate deterministic embeddings for common test phrases
    base_embedding = [0.0] * dim

    return {
        "def authenticate": [0.1, 0.2, 0.3] + base_embedding[:dim-3],
        "user authentication": [0.2, 0.3, 0.1] + base_embedding[:dim-3],
        "login function": [0.3, 0.1, 0.2] + base_embedding[:dim-3],
        "database connection": [0.4, 0.2, 0.1] + base_embedding[:dim-3],
        "test function": [0.5, 0.3, 0.2] + base_embedding[:dim-3],
        "api request": [0.6, 0.4, 0.1] + base_embedding[:dim-3],
        "def test": [0.2, 0.5, 0.3] + base_embedding[:dim-3],
        "class User": [0.3, 0.2, 0.5] + base_embedding[:dim-3],
        "_embedding_dim": dim,  # Store dim for mock_embeddings fixture
    }


@pytest.fixture(autouse=True)
def mock_embeddings_globally(request, monkeypatch, mock_embedding_cache):
    """Auto-mock embedding generator globally to prevent loading real models.

    This fixture is autouse=True to prevent memory leaks from loading the
    ~420MB embedding model in every test worker. Tests that need real
    embeddings should use the @pytest.mark.real_embeddings marker.

    The mock generates deterministic embeddings based on text hash, which
    is sufficient for most unit and integration tests.
    """
    # Skip mocking if test has real_embeddings marker
    if request.node.get_closest_marker("real_embeddings"):
        return  # Let real embedding generator be used

    from src.embeddings.generator import EmbeddingGenerator
    from src.embeddings.parallel_generator import ParallelEmbeddingGenerator
    from src.core.exceptions import EmbeddingError

    # Get embedding dimension from cache
    dim = mock_embedding_cache.get("_embedding_dim", 768)

    async def mock_generate(self, text):
        """Generate mock embedding based on cached values or hash."""
        # Handle edge cases like real generator does
        if text is None:
            raise EmbeddingError("Cannot generate embedding for None")
        if not text or not text.strip():
            raise EmbeddingError("Cannot generate embedding for empty text")

        # Return cached embedding if available
        if text in mock_embedding_cache and not text.startswith("_"):
            return mock_embedding_cache[text]

        # For other texts, generate deterministic embedding based on hash
        hash_val = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
        base_value = (hash_val % 100) / 100.0

        # Create normalized embedding (unit vector)
        embedding = []
        for i in range(dim):
            val = (base_value + (i * 0.001)) % 1.0
            embedding.append(val)

        # Normalize to unit length (like real embeddings)
        magnitude = sum(x * x for x in embedding) ** 0.5
        if magnitude > 0:
            embedding = [x / magnitude for x in embedding]

        return embedding

    monkeypatch.setattr(EmbeddingGenerator, "generate", mock_generate)

    # Mock initialize() to prevent loading the real 420MB model
    async def mock_initialize(self):
        """Mock initialize - set up fake model state without loading real model."""
        self.model = "mocked"  # Set to truthy value so model_loaded checks pass
        self._initialized = True
        # Set embedding_dim based on model name
        model_dims = {"all-MiniLM-L6-v2": 384, "all-mpnet-base-v2": 768}
        self.embedding_dim = model_dims.get(self.model_name, 768)

    monkeypatch.setattr(EmbeddingGenerator, "initialize", mock_initialize)

    # Also mock batch generation if it exists
    try:
        async def mock_generate_batch(self, texts):
            """Generate mock embeddings for batch of texts."""
            return [await mock_generate(self, text) for text in texts]

        monkeypatch.setattr(EmbeddingGenerator, "generate_batch", mock_generate_batch)
    except AttributeError:
        pass  # generate_batch might not exist

    # Mock ParallelEmbeddingGenerator to prevent spawning worker processes that load the model
    async def mock_parallel_initialize(self):
        """Mock initialize - skip process pool creation."""
        self._initialized = True
        self.use_mps = False
        self.executor = None  # No real executor needed

    async def mock_parallel_generate(self, text):
        """Generate mock embedding for parallel generator."""
        return await mock_generate(self, text)

    async def mock_parallel_batch_generate(self, texts, **kwargs):
        """Generate mock embeddings for batch in parallel generator."""
        return [await mock_generate(self, text) for text in texts]

    monkeypatch.setattr(ParallelEmbeddingGenerator, "initialize", mock_parallel_initialize)
    monkeypatch.setattr(ParallelEmbeddingGenerator, "generate", mock_parallel_generate)
    monkeypatch.setattr(ParallelEmbeddingGenerator, "batch_generate", mock_parallel_batch_generate)


@pytest.fixture(autouse=True)
def disable_auto_indexing_and_force_cpu(monkeypatch):
    """Globally disable auto-indexing and force CPU mode for all tests.

    Auto-indexing triggers full repository scans during server initialization,
    which overwhelms Qdrant during test fixture setup and causes 60s timeouts.

    Force CPU mode prevents MPS (Apple Silicon GPU) from loading large models
    in each test worker, which caused 80GB+ memory usage with parallel tests.

    This fixture automatically applies to ALL tests via autouse=True.
    Tests that specifically need indexing should explicitly enable it.
    """
    monkeypatch.setenv("CLAUDE_RAG_AUTO_INDEX_ENABLED", "false")
    monkeypatch.setenv("CLAUDE_RAG_AUTO_INDEX_ON_STARTUP", "false")
    # Force CPU mode to prevent MPS loading large models in each worker
    # Use double underscore for nested pydantic config: performance.force_cpu
    monkeypatch.setenv("CLAUDE_RAG_PERFORMANCE__FORCE_CPU", "true")
    monkeypatch.setenv("CLAUDE_RAG_PERFORMANCE__GPU_ENABLED", "false")
    # Disable parallel embeddings to prevent spawning worker processes that
    # each load the 420MB model (causing 15GB+ memory usage)
    monkeypatch.setenv("CLAUDE_RAG_PERFORMANCE__PARALLEL_EMBEDDINGS", "false")


@pytest.fixture
def small_test_project(tmp_path):
    """Create small test project with 5 files for fast indexing.

    This fixture creates a minimal test project that indexes quickly,
    reducing test time from 60-80s to 10-15s for tests that need indexed code.

    Scope: function (cannot be session-scoped)

    Why function-scoped:
    1. Depends on tmp_path which is function-scoped (pytest constraint)
    2. Tests using this fixture typically index into the database with
       the same project_name, causing cross-test contamination if shared
    3. Each test expects a fresh indexing operation

    To create a session-scoped version, use tmp_path_factory and ensure
    tests use unique project names. See test_project_factory for a
    reusable alternative.
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
# This prevents Qdrant overload from parallel workers creating/deleting collections
# Pool size matches pytest -n 4 default (see pytest.ini)
COLLECTION_POOL = [f"test_pool_{i}" for i in range(4)]
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

    Handles ephemeral Qdrant instances (test-isolated.sh) by waiting for
    the server to be ready before initializing the client.
    """
    import os
    import time
    from qdrant_client import QdrantClient

    qdrant_url = os.getenv("CLAUDE_RAG_QDRANT_URL", "http://localhost:6333")

    # Wait for Qdrant to be ready (handles ephemeral test instances)
    import requests
    max_retries = 10
    retry_delay = 0.2

    for attempt in range(max_retries):
        try:
            response = requests.get(f"{qdrant_url}/readyz", timeout=5)
            if response.status_code == 200:
                break
        except Exception:
            pass

        if attempt < max_retries - 1:
            time.sleep(retry_delay)

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

    # Get vector size from config (matches embedding model)
    from src.config import get_config
    config = get_config()
    model_dims = {"all-MiniLM-L6-v2": 384, "all-MiniLM-L12-v2": 384, "all-mpnet-base-v2": 768}
    vector_size = model_dims.get(config.embedding_model, 768)

    for name in COLLECTION_POOL:
        try:
            if name not in collection_names:
                # Create only if doesn't exist
                qdrant_client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
                )
        except Exception:
            # Creation failure is not critical - collection might exist
            pass

    yield

    # Clean up all test collections at end of session
    # This prevents data accumulation across test runs
    from qdrant_client.models import PointIdsList
    for name in COLLECTION_POOL:
        try:
            # Delete all points (scroll in batches to handle large collections)
            while True:
                points, _ = qdrant_client.scroll(
                    collection_name=name,
                    limit=1000,
                    with_payload=False,
                    with_vectors=False
                )
                if not points:
                    break
                point_ids = [p.id for p in points]
                qdrant_client.delete(
                    collection_name=name,
                    points_selector=PointIdsList(points=point_ids)
                )
        except Exception:
            pass  # Collection might not exist or be inaccessible


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
    """Provide per-test unique collection for true isolation.

    Creates a new collection for each test with a unique name instead of
    reusing pool collections. This prevents cross-test contamination even
    when multiple tests run sequentially on the same worker.
    """
    import os
    from qdrant_client.models import PointIdsList
    import time
    import uuid

    storage_backend = os.getenv("CLAUDE_RAG_STORAGE_BACKEND", "qdrant")

    # Create a truly unique collection per test
    unique_collection = f"test_{uuid.uuid4().hex[:12]}"
    monkeypatch.setenv("CLAUDE_RAG_QDRANT_COLLECTION_NAME", unique_collection)

    if storage_backend != "qdrant":
        # For SQLite backend, just return unique name (no cleanup needed)
        yield unique_collection
        return

    # Note: New unique collection is created via Qdrant's auto-creation
    # on first use, so no explicit creation needed here

    yield unique_collection

    # Cleanup: delete the collection to prevent orphaning
    try:
        qdrant_client.delete_collection(collection_name=unique_collection)
    except Exception:
        pass  # Collection might not have been created or might be already deleted


# ============================================================================
# Qdrant Throughput Throttling (Reduces load during parallel tests)
# ============================================================================

import asyncio as _throttle_asyncio

# Semaphore to limit concurrent Qdrant operations across all workers
_qdrant_semaphore = None
_QDRANT_MAX_CONCURRENT_OPS = 2  # Max concurrent ops per worker


@pytest.fixture
def throttled_qdrant(qdrant_client):
    """Throttled Qdrant client that limits concurrent operations.

    Use this fixture instead of qdrant_client for tests that do heavy
    Qdrant operations to prevent overwhelming the server during parallel runs.
    """
    global _qdrant_semaphore
    if _qdrant_semaphore is None:
        _qdrant_semaphore = _throttle_asyncio.Semaphore(_QDRANT_MAX_CONCURRENT_OPS)

    class ThrottledClient:
        def __init__(self, client, semaphore):
            self._client = client
            self._semaphore = semaphore

        def __getattr__(self, name):
            attr = getattr(self._client, name)
            if callable(attr):
                def throttled(*args, **kwargs):
                    # Small delay to stagger operations
                    import time
                    time.sleep(0.01)  # 10ms stagger
                    return attr(*args, **kwargs)
                return throttled
            return attr

    yield ThrottledClient(qdrant_client, _qdrant_semaphore)


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

        # Skip timing-sensitive tests in parallel execution
        if "skip_ci" in item.keywords:
            # Check if running under pytest-xdist (parallel execution)
            if hasattr(config, "workerinput") or getattr(config, "option", None) and getattr(config.option, "numprocesses", None):
                item.add_marker(pytest.mark.skip(reason="Timing-sensitive under parallel execution"))

        # Skip Docker tests if Docker not running
        if "requires_docker" in item.keywords:
            try:
                import docker
                client = docker.from_env()
                client.ping()
            except Exception:
                item.add_marker(pytest.mark.skip(reason="Docker not available"))
