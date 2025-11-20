# BUG-015: Health Check False Negative for Qdrant

## TODO Reference
- ID: BUG-015
- Severity: HIGH
- Component: `src/cli/health_command.py:143`

## Objective
Fix health check command to correctly detect when Qdrant is running and healthy.

## Current State
- Health check uses `/health` endpoint which doesn't exist on Qdrant
- Returns false negative ("Not reachable") even when Qdrant is fully functional
- Conflicts with `validate-install` command which correctly detects Qdrant
- Causes user confusion during setup

## Root Cause Analysis
The health check was using the wrong endpoint:
```python
# Incorrect (line 143)
result = subprocess.run(["curl", "-s", f"{config.qdrant_url}/health"], ...)
if result.returncode == 0 and "ok" in result.stdout.lower():
```

Qdrant doesn't have a `/health` endpoint. The root endpoint `/` returns JSON with version info:
```bash
$ curl http://localhost:6333/
{"title":"qdrant - vector search engine","version":"1.16.0",...}
```

## Implementation

### Fix Applied
```python
# Corrected (line 143)
result = subprocess.run(["curl", "-s", f"{config.qdrant_url}/"], ...)
# Qdrant root endpoint returns JSON with "version" field
if result.returncode == 0 and "version" in result.stdout.lower():
```

### Files Changed
- `src/cli/health_command.py` (lines 143-149)

## Testing

### Before Fix
```bash
$ python -m src.cli health
Storage Backend
  ✗ Qdrant                         Not reachable at http://localhost:6333
```

### After Fix
```bash
$ python -m src.cli health
Storage Backend
  ✓ Qdrant                         Running at http://localhost:6333
```

### Verification
```bash
# Verify Qdrant is actually running
$ curl http://localhost:6333/
{"title":"qdrant - vector search engine","version":"1.16.0",...}  # ✅ Works

# Verify health check now passes
$ python -m src.cli health 2>&1 | grep "Qdrant"
  ✓ Qdrant                         Running at http://localhost:6333  # ✅ Correct
```

## Impact
- **User Experience:** No more misleading error messages during setup
- **Consistency:** Health check now matches validate-install behavior
- **Trust:** Users won't think their Qdrant installation is broken
- **Support:** Reduces confusion and support requests

## Next Steps
- ✅ Fix implemented and tested
- ✅ Documentation updated
- [ ] Consider adding health check tests to test suite
- [ ] Update troubleshooting guide if it references this issue

## Notes
- Quick 1-line fix (changed endpoint from `/health` to `/`)
- No breaking changes
- Backwards compatible (SQLite path unchanged)
- Should update Docker healthcheck (BUG-019) similarly
