# UX-019: Optimization Suggestions

## TODO Reference
- TODO.md: "UX-019: Optimization Suggestions (~2 days)"
- Requirements:
  - Detect large binary files, suggest exclusion
  - Identify redundant directories (node_modules, .git)
  - Suggest .ragignore patterns
  - Performance impact estimates

## Objective
Provide intelligent optimization suggestions to users during indexing, helping them identify files/directories that should be excluded for better performance.

## Current State

### Existing Implementation
- **TimeEstimator.suggest_optimizations()** exists in `src/memory/time_estimator.py` (lines 94-150)
- Current suggestions:
  - node_modules exclusion (with time savings)
  - test directories exclusion (if > 50 files)
  - .git directory exclusion
  - vendor/third_party exclusion
  - .ragignore creation suggestion

### Limitations
1. **Basic detection**: Only pattern-based (path matching)
2. **No file size analysis**: Doesn't detect large binary files
3. **No .ragignore generation**: Suggests creation but doesn't generate patterns
4. **No interactive mode**: Just logs suggestions, no action
5. **Limited patterns**: Missing common patterns (build dirs, cache, logs)

## Implementation Plan

### Phase 1: Enhanced File Analysis
- [ ] Create `OptimizationAnalyzer` class
- [ ] Add binary file detection (magic number checking)
- [ ] Add file size analysis (detect large files > 1MB)
- [ ] Detect common build directories (dist, build, target, .next, etc.)
- [ ] Detect cache directories (.cache, __pycache__, .pytest_cache)
- [ ] Detect log files (*.log)
- [ ] Calculate accurate performance impact per suggestion

### Phase 2: .ragignore Generation
- [ ] Create `.ragignore` file format parser
- [ ] Generate optimized .ragignore patterns from analysis
- [ ] Merge with existing .ragignore if present
- [ ] Validate patterns before writing

### Phase 3: CLI Integration
- [ ] Add `--suggest-optimizations` flag to `index` command
- [ ] Add `--auto-optimize` flag to automatically apply suggestions
- [ ] Add `optimize` CLI command for analyzing existing projects
- [ ] Interactive mode for selecting which suggestions to apply

### Phase 4: Performance Impact Estimation
- [ ] Enhance time estimation with optimization impact
- [ ] Show "before vs after" metrics
- [ ] Calculate storage savings (disk, vector DB)
- [ ] Estimate indexing speed improvement

### Phase 5: Testing
- [ ] Unit tests for OptimizationAnalyzer
- [ ] Unit tests for .ragignore generation
- [ ] Integration tests for CLI commands
- [ ] Test accuracy of performance estimates

## Architecture

### Class Design

```python
class OptimizationAnalyzer:
    """Analyze files and suggest optimizations."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.file_stats = {}  # path -> FileStats

    async def analyze(self) -> AnalysisResult:
        """Analyze directory and generate suggestions."""

    def detect_binary_files(self) -> List[Path]:
        """Detect binary files by magic number."""

    def detect_large_files(self, threshold_mb: float = 1.0) -> List[Path]:
        """Detect files larger than threshold."""

    def detect_redundant_directories(self) -> Dict[str, DirectoryInfo]:
        """Detect node_modules, .git, build dirs, etc."""

    def detect_cache_directories(self) -> List[Path]:
        """Detect cache directories."""

    def estimate_impact(self) -> ImpactEstimate:
        """Estimate performance impact of suggestions."""

    def generate_ragignore(self) -> str:
        """Generate .ragignore content from suggestions."""


class RagignoreManager:
    """Manage .ragignore file."""

    def read_existing(self, directory: Path) -> List[str]:
        """Read existing .ragignore patterns."""

    def merge_patterns(self, existing: List[str], new: List[str]) -> List[str]:
        """Merge patterns, avoiding duplicates."""

    def write(self, directory: Path, patterns: List[str]) -> None:
        """Write .ragignore file."""

    def validate_pattern(self, pattern: str) -> bool:
        """Validate gitignore-style pattern."""
```

### Data Models

```python
@dataclass
class FileStats:
    path: Path
    size_bytes: int
    is_binary: bool
    mime_type: Optional[str]
    category: str  # 'source', 'binary', 'log', 'cache', etc.

@dataclass
class DirectoryInfo:
    path: Path
    file_count: int
    total_size_bytes: int
    category: str  # 'node_modules', 'build', 'cache', etc.

@dataclass
class OptimizationSuggestion:
    type: str  # 'exclude_binary', 'exclude_directory', 'exclude_pattern'
    description: str
    pattern: str  # .ragignore pattern
    affected_files: int
    size_savings_mb: float
    time_savings_seconds: float
    priority: int  # 1-5, higher is more important

@dataclass
class AnalysisResult:
    total_files: int
    total_size_mb: float
    suggestions: List[OptimizationSuggestion]
    estimated_speedup: float  # e.g., 2.5x faster
    estimated_storage_savings_mb: float
```

## Common Patterns to Detect

### Build Directories
- `dist/`, `build/`, `out/`, `target/` (general)
- `.next/`, `.nuxt/`, `.vuepress/` (JS frameworks)
- `bin/`, `obj/` (C#/.NET)
- `cmake-build-*` (CMake)

### Dependency Directories
- `node_modules/` (Node.js)
- `vendor/` (PHP, Go)
- `venv/`, `env/`, `.venv/` (Python)
- `.virtualenv/`
- `site-packages/`

### Cache Directories
- `.cache/`
- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `.turbo/`
- `.parcel-cache/`

### Version Control
- `.git/`
- `.svn/`
- `.hg/`

### IDE/Editor
- `.idea/` (IntelliJ)
- `.vscode/` (VSCode)
- `.vs/` (Visual Studio)
- `*.swp`, `*.swo` (Vim)

### Logs and Temporary Files
- `*.log`
- `*.tmp`
- `.DS_Store` (macOS)
- `Thumbs.db` (Windows)

### Binary Files
- `*.exe`, `*.dll`, `*.so`, `*.dylib`
- `*.jpg`, `*.jpeg`, `*.png`, `*.gif`, `*.ico`
- `*.pdf`, `*.zip`, `*.tar`, `*.gz`
- `*.mp4`, `*.mp3`, `*.wav`

## Progress Tracking

### Current Progress
- [x] Analyzed existing code
- [x] Created planning document
- [ ] Implement Phase 1: Enhanced File Analysis
- [ ] Implement Phase 2: .ragignore Generation
- [ ] Implement Phase 3: CLI Integration
- [ ] Implement Phase 4: Performance Impact Estimation
- [ ] Implement Phase 5: Testing

## Notes & Decisions

### Design Decisions

1. **Leverage existing TimeEstimator**: Build on top of `suggest_optimizations()` rather than replacing
2. **Magic number detection**: Use Python's `mimetypes` + manual checks for binary detection
3. **.ragignore format**: Use gitignore syntax (widely understood)
4. **Priority scoring**: Base on time savings + file count
5. **Default thresholds**:
   - Large file: > 1MB
   - Large directory: > 100 files
   - Binary file: detected via mime type

### Edge Cases

1. **Mixed directories**: Some source in node_modules (monorepos)
   - **Decision**: Still suggest exclusion, user can customize
2. **Existing .ragignore**: Merge patterns, don't overwrite
   - **Decision**: Read existing, add new patterns, write back
3. **False positives**: Some .log files are source code examples
   - **Decision**: Suggest but don't auto-apply, let user choose

## Test Cases

### Unit Tests (25 tests)

1. **OptimizationAnalyzer**:
   - `test_detect_binary_files()` - Detect .jpg, .png, .exe
   - `test_detect_large_files()` - Files > 1MB threshold
   - `test_detect_node_modules()` - Find node_modules directories
   - `test_detect_build_directories()` - dist, build, .next, target
   - `test_detect_cache_directories()` - __pycache__, .cache
   - `test_detect_venv_directories()` - venv, .venv, env
   - `test_detect_git_directory()` - .git exclusion
   - `test_estimate_impact()` - Calculate time/space savings
   - `test_generate_suggestions()` - Create prioritized suggestions
   - `test_empty_directory()` - Handle empty directories
   - `test_no_optimizations_needed()` - Clean project, no suggestions

2. **RagignoreManager**:
   - `test_read_existing_ragignore()` - Parse existing file
   - `test_merge_patterns()` - Combine old and new patterns
   - `test_deduplicate_patterns()` - Remove duplicates
   - `test_validate_pattern()` - Validate gitignore syntax
   - `test_write_ragignore()` - Create new file
   - `test_preserve_comments()` - Keep existing comments

3. **Binary Detection**:
   - `test_detect_image_files()` - .jpg, .png, .gif
   - `test_detect_executables()` - .exe, .dll, .so
   - `test_detect_archives()` - .zip, .tar.gz
   - `test_text_files_not_binary()` - .py, .js marked as text

4. **Impact Estimation**:
   - `test_calculate_time_savings()` - Accurate time estimates
   - `test_calculate_storage_savings()` - Disk + vector DB
   - `test_speedup_calculation()` - Before/after comparison
   - `test_priority_scoring()` - High impact gets high priority

### Integration Tests (8 tests)

1. **CLI Integration**:
   - `test_suggest_optimizations_flag()` - CLI shows suggestions
   - `test_auto_optimize_flag()` - Applies suggestions automatically
   - `test_optimize_command()` - Standalone optimize command
   - `test_interactive_mode()` - User selects suggestions

2. **End-to-End**:
   - `test_analyze_real_project()` - Analyze actual codebase
   - `test_generate_ragignore_file()` - Create working .ragignore
   - `test_merge_with_existing()` - Merge patterns correctly
   - `test_reindex_after_optimization()` - Verify speedup

## Implementation Checklist

### Files to Create
- [ ] `src/memory/optimization_analyzer.py` - Main analyzer class
- [ ] `src/memory/ragignore_manager.py` - .ragignore file management
- [ ] `tests/unit/test_optimization_analyzer.py` - Analyzer tests
- [ ] `tests/unit/test_ragignore_manager.py` - Ragignore tests
- [ ] `tests/integration/test_optimization_cli.py` - CLI integration tests

### Files to Modify
- [ ] `src/memory/time_estimator.py` - Integrate with OptimizationAnalyzer
- [ ] `src/cli/index_command.py` - Add optimization flags
- [ ] `src/cli/__init__.py` - Add `optimize` command
- [ ] `CHANGELOG.md` - Add UX-019 entry

### Documentation Updates
- [ ] README.md - Document optimization features
- [ ] docs/CLI.md - Document `optimize` command and flags

## Success Criteria

1. ✅ **Accurate detection**: Correctly identify 90%+ of optimization opportunities
2. ✅ **Valid .ragignore**: Generated patterns work correctly
3. ✅ **Performance impact**: Estimates within 20% of actual improvement
4. ✅ **CLI integration**: Flags work as expected
5. ✅ **Test coverage**: 85%+ coverage for new code
6. ✅ **No false negatives**: Don't miss major optimizations (node_modules, .git)
7. ✅ **User-friendly**: Clear, actionable suggestions with impact metrics

## Completion Summary

(To be filled upon completion)
