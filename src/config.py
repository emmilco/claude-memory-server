"""Configuration management for Claude Memory RAG Server."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Literal
from pathlib import Path
import os


class ServerConfig(BaseSettings):
    """Server configuration with environment variable support."""

    # Core settings
    server_name: str = "claude-memory-rag"
    log_level: str = "INFO"

    # Storage backend selection
    storage_backend: Literal["sqlite", "qdrant"] = "qdrant"
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

    model_config = SettingsConfigDict(
        env_prefix="CLAUDE_RAG_",
        env_file=".env",
        env_file_encoding='utf-8',
        case_sensitive=False
    )

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
