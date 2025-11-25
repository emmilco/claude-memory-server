"""Configuration management for Claude Memory RAG Server."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel, model_validator, field_validator
from typing import Optional, Literal
from pathlib import Path
from enum import Enum
import os
import json
import logging

logger = logging.getLogger(__name__)


class FeatureLevel(str, Enum):
    """Feature maturity levels for easy configuration presets."""
    BASIC = "basic"           # Stable, production-ready features only
    ADVANCED = "advanced"     # All stable features including power-user features
    EXPERIMENTAL = "experimental"  # All features including unstable/experimental


class PerformanceFeatures(BaseModel):
    """Performance optimization features."""

    # Embedding generation
    parallel_embeddings: bool = True  # Use multiprocessing for faster embedding generation
    parallel_workers: Optional[int] = None  # Auto-detect CPU count if None

    # Search optimizations
    hybrid_search: bool = True  # BM25 + Vector hybrid search
    importance_scoring: bool = True  # Intelligent importance scoring for code units

    # GPU acceleration
    gpu_enabled: bool = True  # Auto-use GPU if available
    gpu_memory_fraction: float = 0.8  # Max GPU memory to use (0.0-1.0)
    force_cpu: bool = False  # Override GPU detection, use CPU only

    @field_validator('force_cpu')
    @classmethod
    def validate_gpu_cpu_exclusive(cls, v: bool, info) -> bool:
        """Ensure gpu_enabled and force_cpu are mutually exclusive."""
        if v and info.data.get('gpu_enabled', False):
            raise ValueError("Cannot enable both gpu_enabled and force_cpu")
        return v


class SearchFeatures(BaseModel):
    """Search and retrieval features."""

    # Core search
    hybrid_search: bool = True  # BM25 + Vector hybrid search
    retrieval_gate_enabled: bool = True  # Gate low-quality retrievals
    retrieval_gate_threshold: float = 0.8

    # Cross-project search
    cross_project_enabled: bool = True  # Allow searching across projects
    cross_project_default_mode: str = "current"  # "current" or "all"

    # Query expansion
    query_expansion_enabled: bool = True  # Expand queries with synonyms/context
    query_expansion_synonyms: bool = True  # Programming term synonyms
    query_expansion_code_context: bool = True  # Code domain patterns
    query_expansion_max_synonyms: int = 2
    query_expansion_max_context_terms: int = 3


class AnalyticsFeatures(BaseModel):
    """Analytics and monitoring features."""

    usage_tracking: bool = True  # Track memory usage patterns
    usage_pattern_analytics: bool = True  # Analyze usage patterns for insights
    usage_analytics_retention_days: int = 90

    @field_validator('usage_pattern_analytics')
    @classmethod
    def validate_analytics_requires_tracking(cls, v: bool, info) -> bool:
        """Pattern analytics requires usage tracking."""
        if v and not info.data.get('usage_tracking', False):
            raise ValueError(
                "usage_pattern_analytics requires usage_tracking to be enabled"
            )
        return v


class MemoryFeatures(BaseModel):
    """Memory management features."""

    # Pruning
    auto_pruning: bool = True  # Automatic memory pruning
    pruning_schedule: str = "0 2 * * *"  # Cron format: 2 AM daily
    session_state_ttl_hours: int = 48

    # Conversation tracking
    conversation_tracking: bool = True  # Track conversation context
    conversation_session_timeout_minutes: int = 30

    # Proactive suggestions
    proactive_suggestions: bool = True  # Analyze messages for context patterns
    proactive_suggestions_threshold: float = 0.90


class IndexingFeatures(BaseModel):
    """Code indexing features."""

    # File watching
    file_watcher: bool = True  # Watch for file changes
    watch_debounce_ms: int = 1000

    # Auto-indexing
    auto_index_enabled: bool = True  # Enable automatic indexing
    auto_index_on_startup: bool = True  # Index on MCP server startup
    auto_index_size_threshold: int = 500  # Files threshold for background mode
    auto_index_recursive: bool = True  # Recursive directory indexing
    auto_index_show_progress: bool = True  # Show progress indicators
    auto_index_exclude_patterns: list[str] = [
        "node_modules/**", ".git/**", "venv/**", "__pycache__/**", "*.pyc",
        "dist/**", "build/**", ".next/**", "target/**", "*.min.js", "*.map"
    ]

    # Git indexing
    git_indexing: bool = True  # Index git history
    git_index_commit_count: int = 1000
    git_index_branches: str = "current"  # "current" or "all"
    git_index_tags: bool = True
    git_index_diffs: bool = True

    @field_validator('auto_index_on_startup')
    @classmethod
    def validate_auto_index_children(cls, v: bool, info) -> bool:
        """Auto-index children require parent enabled."""
        if v and not info.data.get('auto_index_enabled', False):
            raise ValueError(
                "auto_index_on_startup requires auto_index_enabled=True"
            )
        return v


class AdvancedFeatures(BaseModel):
    """Advanced/experimental features."""

    # Multi-repository support
    multi_repository: bool = True  # Enable multi-repository features
    multi_repo_max_parallel: int = 3  # Max concurrent repository operations

    # Graceful degradation
    rust_fallback: bool = True  # Fall back to Python parser if Rust unavailable
    warn_on_degradation: bool = True  # Show warnings when running in degraded mode

    # Security
    read_only_mode: bool = False  # Restrict to read-only operations
    input_validation: bool = True  # Validate all inputs


class ServerConfig(BaseSettings):
    """
    Server configuration with environment variable support.

    REF-017: Configuration now organized into feature groups for better manageability.
    Legacy flat flags are still supported for backward compatibility with deprecation warnings.
    """

    # Core settings
    server_name: str = "claude-memory-rag"
    log_level: str = "INFO"

    # Storage backend (Qdrant required for semantic code search)
    storage_backend: Literal["qdrant"] = "qdrant"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection_name: str = "memory"

    # Connection pooling (PERF-007)
    qdrant_pool_size: int = 5  # Maximum connections in pool
    qdrant_pool_min_size: int = 1  # Minimum connections to maintain
    qdrant_pool_timeout: float = 10.0  # Max wait for connection (seconds)
    qdrant_pool_recycle: int = 3600  # Recycle connections after N seconds (1 hour)
    qdrant_prefer_grpc: bool = False  # Use gRPC for better performance
    qdrant_health_check_interval: int = 60  # Health check every N seconds

    # Performance tuning
    embedding_batch_size: int = 32
    max_query_context_tokens: int = 8000
    retrieval_timeout_ms: int = 500

    # Embedding settings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_cache_enabled: bool = True
    embedding_cache_path: str = "~/.claude-rag/embedding_cache.db"
    embedding_cache_ttl_days: int = 30

    # SQLite for metadata tracking (not for vector storage - Qdrant only)
    sqlite_path: str = "~/.claude-rag/metadata.db"  # For ProjectIndexTracker metadata

    # Feature Groups (REF-017: New organized structure)
    performance: PerformanceFeatures = PerformanceFeatures()
    search: SearchFeatures = SearchFeatures()
    analytics: AnalyticsFeatures = AnalyticsFeatures()
    memory: MemoryFeatures = MemoryFeatures()
    indexing: IndexingFeatures = IndexingFeatures()
    advanced: AdvancedFeatures = AdvancedFeatures()

    # Feature level presets (NEW!)
    feature_level: Optional[FeatureLevel] = None

    # Legacy flat flags (DEPRECATED - for backward compatibility)
    # These will be removed in v5.0.0 - migrate to feature groups
    enable_parallel_embeddings: Optional[bool] = None
    embedding_parallel_workers: Optional[int] = None
    enable_input_validation: Optional[bool] = None
    enable_file_watcher: Optional[bool] = None
    enable_importance_scoring: Optional[bool] = None
    allow_rust_fallback: Optional[bool] = None
    warn_on_degradation: Optional[bool] = None
    auto_index_enabled: Optional[bool] = None
    auto_index_on_startup: Optional[bool] = None
    auto_index_size_threshold: Optional[int] = None
    auto_index_recursive: Optional[bool] = None
    auto_index_show_progress: Optional[bool] = None
    auto_index_exclude_patterns: Optional[list[str]] = None
    enable_retrieval_gate: Optional[bool] = None
    retrieval_gate_threshold: Optional[float] = None
    enable_auto_pruning: Optional[bool] = None
    pruning_schedule: Optional[str] = None
    session_state_ttl_hours: Optional[int] = None
    enable_usage_tracking: Optional[bool] = None
    enable_usage_pattern_analytics: Optional[bool] = None
    usage_analytics_retention_days: Optional[int] = None
    enable_conversation_tracking: Optional[bool] = None
    conversation_session_timeout_minutes: Optional[int] = None
    enable_query_expansion: Optional[bool] = None
    query_expansion_synonyms: Optional[bool] = None
    query_expansion_code_context: Optional[bool] = None
    query_expansion_max_synonyms: Optional[int] = None
    query_expansion_max_context_terms: Optional[int] = None
    enable_git_indexing: Optional[bool] = None
    git_index_commit_count: Optional[int] = None
    git_index_branches: Optional[str] = None
    git_index_tags: Optional[bool] = None
    git_index_diffs: Optional[bool] = None
    enable_hybrid_search: Optional[bool] = None
    enable_cross_project_search: Optional[bool] = None
    cross_project_default_mode: Optional[str] = None
    enable_gpu: Optional[bool] = None
    force_cpu: Optional[bool] = None
    gpu_memory_fraction: Optional[float] = None
    enable_multi_repository: Optional[bool] = None
    multi_repo_max_parallel: Optional[int] = None
    enable_proactive_suggestions: Optional[bool] = None
    proactive_suggestions_threshold: Optional[float] = None
    read_only_mode: Optional[bool] = None

    # Other settings (not feature flags)
    max_memory_size_bytes: int = 10240  # 10KB
    watch_debounce_ms: int = 1000
    importance_complexity_weight: float = 1.0
    importance_usage_weight: float = 1.0
    importance_criticality_weight: float = 1.0
    usage_batch_size: int = 100
    usage_flush_interval_seconds: int = 60
    ranking_weight_similarity: float = 0.6
    ranking_weight_recency: float = 0.2
    ranking_weight_usage: float = 0.2
    recency_decay_halflife_days: float = 7.0
    conversation_query_history_size: int = 5
    query_expansion_similarity_threshold: float = 0.7
    deduplication_fetch_multiplier: int = 3
    git_auto_size_threshold_mb: int = 500
    git_diff_size_limit_kb: int = 10
    hybrid_search_alpha: float = 0.5
    hybrid_fusion_method: str = "weighted"
    bm25_k1: float = 1.5
    bm25_b: float = 0.75
    cross_project_opt_in_file: str = "~/.claude-rag/cross_project_consent.json"
    repository_storage_path: str = "~/.claude-rag/repositories.json"
    workspace_storage_path: str = "~/.claude-rag/workspaces.json"

    model_config = SettingsConfigDict(
        env_prefix="CLAUDE_RAG_",
        case_sensitive=False,
        extra="ignore"  # REF-010: Ignore deprecated config options for backward compatibility
    )

    @model_validator(mode='after')
    def migrate_legacy_flags(self) -> 'ServerConfig':
        """
        Migrate legacy flat flags to feature groups (REF-017).

        This ensures backward compatibility - old configs continue to work
        with deprecation warnings pointing users to the new structure.
        """
        # Track if any legacy flags were used
        legacy_used = False

        # Performance features migration
        if self.enable_parallel_embeddings is not None:
            self.performance.parallel_embeddings = self.enable_parallel_embeddings
            legacy_used = True
        if self.embedding_parallel_workers is not None:
            self.performance.parallel_workers = self.embedding_parallel_workers
        if self.enable_importance_scoring is not None:
            self.performance.importance_scoring = self.enable_importance_scoring
            legacy_used = True
        if self.enable_gpu is not None:
            self.performance.gpu_enabled = self.enable_gpu
            legacy_used = True
        if self.force_cpu is not None:
            self.performance.force_cpu = self.force_cpu
            legacy_used = True
        if self.gpu_memory_fraction is not None:
            self.performance.gpu_memory_fraction = self.gpu_memory_fraction

        # Search features migration
        if self.enable_hybrid_search is not None:
            self.performance.hybrid_search = self.enable_hybrid_search
            self.search.hybrid_search = self.enable_hybrid_search
            legacy_used = True
        if self.enable_retrieval_gate is not None:
            self.search.retrieval_gate_enabled = self.enable_retrieval_gate
            legacy_used = True
        if self.retrieval_gate_threshold is not None:
            self.search.retrieval_gate_threshold = self.retrieval_gate_threshold
        if self.enable_cross_project_search is not None:
            self.search.cross_project_enabled = self.enable_cross_project_search
            legacy_used = True
        if self.cross_project_default_mode is not None:
            self.search.cross_project_default_mode = self.cross_project_default_mode
        if self.enable_query_expansion is not None:
            self.search.query_expansion_enabled = self.enable_query_expansion
            legacy_used = True
        if self.query_expansion_synonyms is not None:
            self.search.query_expansion_synonyms = self.query_expansion_synonyms
        if self.query_expansion_code_context is not None:
            self.search.query_expansion_code_context = self.query_expansion_code_context
        if self.query_expansion_max_synonyms is not None:
            self.search.query_expansion_max_synonyms = self.query_expansion_max_synonyms
        if self.query_expansion_max_context_terms is not None:
            self.search.query_expansion_max_context_terms = self.query_expansion_max_context_terms

        # Analytics features migration
        if self.enable_usage_tracking is not None:
            self.analytics.usage_tracking = self.enable_usage_tracking
            legacy_used = True
        if self.enable_usage_pattern_analytics is not None:
            self.analytics.usage_pattern_analytics = self.enable_usage_pattern_analytics
            legacy_used = True
        if self.usage_analytics_retention_days is not None:
            self.analytics.usage_analytics_retention_days = self.usage_analytics_retention_days

        # Memory features migration
        if self.enable_auto_pruning is not None:
            self.memory.auto_pruning = self.enable_auto_pruning
            legacy_used = True
        if self.pruning_schedule is not None:
            self.memory.pruning_schedule = self.pruning_schedule
        if self.session_state_ttl_hours is not None:
            self.memory.session_state_ttl_hours = self.session_state_ttl_hours
        if self.enable_conversation_tracking is not None:
            self.memory.conversation_tracking = self.enable_conversation_tracking
            legacy_used = True
        if self.conversation_session_timeout_minutes is not None:
            self.memory.conversation_session_timeout_minutes = self.conversation_session_timeout_minutes
        if self.enable_proactive_suggestions is not None:
            self.memory.proactive_suggestions = self.enable_proactive_suggestions
            legacy_used = True
        if self.proactive_suggestions_threshold is not None:
            self.memory.proactive_suggestions_threshold = self.proactive_suggestions_threshold

        # Indexing features migration
        if self.enable_file_watcher is not None:
            self.indexing.file_watcher = self.enable_file_watcher
            legacy_used = True
        if self.watch_debounce_ms is not None:
            self.indexing.watch_debounce_ms = self.watch_debounce_ms
        if self.auto_index_enabled is not None:
            self.indexing.auto_index_enabled = self.auto_index_enabled
            legacy_used = True
        if self.auto_index_on_startup is not None:
            self.indexing.auto_index_on_startup = self.auto_index_on_startup
            legacy_used = True
        if self.auto_index_size_threshold is not None:
            self.indexing.auto_index_size_threshold = self.auto_index_size_threshold
        if self.auto_index_recursive is not None:
            self.indexing.auto_index_recursive = self.auto_index_recursive
            legacy_used = True
        if self.auto_index_show_progress is not None:
            self.indexing.auto_index_show_progress = self.auto_index_show_progress
            legacy_used = True
        if self.auto_index_exclude_patterns is not None:
            self.indexing.auto_index_exclude_patterns = self.auto_index_exclude_patterns
        if self.enable_git_indexing is not None:
            self.indexing.git_indexing = self.enable_git_indexing
            legacy_used = True
        if self.git_index_commit_count is not None:
            self.indexing.git_index_commit_count = self.git_index_commit_count
        if self.git_index_branches is not None:
            self.indexing.git_index_branches = self.git_index_branches
        if self.git_index_tags is not None:
            self.indexing.git_index_tags = self.git_index_tags
        if self.git_index_diffs is not None:
            self.indexing.git_index_diffs = self.git_index_diffs

        # Advanced features migration
        if self.enable_multi_repository is not None:
            self.advanced.multi_repository = self.enable_multi_repository
            legacy_used = True
        if self.multi_repo_max_parallel is not None:
            self.advanced.multi_repo_max_parallel = self.multi_repo_max_parallel
        if self.allow_rust_fallback is not None:
            self.advanced.rust_fallback = self.allow_rust_fallback
            legacy_used = True
        if self.warn_on_degradation is not None:
            self.advanced.warn_on_degradation = self.warn_on_degradation
            legacy_used = True
        if self.read_only_mode is not None:
            self.advanced.read_only_mode = self.read_only_mode
            legacy_used = True
        if self.enable_input_validation is not None:
            self.advanced.input_validation = self.enable_input_validation
            legacy_used = True

        # Log deprecation warning if legacy flags were used
        if legacy_used:
            logger.warning(
                "DEPRECATION WARNING: Legacy flat feature flags are deprecated and will be removed in v5.0.0. "
                "Please migrate to feature groups (e.g., use 'performance.parallel_embeddings' instead of 'enable_parallel_embeddings'). "
                "See documentation for migration guide."
            )

        return self

    @model_validator(mode='after')
    def apply_feature_level_preset(self) -> 'ServerConfig':
        """
        Apply feature level presets (BASIC, ADVANCED, EXPERIMENTAL) (REF-017).

        This allows users to configure all features with a single setting.
        """
        if self.feature_level == FeatureLevel.BASIC:
            # Disable experimental/advanced features for stable production use
            self.memory.proactive_suggestions = False
            self.indexing.git_index_diffs = False
            self.advanced.multi_repository = False
            logger.info("Applied BASIC feature level preset - production-ready features only")

        elif self.feature_level == FeatureLevel.ADVANCED:
            # Enable all stable features including power-user features
            self.memory.proactive_suggestions = True
            self.indexing.git_indexing = True
            self.analytics.usage_pattern_analytics = True
            logger.info("Applied ADVANCED feature level preset - all stable features enabled")

        elif self.feature_level == FeatureLevel.EXPERIMENTAL:
            # Enable everything (bleeding edge)
            logger.warning("Applied EXPERIMENTAL feature level - all features enabled including unstable ones")

        return self

    @model_validator(mode='after')
    def validate_ranking_weights(self) -> 'ServerConfig':
        """Validate ranking weights sum to 1.0 and are non-negative (UX-051)."""
        weights = {
            'ranking_weight_similarity': self.ranking_weight_similarity,
            'ranking_weight_recency': self.ranking_weight_recency,
            'ranking_weight_usage': self.ranking_weight_usage,
        }

        # Check non-negative
        negative = {k: v for k, v in weights.items() if v < 0}
        if negative:
            raise ValueError(
                f"Ranking weights cannot be negative: {negative}. "
                f"All weights must be >= 0.0."
            )

        # Check sum with tight tolerance (±0.01 as per task requirements)
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            raise ValueError(
                f"Ranking weights must sum to 1.0 (got {weight_sum:.3f}).\n"
                f"Current values:\n"
                f"  - similarity: {self.ranking_weight_similarity}\n"
                f"  - recency: {self.ranking_weight_recency}\n"
                f"  - usage: {self.ranking_weight_usage}\n"
                f"Suggestion: Adjust weights proportionally to sum to 1.0"
            )

        return self

    @model_validator(mode='after')
    def validate_feature_dependencies(self) -> 'ServerConfig':
        """Validate that dependent configuration options are consistent (UX-051)."""
        issues = []

        # Hybrid search dependencies
        if not self.search.hybrid_search and self.hybrid_search_alpha != 0.5:
            issues.append(
                f"hybrid_search_alpha is set to {self.hybrid_search_alpha} but "
                f"search.hybrid_search=False. Either enable hybrid search or use "
                f"the default alpha value (0.5)."
            )

        # Importance scoring dependencies
        if not self.performance.importance_scoring:
            if (self.importance_complexity_weight != 1.0 or
                self.importance_usage_weight != 1.0 or
                self.importance_criticality_weight != 1.0):
                issues.append(
                    "Importance weights are customized "
                    f"(complexity={self.importance_complexity_weight}, "
                    f"usage={self.importance_usage_weight}, "
                    f"criticality={self.importance_criticality_weight}) but "
                    f"performance.importance_scoring=False. "
                    f"Either enable importance scoring or use default weights (1.0)."
                )

        # Query expansion dependencies (only check numeric settings, not boolean flags)
        if not self.search.query_expansion_enabled:
            if (self.search.query_expansion_max_synonyms != 2 or
                self.search.query_expansion_max_context_terms != 3):
                issues.append(
                    "Query expansion options are customized but "
                    "search.query_expansion_enabled=False. "
                    "Either enable query expansion or use default settings."
                )

        # Retrieval gate dependencies
        if not self.search.retrieval_gate_enabled and self.search.retrieval_gate_threshold != 0.8:
            issues.append(
                f"retrieval_gate_threshold is set to {self.search.retrieval_gate_threshold} "
                f"but search.retrieval_gate_enabled=False. "
                f"Either enable retrieval gate or use the default threshold (0.8)."
            )

        if issues:
            raise ValueError(
                "Configuration has inconsistent feature dependencies:\n" +
                "\n".join(f"  - {issue}" for issue in issues)
            )

        return self

    @model_validator(mode='after')
    def validate_config(self) -> 'ServerConfig':
        """Validate configuration consistency and constraints."""

        # Validate embedding batch size
        if self.embedding_batch_size < 1:
            raise ValueError("embedding_batch_size must be >= 1")
        if self.embedding_batch_size > 256:
            raise ValueError("embedding_batch_size must not exceed 256 (memory constraint)")

        # Validate Qdrant URL format
        if self.storage_backend == "qdrant":
            if not self.qdrant_url.startswith(("http://", "https://")):
                raise ValueError("qdrant_url must start with http:// or https://")

        # Validate cache TTL
        if self.embedding_cache_ttl_days < 1:
            raise ValueError("embedding_cache_ttl_days must be >= 1")
        if self.embedding_cache_ttl_days > 3650:
            raise ValueError("embedding_cache_ttl_days should not exceed 10 years (3650 days)")

        # Validate memory size limit
        if self.max_memory_size_bytes < 1024:  # At least 1KB
            raise ValueError("max_memory_size_bytes must be at least 1024 (1KB)")

        # Validate timeouts
        if self.retrieval_timeout_ms < 100:
            raise ValueError("retrieval_timeout_ms should be at least 100ms")
        if self.retrieval_timeout_ms > 30000:
            raise ValueError("retrieval_timeout_ms should not exceed 30 seconds")

        # Validate pruning configuration (use feature group values)
        if self.memory.session_state_ttl_hours < 1:
            raise ValueError("session_state_ttl_hours must be at least 1 hour")
        if self.memory.session_state_ttl_hours > 720:  # 30 days
            raise ValueError("session_state_ttl_hours should not exceed 720 (30 days)")

        if self.usage_batch_size < 1:
            raise ValueError("usage_batch_size must be at least 1")
        if self.usage_batch_size > 10000:
            raise ValueError("usage_batch_size should not exceed 10000")

        if self.usage_flush_interval_seconds < 1:
            raise ValueError("usage_flush_interval_seconds must be at least 1 second")

        if self.recency_decay_halflife_days <= 0:
            raise ValueError("recency_decay_halflife_days must be positive")

        # Validate probability thresholds (UX-051)
        if not 0.0 <= self.search.retrieval_gate_threshold <= 1.0:
            raise ValueError(
                f"search.retrieval_gate_threshold must be between 0.0 and 1.0 "
                f"(got {self.search.retrieval_gate_threshold}). "
                f"This represents a similarity threshold."
            )

        if not 0.0 <= self.hybrid_search_alpha <= 1.0:
            raise ValueError(
                f"hybrid_search_alpha must be between 0.0 and 1.0 "
                f"(got {self.hybrid_search_alpha}). "
                f"This represents the balance between BM25 and vector search."
            )

        if not 0.0 <= self.memory.proactive_suggestions_threshold <= 1.0:
            raise ValueError(
                f"memory.proactive_suggestions_threshold must be between 0.0 and 1.0 "
                f"(got {self.memory.proactive_suggestions_threshold}). "
                f"This represents a confidence threshold."
            )

        if not 0.0 <= self.query_expansion_similarity_threshold <= 1.0:
            raise ValueError(
                f"query_expansion_similarity_threshold must be between 0.0 and 1.0 "
                f"(got {self.query_expansion_similarity_threshold}). "
                f"This represents a similarity threshold."
            )

        # Validate conversation tracking settings
        if self.memory.conversation_session_timeout_minutes < 1:
            raise ValueError("conversation_session_timeout_minutes must be at least 1")
        if self.memory.conversation_session_timeout_minutes > 1440:  # 24 hours
            raise ValueError("conversation_session_timeout_minutes should not exceed 1440 (24 hours)")

        if self.conversation_query_history_size < 1:
            raise ValueError("conversation_query_history_size must be at least 1")
        if self.conversation_query_history_size > 50:
            raise ValueError("conversation_query_history_size should not exceed 50")

        if self.deduplication_fetch_multiplier < 1:
            raise ValueError("deduplication_fetch_multiplier must be at least 1")
        if self.deduplication_fetch_multiplier > 10:
            raise ValueError("deduplication_fetch_multiplier should not exceed 10")

        # Validate git indexing settings
        if self.indexing.git_index_commit_count < 1:
            raise ValueError("git_index_commit_count must be at least 1")
        if self.indexing.git_index_commit_count > 100000:
            raise ValueError("git_index_commit_count should not exceed 100000")

        if self.indexing.git_index_branches not in ["current", "all"]:
            raise ValueError("git_index_branches must be 'current' or 'all'")

        if self.git_auto_size_threshold_mb < 1:
            raise ValueError("git_auto_size_threshold_mb must be at least 1")

        if self.git_diff_size_limit_kb < 1:
            raise ValueError("git_diff_size_limit_kb must be at least 1")

        # Validate importance scoring weights (FEAT-049)
        if not 0.0 <= self.importance_complexity_weight <= 2.0:
            raise ValueError("importance_complexity_weight must be between 0.0 and 2.0")
        if not 0.0 <= self.importance_usage_weight <= 2.0:
            raise ValueError("importance_usage_weight must be between 0.0 and 2.0")
        if not 0.0 <= self.importance_criticality_weight <= 2.0:
            raise ValueError("importance_criticality_weight must be between 0.0 and 2.0")

        # Validate GPU settings (PERF-002) - use feature group values
        if not 0.0 <= self.performance.gpu_memory_fraction <= 1.0:
            raise ValueError("gpu_memory_fraction must be between 0.0 and 1.0")

        # Validate auto-indexing settings - use feature group values
        if self.indexing.auto_index_size_threshold < 1:
            raise ValueError("auto_index_size_threshold must be at least 1")
        if self.indexing.auto_index_size_threshold > 100000:
            raise ValueError("auto_index_size_threshold should not exceed 100000")

        return self

    def get_expanded_path(self, path: str) -> Path:
        """Expand ~ and environment variables in path."""
        return Path(os.path.expanduser(os.path.expandvars(path)))

    @property
    def embedding_cache_path_expanded(self) -> Path:
        """Get expanded embedding cache path."""
        path = self.get_expanded_path(self.embedding_cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def sqlite_path_expanded(self) -> Path:
        """Get expanded SQLite metadata database path."""
        path = self.get_expanded_path(self.sqlite_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


# Global config instance
_config: Optional[ServerConfig] = None

# User config file location
_USER_CONFIG_PATH = Path.home() / ".claude-rag" / "config.json"


def _load_user_config_overrides() -> dict:
    """
    Load user configuration overrides from ~/.claude-rag/config.json.

    This allows persistent configuration that survives across all projects
    and working directories, unlike .env files which are project-specific.

    Returns:
        Dict of config overrides, or empty dict if no config file exists
    """
    if not _USER_CONFIG_PATH.exists():
        return {}

    try:
        with open(_USER_CONFIG_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        import logging
        logging.warning(f"Failed to load user config from {_USER_CONFIG_PATH}: {e}")
        return {}


def get_config() -> ServerConfig:
    """
    Get or create global configuration instance.

    Configuration priority (highest to lowest):
    1. Environment variables (CLAUDE_RAG_*)
    2. User config file (~/.claude-rag/config.json)
    3. Built-in defaults
    """
    global _config
    if _config is None:
        # Load user config overrides
        user_overrides = _load_user_config_overrides()

        # Create config with overrides applied
        # Pydantic will merge: env vars > init kwargs > defaults
        _config = ServerConfig(**user_overrides)
    return _config


def set_config(config: ServerConfig) -> None:
    """Set global configuration instance (mainly for testing)."""
    global _config
    _config = config
