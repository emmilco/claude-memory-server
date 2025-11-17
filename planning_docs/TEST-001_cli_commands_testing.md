# TEST-001: CLI Commands Testing

## TODO Reference
- **TODO.md ID:** TEST-001
- **Description:** CLI commands testing (~15 tests) → +5.5% coverage
- **Priority:** High
- **Estimated Impact:** +5.5% overall code coverage

## Objective
Add comprehensive test coverage for CLI commands (index and watch) to increase overall code coverage from 63.72% to ~69%. This addresses the current 0% coverage of CLI modules.

## Current State
- **Files with 0% coverage:**
  - `src/cli/index_command.py` (123 lines)
  - `src/cli/watch_command.py` (78 lines)
  - `src/cli/__init__.py` (entry point)
- **Total uncovered lines:** ~201 lines
- **Current overall coverage:** 63.72%

## Implementation Plan

### Phase 1: Setup Test Infrastructure
- [ ] Create `tests/unit/test_cli_index.py`
- [ ] Create `tests/unit/test_cli_watch.py`
- [ ] Setup pytest fixtures for CLI testing
- [ ] Mock file system operations (Path, os.path)
- [ ] Mock async operations for watch command

### Phase 2: Index Command Tests
- [ ] Test successful indexing of single file
- [ ] Test successful indexing of directory
- [ ] Test recursive vs non-recursive indexing
- [ ] Test project name handling
- [ ] Test error handling (file not found, permissions)
- [ ] Test progress reporting output
- [ ] Test argument parsing validation

### Phase 3: Watch Command Tests
- [ ] Test successful start of file watcher
- [ ] Test initial indexing before watch
- [ ] Test file change detection simulation
- [ ] Test graceful shutdown (Ctrl+C)
- [ ] Test error recovery
- [ ] Test debounce behavior
- [ ] Test project name handling

### Phase 4: Integration Tests
- [ ] Test end-to-end index command with real files
- [ ] Test watch command with simulated file changes
- [ ] Verify Qdrant integration (mocked)

## Test Strategy

### Mocking Approach
```python
# Mock the IncrementalIndexer
@patch('src.cli.index_command.IncrementalIndexer')
async def test_index_command_success(mock_indexer):
    mock_instance = AsyncMock()
    mock_instance.index_directory.return_value = {
        'indexed_files': 5,
        'total_units': 100,
        'errors': []
    }
    mock_indexer.return_value = mock_instance
```

### Test Categories
1. **Happy Path Tests** - Normal successful operations
2. **Error Handling Tests** - Various failure scenarios
3. **Edge Cases** - Empty directories, special characters, etc.
4. **Argument Validation** - Invalid arguments, missing required params

## Progress Tracking

### Completed
- [x] Created this planning document
- [ ] Setup test infrastructure
- [ ] Implemented index command tests
- [ ] Implemented watch command tests
- [ ] All tests passing
- [ ] Coverage goal achieved

### Current Status
- **Date Started:** Not yet started
- **Last Updated:** Planning phase
- **Blockers:** None identified

## Code Snippets

### Sample Test Structure
```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path
from src.cli.index_command import index_command

@pytest.mark.asyncio
async def test_index_directory_success():
    """Test successful directory indexing."""
    with patch('src.cli.index_command.IncrementalIndexer') as mock_indexer:
        # Setup mock
        mock_instance = AsyncMock()
        mock_instance.index_directory.return_value = {
            'indexed_files': 10,
            'total_units': 250,
            'errors': []
        }
        mock_indexer.return_value = mock_instance

        # Run command
        await index_command(Path('./test_dir'), 'test_project', recursive=True)

        # Verify
        mock_instance.index_directory.assert_called_once_with(
            Path('./test_dir'),
            recursive=True
        )
```

## Notes & Decisions

### Key Considerations
1. **Async Testing**: Use `pytest-asyncio` for async test support
2. **Mock Strategy**: Mock at the IncrementalIndexer level, not individual methods
3. **Output Testing**: Capture stdout/stderr for progress message validation
4. **File System**: Use `tmp_path` fixture for temporary test files

### Dependencies
- pytest-asyncio
- pytest-mock or unittest.mock
- May need to refactor CLI code for better testability

## Verification Checklist

### Definition of Done
- [ ] All 15+ tests written and passing
- [ ] Code coverage increased by at least 5%
- [ ] No regression in existing tests
- [ ] Documentation updated if CLI interface changed
- [ ] CI/CD pipeline still green

### Test Coverage Targets
- `index_command.py`: >85% coverage
- `watch_command.py`: >85% coverage
- Overall project: ~69% (from 63.72%)

## Related Items
- **Dependencies:** None
- **Blocks:** Overall 85% coverage goal
- **Related PRs:** TBD

## References
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [Python unittest.mock guide](https://docs.python.org/3/library/unittest.mock.html)
- Current test examples in `tests/unit/`