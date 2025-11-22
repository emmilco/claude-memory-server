"""Configuration management for Claude Memory RAG Server."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Optional, Literal
from pathlib import Path
import os
import json


class ServerConfig(BaseSettings):
    """Server configuration with environment variable support."""

    # Core settings
    server_name: str = "claude-memory-rag"
    log_level: str = "INFO"

    # Storage backend (Qdrant required for semantic code search)
    storage_backend: Literal["qdrant"] = "qdrant"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection_name: str = "memory"

    # Performance tuning
    embedding_batch_size: int = 32
    max_query_context_tokens: int = 8000
    retrieval_timeout_ms: int = 500

    # Retrieval gate (stub implementation for test compatibility)
    enable_retrieval_gate: bool = False
    retrieval_gate_threshold: float = 0.5

    # Embedding settings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_cache_enabled: bool = True
    embedding_cache_path: str = "~/.claude-rag/embedding_cache.db"
    embedding_cache_ttl_days: int = 30

    # SQLite for metadata tracking (not for vector storage - Qdrant only)
    sqlite_path: str = "~/.claude-rag/metadata.db"  # For ProjectIndexTracker metadata

    # Parallel embedding generation (PERF-001)
    enable_parallel_embeddings: bool = True  # Use multiprocessing for embeddings
    embedding_parallel_workers: Optional[int] = None  # Auto-detect CPU count if None

    # Security
    read_only_mode: bool = False
    enable_input_validation: bool = True
    max_memory_size_bytes: int = 10240  # 10KB

    # Code indexing
    enable_file_watcher: bool = True
    watch_debounce_ms: int = 1000

    # Importance scoring (FEAT-049)
    enable_importance_scoring: bool = True  # Enable intelligent importance scoring for code units
    importance_complexity_weight: float = 1.0  # Weight for complexity factors (0.0-2.0)
    importance_usage_weight: float = 1.0  # Weight for usage/centrality factors (0.0-2.0)
    importance_criticality_weight: float = 1.0  # Weight for keyword/pattern factors (0.0-2.0)

    # Graceful degradation (UX-012)
    # NOTE: allow_qdrant_fallback removed in REF-010 - Qdrant is now required
    allow_rust_fallback: bool = True  # Fall back to Python parser if Rust unavailable
    warn_on_degradation: bool = True  # Show warnings when running in degraded mode

    # Memory pruning and ranking
    session_state_ttl_hours: int = 48
    enable_auto_pruning: bool = True
    pruning_schedule: str = "0 2 * * *"  # Cron format: 2 AM daily
    enable_usage_tracking: bool = True
    usage_batch_size: int = 100
    usage_flush_interval_seconds: int = 60

    # Ranking weights (must sum to 1.0)
    ranking_weight_similarity: float = 0.6
    ranking_weight_recency: float = 0.2
    ranking_weight_usage: float = 0.2

    # Decay parameters
    recency_decay_halflife_days: float = 7.0  # Half-life for recency decay

    # Conversation tracking
    enable_conversation_tracking: bool = True
    conversation_session_timeout_minutes: int = 30
    conversation_query_history_size: int = 5
    query_expansion_similarity_threshold: float = 0.7
    deduplication_fetch_multiplier: int = 3

    # Query expansion (FEAT-024)
    enable_query_expansion: bool = True
    query_expansion_synonyms: bool = True  # Programming term synonyms
    query_expansion_code_context: bool = True  # Code domain patterns
    query_expansion_max_synonyms: int = 2  # Max synonyms per term
    query_expansion_max_context_terms: int = 3  # Max context terms

    # Git history indexing
    enable_git_indexing: bool = True
    git_index_commit_count: int = 1000
    git_index_branches: str = "current"  # current|all
    git_index_tags: bool = True
    git_index_diffs: bool = True  # Auto-disabled for large repos
    git_auto_size_threshold_mb: int = 500
    git_diff_size_limit_kb: int = 10  # Skip diffs larger than this

    # Hybrid search (BM25 + Vector)
    enable_hybrid_search: bool = True
    hybrid_search_alpha: float = 0.5  # Weight: 0=keyword only, 1=semantic only
    hybrid_fusion_method: str = "weighted"  # "weighted", "rrf", or "cascade"
    bm25_k1: float = 1.5  # Term saturation parameter
    bm25_b: float = 0.75  # Length normalization parameter

    # Cross-project learning (FEAT-030)
    enable_cross_project_search: bool = True  # Allow searching across projects
    cross_project_default_mode: str = "current"  # "current" or "all"
    cross_project_opt_in_file: str = "~/.claude-rag/cross_project_consent.json"

    # Multi-repository support (FEAT-017)
    enable_multi_repository: bool = True  # Enable multi-repository features
    multi_repo_max_parallel: int = 3  # Max concurrent repository operations
    repository_storage_path: str = "~/.claude-rag/repositories.json"
    workspace_storage_path: str = "~/.claude-rag/workspaces.json"

    # Proactive context suggestions (FEAT-028)
    enable_proactive_suggestions: bool = True  # Analyze messages for patterns
    proactive_suggestions_threshold: float = 0.90  # Confidence threshold for auto-injection

    model_config = SettingsConfigDict(
        env_prefix="CLAUDE_RAG_",
        case_sensitive=False,
        extra="ignore"  # REF-010: Ignore deprecated config options like allow_qdrant_fallback for backward compatibility
    )

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

        # Validate pruning configuration
        if self.session_state_ttl_hours < 1:
            raise ValueError("session_state_ttl_hours must be at least 1 hour")
        if self.session_state_ttl_hours > 720:  # 30 days
            raise ValueError("session_state_ttl_hours should not exceed 720 (30 days)")

        if self.usage_batch_size < 1:
            raise ValueError("usage_batch_size must be at least 1")
        if self.usage_batch_size > 10000:
            raise ValueError("usage_batch_size should not exceed 10000")

        if self.usage_flush_interval_seconds < 1:
            raise ValueError("usage_flush_interval_seconds must be at least 1 second")

        # Validate ranking weights sum to 1.0
        weight_sum = (
            self.ranking_weight_similarity +
            self.ranking_weight_recency +
            self.ranking_weight_usage
        )
        if not (0.99 <= weight_sum <= 1.01):  # Allow small floating point error
            raise ValueError(
                f"Ranking weights must sum to 1.0 (got {weight_sum}). "
                f"Adjust ranking_weight_similarity, ranking_weight_recency, and ranking_weight_usage."
            )

        if self.recency_decay_halflife_days <= 0:
            raise ValueError("recency_decay_halflife_days must be positive")

        # Validate conversation tracking settings
        if self.conversation_session_timeout_minutes < 1:
            raise ValueError("conversation_session_timeout_minutes must be at least 1")
        if self.conversation_session_timeout_minutes > 1440:  # 24 hours
            raise ValueError("conversation_session_timeout_minutes should not exceed 1440 (24 hours)")

        if self.conversation_query_history_size < 1:
            raise ValueError("conversation_query_history_size must be at least 1")
        if self.conversation_query_history_size > 50:
            raise ValueError("conversation_query_history_size should not exceed 50")

        if not 0.0 <= self.query_expansion_similarity_threshold <= 1.0:
            raise ValueError("query_expansion_similarity_threshold must be between 0.0 and 1.0")

        if self.deduplication_fetch_multiplier < 1:
            raise ValueError("deduplication_fetch_multiplier must be at least 1")
        if self.deduplication_fetch_multiplier > 10:
            raise ValueError("deduplication_fetch_multiplier should not exceed 10")

        # Validate git indexing settings
        if self.git_index_commit_count < 1:
            raise ValueError("git_index_commit_count must be at least 1")
        if self.git_index_commit_count > 100000:
            raise ValueError("git_index_commit_count should not exceed 100000")

        if self.git_index_branches not in ["current", "all"]:
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
