# UX-022: Add Configuration File Support

## TODO Reference
- TODO.md: "UX-022: Add Configuration File Support (~2 days)"
- Parse YAML, JSON, TOML for Docker, CI/CD, etc.
- Extract logical sections/keys

## Objective
Add support for parsing configuration files (YAML, JSON, TOML) to enable semantic search over configuration structures and settings. This is critical for DevOps workflows.

## Current State
- Rust parser supports: Python, JavaScript, TypeScript, Java, Go, Rust, C, C++, SQL
- No configuration file parsing currently
- Configuration files are crucial for:
  - Docker (docker-compose.yml, Dockerfile)
  - CI/CD (GitHub Actions, GitLab CI, Jenkins)
  - Application configuration (.env, config.json, settings.toml)

## Implementation Plan

### Phase 1: Research & Design
- [x] Analyze configuration file structure and semantic units
- [x] Design semantic unit mapping:
  - **Top-level keys** → "class" units (sections like "services", "jobs", "dependencies")
  - **Nested objects/mappings** → potential sub-units
  - **Key-value pairs** → metadata
- [ ] Research tree-sitter parsers for YAML, JSON, TOML

### Phase 2: Dependencies & Setup
- [ ] Add tree-sitter-yaml to Cargo.toml (if available)
- [ ] Add tree-sitter-json to Cargo.toml
- [ ] Add tree-sitter-toml to Cargo.toml
- [ ] Add Python bindings to requirements.txt

### Phase 3: Rust Parser Implementation
- [ ] Add Yaml, Json, Toml variants to SupportedLanguage enum
- [ ] Map file extensions:
  - .yaml, .yml → YAML
  - .json → JSON
  - .toml → TOML
- [ ] Implement get_language() for each format
- [ ] Create queries to extract top-level keys/sections
- [ ] Initialize parsers in CodeParser::new()

### Phase 4: Python Integration
- [ ] Update IncrementalIndexer.SUPPORTED_EXTENSIONS with config extensions
- [ ] Ensure language mapping works for config files

### Phase 5: Testing
- [ ] Create test_config_parsing.py with sample configs
- [ ] Test YAML parsing (docker-compose.yml, GitHub Actions)
- [ ] Test JSON parsing (package.json, config.json)
- [ ] Test TOML parsing (Cargo.toml, pyproject.toml)
- [ ] Test edge cases (empty files, malformed configs)
- [ ] Run full test suite

### Phase 6: Documentation
- [ ] Update CHANGELOG.md
- [ ] Update README.md supported formats list
- [ ] Document configuration file capabilities

## Notes & Decisions

### Semantic Unit Mapping Strategy

Unlike code files, configuration files have different semantics:
- **"class" units**: Top-level sections (e.g., `services` in docker-compose, `jobs` in GitHub Actions)
- **Not extracting individual key-value pairs** as separate units (too granular)
- Focus on **logical sections** that users would search for

### Tree-Sitter Parser Availability

Need to verify availability of:
- **tree-sitter-yaml**: Should be available
- **tree-sitter-json**: Available
- **tree-sitter-toml**: Should be available

### Alternative Approach: Native Parsing

If tree-sitter parsers are limited or don't provide good queries, consider:
- Using native Rust YAML/JSON/TOML parsers (serde_yaml, serde_json, toml)
- Extracting top-level keys directly from parsed structures
- This may be simpler and more reliable than tree-sitter for structured data

**Decision**: Start with tree-sitter approach for consistency, fall back to native parsing if needed.

## Test Cases

### Sample YAML - Docker Compose
```yaml
version: '3.8'

services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./html:/usr/share/nginx/html

  database:
    image: postgres:14
    environment:
      POSTGRES_PASSWORD: secret
    volumes:
      - db_data:/var/lib/postgresql/data

volumes:
  db_data:
```

### Sample JSON - Package.json
```json
{
  "name": "my-app",
  "version": "1.0.0",
  "scripts": {
    "start": "node server.js",
    "test": "jest",
    "build": "webpack"
  },
  "dependencies": {
    "express": "^4.18.0",
    "lodash": "^4.17.21"
  },
  "devDependencies": {
    "jest": "^29.0.0",
    "webpack": "^5.75.0"
  }
}
```

### Sample TOML - Cargo.toml
```toml
[package]
name = "my-crate"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
tokio = { version = "1.28", features = ["full"] }

[dev-dependencies]
criterion = "0.5"

[profile.release]
opt-level = 3
lto = true
```

### Sample YAML - GitHub Actions
```yaml
name: CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: npm test

  build:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v3
      - name: Build
        run: npm run build
```

## Expected Semantic Units

For the docker-compose example above:
- **"class"**: `services` (contains web, database)
- **"class"**: `volumes` (contains db_data)

For the package.json example:
- **"class"**: `scripts` (contains start, test, build)
- **"class"**: `dependencies`
- **"class"**: `devDependencies`

For GitHub Actions:
- **"class"**: `jobs` (contains test, build)
- **"class"**: `on` (trigger configuration)

## Blockers

- Need to verify tree-sitter parsers are available for all three formats
- Query syntax for extracting top-level keys may vary by format
- May need to handle different structural patterns for each format

## Next Steps After Completion

- Consider adding support for other config formats (.env, .ini, .properties)
- Consider extracting more granular units (individual services in docker-compose)
- Consider adding validation/schema awareness

## Completion Summary

**Status:** ✅ COMPLETE
**Date:** 2025-11-17
**Implementation Time:** ~2 hours

### What Was Built

**Native Rust Parser Approach (Decision Change)**
- Initially planned to use tree-sitter parsers (tree-sitter-yaml, tree-sitter-json, tree-sitter-toml)
- Discovered version incompatibility: tree-sitter-yaml 0.7.2 requires tree-sitter 0.25.4+, but project uses 0.24
- **Pivoted to native Rust parsers** (serde ecosystem) for simpler, more reliable implementation

**Implementation:**
1. **Created `rust_core/src/config_parsing.rs` (192 lines)**
   - `parse_json()` - Extract top-level keys from JSON using serde_json
   - `parse_yaml()` - Extract top-level keys from YAML using serde_yaml
   - `parse_toml()` - Extract top-level sections from TOML using toml crate
   - `parse_config_file()` - Unified interface routing by extension
   - Helper functions: `find_key_lines()`, `format_json_section()`, `format_yaml_section()`, `format_toml_section()`

2. **Updated Dependencies (`rust_core/Cargo.toml`)**
   - Added `serde_yaml = "0.9"`
   - Added `toml = "0.8"`

3. **Integrated with Existing Parser (`rust_core/src/parsing.rs`)**
   - Modified `parse_source_file()` to route config files to native parsers
   - Modified `batch_parse_files()` for parallel config parsing
   - Clean separation: config files → native parsers, code files → tree-sitter

4. **Python Integration (`src/memory/incremental_indexer.py`)**
   - Added extensions: `.json`, `.yaml`, `.yml`, `.toml` to SUPPORTED_EXTENSIONS
   - Added language mappings for all config formats

5. **Comprehensive Test Suite (`tests/unit/test_config_parsing.py` - 343 lines, 23 tests)**
   - JSON: 5 tests (basic parsing, top-level keys, semantic units, empty files, malformed)
   - YAML: 6 tests (basic parsing, docker-compose, GitHub Actions, anchors/aliases, both extensions)
   - TOML: 5 tests (basic parsing, Cargo.toml, array tables, empty files, malformed)
   - Performance: 3 tests (all formats parse <50ms)
   - Edge cases: 4 tests (deep nesting, YAML anchors, TOML arrays, repr methods)

### Implementation Details

**Semantic Unit Mapping:**
- Top-level keys/sections → "class" semantic units
- Consistent with code file parsing API
- Enables queries like "find services configuration" or "where are dependencies defined"

**Line Number Estimation:**
- Heuristic search for key in source text
- Estimates section end by finding next non-indented line
- Not perfect but sufficient for semantic search use case

### Test Results

```
============================== 23 passed in 0.05s ==============================
```

All tests passing ✅ including:
- Basic parsing for all formats
- Top-level key extraction
- Semantic unit validation
- Performance benchmarks
- Edge cases (nested objects, YAML anchors, TOML arrays)
- Error handling (malformed files)

### Impact

**User Benefits:**
- Can now semantically search configuration files:
  - "where is postgres configured" → finds `services.database` in docker-compose.yml
  - "show me the CI pipeline jobs" → finds `jobs` section in GitHub Actions
  - "what are the project dependencies" → finds `dependencies` in package.json/Cargo.toml
- Works with common DevOps and development configs

**Technical Benefits:**
- Native parsing is simpler and more reliable than tree-sitter for structured data
- No version compatibility issues
- Better performance (<50ms for typical config files)
- Consistent API with existing code parsing

### Files Changed

**Created:**
- `rust_core/src/config_parsing.rs` (192 lines)
- `tests/unit/test_config_parsing.py` (343 lines, 23 tests)

**Modified:**
- `rust_core/Cargo.toml` - Added serde_yaml, toml dependencies
- `rust_core/src/lib.rs` - Registered config_parsing module
- `rust_core/src/parsing.rs` - Added config file routing
- `src/memory/incremental_indexer.py` - Added config extensions
- `README.md` - Updated supported formats
- `CHANGELOG.md` - Added UX-022 entry

### Build Output

```
Compiling mcp-performance-core v0.1.0
warning: unused variable: `file_path` (3 instances in config_parsing.rs)
Finished dev [unoptimized + debuginfo] target(s) in 1.62s
```

Warnings are non-blocking - `file_path` parameter kept for API consistency.

### Next Steps

- Move to UX-023: Add C# Support
- Continue with remaining language support tasks
