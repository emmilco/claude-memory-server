# Known Issues

## Rust PyO3 Compilation Issue
**Status:** Deferred for later implementation  
**Date:** November 15, 2025

### Problem
The Rust PyO3 extension fails to link against Python shared libraries on macOS.  Both pyenv-installed Python 3.13.6 and Homebrew Python 3.13.7 have linking issues where the linker cannot find Python symbols (`_PyBytes_AsString`, `_PyErr_GetRaisedException`, etc.).

### Attempted Solutions
1. Setting `DYLD_LIBRARY_PATH` and `RUSTFLAGS` - still failed
2. Using Homebrew Python instead of pyenv - same issue  
3. Attempted maturin build - cargo PATH issues

### Current Workaround
Python fallback implementations are in place for all Rust functions:
- `batch_normalize_embeddings` → `batch_normalize_embeddings_python`
- `cosine_similarity` → `cosine_similarity_python`

The `RustBridge` class in `src/embeddings/rust_bridge.py` automatically falls back to Python implementations.

### Performance Impact
- Python normalization: ~2-5x slower than potential Rust implementation
- Acceptable for Phase 1 development
- Rust optimization can be added in Phase 3 after core functionality is stable

### Next Steps (Future)
- Investigate using `abi3` limited API for better compatibility
- Try with Python 3.12 which has better PyO3 support
- Consider using docker-based build environment
- Or wait for PyO3 0.28+ which may have better Python 3.13 support

