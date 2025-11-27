"""Tests for GPU configuration."""

import pytest
from pydantic import ValidationError

from src.config import ServerConfig


class TestGpuConfig:
    """Test GPU configuration settings."""

    def test_default_gpu_settings(self):
        """Test default GPU configuration values."""
        config = ServerConfig()

        assert config.performance.gpu_enabled is True
        assert config.performance.force_cpu is False
        assert config.performance.gpu_memory_fraction == 0.8

    def test_gpu_memory_fraction_valid(self):
        """Test valid GPU memory fraction values."""
        # Test minimum value
        config = ServerConfig(performance={"gpu_memory_fraction": 0.0})
        assert config.performance.gpu_memory_fraction == 0.0

        # Test maximum value
        config = ServerConfig(performance={"gpu_memory_fraction": 1.0})
        assert config.performance.gpu_memory_fraction == 1.0

        # Test middle value
        config = ServerConfig(performance={"gpu_memory_fraction": 0.5})
        assert config.performance.gpu_memory_fraction == 0.5

    def test_gpu_memory_fraction_invalid_low(self):
        """Test GPU memory fraction below valid range."""
        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(performance={"gpu_memory_fraction": -0.1})

        assert "gpu_memory_fraction must be between 0.0 and 1.0" in str(exc_info.value)

    def test_gpu_memory_fraction_invalid_high(self):
        """Test GPU memory fraction above valid range."""
        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(performance={"gpu_memory_fraction": 1.5})

        assert "gpu_memory_fraction must be between 0.0 and 1.0" in str(exc_info.value)

    def test_enable_gpu_toggle(self):
        """Test enabling/disabling GPU."""
        # GPU enabled
        config = ServerConfig(performance={"gpu_enabled": True})
        assert config.performance.gpu_enabled is True

        # GPU disabled
        config = ServerConfig(performance={"gpu_enabled": False})
        assert config.performance.gpu_enabled is False

    def test_force_cpu_toggle(self):
        """Test forcing CPU mode."""
        # Force CPU enabled (must disable gpu_enabled to avoid mutual exclusion)
        config = ServerConfig(performance={"force_cpu": True, "gpu_enabled": False})
        assert config.performance.force_cpu is True

        # Force CPU disabled
        config = ServerConfig(performance={"force_cpu": False})
        assert config.performance.force_cpu is False
