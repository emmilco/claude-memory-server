# REF-021: Consolidate Hardcoded Values into src/config.py

**Status:** Planned
**Priority:** Medium (Tech Debt)
**Estimated Effort:** ~2-3 hours
**Created:** 2025-11-29

---

## Objective

Extract hardcoded values with **dependency relationships** and consolidate them into `src/config.py`. Focus on values where changing one instance requires changing others to maintain consistency.

---

## Key Dependencies Identified

| Category | Values | Files Affected |
|----------|--------|----------------|
| **Embedding Dimensions** | 384 (MiniLM), 768 (MPNet) | 8+ files |
| **Model Names** | "all-mpnet-base-v2", "all-mpnet-base-v2", etc. | 6+ files |
| **Base Directory** | `~/.claude-rag` | 10+ files |
| **Qdrant URL** | `http://localhost:6333` | 5+ files |
| **Collection Names** | "memory", "code_call_graph" | 3+ files |
| **Health Timeouts** | 0.05/0.1/0.2s and 0.5/1.0/2.0s tiers | 2 files |

---

## Implementation Plan

### Step 1: Expand `src/config.py` with Consolidated Constants

Add new constants section at the top of the file (before the Pydantic classes):

```python
# =============================================================================
# COMPILE-TIME CONSTANTS (not user-configurable)
# =============================================================================

# Embedding model names
EMBEDDING_MODEL_MINILM_L6 = "all-mpnet-base-v2"
EMBEDDING_MODEL_MINILM_L12 = "all-MiniLM-L12-v2"
EMBEDDING_MODEL_MPNET = "all-mpnet-base-v2"

# Model -> dimension mapping (already exists, ensure uses constants above)
EMBEDDING_MODEL_DIMENSIONS = {
    EMBEDDING_MODEL_MINILM_L6: 384,
    EMBEDDING_MODEL_MINILM_L12: 384,
    EMBEDDING_MODEL_MPNET: 768,
}

DEFAULT_EMBEDDING_MODEL = EMBEDDING_MODEL_MPNET
DEFAULT_EMBEDDING_DIM = EMBEDDING_MODEL_DIMENSIONS[DEFAULT_EMBEDDING_MODEL]

# Base data directory
BASE_DATA_DIR_NAME = ".claude-rag"

def get_base_data_dir() -> Path:
    return Path.home() / BASE_DATA_DIR_NAME

# Qdrant collection names
QDRANT_COLLECTION_MEMORY = "memory"
QDRANT_COLLECTION_CALL_GRAPH = "code_call_graph"

# Default Qdrant URL
DEFAULT_QDRANT_URL = "http://localhost:6333"

# Health check timeouts (seconds) - standard tier
HEALTH_CHECK_FAST_TIMEOUT = 0.05
HEALTH_CHECK_MEDIUM_TIMEOUT = 0.1
HEALTH_CHECK_DEEP_TIMEOUT = 0.2

# Health check timeouts - relaxed tier for production
HEALTH_CHECK_FAST_TIMEOUT_RELAXED = 0.5
HEALTH_CHECK_MEDIUM_TIMEOUT_RELAXED = 1.0
HEALTH_CHECK_DEEP_TIMEOUT_RELAXED = 2.0

# Vector storage
VECTOR_SIZE_FLOAT32 = 4  # bytes per float32

def get_embedding_size_bytes(dimensions: int = DEFAULT_EMBEDDING_DIM) -> int:
    return dimensions * VECTOR_SIZE_FLOAT32

def get_embedding_dim_for_model(model_name: str) -> int:
    if model_name not in EMBEDDING_MODEL_DIMENSIONS:
        raise ValueError(f"Unsupported model: {model_name}")
    return EMBEDDING_MODEL_DIMENSIONS[model_name]
```

Then update `ServerConfig` defaults to use these constants where applicable.

### Step 2: Update Files with Duplicate `model_dims` Dictionaries

| File | Change |
|------|--------|
| `src/store/qdrant_setup.py` | Remove local `model_dims`, import from `src.config` |
| `src/store/call_graph_store.py` | Remove local `model_dims`, import from `src.config`; use `QDRANT_COLLECTION_CALL_GRAPH` |
| `src/embeddings/generator.py` | Remove `MODELS` class attr, import `EMBEDDING_MODEL_DIMENSIONS` from `src.config` |
| `src/embeddings/parallel_generator.py` | Remove `MODELS` class attr, import from `src.config` |

### Step 3: Fix Hardcoded Dimension Values

| File | Current | Fix |
|------|---------|-----|
| `src/memory/storage_optimizer.py:212` | `384 * 4` | `from src.config import get_embedding_size_bytes` |
| `src/memory/bulk_operations.py:164` | `384 * 4` | `from src.config import get_embedding_size_bytes` |
| `src/cli/status_command.py:222` | `384` | Use config's `embedding_dimensions` |
| `src/cli/memory_browser.py:224` | `384` | `from src.config import DEFAULT_EMBEDDING_DIM` |

### Step 4: Replace Hardcoded Paths

| File | Path | Replace With |
|------|------|--------------|
| `src/analytics/token_tracker.py:69` | `Path.home() / ".claude-rag"` | `from src.config import get_base_data_dir` |
| `src/store/qdrant_store.py:2365` | `.../.claude-rag/feedback.db` | `get_base_data_dir() / "feedback.db"` |
| `src/cli/health_monitor_command.py:35` | `.../.claude-rag/metrics.db` | `get_base_data_dir() / "metrics.db"` |
| `src/cli/validate_setup_command.py:155` | `http://localhost:6333` | `from src.config import DEFAULT_QDRANT_URL` |

### Step 5: Update Health Check Timeouts

| File | Change |
|------|--------|
| `src/store/connection_health_checker.py` | Import and use `HEALTH_CHECK_*_TIMEOUT` |
| `src/store/qdrant_store.py:76-78` | Import and use `HEALTH_CHECK_*_TIMEOUT_RELAXED` |

---

## Files to Modify (Summary)

| Category | Files | Est. Changes |
|----------|-------|--------------|
| **Expand** | `src/config.py` | ~50 lines added |
| **Remove Duplicates** | 4 files (embeddings, store) | ~8 lines each |
| **Fix Dimensions** | 4 files (memory, cli) | ~2 lines each |
| **Fix Paths** | 4 files | ~2-4 lines each |
| **Fix Timeouts** | 2 files | ~6 lines each |
| **Total** | ~14 files | ~100 lines |

---

## Critical Files to Read Before Implementation

1. `src/config.py` - Current config structure (will be expanded)
2. `src/store/qdrant_setup.py` - Duplicate model_dims
3. `src/embeddings/generator.py` - Duplicate MODELS
4. `src/store/connection_health_checker.py` - Timeout patterns
5. `src/memory/bulk_operations.py` - Hardcoded 384

---

## Testing Strategy

1. Run existing tests after each step to catch regressions
2. Key test files to run:
   - `pytest tests/unit/test_config.py -v`
   - `pytest tests/unit/test_embeddings*.py -v`
   - `pytest tests/unit/test_store*.py -v`
3. Final verification: `python scripts/verify-complete.py`

---

## Notes

- This task was originally scoped broader ("move hardcoded thresholds to config") but refined to focus specifically on **values with dependency relationships**
- User preference: Consolidate into `src/config.py` rather than creating a separate `settings.py`
- All new constants are compile-time (not runtime configurable via env vars)
