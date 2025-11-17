"""Configuration management for Claude Memory RAG Server."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Optional, Literal
from pathlib import Path
import os


class ServerConfig(BaseSettings):
    """Server configuration with environment variable support."""

    # Core settings
    server_name: str = "claude-memory-rag"
    log_level: str = "INFO"

    # Storage backend selection (SQLite is default for easier setup, upgrade to Qdrant for production)
    storage_backend: Literal["sqlite", "qdrant"] = "sqlite"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection_name: str = "memory"
    sqlite_path: str = "~/.claude-rag/memory.db"

    # Performance tuning
    embedding_batch_size: int = 32
    max_query_context_tokens: int = 8000
    retrieval_timeout_ms: int = 500

    # Embedding settings
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_cache_enabled: bool = True
    embedding_cache_path: str = "~/.claude-rag/embedding_cache.db"
    embedding_cache_ttl_days: int = 30

    # Security
    read_only_mode: bool = False
    enable_input_validation: bool = True
    max_memory_size_bytes: int = 10240  # 10KB

    # Code indexing
    enable_file_watcher: bool = True
    watch_debounce_ms: int = 1000

    # Adaptive retrieval
    enable_retrieval_gate: bool = True
    retrieval_gate_threshold: float = 0.8

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

    model_config = SettingsConfigDict(
        env_prefix="CLAUDE_RAG_",
        env_file=".env",
        env_file_encoding='utf-8',
        case_sensitive=False
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
        
        # Validate retrieval gate threshold
        if not 0.0 <= self.retrieval_gate_threshold <= 1.0:
            raise ValueError("retrieval_gate_threshold must be between 0.0 and 1.0")
        
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

        return self

    def get_expanded_path(self, path: str) -> Path:
        """Expand ~ and environment variables in path."""
        return Path(os.path.expanduser(os.path.expandvars(path)))

    @property
    def sqlite_path_expanded(self) -> Path:
        """Get expanded SQLite path."""
        path = self.get_expanded_path(self.sqlite_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def embedding_cache_path_expanded(self) -> Path:
        """Get expanded embedding cache path."""
        path = self.get_expanded_path(self.embedding_cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path


# Global config instance
_config: Optional[ServerConfig] = None


def get_config() -> ServerConfig:
    """Get or create global configuration instance."""
    global _config
    if _config is None:
        _config = ServerConfig()
    return _config


def set_config(config: ServerConfig) -> None:
    """Set global configuration instance (mainly for testing)."""
    global _config
    _config = config
