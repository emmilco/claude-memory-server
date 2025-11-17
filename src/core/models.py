"""Core data models for Claude Memory RAG Server."""

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
from datetime import datetime, UTC
from enum import Enum
from typing import List, Optional, Dict, Any
from uuid import uuid4


class ContextLevel(str, Enum):
    """Context stratification levels for memory prioritization."""

    USER_PREFERENCE = "USER_PREFERENCE"  # User style, preferences, coding patterns
    PROJECT_CONTEXT = "PROJECT_CONTEXT"  # Project-specific facts, architecture
    SESSION_STATE = "SESSION_STATE"  # Temporary session information


class MemoryCategory(str, Enum):
    """Memory category types."""

    PREFERENCE = "preference"  # User preferences
    FACT = "fact"  # Factual information
    EVENT = "event"  # Events and changes
    WORKFLOW = "workflow"  # Processes and workflows
    CONTEXT = "context"  # General context


class MemoryScope(str, Enum):
    """Memory scope (global vs project-specific)."""

    GLOBAL = "global"
    PROJECT = "project"


class MemoryUnit(BaseModel):
    """Core memory record with metadata."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(..., min_length=1, max_length=50000)  # Increased for code indexing
    category: MemoryCategory
    context_level: ContextLevel = ContextLevel.PROJECT_CONTEXT
    scope: MemoryScope = MemoryScope.GLOBAL
    project_name: Optional[str] = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    embedding_model: str = "all-MiniLM-L6-v2"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate content is not empty and within size limits."""
        v = v.strip()
        if not v:
            raise ValueError("Content cannot be empty")
        if len(v.encode("utf-8")) > 51200:  # 50KB limit (increased for code indexing)
            raise ValueError("Content exceeds maximum size of 50KB")
        return v

    @model_validator(mode='after')
    def validate_project_name(self) -> 'MemoryUnit':
        """Validate project_name is required when scope is PROJECT."""
        if self.scope == MemoryScope.PROJECT and not self.project_name:
            raise ValueError("project_name is required when scope is PROJECT")
        return self

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate and normalize tags."""
        if len(v) > 20:
            raise ValueError("Maximum 20 tags allowed")
        return [tag.strip().lower() for tag in v if tag.strip()]

    model_config = ConfigDict(
        use_enum_values=False,
        json_schema_extra={
            "example": {
                "content": "User prefers Python over JavaScript for backend development",
                "category": "preference",
                "context_level": "USER_PREFERENCE",
                "scope": "global",
                "importance": 0.9,
                "tags": ["language", "preference"],
            }
        }
    )


class StoreMemoryRequest(BaseModel):
    """Request model for storing a new memory."""

    content: str = Field(..., min_length=1, max_length=50000)  # Increased for code indexing
    category: MemoryCategory
    scope: MemoryScope = MemoryScope.GLOBAL
    project_name: Optional[str] = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    context_level: Optional[ContextLevel] = None  # Auto-classified if not provided

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate content."""
        v = v.strip()
        if not v:
            raise ValueError("Content cannot be empty")
        # Check for potential injection patterns
        dangerous_patterns = ["DROP TABLE", "DELETE FROM", "'; --", "UNION SELECT"]
        content_upper = v.upper()
        for pattern in dangerous_patterns:
            if pattern in content_upper:
                raise ValueError(f"Content contains suspicious pattern: {pattern}")
        return v


class QueryRequest(BaseModel):
    """Request model for querying memories."""

    query: str = Field(..., min_length=1, max_length=1000)
    limit: int = Field(default=5, ge=1, le=100)
    context_level: Optional[ContextLevel] = None
    scope: Optional[MemoryScope] = None
    project_name: Optional[str] = None
    category: Optional[MemoryCategory] = None
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate query string."""
        v = v.strip()
        if not v:
            raise ValueError("Query cannot be empty")
        return v


class MemoryResult(BaseModel):
    """A single memory search result with score."""

    memory: MemoryUnit
    score: float = Field(..., ge=0.0, le=1.0)
    relevance_reason: Optional[str] = None


class RetrievalResponse(BaseModel):
    """Response model for memory retrieval."""

    results: List[MemoryResult]
    total_found: int
    query_time_ms: float
    used_cache: bool = False

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "results": [
                    {
                        "memory": {
                            "content": "User prefers Python",
                            "category": "preference",
                            "context_level": "USER_PREFERENCE",
                        },
                        "score": 0.95,
                    }
                ],
                "total_found": 1,
                "query_time_ms": 45.2,
                "used_cache": False,
            }
        }
    )


class DeleteMemoryRequest(BaseModel):
    """Request model for deleting a memory."""

    memory_id: str = Field(..., min_length=1)


class StatusResponse(BaseModel):
    """Server status response."""

    server_name: str
    version: str
    read_only_mode: bool
    storage_backend: str
    memory_count: int
    qdrant_available: bool
    file_watcher_enabled: bool
    retrieval_gate_enabled: bool
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SearchFilters(BaseModel):
    """Filters for memory search."""

    context_level: Optional[ContextLevel] = None
    scope: Optional[MemoryScope] = None
    project_name: Optional[str] = None
    category: Optional[MemoryCategory] = None
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Qdrant filtering."""
        filters = {}
        if self.context_level:
            filters["context_level"] = self.context_level.value
        if self.scope:
            filters["scope"] = self.scope.value
        if self.project_name:
            filters["project_name"] = self.project_name
        if self.category:
            filters["category"] = self.category.value
        if self.min_importance > 0.0:
            filters["min_importance"] = self.min_importance
        if self.tags:
            filters["tags"] = self.tags
        return filters


class SuccessResponse(BaseModel):
    """Standard success response format for API operations."""

    status: str = Field(default="success", description="Response status")
    message: Optional[str] = Field(default=None, description="Success message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Response data")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Response timestamp"
    )


class ErrorResponse(BaseModel):
    """Standard error response format for API operations."""

    status: str = Field(default="error", description="Response status")
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details"
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Request ID for tracking"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Error timestamp"
    )
