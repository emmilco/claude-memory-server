# Manual Test Scripts

This directory contains manual test scripts for end-to-end testing of the MCP server.

## Test Scripts

### test_all_features.py
Comprehensive end-to-end test suite for all MCP server features.

**Tests:**
- Code search (semantic, keyword, hybrid)
- Memory management (store, retrieve, list)
- Project management (status, list files, list units)
- Cross-project search
- Dependency analysis
- Performance metrics
- Re-indexing

**Usage:**
```bash
python tests/manual/test_all_features.py
```

**Note:** Requires an initialized server with indexed projects.

---

### debug_search.py
Debug script for investigating search_code results.

**Usage:**
```bash
python tests/manual/debug_search.py
```

---

### eval_test.py
Quick evaluation test for semantic code search quality.

**Usage:**
```bash
python tests/manual/eval_test.py
```

---

## Running Tests

These tests connect directly to the server via Python API, not through the MCP protocol.

For MCP protocol testing, use the server in Claude Code and interact with it directly.

## Related Documentation

- Full E2E test report: `docs/E2E_TEST_REPORT.md`
- Test results from 2025-11-20 testing session
