"""Tests for GPU detection utilities."""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.embeddings.gpu_utils import detect_cuda, get_gpu_info, get_optimal_device


class TestDetectCuda:
    """Test CUDA detection."""

    def test_cuda_available(self):
        """Test when CUDA is available."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = True

        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = detect_cuda()

            assert result is True
            mock_torch.cuda.is_available.assert_called_once()

    def test_cuda_unavailable(self):
        """Test when CUDA is not available."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.return_value = False

        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = detect_cuda()

            assert result is False
            mock_torch.cuda.is_available.assert_called_once()

    def test_pytorch_not_installed(self):
        """Test when PyTorch is not installed."""
        # Temporarily remove torch from sys.modules
        import sys
        torch_backup = sys.modules.get("torch")

        if "torch" in sys.modules:
            del sys.modules["torch"]

        try:
            with patch.dict("sys.modules", {"torch": None}):
                with patch("builtins.__import__", side_effect=ImportError("No module named 'torch'")):
                    result = detect_cuda()
                    assert result is False
        finally:
            if torch_backup is not None:
                sys.modules["torch"] = torch_backup

    def test_cuda_detection_error(self):
        """Test when CUDA detection raises an error."""
        mock_torch = MagicMock()
        mock_torch.cuda.is_available.side_effect = RuntimeError("CUDA error")

        with patch.dict("sys.modules", {"torch": mock_torch}):
            result = detect_cuda()

            assert result is False


class TestGetGpuInfo:
    """Test GPU information retrieval."""

    def test_get_gpu_info_success(self):
        """Test getting GPU info when available."""
        mock_props = Mock()
        mock_props.total_memory = 8 * (1024**3)  # 8 GB

        mock_torch = MagicMock()
        mock_torch.cuda.device_count.return_value = 1
        mock_torch.cuda.get_device_name.return_value = "NVIDIA GeForce RTX 3080"
        mock_torch.cuda.get_device_capability.return_value = (8, 6)
        mock_torch.cuda.get_device_properties.return_value = mock_props
        mock_torch.__version__ = "2.0.0"
        mock_torch.version.cuda = "11.8"

        with patch("src.embeddings.gpu_utils.detect_cuda", return_value=True), \
             patch.dict("sys.modules", {"torch": mock_torch}):

            result = get_gpu_info()

            assert result is not None
            assert result["device_count"] == 1
            assert result["device_name"] == "NVIDIA GeForce RTX 3080"
            assert result["device_capability"] == (8, 6)
            assert result["total_memory_gb"] == 8.0
            assert result["pytorch_version"] == "2.0.0"
            assert result["cuda_version"] == "11.8"

    def test_get_gpu_info_no_cuda(self):
        """Test getting GPU info when CUDA is not available."""
        with patch("src.embeddings.gpu_utils.detect_cuda", return_value=False):
            result = get_gpu_info()

            assert result is None

    def test_get_gpu_info_no_devices(self):
        """Test when CUDA is available but no devices found."""
        mock_torch = MagicMock()
        mock_torch.cuda.device_count.return_value = 0

        with patch("src.embeddings.gpu_utils.detect_cuda", return_value=True), \
             patch.dict("sys.modules", {"torch": mock_torch}):

            result = get_gpu_info()

            assert result is None

    def test_get_gpu_info_error(self):
        """Test when getting GPU info raises an error."""
        mock_torch = MagicMock()
        mock_torch.cuda.device_count.side_effect = RuntimeError("CUDA error")

        with patch("src.embeddings.gpu_utils.detect_cuda", return_value=True), \
             patch.dict("sys.modules", {"torch": mock_torch}):

            result = get_gpu_info()

            assert result is None


class TestGetOptimalDevice:
    """Test optimal device selection."""

    def test_get_optimal_device_cuda(self):
        """Test when CUDA is available."""
        with patch("src.embeddings.gpu_utils.detect_cuda", return_value=True):
            result = get_optimal_device()

            assert result == "cuda"

    def test_get_optimal_device_cpu(self):
        """Test when CUDA is not available."""
        with patch("src.embeddings.gpu_utils.detect_cuda", return_value=False):
            result = get_optimal_device()

            assert result == "cpu"
