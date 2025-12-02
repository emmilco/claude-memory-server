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
    CODE = "code"  # Code snippets and functions


class MemoryScope(str, Enum):
    """Memory scope (global vs project-specific)."""

    GLOBAL = "global"
    PROJECT = "project"


class LifecycleState(str, Enum):
    """Memory lifecycle states for automatic archival and weighting."""

    ACTIVE = "ACTIVE"  # 0-7 days, frequently accessed, full weight (1.0x)
    RECENT = "RECENT"  # 7-30 days, moderately relevant, reduced weight (0.7x)
    ARCHIVED = "ARCHIVED"  # 30-180 days, historical, heavy penalty (0.3x)
    STALE = "STALE"  # 180+ days, candidate for deletion, minimal weight (0.1x)


class ProvenanceSource(str, Enum):
    """Source of memory creation."""

    USER_EXPLICIT = "user_explicit"  # User directly stated
    CLAUDE_INFERRED = "claude_inferred"  # Claude inferred from conversation
    DOCUMENTATION = "documentation"  # From code docs/comments
    AUTO_CLASSIFIED = "auto_classified"  # Auto-classified category
    IMPORTED = "imported"  # Imported from external source
    CODE_INDEXED = "code_indexed"  # From code indexing
    LEGACY = "legacy"  # Migrated from old system


class MergeStrategy(str, Enum):
    """Strategy for merging duplicate memories."""

    KEEP_MOST_RECENT = "keep_most_recent"  # Keep the newest memory
    KEEP_HIGHEST_IMPORTANCE = "keep_highest_importance"  # Keep most important
    KEEP_MOST_ACCESSED = "keep_most_accessed"  # Keep most frequently accessed
    MERGE_CONTENT = "merge_content"  # Combine content from all
    USER_SELECTED = "user_selected"  # User manually selected canonical


class MemoryProvenance(BaseModel):
    """Provenance metadata for a memory."""

    source: ProvenanceSource = ProvenanceSource.USER_EXPLICIT
    created_by: str = "user_statement"  # Description of creation method
    last_confirmed: Optional[datetime] = None  # When user last verified
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)  # System confidence
    verified: bool = False  # User explicitly verified
    conversation_id: Optional[str] = None  # Associated conversation
    file_context: List[str] = Field(default_factory=list)  # Files being worked on
    notes: Optional[str] = None  # Additional provenance notes

    model_config = ConfigDict(use_enum_values=False)


class MemoryUnit(BaseModel):
    """Core memory record with metadata."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str = Field(
        ..., min_length=1, max_length=50000
    )  # Increased for code indexing
    category: MemoryCategory
    context_level: ContextLevel = ContextLevel.PROJECT_CONTEXT
    scope: MemoryScope = MemoryScope.GLOBAL
    project_name: Optional[str] = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    embedding_model: str = "all-MiniLM-L6-v2"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_accessed: datetime = Field(default_factory=lambda: datetime.now(UTC))
    lifecycle_state: LifecycleState = LifecycleState.ACTIVE
    provenance: MemoryProvenance = Field(default_factory=MemoryProvenance)
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

    @model_validator(mode="after")
    def validate_project_name(self) -> "MemoryUnit":
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
        },
    )


class StoreMemoryRequest(BaseModel):
    """Request model for storing a new memory."""

    content: str = Field(
        ..., min_length=1, max_length=50000
    )  # Increased for code indexing
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
    advanced_filters: Optional["AdvancedSearchFilters"] = None  # Forward reference

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Validate query string."""
        v = v.strip()
        if not v:
            raise ValueError("Query cannot be empty")
        return v


class AdvancedSearchFilters(BaseModel):
    """Advanced filtering options for memory search."""

    # Date filtering
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    updated_after: Optional[datetime] = None
    updated_before: Optional[datetime] = None
    accessed_after: Optional[datetime] = None
    accessed_before: Optional[datetime] = None

    # Tag logic
    tags_any: Optional[List[str]] = None  # Match ANY of these tags (OR)
    tags_all: Optional[List[str]] = None  # Match ALL of these tags (AND)
    tags_none: Optional[List[str]] = None  # Exclude these tags (NOT)

    # Lifecycle filtering
    lifecycle_states: Optional[List[LifecycleState]] = None

    # Exclusions
    exclude_categories: Optional[List[MemoryCategory]] = None
    exclude_projects: Optional[List[str]] = None

    # Provenance filtering
    min_trust_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source: Optional[ProvenanceSource] = None

    model_config = ConfigDict(use_enum_values=False)

    @field_validator("tags_any", "tags_all", "tags_none")
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate and normalize tag lists."""
        if v is None:
            return None
        return [tag.strip().lower() for tag in v if tag.strip()]


class CodeSearchFilters(BaseModel):
    """
    Advanced filtering options specifically for code search.

    FEAT-056: Extends search_code with glob patterns, complexity filters,
    date ranges, and multi-criteria sorting.
    """

    # Glob pattern matching (NOT substring)
    file_pattern: Optional[str] = Field(
        default=None,
        description="Glob pattern for file paths (e.g., '**/*.test.py', 'src/**/auth*.ts')",
    )

    # Exclusion patterns
    exclude_patterns: Optional[List[str]] = Field(
        default=None,
        description="Glob patterns to exclude (e.g., ['**/*.test.py', '**/generated/**'])",
    )

    # Complexity filters
    complexity_min: Optional[int] = Field(
        default=None, ge=0, description="Minimum cyclomatic complexity"
    )
    complexity_max: Optional[int] = Field(
        default=None, ge=0, description="Maximum cyclomatic complexity"
    )

    # Line count filters
    line_count_min: Optional[int] = Field(default=None, ge=0)
    line_count_max: Optional[int] = Field(default=None, ge=0)

    # Date range filters (file modification time)
    modified_after: Optional[datetime] = Field(
        default=None, description="Filter by file modification time (after this date)"
    )
    modified_before: Optional[datetime] = Field(
        default=None, description="Filter by file modification time (before this date)"
    )

    # Sorting
    sort_by: Optional[str] = Field(
        default="relevance",
        description="Sort order: relevance, complexity, size, recency, importance",
    )
    sort_order: Optional[str] = Field(
        default="desc", description="Sort direction: asc or desc"
    )

    model_config = ConfigDict(use_enum_values=False)

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v: Optional[str]) -> str:
        """Validate sort_by parameter."""
        if v is None:
            return "relevance"
        allowed = ["relevance", "complexity", "size", "recency", "importance"]
        if v not in allowed:
            raise ValueError(f"sort_by must be one of: {', '.join(allowed)}")
        return v

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v: Optional[str]) -> str:
        """Validate sort_order parameter."""
        if v is None:
            return "desc"
        if v not in ["asc", "desc"]:
            raise ValueError("sort_order must be 'asc' or 'desc'")
        return v

    @field_validator("complexity_min", "complexity_max")
    @classmethod
    def validate_complexity(cls, v: Optional[int]) -> Optional[int]:
        """Validate complexity bounds."""
        if v is not None and v < 0:
            raise ValueError("Complexity values must be non-negative")
        return v

    @field_validator("line_count_min", "line_count_max")
    @classmethod
    def validate_line_count(cls, v: Optional[int]) -> Optional[int]:
        """Validate line count bounds."""
        if v is not None and v < 0:
            raise ValueError("Line count values must be non-negative")
        return v


class TrustSignals(BaseModel):
    """Trust signals and explanations for a search result."""

    why_shown: List[str] = Field(
        default_factory=list
    )  # Reasons why this result matched
    trust_score: float = Field(ge=0.0, le=1.0)  # Overall trust score (0-1)
    confidence_level: str  # "excellent", "good", "fair", "poor"
    last_verified: Optional[str] = None  # Human-readable time since verification
    provenance_summary: Dict[str, Any] = Field(default_factory=dict)  # Provenance info
    related_count: int = 0  # Number of related memories
    contradiction_detected: bool = False  # Whether contradictions exist

    model_config = ConfigDict(use_enum_values=False)


class MemoryResult(BaseModel):
    """A single memory search result with score."""

    memory: MemoryUnit
    score: float = Field(..., ge=0.0, le=1.0)
    relevance_reason: Optional[str] = None
    trust_signals: Optional[TrustSignals] = None  # Trust and provenance information
    explanation: Optional[List[str]] = None  # Detailed explanation of result


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
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SearchFilters(BaseModel):
    """Filters for memory search."""

    context_level: Optional[ContextLevel] = None
    scope: Optional[MemoryScope] = None
    project_name: Optional[str] = None
    category: Optional[MemoryCategory] = None
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)
    max_importance: float = Field(default=1.0, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)
    lifecycle_state: Optional[LifecycleState] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    advanced_filters: Optional[AdvancedSearchFilters] = None

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
        if self.max_importance < 1.0:
            filters["max_importance"] = self.max_importance
        if self.tags:
            filters["tags"] = self.tags
        if self.lifecycle_state:
            filters["lifecycle_state"] = self.lifecycle_state.value
        if self.date_from:
            filters["date_from"] = self.date_from
        if self.date_to:
            filters["date_to"] = self.date_to
        if self.advanced_filters:
            filters["advanced_filters"] = self.advanced_filters
        return filters


class SuccessResponse(BaseModel):
    """Standard success response format for API operations."""

    status: str = Field(default="success", description="Response status")
    message: Optional[str] = Field(default=None, description="Success message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Response data")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


class ErrorResponse(BaseModel):
    """Standard error response format for API operations."""

    status: str = Field(default="error", description="Response status")
    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional error details"
    )
    request_id: Optional[str] = Field(
        default=None, description="Request ID for tracking"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Error timestamp"
    )


class UpdateMemoryRequest(BaseModel):
    """Request to update an existing memory.

    Only fields that are provided will be updated. All fields except
    memory_id are optional.
    """

    memory_id: str = Field(..., description="ID of memory to update (required)")

    # Optional update fields
    content: Optional[str] = Field(None, min_length=1, max_length=50000)
    category: Optional[MemoryCategory] = None
    importance: Optional[float] = Field(None, ge=0.0, le=1.0)
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    context_level: Optional[ContextLevel] = None

    # Update behavior flags
    preserve_timestamps: bool = Field(
        default=True, description="Keep created_at, update modified_at"
    )
    regenerate_embedding: bool = Field(
        default=True, description="Auto-regenerate embedding if content changes"
    )

    @model_validator(mode="after")
    def validate_has_updates(self) -> "UpdateMemoryRequest":
        """Validate at least one field is being updated."""
        update_fields = [
            self.content,
            self.category,
            self.importance,
            self.tags,
            self.metadata,
            self.context_level,
        ]

        if all(field is None for field in update_fields):
            raise ValueError("At least one field must be provided for update")

        return self

    @field_validator("tags")
    @classmethod
    def validate_tags_list(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate tags if provided."""
        if v is None:
            return v

        if len(v) > 20:
            raise ValueError("Maximum 20 tags allowed")

        validated_tags = []
        for tag in v:
            if not isinstance(tag, str):
                raise ValueError("Tags must be strings")
            tag_clean = tag.strip().lower()
            if not tag_clean:
                continue
            if len(tag_clean) > 50:
                raise ValueError("Tags must be <= 50 characters")
            validated_tags.append(tag_clean)

        return validated_tags

    model_config = ConfigDict(use_enum_values=False)


class UpdateMemoryResponse(BaseModel):
    """Response from memory update operation."""

    memory_id: str = Field(..., description="ID of updated memory")
    status: str = Field(default="updated", description="Update status")
    updated_fields: List[str] = Field(
        default_factory=list, description="List of fields that were changed"
    )
    embedding_regenerated: bool = Field(
        default=False, description="Whether embedding was regenerated"
    )
    updated_at: str = Field(..., description="ISO timestamp of update")
    previous_version: Optional[Dict[str, Any]] = Field(
        default=None, description="Previous values for audit trail (optional)"
    )

    model_config = ConfigDict(use_enum_values=False)


class RelevanceFactors(BaseModel):
    """Breakdown of relevance scoring factors."""

    semantic_similarity: float = Field(ge=0.0, le=1.0)
    recency: float = Field(ge=0.0, le=1.0)
    importance: float = Field(ge=0.0, le=1.0)
    context_match: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(use_enum_values=False)


class Suggestion(BaseModel):
    """A single proactive suggestion."""

    memory_id: str = Field(..., description="ID of suggested memory/code")
    content: str = Field(..., description="Memory/code content")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Overall confidence score"
    )
    reason: str = Field(..., description="Explanation of why this was suggested")
    source_type: str = Field(..., description="Type: 'memory' or 'code'")
    relevance_factors: RelevanceFactors = Field(..., description="Scoring breakdown")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata (file_path, tags, etc.)"
    )

    model_config = ConfigDict(use_enum_values=False)


class DetectedIntentInfo(BaseModel):
    """Information about detected user intent."""

    intent_type: str = Field(..., description="Type of intent detected")
    keywords: List[str] = Field(default_factory=list, description="Extracted keywords")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Intent detection confidence"
    )
    search_query: str = Field(..., description="Synthesized search query")

    model_config = ConfigDict(use_enum_values=False)


class SuggestionResponse(BaseModel):
    """Response from proactive suggestion request."""

    suggestions: List[Suggestion] = Field(
        default_factory=list, description="List of suggestions ordered by confidence"
    )
    detected_intent: DetectedIntentInfo = Field(
        ..., description="Detected intent information"
    )
    confidence_threshold: float = Field(
        ..., ge=0.0, le=1.0, description="Minimum confidence threshold used"
    )
    total_suggestions: int = Field(..., description="Number of suggestions returned")
    session_id: str = Field(..., description="Conversation session ID")

    model_config = ConfigDict(use_enum_values=False)


class FeedbackRating(str, Enum):
    """User feedback rating for search results."""

    HELPFUL = "helpful"
    NOT_HELPFUL = "not_helpful"


class SearchFeedback(BaseModel):
    """User feedback for a search query and its results."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    search_id: str = Field(
        ..., description="Unique ID of the search this feedback relates to"
    )
    query: str = Field(..., description="Original search query")
    result_ids: List[str] = Field(
        default_factory=list, description="IDs of results returned"
    )
    rating: FeedbackRating = Field(
        ..., description="User rating: helpful or not_helpful"
    )
    comment: Optional[str] = Field(None, description="Optional user comment")
    project_name: Optional[str] = Field(None, description="Project context")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="When feedback was submitted",
    )
    user_id: Optional[str] = Field(None, description="Optional user identifier")

    model_config = ConfigDict(use_enum_values=False)


class QualityMetrics(BaseModel):
    """Aggregated quality metrics for search results."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    time_window: str = Field(..., description="Time window: hour, day, or week")
    window_start: str = Field(..., description="Start of time window (ISO format)")
    total_searches: int = Field(default=0, description="Total number of searches")
    helpful_count: int = Field(default=0, description="Number of helpful ratings")
    not_helpful_count: int = Field(
        default=0, description="Number of not helpful ratings"
    )
    avg_result_count: float = Field(
        default=0.0, description="Average number of results returned"
    )
    project_name: Optional[str] = Field(None, description="Project filter")
    updated_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Last update timestamp",
    )

    @property
    def helpfulness_rate(self) -> float:
        """Calculate helpfulness rate (0.0 to 1.0)."""
        total_rated = self.helpful_count + self.not_helpful_count
        if total_rated == 0:
            return 0.0
        return self.helpful_count / total_rated

    model_config = ConfigDict(use_enum_values=False)


# FEAT-020: Usage Patterns Tracking Models


class GetUsageStatisticsRequest(BaseModel):
    """Request for overall usage statistics."""

    days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Number of days to look back for statistics",
    )

    model_config = ConfigDict(use_enum_values=False)


class GetUsageStatisticsResponse(BaseModel):
    """Response with overall usage statistics."""

    period_days: int = Field(..., description="Number of days covered")
    total_queries: int = Field(default=0, description="Total number of queries")
    unique_queries: int = Field(default=0, description="Number of unique query texts")
    avg_query_time_ms: float = Field(
        default=0.0, description="Average query execution time"
    )
    avg_result_count: float = Field(
        default=0.0, description="Average number of results per query"
    )
    total_code_accesses: int = Field(
        default=0, description="Total code file/function accesses"
    )
    unique_files: int = Field(default=0, description="Number of unique files accessed")
    unique_functions: int = Field(
        default=0, description="Number of unique functions accessed"
    )
    most_active_day: Optional[str] = Field(None, description="Date of most activity")
    most_active_day_count: int = Field(
        default=0, description="Query count on most active day"
    )

    model_config = ConfigDict(use_enum_values=False)


class GetTopQueriesRequest(BaseModel):
    """Request for most frequent queries."""

    limit: int = Field(
        default=10, ge=1, le=100, description="Maximum number of queries to return"
    )
    days: int = Field(
        default=30, ge=1, le=365, description="Number of days to look back"
    )

    model_config = ConfigDict(use_enum_values=False)


class QueryStatistics(BaseModel):
    """Statistics for a single query."""

    query: str = Field(..., description="The query text")
    count: int = Field(..., description="Number of times queried")
    avg_result_count: float = Field(
        default=0.0, description="Average number of results"
    )
    avg_execution_time_ms: float = Field(
        default=0.0, description="Average execution time"
    )
    last_used: str = Field(..., description="ISO timestamp of last use")

    model_config = ConfigDict(use_enum_values=False)


class GetTopQueriesResponse(BaseModel):
    """Response with most frequent queries."""

    queries: List[QueryStatistics] = Field(
        default_factory=list,
        description="List of query statistics ordered by frequency",
    )
    period_days: int = Field(..., description="Number of days covered")
    total_returned: int = Field(..., description="Number of queries returned")

    model_config = ConfigDict(use_enum_values=False)


class GetFrequentlyAccessedCodeRequest(BaseModel):
    """Request for most frequently accessed code."""

    limit: int = Field(
        default=10, ge=1, le=100, description="Maximum number of items to return"
    )
    days: int = Field(
        default=30, ge=1, le=365, description="Number of days to look back"
    )

    model_config = ConfigDict(use_enum_values=False)


class CodeAccessStatistics(BaseModel):
    """Statistics for accessed code files/functions."""

    file_path: str = Field(..., description="Path to the code file")
    function_name: Optional[str] = Field(
        None, description="Function/method name if applicable"
    )
    access_count: int = Field(..., description="Number of times accessed")
    last_accessed: str = Field(..., description="ISO timestamp of last access")

    model_config = ConfigDict(use_enum_values=False)


class GetFrequentlyAccessedCodeResponse(BaseModel):
    """Response with most frequently accessed code."""

    code_items: List[CodeAccessStatistics] = Field(
        default_factory=list,
        description="List of code access statistics ordered by frequency",
    )
    period_days: int = Field(..., description="Number of days covered")
    total_returned: int = Field(..., description="Number of items returned")

    model_config = ConfigDict(use_enum_values=False)
