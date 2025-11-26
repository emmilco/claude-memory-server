"""Tests for embedding generator GPU support."""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from src.embeddings.generator import EmbeddingGenerator
from src.config import ServerConfig


class TestGeneratorGpuSupport:
    """Test GPU support in embedding generator."""

    def test_device_determination_gpu_enabled_available(self):
        """Test device determination when GPU is enabled and available."""
        config = ServerConfig(enable_gpu=True, force_cpu=False)

        with patch("src.embeddings.generator.get_optimal_device", return_value="cuda"), \
             patch("src.embeddings.generator.get_gpu_info", return_value={
                 "device_name": "NVIDIA GeForce RTX 3080",
                 "total_memory_gb": 10.0,
                 "cuda_version": "11.8"
             }):

            generator = EmbeddingGenerator(config)

            assert generator.device == "cuda"

    def test_device_determination_force_cpu(self):
        """Test device determination when CPU is forced."""
        config = ServerConfig(enable_gpu=True, force_cpu=True)

        with patch("src.embeddings.generator.get_optimal_device") as mock_device:
            generator = EmbeddingGenerator(config)

            assert generator.device == "cpu"
            # Should not call get_optimal_device if force_cpu is True
            mock_device.assert_not_called()

    def test_device_determination_gpu_disabled(self):
        """Test device determination when GPU is disabled."""
        config = ServerConfig(enable_gpu=False, force_cpu=False)

        with patch("src.embeddings.generator.get_optimal_device") as mock_device:
            generator = EmbeddingGenerator(config)

            assert generator.device == "cpu"
            # Should not call get_optimal_device if enable_gpu is False
            mock_device.assert_not_called()

    def test_device_determination_gpu_unavailable(self):
        """Test device determination when GPU is not available."""
        config = ServerConfig(enable_gpu=True, force_cpu=False)

        with patch("src.embeddings.generator.get_optimal_device", return_value="cpu"), \
             patch("src.embeddings.generator.get_gpu_info", return_value=None):

            generator = EmbeddingGenerator(config)

            assert generator.device == "cpu"

    def test_model_load_with_gpu(self):
        """Test model loading with GPU device."""
        config = ServerConfig(enable_gpu=True, force_cpu=False, gpu_memory_fraction=0.7)

        mock_model = Mock()
        mock_model.to = Mock(return_value=mock_model)

        mock_torch = MagicMock()

        with patch("src.embeddings.generator.get_optimal_device", return_value="cuda"), \
             patch("src.embeddings.generator.get_gpu_info", return_value={
                 "device_name": "NVIDIA GPU", "total_memory_gb": 8.0, "cuda_version": "11.8"
             }), \
             patch("src.embeddings.generator.SentenceTransformer", return_value=mock_model), \
             patch.dict("sys.modules", {"torch": mock_torch}):

            generator = EmbeddingGenerator(config)
            model = generator._load_model()

            # Verify model was moved to CUDA
            mock_model.to.assert_called_with("cuda")

            # Verify GPU memory fraction was set
            mock_torch.cuda.set_per_process_memory_fraction.assert_called_once_with(0.7, 0)

            # BEHAVIORAL ASSERTIONS: Verify generator state reflects GPU configuration
            assert generator.device == "cuda", "Generator device should be set to cuda"
            assert generator.model is not None, "Model should be initialized"
            assert generator.model == mock_model, "Model should be the loaded SentenceTransformer"

    def test_model_load_with_cpu(self):
        """Test model loading with CPU device."""
        config = ServerConfig(enable_gpu=False, force_cpu=True)

        mock_model = Mock()
        mock_model.to = Mock(return_value=mock_model)

        with patch("src.embeddings.generator.get_optimal_device", return_value="cpu"), \
             patch("src.embeddings.generator.SentenceTransformer", return_value=mock_model):

            generator = EmbeddingGenerator(config)
            model = generator._load_model()

            # Verify model was moved to CPU
            mock_model.to.assert_called_with("cpu")

            # BEHAVIORAL ASSERTIONS: Verify generator state reflects CPU configuration
            assert generator.device == "cpu", "Generator device should be set to cpu"
            assert generator.model is not None, "Model should be initialized"
            assert generator.model == mock_model, "Model should be the loaded SentenceTransformer"

    def test_model_load_gpu_fallback_to_cpu(self):
        """Test fallback to CPU when GPU loading fails."""
        config = ServerConfig(enable_gpu=True, force_cpu=False)

        mock_model = Mock()
        # First call to .to("cuda") fails, second call to .to("cpu") succeeds
        mock_model.to = Mock(side_effect=[RuntimeError("CUDA error"), mock_model])

        with patch("src.embeddings.generator.get_optimal_device", return_value="cuda"), \
             patch("src.embeddings.generator.get_gpu_info", return_value={
                 "device_name": "NVIDIA GPU", "total_memory_gb": 8.0, "cuda_version": "11.8"
             }), \
             patch("src.embeddings.generator.SentenceTransformer", return_value=mock_model):

            generator = EmbeddingGenerator(config)

            # Initially, device should be cuda (determined before model load)
            assert generator.device == "cuda", "Device should initially be cuda before fallback"

            model = generator._load_model()

            # Verify it tried CUDA first, then fell back to CPU
            assert mock_model.to.call_count == 2
            mock_model.to.assert_any_call("cuda")
            mock_model.to.assert_called_with("cpu")  # Final call should be CPU

            # BEHAVIORAL ASSERTIONS: Verify generator state reflects CPU fallback
            assert generator.device == "cpu", "Generator device should fall back to cpu after GPU error"
            assert generator.model is not None, "Model should be initialized despite GPU error"
            assert generator.model == mock_model, "Model should be the loaded SentenceTransformer"

    @pytest.mark.requires_gpu
    def test_benchmark_includes_device(self):
        """Test that benchmark results include device information."""
        config = ServerConfig(enable_gpu=True, force_cpu=False)

        mock_model = Mock()
        mock_model.to = Mock(return_value=mock_model)
        mock_model.encode = Mock(return_value=MagicMock())

        mock_torch = MagicMock()

        with patch("src.embeddings.generator.get_optimal_device", return_value="cuda"), \
             patch("src.embeddings.generator.get_gpu_info", return_value={
                 "device_name": "NVIDIA GPU", "total_memory_gb": 8.0, "cuda_version": "11.8"
             }), \
             patch("src.embeddings.generator.SentenceTransformer", return_value=mock_model), \
             patch.dict("sys.modules", {"torch": mock_torch}), \
             patch("src.embeddings.generator.RustBridge.batch_normalize") as mock_normalize:

            # Setup normalize to return proper format
            mock_normalize.return_value = [[0.1] * 384]

            generator = EmbeddingGenerator(config)

            # Run benchmark
            import asyncio
            result = asyncio.run(generator.benchmark(num_texts=5))

            assert "device" in result
            assert result["device"] == "cuda"

    def test_gpu_memory_fraction_not_set_when_full(self):
        """Test that GPU memory fraction is not set when it's 1.0."""
        config = ServerConfig(enable_gpu=True, force_cpu=False, gpu_memory_fraction=1.0)

        mock_model = Mock()
        mock_model.to = Mock(return_value=mock_model)

        mock_torch = MagicMock()

        with patch("src.embeddings.generator.get_optimal_device", return_value="cuda"), \
             patch("src.embeddings.generator.get_gpu_info", return_value={
                 "device_name": "NVIDIA GPU", "total_memory_gb": 8.0, "cuda_version": "11.8"
             }), \
             patch("src.embeddings.generator.SentenceTransformer", return_value=mock_model), \
             patch.dict("sys.modules", {"torch": mock_torch}):

            generator = EmbeddingGenerator(config)
            model = generator._load_model()

            # Verify GPU memory fraction was NOT set (since it's 1.0)
            mock_torch.cuda.set_per_process_memory_fraction.assert_not_called()
