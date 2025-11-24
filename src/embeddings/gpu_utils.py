"""GPU detection and utilities for embedding acceleration."""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def detect_cuda() -> bool:
    """
    Detect if CUDA is available.

    Returns:
        bool: True if CUDA available and working
    """
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        logger.debug("PyTorch not installed, CUDA unavailable")
        return False
    except Exception as e:
        logger.debug(f"CUDA detection failed: {e}")
        return False


def get_gpu_info() -> Optional[Dict[str, Any]]:
    """
    Get GPU information if available.

    Returns:
        Dict with GPU details or None if no GPU
    """
    if not detect_cuda():
        return None

    try:
        import torch

        device_count = torch.cuda.device_count()
        if device_count == 0:
            return None

        device_name = torch.cuda.get_device_name(0)
        device_capability = torch.cuda.get_device_capability(0)
        total_memory = torch.cuda.get_device_properties(0).total_memory
        memory_gb = total_memory / (1024**3)

        return {
            "device_count": device_count,
            "device_name": device_name,
            "device_capability": device_capability,
            "total_memory_gb": round(memory_gb, 2),
            "pytorch_version": torch.__version__,
            "cuda_version": torch.version.cuda,
        }
    except Exception as e:
        logger.warning(f"Failed to get GPU info: {e}")
        return None


def get_optimal_device() -> str:
    """
    Get optimal device for model.

    Returns:
        str: "cuda" if available, otherwise "cpu"
    """
    return "cuda" if detect_cuda() else "cpu"
