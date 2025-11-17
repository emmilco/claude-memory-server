"""Unit tests for configuration module."""

import pytest
import os
from pathlib import Path
from src.config import ServerConfig, get_config, set_config


def test_config_defaults():
    """Test that configuration loads with default values."""
    config = ServerConfig()
    assert config.server_name == "claude-memory-rag"
    assert config.log_level == "INFO"
    assert config.storage_backend == "sqlite"  # Default is SQLite for easier setup
    assert config.qdrant_url == "http://localhost:6333"
    assert config.embedding_batch_size == 32
    assert config.read_only_mode is False


def test_config_from_env(monkeypatch):
    """Test that configuration loads from environment variables."""
    monkeypatch.setenv("CLAUDE_RAG_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("CLAUDE_RAG_READ_ONLY_MODE", "true")
    monkeypatch.setenv("CLAUDE_RAG_QDRANT_URL", "http://custom:6333")

    config = ServerConfig()
    assert config.log_level == "DEBUG"
    assert config.read_only_mode is True
    assert config.qdrant_url == "http://custom:6333"


def test_config_storage_backend_validation():
    """Test that storage backend only accepts valid values."""
    # Valid backends
    config1 = ServerConfig(storage_backend="qdrant")
    assert config1.storage_backend == "qdrant"

    config2 = ServerConfig(storage_backend="sqlite")
    assert config2.storage_backend == "sqlite"

    # Invalid backend should raise validation error
    with pytest.raises(Exception):  # Pydantic validation error
        ServerConfig(storage_backend="invalid")


def test_path_expansion():
    """Test that paths are expanded correctly."""
    config = ServerConfig(sqlite_path="~/.claude-rag/test.db")
    expanded = config.sqlite_path_expanded
    assert isinstance(expanded, Path)
    assert "~" not in str(expanded)


def test_global_config():
    """Test global configuration singleton."""
    config1 = get_config()
    config2 = get_config()
    assert config1 is config2

    # Test setting custom config
    custom_config = ServerConfig(server_name="custom-server")
    set_config(custom_config)
    assert get_config().server_name == "custom-server"


def test_embedding_cache_settings():
    """Test embedding cache configuration."""
    config = ServerConfig()
    assert config.embedding_cache_enabled is True
    assert config.embedding_cache_ttl_days == 30
    assert "embedding_cache.db" in config.embedding_cache_path


def test_security_settings():
    """Test security-related configuration."""
    config = ServerConfig()
    assert config.enable_input_validation is True
    assert config.max_memory_size_bytes == 10240


def test_retrieval_gate_settings():
    """Test adaptive retrieval configuration."""
    config = ServerConfig()
    assert config.enable_retrieval_gate is True
    assert config.retrieval_gate_threshold == 0.8
