"""E2E tests for first-run experience and installation verification.

These tests verify that a new installation works correctly and
that all dependencies and configuration are properly set up.

NOTE: These tests are currently skipped pending API compatibility fixes.
See TEST-027 for tracking.
"""

import pytest

# E2E tests for first-run experience - API compatibility fixed


# ============================================================================
# Installation Verification Tests (3 tests)
# ============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_dependencies_available():
    """Test: All required packages installed.

    Verifies that all critical dependencies are available and importable.
    This simulates a first-run environment check.
    """
    # Critical dependencies that must be available
    critical_deps = [
        "qdrant_client",
        "sentence_transformers",
        "pytest",
        "asyncio",
    ]

    missing_deps = []
    for dep in critical_deps:
        try:
            __import__(dep)
        except ImportError:
            missing_deps.append(dep)

    assert len(missing_deps) == 0, f"Missing dependencies: {missing_deps}"

    # Verify core modules are importable
    core_modules = [
        "src.core.server",
        "src.core.models",
        "src.config",
        "src.store.qdrant_store",
        "src.embeddings.generator",
    ]

    missing_modules = []
    for module in core_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)

    assert len(missing_modules) == 0, f"Missing core modules: {missing_modules}"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_qdrant_connectable(qdrant_client):
    """Test: Can connect to Qdrant.

    Verifies that Qdrant is running and accessible.
    This is a critical first-run check.
    """
    # Use the session-scoped qdrant_client fixture
    assert qdrant_client is not None

    # Try to get collections (basic connectivity test)
    try:
        collections = qdrant_client.get_collections()
        assert collections is not None
        # Should have at least the test pool collections
        assert len(collections.collections) > 0
    except Exception as e:
        pytest.fail(f"Cannot connect to Qdrant: {e}")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_embedding_model_loadable():
    """Test: Can load embedding model.

    Verifies that the embedding model can be loaded successfully.
    This is important for first-run experience.
    """
    from src.embeddings.generator import EmbeddingGenerator

    # Create generator (model loads lazily on first use)
    generator = EmbeddingGenerator()

    # Explicitly preload the model to test loading works
    await generator.initialize()

    # Verify model is loaded
    assert generator.model is not None

    # Try generating a test embedding
    embedding = await generator.generate("test text for embedding")

    # Verify embedding has correct dimensions
    assert (
        len(embedding) == 768
    )  # all-mpnet-base-v2 produces 768-dimensional embeddings
    assert all(isinstance(x, (int, float)) for x in embedding)


# ============================================================================
# Configuration Tests (2 tests)
# ============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_default_config_valid(fresh_server):
    """Test: Default config works without modification.

    Verifies that a fresh installation with default configuration
    can initialize successfully.
    """
    server = fresh_server  # This uses default config from get_config()

    # Server should be initialized (done by fixture)
    assert server is not None

    # Should be able to get status
    status = await server.get_status()
    assert status is not None

    # Status should include server info (may have error if something went wrong)
    assert "server_name" in status or "storage_backend" in status

    # If no error, check expected fields
    if "error" not in status:
        if "storage_backend" in status:
            assert status["storage_backend"] in ["qdrant", "sqlite"]


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_custom_config_applied(
    clean_environment, unique_qdrant_collection, monkeypatch
):
    """Test: Custom config options respected.

    Verifies that configuration can be customized and that
    custom settings are properly applied.
    """
    from src.core.server import MemoryRAGServer
    from src.config import get_config

    # Set some custom configuration via environment variables
    custom_settings = {
        "CLAUDE_RAG_SQLITE_PATH": str(clean_environment / "custom.db"),
        "CLAUDE_RAG_EMBEDDING_CACHE_SIZE": "500",
        "CLAUDE_RAG_SEARCH_DEFAULT_LIMIT": "15",
    }

    for key, value in custom_settings.items():
        monkeypatch.setenv(key, value)

    # Create server with custom config
    config = get_config()
    server = MemoryRAGServer(config=config)
    await server.initialize()

    try:
        # Verify custom settings are applied
        # Check SQLite path
        if hasattr(server, "store") and hasattr(server.store, "db_path"):
            # SQLite store
            assert (
                str(server.store.db_path) == custom_settings["CLAUDE_RAG_SQLITE_PATH"]
            )

        # Test that server works with custom config
        status = await server.get_status()
        assert status is not None
        assert "server_name" in status or "storage_backend" in status

    finally:
        await server.close()


# ============================================================================
# Additional First-Run Experience Tests
# ============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_first_index_performance(fresh_server, sample_code_project):
    """Test: First indexing operation completes in reasonable time.

    Verifies that a new user's first indexing experience is performant.
    """
    import time

    server = fresh_server
    project_path = sample_code_project

    # Measure indexing time
    start_time = time.time()
    result = await server.index_codebase(
        directory_path=str(project_path),
        project_name="first-index-test",
        recursive=True,
    )
    index_time = time.time() - start_time

    # Verify indexing completed
    assert result is not None
    assert result.get("files_indexed", 0) > 0

    # Verify reasonable performance
    # For a small project (5 files), should complete quickly
    # Allow up to 30 seconds for first-time indexing (includes model loading)
    assert index_time < 30.0, f"First indexing took {index_time:.1f}s, expected < 30s"

    print(f"First indexing completed in {index_time:.2f}s")
    print(f"Files indexed: {result.get('files_indexed', 0)}")
    print(f"Units indexed: {result.get('units_indexed', 0)}")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_error_messages_helpful(fresh_server):
    """Test: Error messages are actionable and helpful for new users.

    Verifies that common errors provide useful guidance.
    """
    server = fresh_server

    # Test 1: Search non-existent project
    try:
        result = await server.search_code(
            query="test", project_name="non-existent-project-xyz", limit=5
        )

        # Should either return empty results or include helpful message
        if result.get("status") == "success":
            assert len(result.get("results", [])) == 0
            # Should include suggestions or quality info
            assert "quality" in result or "suggestions" in result
        else:
            # Error should be informative
            assert "message" in result or "error" in result

    except Exception as e:
        # Exception message should be helpful
        error_msg = str(e).lower()
        assert len(error_msg) > 10  # Should have meaningful message
        # Ideally includes the project name
        assert (
            "non-existent" in error_msg
            or "project" in error_msg
            or "not found" in error_msg
        )

    # Test 2: Invalid directory path
    try:
        result = await server.index_codebase(
            directory_path="/path/that/does/not/exist/xyz123",
            project_name="test-project",
        )

        # Should fail gracefully with helpful message
        if isinstance(result, dict):
            # Check for error indication
            assert (
                result.get("status") == "error" or result.get("files_indexed", 0) == 0
            )

    except Exception as e:
        error_msg = str(e).lower()
        # Should mention the problem clearly
        assert any(
            keyword in error_msg
            for keyword in ["not found", "does not exist", "invalid", "directory"]
        )


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_readme_quick_start_works(fresh_server, sample_code_project):
    """Test: README quick start instructions actually work.

    Simulates following the README to ensure new users can get started.
    This test validates the documented quick start flow.
    """
    server = fresh_server

    # Step 1: Index a codebase (from README)
    result = await server.index_codebase(
        directory_path=str(sample_code_project),
        project_name="my-project",
        recursive=True,
    )

    assert result is not None
    assert result.get("files_indexed", 0) > 0
    print(f"✓ Indexed {result['files_indexed']} files")

    # Step 2: Search the code (from README)
    search_result = await server.search_code(
        query="authentication", project_name="my-project", limit=5
    )

    assert search_result is not None
    assert search_result.get("status") == "success"
    assert len(search_result.get("results", [])) > 0
    print(f"✓ Found {len(search_result['results'])} results")

    # Step 3: Store a memory (from README)
    memory_result = await server.store_memory(
        content="This project uses SHA-256 for password hashing",
        category="fact",
        tags=["security", "authentication"],
    )

    assert memory_result is not None
    assert "memory_id" in memory_result
    print(f"✓ Stored memory with ID: {memory_result['memory_id'][:16]}...")

    # Step 4: Retrieve memories (from README)
    memories_result = await server.retrieve_memories(query="password hashing", limit=5)

    assert memories_result is not None
    # Handle both dict with results and list formats
    if isinstance(memories_result, dict):
        memories = memories_result.get("results", [])
    else:
        memories = memories_result
    assert len(memories) > 0
    print(f"✓ Retrieved {len(memories)} memories")

    # Step 5: Check status (from README)
    status = await server.get_status()

    assert status is not None
    assert "error" not in status, f"Status returned error: {status.get('error')}"
    assert status.get("qdrant_available", False), "Qdrant should be available"
    print(f"✓ Status: {status.get('memory_count', 0)} memories indexed")

    print("\n✅ All README quick start steps verified!")
