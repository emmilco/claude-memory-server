"""Test configuration and shared fixtures."""

import pytest
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Callable
import asyncio


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
