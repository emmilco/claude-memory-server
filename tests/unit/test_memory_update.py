"""Unit tests for memory update operations."""

import pytest
from datetime import datetime, UTC
from src.core.models import (
    UpdateMemoryRequest,
    UpdateMemoryResponse,
    MemoryCategory,
    ContextLevel,
)
from pydantic import ValidationError


class TestUpdateMemoryRequest:
    """Test UpdateMemoryRequest model validation."""

    def test_valid_request_with_content(self):
        """Test valid update request with content."""
        request = UpdateMemoryRequest(memory_id="test-123", content="Updated content")
        assert request.memory_id == "test-123"
        assert request.content == "Updated content"
        assert request.regenerate_embedding is True

    def test_valid_request_with_multiple_fields(self):
        """Test valid update request with multiple fields."""
        request = UpdateMemoryRequest(
            memory_id="test-123",
            content="Updated content",
            category=MemoryCategory.PREFERENCE,
            importance=0.8,
            tags=["tag1", "tag2"],
            metadata={"key": "value"},
            context_level=ContextLevel.USER_PREFERENCE,
        )
        assert request.memory_id == "test-123"
        assert request.content == "Updated content"
        assert request.category == MemoryCategory.PREFERENCE
        assert request.importance == 0.8
        assert request.tags == ["tag1", "tag2"]
        assert request.metadata == {"key": "value"}
        assert request.context_level == ContextLevel.USER_PREFERENCE

    def test_valid_request_with_only_metadata(self):
        """Test valid update request with only metadata."""
        request = UpdateMemoryRequest(memory_id="test-123", metadata={"updated": True})
        assert request.memory_id == "test-123"
        assert request.content is None
        assert request.metadata == {"updated": True}

    def test_invalid_request_no_updates(self):
        """Test that request fails if no fields are provided for update."""
        with pytest.raises(ValidationError) as exc_info:
            UpdateMemoryRequest(memory_id="test-123")
        assert "At least one field must be provided for update" in str(exc_info.value)

    def test_invalid_content_too_long(self):
        """Test that content exceeding max length fails."""
        with pytest.raises(ValidationError):
            UpdateMemoryRequest(
                memory_id="test-123",
                content="x" * 60000,  # Exceeds 50000 max
            )

    def test_invalid_importance_out_of_range(self):
        """Test that importance outside 0.0-1.0 fails."""
        with pytest.raises(ValidationError):
            UpdateMemoryRequest(memory_id="test-123", importance=1.5)

        with pytest.raises(ValidationError):
            UpdateMemoryRequest(memory_id="test-123", importance=-0.1)

    def test_invalid_too_many_tags(self):
        """Test that more than 20 tags fails."""
        with pytest.raises(ValidationError) as exc_info:
            UpdateMemoryRequest(
                memory_id="test-123",
                tags=[f"tag{i}" for i in range(25)],  # 25 tags
            )
        assert "Maximum 20 tags allowed" in str(exc_info.value)

    def test_tags_validation_strips_whitespace(self):
        """Test that tags are normalized (stripped and lowercased)."""
        request = UpdateMemoryRequest(
            memory_id="test-123", tags=["  TAG1  ", "Tag2", "  tag3"]
        )
        assert request.tags == ["tag1", "tag2", "tag3"]

    def test_tags_validation_removes_empty(self):
        """Test that empty tags are removed."""
        request = UpdateMemoryRequest(
            memory_id="test-123", tags=["tag1", "  ", "", "tag2"]
        )
        assert request.tags == ["tag1", "tag2"]

    def test_tags_validation_max_length(self):
        """Test that tags exceeding 50 characters fail."""
        with pytest.raises(ValidationError) as exc_info:
            UpdateMemoryRequest(
                memory_id="test-123",
                tags=["x" * 60],  # 60 characters
            )
        assert "Tags must be <= 50 characters" in str(exc_info.value)

    def test_preserve_timestamps_flag(self):
        """Test preserve_timestamps flag."""
        request = UpdateMemoryRequest(
            memory_id="test-123", content="Updated", preserve_timestamps=False
        )
        assert request.preserve_timestamps is False

    def test_regenerate_embedding_flag(self):
        """Test regenerate_embedding flag."""
        request = UpdateMemoryRequest(
            memory_id="test-123", content="Updated", regenerate_embedding=False
        )
        assert request.regenerate_embedding is False


class TestUpdateMemoryResponse:
    """Test UpdateMemoryResponse model."""

    def test_valid_response(self):
        """Test valid update response."""
        response = UpdateMemoryResponse(
            memory_id="test-123",
            status="updated",
            updated_fields=["content", "importance"],
            embedding_regenerated=True,
            updated_at=datetime.now(UTC).isoformat(),
        )
        assert response.memory_id == "test-123"
        assert response.status == "updated"
        assert response.updated_fields == ["content", "importance"]
        assert response.embedding_regenerated is True

    def test_response_with_no_embedding_regeneration(self):
        """Test response when embedding not regenerated."""
        response = UpdateMemoryResponse(
            memory_id="test-123",
            status="updated",
            updated_fields=["importance"],
            embedding_regenerated=False,
            updated_at=datetime.now(UTC).isoformat(),
        )
        assert response.embedding_regenerated is False

    def test_response_serialization(self):
        """Test response can be serialized to dict."""
        response = UpdateMemoryResponse(
            memory_id="test-123",
            status="updated",
            updated_fields=["content"],
            embedding_regenerated=True,
            updated_at=datetime.now(UTC).isoformat(),
        )
        data = response.model_dump()
        assert data["memory_id"] == "test-123"
        assert data["status"] == "updated"
        assert data["updated_fields"] == ["content"]
        assert data["embedding_regenerated"] is True
        assert "updated_at" in data
