# E2E Testing Orchestration Guide
# Parallel Testing with Docker Agents

**Version:** 1.0
**Date:** 2025-11-20
**Purpose:** Run E2E tests in parallel using multiple Docker containers

---

## Overview

This orchestration system allows you to run the comprehensive E2E test plan (200+ tests) in parallel across 10 Docker containers, significantly reducing total test time.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Docker Compose Orchestrator                            │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  Agent 1 │  │  Agent 2 │  │  Agent N │  ...        │
│  │ Install  │  │ MCP-Mem  │  │ Quality  │             │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘             │
│       │             │             │                     │
│       └─────────────┼─────────────┘                     │
│                     │                                   │
│              ┌──────▼──────┐                            │
│              │   Qdrant    │  (Shared)                  │
│              └─────────────┘                            │
│                                                          │
│  ┌──────────────────────────────────────┐              │
│  │  Coordinator                          │              │
│  │  - Collects results from all agents  │              │
│  │  - Aggregates bugs                   │              │
│  │  - Generates final report            │              │
│  └──────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────┘
```

### Components

1. **10 Testing Agents** - Each runs a section of tests in parallel
2. **1 Shared Qdrant Instance** - All agents connect to same vector DB
3. **1 Coordinator** - Aggregates results and generates final report

### Test Distribution

| Agent | Section | Tests | Duration | Priority |
|-------|---------|-------|----------|----------|
| agent-install | Installation & Setup | 10 | 45 min | HIGH |
| agent-mcp-memory | MCP Memory Tools | 13 | 60 min | CRITICAL |
| agent-mcp-code | MCP Code Tools | 11 | 60 min | CRITICAL |
| agent-mcp-advanced | MCP Multi-Project | 11 | 45 min | HIGH |
| agent-cli-core | CLI Core Commands | 9 | 60 min | HIGH |
| agent-cli-management | CLI Management | 25 | 90 min | MEDIUM |
| agent-code-search | Code Search Tests | 14 | 90 min | CRITICAL |
| agent-features | Features Tests | 11 | 60 min | HIGH |
| agent-ui-config | UI/Config Tests | 20 | 90 min | MEDIUM |
| agent-quality | Quality Tests | 12 | 120 min | HIGH |

**Total:** 136 automated test scenarios (manual tests require human execution)

---

## Quick Start

### Prerequisites

```bash
# Required
- Docker Engine 20.10+
- Docker Compose 2.0+
- 16GB RAM (recommended)
- 20GB disk space

# Optional
- Docker Desktop (for UI)
```

### Run All Tests in Parallel

```bash
# Navigate to project root
cd /path/to/claude-memory-server

# Build and start all agents
docker-compose -f planning_docs/TEST-006_docker_compose.yml up --build

# Monitor progress
docker-compose -f planning_docs/TEST-006_docker_compose.yml logs -f

# Stop all containers
docker-compose -f planning_docs/TEST-006_docker_compose.yml down
```

### View Results

```bash
# Results are saved to ./results/
ls -la ./results/

# View final report
cat ./results/E2E_TEST_REPORT.md

# View JSON report
cat ./results/consolidated_report.json

# View individual agent results
ls ./results/agents/
```

---

## Detailed Usage

### 1. Running Specific Agents

Run only certain test sections:

```bash
# Run only installation tests
docker-compose -f planning_docs/TEST-006_docker_compose.yml up agent-install

# Run only MCP tools tests
docker-compose -f planning_docs/TEST-006_docker_compose.yml up \
  agent-mcp-memory \
  agent-mcp-code \
  agent-mcp-advanced

# Run critical tests only
docker-compose -f planning_docs/TEST-006_docker_compose.yml up \
  agent-mcp-memory \
  agent-mcp-code \
  agent-code-search
```

### 2. Wave-Based Execution

Execute tests in dependency order:

```bash
# Wave 1: Installation (blocking)
docker-compose -f planning_docs/TEST-006_docker_compose.yml up agent-install
# Wait for completion before next wave

# Wave 2: Core functionality (parallel)
docker-compose -f planning_docs/TEST-006_docker_compose.yml up \
  agent-mcp-memory \
  agent-mcp-code \
  agent-mcp-advanced \
  agent-cli-core \
  agent-cli-management \
  agent-code-search

# Wave 3: Advanced features (parallel)
docker-compose -f planning_docs/TEST-006_docker_compose.yml up \
  agent-features \
  agent-ui-config \
  agent-quality
```

### 3. Customizing Test Assignments

Edit `planning_docs/TEST-006_test_assignments.json`:

```json
{
  "test_sections": {
    "my-custom-section": {
      "agent": "agent-custom",
      "description": "Custom test section",
      "test_ids": ["TEST-001", "TEST-002"],
      "estimated_duration_minutes": 30,
      "priority": "high",
      "dependencies": []
    }
  }
}
```

Then add agent to `TEST-006_docker_compose.yml`:

```yaml
agent-custom:
  build:
    context: ..
    dockerfile: planning_docs/TEST-006_docker_agent.Dockerfile
  container_name: e2e-agent-custom
  depends_on:
    qdrant:
      condition: service_healthy
  environment:
    - AGENT_ID=agent-custom
    - TEST_SECTION=my-custom-section
  volumes:
    - ./TEST-006_test_assignments.json:/app/test_assignments.json:ro
    - agent_custom_results:/test_results
  command: ["python", "-m", "testing.orchestrator.agent", "--section", "my-custom-section"]
```

### 4. Debugging Failed Tests

```bash
# View logs for specific agent
docker-compose -f planning_docs/TEST-006_docker_compose.yml logs agent-mcp-memory

# Access agent container
docker-compose -f planning_docs/TEST-006_docker_compose.yml exec agent-mcp-memory /bin/bash

# View agent results
docker-compose -f planning_docs/TEST-006_docker_compose.yml exec agent-mcp-memory cat /test_results/agent-mcp-memory_results.json

# View agent logs
docker-compose -f planning_docs/TEST-006_docker_compose.yml exec agent-mcp-memory cat /test_logs/agent.log
```

### 5. Re-running Failed Agents

```bash
# Restart specific agent
docker-compose -f planning_docs/TEST-006_docker_compose.yml restart agent-mcp-memory

# Rebuild and restart
docker-compose -f planning_docs/TEST-006_docker_compose.yml up --build agent-mcp-memory
```

---

## Understanding Results

### Final Report Structure

```
results/
├── E2E_TEST_REPORT.md              # Human-readable summary
├── consolidated_report.json         # Machine-readable full report
└── agents/
    ├── agent-install_results.json
    ├── agent-mcp-memory_results.json
    ├── agent-mcp-code_results.json
    └── ...
```

### Result Schema

Each agent produces results in this format:

```json
{
  "agent_id": "agent-mcp-memory",
  "section": "mcp-memory",
  "start_time": "2025-11-20T10:00:00",
  "end_time": "2025-11-20T11:00:00",
  "tests": [
    {
      "test_id": "MCP-001",
      "status": "PASS|FAIL|SKIPPED|MANUAL_REQUIRED",
      "start_time": "...",
      "end_time": "...",
      "notes": "...",
      "bugs_found": []
    }
  ],
  "bugs_found": [
    {
      "id": "BUG-XXX",
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "description": "...",
      "test_id": "...",
      "impact": "..."
    }
  ],
  "summary": {
    "total_tests": 13,
    "passed": 10,
    "failed": 2,
    "skipped": 1,
    "manual_required": 0,
    "pass_rate": 76.9,
    "bugs_found": 2
  }
}
```

### Production Readiness Criteria

The coordinator assesses production readiness:

```json
{
  "production_readiness": {
    "ready": true|false,
    "criteria": {
      "zero_critical_bugs": true|false,
      "max_3_high_bugs": true|false,
      "pass_rate_above_95": true|false,
      "zero_failures": true|false
    },
    "recommendation": "✅ READY FOR PRODUCTION"
  }
}
```

**Criteria:**
- ✅ Zero critical bugs
- ✅ ≤ 3 high-priority bugs
- ✅ ≥ 95% pass rate
- ✅ Zero test failures

---

## Integration with Manual Testing

### Current Limitation

The orchestration system provides **infrastructure** but tests currently require **manual execution**.

Each agent's `run_single_test()` method is a placeholder that:
1. Marks test as `MANUAL_REQUIRED`
2. Points to `TEST-006_e2e_test_plan.md` for manual execution

### Future: Automated Test Execution

To fully automate tests, implement test runners for each test ID:

```python
# testing/orchestrator/test_runners.py

def run_test_MCP_001(agent):
    """Run MCP-001: Store a simple preference memory"""
    # 1. Call store_memory MCP tool
    # 2. Verify response
    # 3. Return result
    pass

def run_test_MCP_004(agent):
    """Run MCP-004: Retrieve recently stored memory"""
    # 1. Store a memory
    # 2. Immediately retrieve
    # 3. Verify high relevance score
    # 4. Check for BUG-018
    pass
```

Then update `agent.py`:

```python
from testing.orchestrator import test_runners

def run_single_test(self, test_id: str):
    runner = getattr(test_runners, f'run_test_{test_id.replace("-", "_")}', None)
    if runner:
        return runner(self)
    else:
        return {'status': 'MANUAL_REQUIRED', ...}
```

### Hybrid Approach (Recommended)

For now, use the orchestration system to:

1. **Provision environments** - Each agent gets clean Docker container
2. **Run automated checks** - Health checks, setup validation, etc.
3. **Execute manual tests** - Human testers work within each container
4. **Log results** - Agents save results in standard format
5. **Aggregate** - Coordinator collects all results

**Workflow:**

```bash
# 1. Start all agents
docker-compose -f planning_docs/TEST-006_docker_compose.yml up -d

# 2. Access agent containers for manual testing
docker exec -it e2e-agent-mcp-memory /bin/bash

# 3. Within container, execute tests from TEST-006_e2e_test_plan.md
# 4. Log results to /test_results/manual_results.json

# 5. When done, aggregate
docker-compose -f planning_docs/TEST-006_docker_compose.yml up orchestrator
```

---

## Performance Optimization

### Parallel Execution

Running all 10 agents in parallel:
- **Sequential time:** ~12 hours (all tests manually)
- **Parallel time:** ~2 hours (longest agent: agent-quality at 120 min)
- **Speedup:** 6x faster

### Resource Requirements

**Per Agent:**
- CPU: 1 core
- Memory: 1-2 GB
- Disk: 2 GB

**Total (10 agents + Qdrant):**
- CPU: 11 cores (recommend 8+ core system)
- Memory: 16 GB
- Disk: 25 GB

### Scaling Up/Down

Adjust parallel agents based on available resources:

```bash
# Run fewer agents (4 cores, 8GB RAM)
docker-compose -f planning_docs/TEST-006_docker_compose.yml up \
  agent-install \
  agent-mcp-memory \
  agent-mcp-code \
  agent-code-search

# Run more agents (32 cores, 64GB RAM)
# Split sections further for finer granularity
```

---

## Troubleshooting

### Qdrant Connection Issues

**Symptom:** Agents can't connect to Qdrant

**Solution:**
```bash
# Check Qdrant health
docker-compose -f planning_docs/TEST-006_docker_compose.yml exec qdrant curl http://localhost:6333/

# Restart Qdrant
docker-compose -f planning_docs/TEST-006_docker_compose.yml restart qdrant

# Check agent environment
docker-compose -f planning_docs/TEST-006_docker_compose.yml exec agent-mcp-memory env | grep QDRANT
```

### Build Failures

**Symptom:** Docker build fails

**Solution:**
```bash
# Clear Docker cache
docker-compose -f planning_docs/TEST-006_docker_compose.yml build --no-cache

# Check Dockerfile syntax
docker build -f planning_docs/TEST-006_docker_agent.Dockerfile .

# View build logs
docker-compose -f planning_docs/TEST-006_docker_compose.yml build 2>&1 | tee build.log
```

### Out of Memory

**Symptom:** Containers killed by OOM

**Solution:**
```bash
# Increase Docker memory limit (Docker Desktop)
# Settings > Resources > Memory: 16GB+

# Or run fewer agents at once
docker-compose -f planning_docs/TEST-006_docker_compose.yml up \
  --scale agent-mcp-memory=1 \
  --scale agent-mcp-code=0
```

### Agent Hangs

**Symptom:** Agent doesn't complete

**Solution:**
```bash
# Check agent logs
docker-compose -f planning_docs/TEST-006_docker_compose.yml logs -f agent-mcp-memory

# Access container
docker exec -it e2e-agent-mcp-memory /bin/bash

# Kill and restart
docker-compose -f planning_docs/TEST-006_docker_compose.yml restart agent-mcp-memory
```

---

## Best Practices

### 1. Clean Slate Testing

Always start with clean containers:

```bash
# Remove old containers and volumes
docker-compose -f planning_docs/TEST-006_docker_compose.yml down -v

# Rebuild from scratch
docker-compose -f planning_docs/TEST-006_docker_compose.yml up --build
```

### 2. Isolated Testing

Each agent should be independent:
- ✅ Use unique project names per agent
- ✅ Avoid shared state between agents
- ✅ Clean up after each test

### 3. Comprehensive Logging

Enable detailed logging:

```yaml
environment:
  - LOG_LEVEL=DEBUG
  - PYTHONUNBUFFERED=1
```

### 4. Result Preservation

Save results before teardown:

```bash
# Copy results out of containers
docker cp e2e-agent-mcp-memory:/test_results ./backup/

# Or use volumes (already configured)
```

### 5. Continuous Integration

Integrate with CI/CD:

```yaml
# .github/workflows/e2e-tests.yml
name: E2E Tests
on: [push]
jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run E2E tests
        run: |
          docker-compose -f planning_docs/TEST-006_docker_compose.yml up --abort-on-container-exit
      - name: Upload results
        uses: actions/upload-artifact@v2
        with:
          name: e2e-results
          path: ./results/
```

---

## Next Steps

### Phase 1: Manual Testing with Orchestration (Current)
- ✅ Infrastructure ready
- ⏳ Execute tests manually within containers
- ⏳ Log results using agent framework

### Phase 2: Semi-Automated Testing
- Automate setup/health checks
- Automate simple PASS/FAIL tests
- Keep UX/quality tests manual

### Phase 3: Fully Automated Testing
- Implement all test runners
- Integrate with CI/CD
- Scheduled nightly runs

---

## Files Reference

All orchestration files in `planning_docs/`:

- `TEST-006_docker_agent.Dockerfile` - Agent container definition
- `TEST-006_docker_compose.yml` - Multi-agent orchestration
- `TEST-006_test_assignments.json` - Test distribution config
- `TEST-006_orchestration_guide.md` - This file

Agent code in `testing/orchestrator/`:

- `__init__.py` - Module initialization
- `agent.py` - Individual test agent
- `coordinator.py` - Result aggregation
- `test_runners.py` - (Future) Automated test implementations

---

## Support

**Questions?**
- Check `TEST-006_e2e_testing_guide.md` for manual testing guidance
- Check `TEST-006_e2e_test_plan.md` for test scenarios
- Check `TEST-006_e2e_bug_tracker.md` for known bugs

**Issues?**
- File bugs in `TEST-006_e2e_bug_tracker.md`
- Use BUG-XXX format for tracking
- Include agent ID in bug reports

---

**Happy Testing! 🚀**
