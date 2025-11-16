"""Unit tests for core data models."""

import pytest
from datetime import datetime
from src.core.models import (
    ContextLevel,
    MemoryCategory,
    MemoryScope,
    MemoryUnit,
    StoreMemoryRequest,
    QueryRequest,
    MemoryResult,
    RetrievalResponse,
    DeleteMemoryRequest,
    StatusResponse,
    SearchFilters,
)


def test_context_level_enum():
    """Test ContextLevel enum values."""
    assert ContextLevel.USER_PREFERENCE == "USER_PREFERENCE"
    assert ContextLevel.PROJECT_CONTEXT == "PROJECT_CONTEXT"
    assert ContextLevel.SESSION_STATE == "SESSION_STATE"


def test_memory_category_enum():
    """Test MemoryCategory enum values."""
    assert MemoryCategory.PREFERENCE == "preference"
    assert MemoryCategory.FACT == "fact"
    assert MemoryCategory.EVENT == "event"
    assert MemoryCategory.WORKFLOW == "workflow"
    assert MemoryCategory.CONTEXT == "context"


def test_memory_unit_creation():
    """Test creating a valid MemoryUnit."""
    memory = MemoryUnit(
        content="Test memory content",
        category=MemoryCategory.FACT,
        context_level=ContextLevel.PROJECT_CONTEXT,
        scope=MemoryScope.GLOBAL,
    )
    assert memory.content == "Test memory content"
    assert memory.category == MemoryCategory.FACT
    assert memory.importance == 0.5  # default
    assert memory.scope == MemoryScope.GLOBAL
    assert isinstance(memory.id, str)
    assert isinstance(memory.created_at, datetime)


def test_memory_unit_with_project():
    """Test MemoryUnit with project scope."""
    memory = MemoryUnit(
        content="Project-specific fact",
        category=MemoryCategory.FACT,
        scope=MemoryScope.PROJECT,
        project_name="my-project",
    )
    assert memory.scope == MemoryScope.PROJECT
    assert memory.project_name == "my-project"


def test_memory_unit_project_validation():
    """Test that project_name is required for PROJECT scope."""
    with pytest.raises(ValueError, match="project_name is required"):
        MemoryUnit(
            content="Test",
            category=MemoryCategory.FACT,
            scope=MemoryScope.PROJECT,
            # Missing project_name
        )


def test_memory_unit_content_validation():
    """Test content validation rules."""
    # Empty content should fail
    with pytest.raises(ValueError, match="Content cannot be empty"):
        MemoryUnit(
            content="   ",  # Only whitespace
            category=MemoryCategory.FACT,
        )

    # Too large content should fail (>50KB)
    with pytest.raises(Exception):  # Pydantic raises ValidationError
        MemoryUnit(
            content="x" * 60000,  # Exceeds 50KB limit
            category=MemoryCategory.FACT,
        )


def test_memory_unit_importance_validation():
    """Test importance field validation."""
    # Valid importance values
    memory1 = MemoryUnit(
        content="Test", category=MemoryCategory.FACT, importance=0.0
    )
    assert memory1.importance == 0.0

    memory2 = MemoryUnit(
        content="Test", category=MemoryCategory.FACT, importance=1.0
    )
    assert memory2.importance == 1.0

    # Invalid importance (out of range)
    with pytest.raises(ValueError):
        MemoryUnit(content="Test", category=MemoryCategory.FACT, importance=1.5)

    with pytest.raises(ValueError):
        MemoryUnit(content="Test", category=MemoryCategory.FACT, importance=-0.5)


def test_memory_unit_tags_validation():
    """Test tags validation and normalization."""
    memory = MemoryUnit(
        content="Test",
        category=MemoryCategory.FACT,
        tags=["  Python  ", "FastAPI", "API  "],
    )
    # Tags should be stripped and lowercased
    assert memory.tags == ["python", "fastapi", "api"]

    # Too many tags should fail
    with pytest.raises(ValueError, match="Maximum 20 tags"):
        MemoryUnit(
            content="Test", category=MemoryCategory.FACT, tags=[f"tag{i}" for i in range(25)]
        )


def test_store_memory_request():
    """Test StoreMemoryRequest validation."""
    request = StoreMemoryRequest(
        content="User prefers Python",
        category=MemoryCategory.PREFERENCE,
        importance=0.9,
        tags=["python", "language"],
    )
    assert request.content == "User prefers Python"
    assert request.category == MemoryCategory.PREFERENCE
    assert request.importance == 0.9
    assert request.scope == MemoryScope.GLOBAL  # default


def test_store_memory_request_injection_detection():
    """Test that StoreMemoryRequest detects SQL injection patterns."""
    dangerous_inputs = [
        "'; DROP TABLE memories; --",
        "UNION SELECT * FROM passwords",
        "DELETE FROM users",
    ]

    for dangerous_input in dangerous_inputs:
        with pytest.raises(ValueError, match="suspicious pattern"):
            StoreMemoryRequest(
                content=dangerous_input,
                category=MemoryCategory.FACT,
            )


def test_query_request():
    """Test QueryRequest validation."""
    query = QueryRequest(
        query="What are user preferences?",
        limit=10,
        context_level=ContextLevel.USER_PREFERENCE,
    )
    assert query.query == "What are user preferences?"
    assert query.limit == 10
    assert query.context_level == ContextLevel.USER_PREFERENCE
    assert query.min_importance == 0.0  # default


def test_query_request_validation():
    """Test QueryRequest validation rules."""
    # Empty query should fail
    with pytest.raises(ValueError, match="Query cannot be empty"):
        QueryRequest(query="   ")

    # Limit out of range should fail
    with pytest.raises(ValueError):
        QueryRequest(query="test", limit=0)

    with pytest.raises(ValueError):
        QueryRequest(query="test", limit=150)


def test_memory_result():
    """Test MemoryResult model."""
    memory = MemoryUnit(
        content="Test memory", category=MemoryCategory.FACT
    )
    result = MemoryResult(memory=memory, score=0.95, relevance_reason="High similarity")
    assert result.memory.content == "Test memory"
    assert result.score == 0.95
    assert result.relevance_reason == "High similarity"


def test_retrieval_response():
    """Test RetrievalResponse model."""
    memory = MemoryUnit(content="Test", category=MemoryCategory.FACT)
    result = MemoryResult(memory=memory, score=0.9)

    response = RetrievalResponse(
        results=[result], total_found=1, query_time_ms=45.2, used_cache=True
    )
    assert len(response.results) == 1
    assert response.total_found == 1
    assert response.query_time_ms == 45.2
    assert response.used_cache is True


def test_delete_memory_request():
    """Test DeleteMemoryRequest model."""
    request = DeleteMemoryRequest(memory_id="test-id-123")
    assert request.memory_id == "test-id-123"

    # Empty ID should fail
    with pytest.raises(ValueError):
        DeleteMemoryRequest(memory_id="")


def test_status_response():
    """Test StatusResponse model."""
    status = StatusResponse(
        server_name="test-server",
        version="2.0.0",
        read_only_mode=False,
        storage_backend="qdrant",
        memory_count=100,
        qdrant_available=True,
        file_watcher_enabled=True,
        retrieval_gate_enabled=True,
    )
    assert status.server_name == "test-server"
    assert status.memory_count == 100
    assert isinstance(status.timestamp, datetime)


def test_search_filters():
    """Test SearchFilters model."""
    filters = SearchFilters(
        context_level=ContextLevel.USER_PREFERENCE,
        scope=MemoryScope.GLOBAL,
        category=MemoryCategory.PREFERENCE,
        min_importance=0.7,
        tags=["python"],
    )

    filter_dict = filters.to_dict()
    assert filter_dict["context_level"] == "USER_PREFERENCE"
    assert filter_dict["scope"] == "global"
    assert filter_dict["category"] == "preference"
    assert filter_dict["min_importance"] == 0.7
    assert filter_dict["tags"] == ["python"]


def test_search_filters_empty():
    """Test SearchFilters with no filters returns empty dict."""
    filters = SearchFilters()
    filter_dict = filters.to_dict()
    assert filter_dict == {}


def test_memory_unit_metadata():
    """Test MemoryUnit with custom metadata."""
    memory = MemoryUnit(
        content="Test",
        category=MemoryCategory.FACT,
        metadata={"source": "user-input", "language": "en"},
    )
    assert memory.metadata["source"] == "user-input"
    assert memory.metadata["language"] == "en"
