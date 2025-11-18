"""Test configuration and shared fixtures."""

import pytest
import hashlib
from pathlib import Path


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
