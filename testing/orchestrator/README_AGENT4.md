# Agent 4 Test Implementation - Quick Reference

**Purpose:** Performance, Security, Error Handling, and Configuration Tests for TEST-006

## Quick Start

```bash
# Run all Agent 4 tests
cd /Users/elliotmilco/Documents/GitHub/claude-memory-server
python testing/orchestrator/run_agent4_tests.py

# View results
cat testing/results/agent4_results.json
```

## Test Coverage

### Performance (PERF-001 to PERF-003)
| Test ID | Description | Metrics |
|---------|-------------|---------|
| PERF-001 | Search latency | Semantic: 7-13ms, Hybrid: 10-18ms |
| PERF-002 | Indexing speed | 10-20 files/sec |
| PERF-003 | Concurrent load | 5 threads, 50 operations |

### Security (SEC-001 to SEC-003)
| Test ID | Description | Patterns Tested |
|---------|-------------|-----------------|
| SEC-001 | Path injection | 6 traversal patterns |
| SEC-002 | Command injection | 6 injection patterns |
| SEC-003 | Input validation | 6 validation scenarios |

### Error Handling (ERR-001 to ERR-003)
| Test ID | Description | Checks |
|---------|-------------|--------|
| ERR-001 | Missing dependencies | Actionable error messages |
| ERR-002 | Invalid inputs | Graceful handling, no crashes |
| ERR-003 | Network failures | Clear recovery guidance |

### Configuration (CONFIG-001 to CONFIG-003)
| Test ID | Description | Validates |
|---------|-------------|-----------|
| CONFIG-001 | Environment variables | 3 key env vars work |
| CONFIG-002 | Backend switching | Qdrant-only (no SQLite) |
| CONFIG-003 | Model configuration | Custom embedding models |

## Architecture

```
testing/orchestrator/
├── test_implementations.py       # Core test logic (4 classes)
│   ├── PerformanceTests
│   ├── SecurityTests
│   ├── ErrorHandlingTests
│   └── ConfigurationTests
│
├── test_executor.py              # Test routing and execution
│   └── TestExecutor
│       ├── __init__()            # Initializes test classes
│       ├── execute_test()        # Routes to appropriate handler
│       └── _test_*()             # 12 test methods
│
└── run_agent4_tests.py           # Test runner script
```

## Usage Examples

### Individual Test
```python
from testing.orchestrator.test_executor import TestExecutor

executor = TestExecutor(project_root="/app")
result = executor.execute_test("PERF-001")

print(f"Status: {result['status']}")
print(f"Notes: {result['notes']}")
if result['bugs_found']:
    for bug in result['bugs_found']:
        print(f"Bug: {bug['bug_id']} - {bug['description']}")
```

### Batch Execution
```python
test_ids = ["PERF-001", "PERF-002", "PERF-003"]
results = [executor.execute_test(tid) for tid in test_ids]

passed = sum(1 for r in results if r['status'] == 'PASS')
print(f"Passed: {passed}/{len(results)}")
```

## Result Structure

```python
{
    'test_id': 'PERF-001',
    'status': 'PASS',  # PASS, FAIL, ERROR, MANUAL_REQUIRED
    'notes': 'Search latency within acceptable range...',
    'bugs_found': [
        {
            'bug_id': 'BUG-NEW-PERF-001',
            'severity': 'MEDIUM',  # CRITICAL, HIGH, MEDIUM, LOW
            'description': 'Search latency 15ms exceeds target',
            'test_id': 'PERF-001'
        }
    ],
    'start_time': '2025-11-20T10:30:00',
    'end_time': '2025-11-20T10:31:00'
}
```

## Expected Execution Time

- **Full suite:** 7-9 minutes
- **Performance tests:** 4-5 minutes
- **Security tests:** 2-3 minutes
- **Error/Config tests:** 1 minute

## Requirements

- Qdrant running at `localhost:6333`
- Python 3.8+ with all dependencies
- Write access to `/tmp`
- ~500MB free memory
- ~50MB free disk space

## Common Issues

### Import Error
```
ImportError: cannot import name 'PerformanceTests'
```
**Solution:** Ensure you're running from project root
```bash
cd /Users/elliotmilco/Documents/GitHub/claude-memory-server
python -c "import sys; sys.path.insert(0, '.'); from testing.orchestrator.test_implementations import PerformanceTests"
```

### Qdrant Connection Error
```
ERROR_HANDLED: ConnectionError
```
**Solution:** Start Qdrant
```bash
docker-compose up -d qdrant
```

### Performance Test Failures
```
FAIL: Search latency too slow (25ms)
```
**Note:** Performance varies by hardware. CI environments may need different thresholds.

## Integration with E2E Testing

### Wave 3 Execution
Agent 4 tests run in Wave 3 of E2E testing plan:
- After installation verified (Wave 1)
- After core functionality tested (Wave 2)
- Alongside UI/config and feature tests (Wave 3)

### Test Orchestrator Integration
```python
# In orchestrator
from testing.orchestrator.test_executor import TestExecutor

executor = TestExecutor()

# Wave 3: Quality validation
quality_tests = {
    'agent-quality': [
        "PERF-001", "PERF-002", "PERF-003",
        "SEC-001", "SEC-002", "SEC-003",
        "ERR-001", "ERR-002", "ERR-003",
        "CONFIG-001", "CONFIG-002", "CONFIG-003"
    ]
}

results = []
for test_id in quality_tests['agent-quality']:
    result = executor.execute_test(test_id)
    results.append(result)
```

## Bug Tracking

All bugs auto-filed with structure:
```python
{
    'bug_id': 'BUG-NEW-{CATEGORY}-{ID}',
    'severity': 'CRITICAL|HIGH|MEDIUM|LOW',
    'description': 'Detailed description',
    'test_id': 'PERF-001'
}
```

Categories:
- `SEC-PATH` - Path injection
- `SEC-CMD` - Command injection
- `VAL` - Validation
- `PERF-LATENCY` - Performance latency
- `PERF-INDEXING` - Indexing speed
- `PERF-CONCURRENT` - Concurrent operations
- `ERR-DEPS` - Dependency errors
- `ERR-*` - Error handling
- `CFG-ENV` - Environment configuration
- `CFG-BACKEND` - Backend configuration

## Customization

### Adjusting Performance Thresholds
Edit `testing/orchestrator/test_implementations.py`:
```python
# In PerformanceTests.test_search_latency()
semantic_target = 10  # Change from 10ms
hybrid_target = 14    # Change from 14ms

# In PerformanceTests.test_indexing_speed()
target_min = 10  # Change from 10 files/sec
target_max = 20  # Change from 20 files/sec
```

### Adding Security Patterns
Edit `testing/orchestrator/test_implementations.py`:
```python
# In SecurityTests.test_path_injection()
malicious_paths = [
    # Add new patterns here
    "../../../../new/pattern",
]

# In SecurityTests.test_command_injection()
malicious_inputs = [
    # Add new injection patterns
    "new && injection",
]
```

## Documentation

- **Implementation Report:** `planning_docs/TEST-006_agent4_implementation_report.md`
- **Summary:** `planning_docs/TEST-006_agent4_summary.md`
- **Test Plan:** `planning_docs/TEST-006_e2e_test_plan.md`
- **Bug Tracker:** `planning_docs/TEST-006_e2e_bug_tracker.md`

## Support

For issues or questions:
1. Check test output and notes
2. Review implementation report for details
3. Check bug tracker for known issues
4. Verify environment setup (Qdrant, dependencies)

---

**Quick Reference Version:** 1.0
**Last Updated:** 2025-11-20
**Agent:** Agent 4
