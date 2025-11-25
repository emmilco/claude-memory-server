"""Tests for GPU configuration."""

import pytest
from pydantic import ValidationError

from src.config import ServerConfig


class TestGpuConfig:
    """Test GPU configuration settings."""

    def test_default_gpu_settings(self):
        """Test default GPU configuration values.

        Note: Uses nested config structure (config.performance.*) since flat
        attributes are deprecated Optional[X] = None for backward compatibility.
        """
        config = ServerConfig()

        # Use nested config structure (flat attrs are Optional[None] for backward compat)
        assert config.performance.gpu_enabled is True
        assert config.performance.force_cpu is False
        assert config.performance.gpu_memory_fraction == 0.8

    def test_gpu_memory_fraction_valid(self):
        """Test valid GPU memory fraction values."""
        # Test minimum value
        config = ServerConfig(gpu_memory_fraction=0.0)
        assert config.gpu_memory_fraction == 0.0

        # Test maximum value
        config = ServerConfig(gpu_memory_fraction=1.0)
        assert config.gpu_memory_fraction == 1.0

        # Test middle value
        config = ServerConfig(gpu_memory_fraction=0.5)
        assert config.gpu_memory_fraction == 0.5

    def test_gpu_memory_fraction_invalid_low(self):
        """Test GPU memory fraction below valid range."""
        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(gpu_memory_fraction=-0.1)

        assert "gpu_memory_fraction must be between 0.0 and 1.0" in str(exc_info.value)

    def test_gpu_memory_fraction_invalid_high(self):
        """Test GPU memory fraction above valid range."""
        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(gpu_memory_fraction=1.5)

        assert "gpu_memory_fraction must be between 0.0 and 1.0" in str(exc_info.value)

    def test_enable_gpu_toggle(self):
        """Test enabling/disabling GPU."""
        # GPU enabled
        config = ServerConfig(enable_gpu=True)
        assert config.enable_gpu is True

        # GPU disabled
        config = ServerConfig(enable_gpu=False)
        assert config.enable_gpu is False

    def test_force_cpu_toggle(self):
        """Test forcing CPU mode."""
        # Force CPU enabled
        config = ServerConfig(force_cpu=True)
        assert config.force_cpu is True

        # Force CPU disabled
        config = ServerConfig(force_cpu=False)
        assert config.force_cpu is False

    def test_gpu_config_from_env(self, monkeypatch):
        """Test loading GPU config from environment variables."""
        monkeypatch.setenv("CLAUDE_RAG_ENABLE_GPU", "false")
        monkeypatch.setenv("CLAUDE_RAG_FORCE_CPU", "true")
        monkeypatch.setenv("CLAUDE_RAG_GPU_MEMORY_FRACTION", "0.6")

        config = ServerConfig()

        assert config.enable_gpu is False
        assert config.force_cpu is True
        assert config.gpu_memory_fraction == 0.6
