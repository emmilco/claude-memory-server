# First-Run Experience Testing Guide

**Last Updated:** November 18, 2025
**Version:** 4.0
**Status:** Testing Framework Ready

---

## Overview

This document provides a comprehensive testing framework for validating the first-run installation experience across different presets and environments.

## Quick Reference

| Preset | Installation Time | Prerequisites | Complexity |
|--------|------------------|---------------|------------|
| Minimal | ~2 minutes | Python 3.13+ | Low |
| Standard | ~5 minutes | Python 3.13+, Rust | Medium |
| Full | ~10 minutes | Python 3.13+, Rust, Docker | High |

---

## Table of Contents

1. [Pre-Testing Setup](#pre-testing-setup)
2. [Preset Testing Procedures](#preset-testing-procedures)
3. [Automated Validation](#automated-validation)
4. [Common Failure Scenarios](#common-failure-scenarios)
5. [Performance Benchmarks](#performance-benchmarks)
6. [Test Results Template](#test-results-template)

---

## Pre-Testing Setup

### Clean Machine Requirements

**For accurate first-run testing, start with:**

- ✅ Fresh OS installation or VM
- ✅ No Python packages installed (clean pip)
- ✅ No Docker installed (for minimal/standard tests)
- ✅ No Rust toolchain installed (for minimal test)
- ✅ Clean home directory (~/.claude-rag/ should not exist)

### VM Recommendations

**Recommended Test Environments:**

1. **macOS Testing:**
   - macOS 13+ (Ventura or newer)
   - Homebrew installed (for Python)
   - 8GB+ RAM

2. **Ubuntu Testing:**
   - Ubuntu 22.04 LTS or 24.04 LTS
   - 4GB+ RAM
   - Standard apt repositories enabled

3. **Windows Testing:**
   - Windows 10/11
   - WSL2 enabled (for full preset)
   - 8GB+ RAM

### Test Data Preparation

```bash
# Clone repository
git clone https://github.com/anthropics/claude-memory-server.git
cd claude-memory-server

# Create test project for indexing
mkdir -p ~/test-projects/sample-code
cd ~/test-projects/sample-code

# Create sample Python files
cat > app.py << 'EOF'
"""Sample application for testing indexing."""

def greet(name: str) -> str:
    """Greet a user by name."""
    return f"Hello, {name}!"

def main():
    """Main entry point."""
    print(greet("World"))

if __name__ == "__main__":
    main()
EOF

cat > utils.py << 'EOF'
"""Utility functions."""

def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b
EOF
```

---

## Preset Testing Procedures

### Test 1: Minimal Preset

**Target:** Fastest installation with minimal dependencies

**Prerequisites:**
- Python 3.13+

**Procedure:**

1. **Start Timer** ⏱️

2. **Run Setup:**
   ```bash
   python setup.py --preset minimal
   ```

3. **Expected Output:**
   - Welcome banner
   - Prerequisite check: Python ✅
   - Skip Docker check
   - Skip Rust check
   - SQLite configuration
   - Python parser configuration
   - Progress indicators
   - Success message

4. **Stop Timer** ⏱️

5. **Verify Installation:**
   ```bash
   # Run automated validation
   python scripts/validate_installation.py --preset minimal
   ```

6. **Test Basic Functionality:**
   ```bash
   # Start server (in background)
   python -m src.mcp_server &
   SERVER_PID=$!

   # Wait for startup
   sleep 5

   # Test health check
   python -m src.cli health

   # Index test project
   python -m src.cli index ~/test-projects/sample-code --project-name test-app

   # Search test
   python -m src.cli search "greet function"

   # Stop server
   kill $SERVER_PID
   ```

7. **Record Results:**
   - Installation time: ______ minutes
   - Health check: PASS / FAIL
   - Indexing: PASS / FAIL
   - Search: PASS / FAIL
   - Issues encountered: ______________

**Success Criteria:**
- ✅ Installation completes in ≤3 minutes
- ✅ All validation checks pass
- ✅ Can index sample project
- ✅ Can search and retrieve results
- ✅ No errors in logs

---

### Test 2: Standard Preset

**Target:** Good performance with Rust parser

**Prerequisites:**
- Python 3.13+
- Rust toolchain (will be installed if missing)

**Procedure:**

1. **Start Timer** ⏱️

2. **Run Setup:**
   ```bash
   python setup.py --preset standard
   ```

3. **Expected Output:**
   - Welcome banner
   - Prerequisite check: Python ✅
   - Rust check (install if needed)
   - SQLite configuration
   - Rust parser compilation
   - Progress indicators
   - Success message

4. **Stop Timer** ⏱️

5. **Verify Installation:**
   ```bash
   python scripts/validate_installation.py --preset standard
   ```

6. **Test Rust Parser:**
   ```bash
   # Verify Rust module loads
   python -c "from rust_core import parse_python_file; print('Rust parser: OK')"

   # Index with Rust parser
   python -m src.cli index ~/test-projects/sample-code --project-name test-app

   # Verify parsing performance
   python scripts/benchmark_parsing.py
   ```

7. **Record Results:**
   - Installation time: ______ minutes
   - Rust compilation: PASS / FAIL
   - Parser performance: ______ ms/file
   - Issues encountered: ______________

**Success Criteria:**
- ✅ Installation completes in ≤7 minutes
- ✅ Rust module compiles successfully
- ✅ Parser performance: <10ms per file
- ✅ All validation checks pass

---

### Test 3: Full Preset

**Target:** Optimal performance with Qdrant

**Prerequisites:**
- Python 3.13+
- Rust toolchain
- Docker (will check and prompt if missing)

**Procedure:**

1. **Start Timer** ⏱️

2. **Run Setup:**
   ```bash
   python setup.py --preset full
   ```

3. **Expected Output:**
   - Welcome banner
   - Prerequisite check: Python ✅, Docker ✅
   - Rust check (install if needed)
   - Qdrant setup via Docker
   - Rust parser compilation
   - Qdrant health check
   - Success message

4. **Stop Timer** ⏱️

5. **Verify Installation:**
   ```bash
   python scripts/validate_installation.py --preset full
   ```

6. **Test Qdrant Integration:**
   ```bash
   # Check Qdrant running
   curl http://localhost:6333/health

   # Index with Qdrant
   python -m src.cli index ~/test-projects/sample-code --project-name test-app

   # Run performance benchmark
   python scripts/benchmark_scale.py
   ```

7. **Record Results:**
   - Installation time: ______ minutes
   - Qdrant startup: PASS / FAIL
   - Search P95 latency: ______ ms
   - Issues encountered: ______________

**Success Criteria:**
- ✅ Installation completes in ≤12 minutes
- ✅ Qdrant starts successfully
- ✅ Search P95 latency: <50ms
- ✅ All validation checks pass

---

## Automated Validation

### Installation Validation Script

The `scripts/validate_installation.py` script automatically checks:

```bash
python scripts/validate_installation.py --preset <minimal|standard|full>
```

**Checks Performed:**

1. **Python Version**
   - Validates Python 3.13+
   - Checks for required modules

2. **Dependencies**
   - Verifies all requirements.txt packages installed
   - Checks versions match requirements

3. **Configuration Files**
   - .env file exists
   - Required config values present
   - Valid configuration syntax

4. **Parser Availability**
   - Minimal/Standard: Python parser works
   - Standard/Full: Rust parser works

5. **Storage Backend**
   - Minimal/Standard: SQLite database accessible
   - Full: Qdrant connection successful

6. **Core Functionality**
   - Can initialize server
   - Can create memory
   - Can search memories
   - Can retrieve memories

7. **CLI Commands**
   - All commands accessible
   - Help text displays correctly

### Health Check Validation

```bash
# Comprehensive health check
python -m src.cli health --verbose

# Expected output:
# ✅ Python version: 3.13.x
# ✅ Storage backend: [SQLite/Qdrant] connected
# ✅ Embedding model: Loaded
# ✅ Parser: [Python/Rust] available
# ✅ Cache: Working
# ✅ Configuration: Valid
```

---

## Common Failure Scenarios

### Scenario 1: Python Version Too Old

**Error:**
```
Python 3.13+ required. Found: 3.11.5
```

**Test Steps:**
1. Install with Python 3.11
2. Verify error message is clear
3. Verify error includes upgrade instructions

**Expected Behavior:**
- Clear error message
- Link to Python installation guide
- Graceful exit (no crash)

**Recovery:**
```bash
# macOS
brew install python@3.13

# Ubuntu
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.13
```

---

### Scenario 2: Docker Not Available

**Error:**
```
Docker is not running or not installed.
Full preset requires Docker for Qdrant.
```

**Test Steps:**
1. Stop Docker daemon
2. Run setup with full preset
3. Verify error handling

**Expected Behavior:**
- Detects Docker unavailable
- Offers to install Docker
- OR offers to switch to standard preset

**Recovery:**
```bash
# Option 1: Install Docker
# Follow: https://docs.docker.com/get-docker/

# Option 2: Use different preset
python setup.py --preset standard
```

---

### Scenario 3: Rust Compilation Fails

**Error:**
```
Rust compilation failed: cargo build returned exit code 1
```

**Test Steps:**
1. Corrupt Rust code temporarily
2. Run setup with standard/full preset
3. Verify fallback behavior

**Expected Behavior:**
- Detects Rust failure
- Offers to continue with Python parser
- OR retries compilation

**Recovery:**
```bash
# Option 1: Fix Rust installation
rustup update

# Option 2: Use Python parser
python setup.py --preset minimal
```

---

### Scenario 4: Missing Dependencies

**Error:**
```
Failed to install requirements: [package-name]
```

**Test Steps:**
1. Temporarily break pip (wrong version)
2. Run setup
3. Verify error handling

**Expected Behavior:**
- Clear error about which package failed
- Suggests manual installation
- Logs full error for debugging

**Recovery:**
```bash
# Manual installation
pip install --upgrade pip
pip install -r requirements.txt

# Retry setup
python setup.py
```

---

### Scenario 5: Port Conflict (Qdrant)

**Error:**
```
Port 6333 already in use
```

**Test Steps:**
1. Start another service on port 6333
2. Run setup with full preset
3. Verify handling

**Expected Behavior:**
- Detects port conflict
- Suggests stopping conflicting service
- OR offers alternative port

**Recovery:**
```bash
# Find what's using port
lsof -i :6333

# Stop conflicting service or use different port
```

---

## Performance Benchmarks

### Installation Time Benchmarks

**Target Times:**

| Preset | Target | Acceptable Range |
|--------|--------|------------------|
| Minimal | 2 min | 1-3 min |
| Standard | 5 min | 3-7 min |
| Full | 10 min | 7-12 min |

**Factors Affecting Time:**
- Network speed (package downloads)
- CPU speed (Rust compilation)
- Disk speed (Docker image pull)
- System load

### Functionality Benchmarks

After installation, test these operations:

```bash
# 1. Index performance (should complete in <30s for 100 files)
time python -m src.cli index ~/test-projects/sample-code

# 2. Search latency (should be <50ms P95)
python scripts/benchmark_scale.py

# 3. Memory operations (should be <10ms avg)
time python -c "
from src.cli import health_command
import asyncio
asyncio.run(health_command.main())
"
```

---

## Test Results Template

### Test Environment

```
Date: __________
Tester: __________
OS: __________
Python Version: __________
Initial State: Clean / Existing Installation
```

### Minimal Preset Results

```
Installation Time: ______ minutes
Installation Success: YES / NO
Errors Encountered: ______________

Validation Results:
- Python version check: PASS / FAIL
- Dependencies installed: PASS / FAIL
- SQLite database: PASS / FAIL
- Python parser: PASS / FAIL
- Health check: PASS / FAIL
- Sample indexing: PASS / FAIL
- Search functionality: PASS / FAIL

Notes: ______________
```

### Standard Preset Results

```
Installation Time: ______ minutes
Installation Success: YES / NO
Rust Compilation Time: ______ minutes
Errors Encountered: ______________

Validation Results:
- Rust compilation: PASS / FAIL
- Rust parser loaded: PASS / FAIL
- Parsing performance: ______ ms/file
- All minimal checks: PASS / FAIL

Notes: ______________
```

### Full Preset Results

```
Installation Time: ______ minutes
Installation Success: YES / NO
Docker Setup Time: ______ minutes
Errors Encountered: ______________

Validation Results:
- Qdrant startup: PASS / FAIL
- Qdrant health: PASS / FAIL
- Vector search: PASS / FAIL
- Search P95 latency: ______ ms
- All standard checks: PASS / FAIL

Notes: ______________
```

### Overall Assessment

```
First Impression: Excellent / Good / Fair / Poor
Installation Friction: Low / Medium / High
Documentation Clarity: Clear / Adequate / Unclear
Error Messages: Helpful / Adequate / Confusing

Recommendations:
1. ______________
2. ______________
3. ______________

Critical Issues Found: ______________
```

---

## Automated Test Suite

Run all automated tests:

```bash
# Full test suite (requires clean environment)
./scripts/run_first_run_tests.sh

# Individual preset tests
./scripts/test_minimal_preset.sh
./scripts/test_standard_preset.sh
./scripts/test_full_preset.sh
```

---

## Continuous Testing

### CI/CD Integration

Add to GitHub Actions:

```yaml
name: First-Run Experience Tests

on: [push, pull_request]

jobs:
  test-minimal:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      - name: Test Minimal Preset
        run: |
          python scripts/validate_installation.py --preset minimal --automated
```

---

## Appendix: Success Metrics

### Installation Success Rate

**Target:** ≥90% success rate across all presets

**Tracking:**
- Number of successful installations / Total attempts
- By preset type
- By operating system
- By Python version

### Time to First Success

**Target:** Users can index and search within 15 minutes

**Measurement:**
- From `git clone` to successful search
- Includes setup, indexing, and first query

### User Satisfaction

**Target:** ≥4.0/5.0 average rating

**Survey Questions:**
1. How easy was installation? (1-5)
2. Were error messages helpful? (1-5)
3. How clear was documentation? (1-5)
4. Would you recommend to a colleague? (1-5)

---

**Document Version:** 1.0
**Testing Status:** Framework Ready
**Next Steps:** Execute tests on clean machines
**Last Updated:** November 18, 2025
