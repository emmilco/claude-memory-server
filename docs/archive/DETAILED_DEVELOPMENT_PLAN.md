# Detailed Technical Development Plan
## Claude Code Local Performance Server (Python/Rust Hybrid)

**Version:** 2.0 (Machine-Executable)  
**Last Updated:** November 15, 2025  
**Status:** Ready for Implementation

---

## Executive Summary

This document provides a detailed, machine-executable development plan for transforming the current TypeScript MCP memory server into a high-performance Python/Rust hybrid system. The plan is organized into 3 phases with 15 specific, actionable deliverables, each with:
- Exact file paths and structures
- Complete code snippets where applicable
- Testable success criteria
- Dependency tracking and sequencing
- Time estimates in weeks

---

## Phase 1: Foundation & Migration (Weeks 1-4)

### Phase 1 Overview
Establish Python/Rust core, implement Qdrant local vector database, and create performance bridge.

**Phase 1 Completion Criteria:**
- Server starts and responds to MCP requests
- All core APIs work with Python SDK
- Qdrant collection initialized and queryable
- Rust bridge compiles (even if not all features implemented)
- All Phase 1 tests pass (>90% coverage)

---

## Phase 1.0: Core Server Architecture Refactoring

### Task 1.0.1: Create Modular Python Structure
**File:** `src/core/server.py` (NEW), `src/core/models.py` (NEW), `src/config.py` (NEW)  
**Time:** 1.5 weeks  
**Dependencies:** None  
**Success Criteria:**
- Server starts without errors
- All MCP tools registered and callable
- Configuration loads from env and file

**Implementation Steps:**
```bash
# 1. Create directory structure
mkdir -p src/core src/store src/embeddings src/memory src/doc_ingestion src/router

# 2. Create config.py
cat > src/config.py << 'EOF'
from pydantic_settings import BaseSettings
from typing import Optional, Literal

class ServerConfig(BaseSettings):
    # Core settings
    server_name: str = "claude-memory-rag"
    log_level: str = "INFO"
    
    # Storage backend selection
    storage_backend: Literal["sqlite", "qdrant"] = "qdrant"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    sqlite_path: str = "~/.claude-rag/memory.db"
    
    # Performance tuning
    embedding_batch_size: int = 32
    max_query_context_tokens: int = 8000
    retrieval_timeout_ms: int = 500
    
    # Security
    read_only_mode: bool = False
    enable_input_validation: bool = True
    
    # Code indexing
    enable_file_watcher: bool = True
    watch_debounce_ms: int = 1000
    
    class Config:
        env_prefix = "CLAUDE_RAG_"
        env_file = ".env"
EOF

# 3. Create core/models.py with Pydantic schemas
# (Full code in separate detailed schema document)

# 4. Update mcp_server.py to use new structure
```

**Test Script:**
```python
# tests/test_core_server.py
import pytest
from src.config import ServerConfig
from src.core.server import MemoryRAGServer

def test_server_initialization():
    config = ServerConfig()
    server = MemoryRAGServer(config)
    assert server is not None

def test_config_from_env(monkeypatch):
    monkeypatch.setenv("CLAUDE_RAG_LOG_LEVEL", "DEBUG")
    config = ServerConfig()
    assert config.log_level == "DEBUG"
```

---

### Task 1.0.2: Implement Pydantic Validation Models
**File:** `src/core/models.py` (NEW)  
**Time:** 1 week  
**Dependencies:** Task 1.0.1  

**Key Models to Implement:**
- `MemoryUnit`: Core memory record
- `StoreMemoryRequest`: Store endpoint input
- `QueryRequest`: Query endpoint input
- `RetrievalResponse`: Query endpoint output
- `ContextLevel`: Enum for context stratification
- `ProjectContext`: Project-specific isolation

**Example (MemoryUnit):**
```python
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum
from typing import List, Optional

class ContextLevel(str, Enum):
    USER_PREFERENCE = "USER_PREFERENCE"
    PROJECT_CONTEXT = "PROJECT_CONTEXT"
    SESSION_STATE = "SESSION_STATE"

class MemoryUnit(BaseModel):
    id: str
    content: str
    category: str
    context_level: ContextLevel
    scope: str  # "global" or "project"
    project_name: Optional[str] = None
    importance: float = Field(0.5, ge=0.0, le=1.0)
    embedding_model: str = "all-mpnet-base-v2"
    created_at: datetime
    updated_at: datetime
    tags: Optional[List[str]] = []
    
    class Config:
        use_enum_values = False
```

**Test Cases:**
```python
# tests/test_models.py
def test_memory_unit_validation():
    unit = MemoryUnit(
        id="1",
        content="test",
        category="fact",
        context_level=ContextLevel.PROJECT_CONTEXT,
        scope="project",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    assert unit.content == "test"
    assert unit.importance == 0.5
```

---

## Phase 1.1: Qdrant Setup and Integration

### Task 1.1.1: Docker Compose Configuration
**File:** `docker-compose.yml` (NEW)  
**Time:** 0.5 weeks  
**Dependencies:** None  

**Implementation:**
```yaml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant-memory
    ports:
      - "6333:6333"
    environment:
      QDRANT_API_KEY: "${QDRANT_API_KEY:-development}"
    volumes:
      - qdrant_storage:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 5s
      timeout: 10s
      retries: 5
    restart: unless-stopped

volumes:
  qdrant_storage:
    driver: local
```

**Verification:**
```bash
# Start Qdrant
docker-compose up -d

# Verify health
curl http://localhost:6333/health

# Should return: {"status":"ok"}
```

---

### Task 1.1.2: Collection Initialization
**File:** `src/store/qdrant_setup.py` (NEW)  
**Time:** 1 week  
**Dependencies:** Task 1.1.1  
**Success Criteria:**
- Collection created with correct schema
- Payload indices created for filtering
- Health check passes

**Implementation Outline:**
1. Define collection configuration with HNSW parameters
2. Create payload indices for: category, context_level, project_name, scope
3. Test: Insert sample vector, retrieve, verify

**Key Parameters:**
```python
collection_config = {
    "vectors": {
        "size": 384,  # all-mpnet-base-v2 dimension
        "distance": "Cosine"
    },
    "hnsw": {
        "m": 16,
        "ef_construct": 200,
        "full_scan_threshold": 2000
    },
    "quantization": {
        "type": "int8",  # 75% memory savings
    }
}
```

---

### Task 1.1.3: Abstract Store Interface
**File:** `src/store/base.py` (NEW)  
**Time:** 0.5 weeks  
**Dependencies:** Task 1.0.2  

**Interface Methods:**
- `async store(content, embedding, metadata) -> str`
- `async retrieve(query_embedding, filters, limit) -> List[Tuple]`
- `async delete(memory_id) -> bool`
- `async batch_store(items) -> List[str]`
- `async search_with_filters(query_embedding, filters, limit) -> List[Tuple]`

---

### Task 1.1.4: Qdrant Implementation
**File:** `src/store/qdrant_store.py` (NEW)  
**Time:** 1.5 weeks  
**Dependencies:** Tasks 1.1.2, 1.1.3  
**Success Criteria:**
- All interface methods implemented
- Query latency <50ms for 1000 docs
- Batch operations 5x faster than sequential

**Validation Tests:**
```python
# tests/test_qdrant_store.py
@pytest.mark.asyncio
async def test_qdrant_store_basic():
    store = QdrantMemoryStore()
    
    # Store a memory
    memory_id = await store.store(
        content="Test memory",
        embedding=[0.1] * 384,
        metadata={"category": "test"}
    )
    assert memory_id is not None
    
    # Retrieve it
    results = await store.retrieve(
        query_embedding=[0.1] * 384,
        limit=1
    )
    assert len(results) > 0
```

---

### Task 1.1.5: Migration Utility
**File:** `src/store/migration.py` (NEW)  
**Time:** 1 week  
**Dependencies:** Tasks 1.0.1, 1.1.4, existing SQLite store  
**Success Criteria:**
- 100% data integrity after migration
- Dual-write validation passes
- Rollback capability

**Features:**
- Read all memories from SQLite
- Batch insert to Qdrant
- Validate consistency
- Support rollback to SQLite
- Progress reporting

**CLI Command:**
```bash
python -m src.store.migration \
  --source sqlite \
  --source-path ~/.claude-rag/memory.db \
  --target qdrant \
  --target-url http://localhost:6333 \
  --validate
```

---

## Phase 1.2: Rust/Python Bridge

### Task 1.2.1: Rust Project Setup
**File:** `rust_core/` (NEW)  
**Time:** 1 week  
**Dependencies:** None (parallel to Phase 1.0)  

**Setup Commands:**
```bash
# Create Rust project structure
cargo new --lib rust_core
cd rust_core

# Update Cargo.toml with PyO3
cat >> Cargo.toml << 'EOF'
[dependencies]
pyo3 = { version = "0.21", features = ["extension-module"] }
ndarray = "0.15"

[profile.release]
opt-level = 3
lto = true
EOF
```

**Test Compilation:**
```bash
cd rust_core
cargo build --release
# Should complete without errors
```

---

### Task 1.2.2: Basic Rust Functions
**File:** `rust_core/src/lib.rs` (NEW)  
**Time:** 1 week  
**Dependencies:** Task 1.2.1  

**Functions to Implement:**
1. `batch_normalize_embeddings(Vec<Vec<f32>>) -> Vec<Vec<f32>>`
2. `cosine_similarity(Vec<f32>, Vec<f32>) -> f32`

**Example:**
```rust
use pyo3::prelude::*;

#[pyfunction]
pub fn batch_normalize_embeddings(embeddings: Vec<Vec<f32>>) -> PyResult<Vec<Vec<f32>>> {
    Ok(embeddings.iter().map(|emb| {
        let norm: f32 = emb.iter().map(|x| x * x).sum::<f32>().sqrt();
        emb.iter().map(|x| if norm > 0.0 { x / norm } else { 0.0 }).collect()
    }).collect())
}

#[pymodule]
fn mcp_performance_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(batch_normalize_embeddings, m)?)?;
    Ok(())
}
```

---

### Task 1.2.3: Python Wrapper
**File:** `src/embeddings/rust_bridge.py` (NEW)  
**Time:** 0.5 weeks  
**Dependencies:** Task 1.2.2  

**Wrapper Pattern:**
```python
try:
    from mcp_performance_core import batch_normalize_embeddings
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False

class RustBridge:
    @staticmethod
    def batch_normalize(embeddings):
        if RUST_AVAILABLE:
            return batch_normalize_embeddings(embeddings)
        else:
            return [normalize_python(e) for e in embeddings]
```

---

## Phase 1.3: Embedding Engine

### Task 1.3.1: Embedding Generator
**File:** `src/embeddings/generator.py` (REFACTOR)  
**Time:** 1 week  
**Dependencies:** Tasks 1.2.3, Phase 1.0  

**Key Features:**
- Async embedding generation
- Batch processing with configurable sizes
- Model selection (MiniLM-L6, MiniLM-L12, MPNet)
- CPU-only mode for consistency
- Thread pool execution

**Success Criteria:**
- Single embedding: <50ms on CPU
- Batch (32 docs): <1.5s on CPU
- Memory usage <2GB for typical workloads

---

### Task 1.3.2: Embedding Cache
**File:** `src/embeddings/cache.py` (NEW)  
**Time:** 0.5 weeks  
**Dependencies:** Task 1.3.1  

**Features:**
- SQLite cache database
- SHA256-based key lookup
- Automatic expiration (30 days default)
- Cache hit statistics

**Expected Improvement:**
- 90% cache hit rate on repeated queries
- 10x faster retrieval from cache vs. generation

---

## Phase 2: Security & Context Stratification (Weeks 5-8)

### Phase 2 Overview
Implement security hardening and multi-level memory model.

---

## Phase 2.1: Security Hardening

### Task 2.1.1: Input Validation & Sanitization
**File:** `src/core/validation.py` (NEW)  
**Time:** 1 week  
**Dependencies:** Task 1.0.2  

**Validation Layers:**
1. Schema validation (Pydantic)
2. Allowlist field validation
3. Content pattern detection (regex)
4. Size limits enforcement
5. SQL/prompt injection detection

**SQL Injection Test Cases:**
```python
dangerous_inputs = [
    "'; DROP TABLE memories; --",
    "UNION SELECT * FROM passwords",
    "1' OR '1'='1",
]

for inp in dangerous_inputs:
    with pytest.raises(ValidationError):
        StoreMemoryRequest(content=inp, category="test")
```

---

### Task 2.1.2: Read-Only Mode Implementation
**File:** `src/store/readonly_wrapper.py` (NEW)  
**Time:** 0.5 weeks  
**Dependencies:** Task 1.1.3  

**Wrapper Pattern:**
- Wraps any MemoryStore implementation
- Blocks all write operations
- Passes through read operations
- Raises clear errors on write attempts

**CLI Integration:**
```bash
python -m src.mcp_server --read-only
```

---

### Task 2.1.3: Security Logging
**File:** `src/core/security_logger.py` (NEW)  
**Time:** 0.5 weeks  
**Dependencies:** Task 2.1.1  

**Log Events:**
- Validation failures
- SQL injection attempts
- Suspicious patterns detected
- Read-only mode violations
- Unauthorized access attempts

**Log Location:** `~/.claude-rag/security.log`

---

## Phase 2.2: Context Stratification

### Task 2.2.1: Context Level Enhancement
**File:** `src/core/models.py` (ENHANCE)  
**Time:** 1 week  
**Dependencies:** Task 1.0.2  

**Add to MemoryUnit:**
```python
context_level: ContextLevel  # USER_PREFERENCE, PROJECT_CONTEXT, SESSION_STATE
```

**Auto-Classification Logic:**
```python
class ContextLevelClassifier:
    def classify(self, content: str, category: str) -> ContextLevel:
        # Pattern matching logic
        # Returns appropriate ContextLevel enum
```

---

### Task 2.2.2: Specialized Retrieval Tools
**File:** `src/core/tools.py` (NEW)  
**Time:** 1 week  
**Dependencies:** Task 2.2.1  

**New MCP Tools:**
1. `retrieve_preferences(query, limit=5)`
   - Returns USER_PREFERENCE memories only
   - Used for style/preference queries

2. `retrieve_project_context(query, limit=5)`
   - Returns PROJECT_CONTEXT memories only
   - Optionally filtered by project_name

3. `retrieve_session_state(query, limit=3)`
   - Returns SESSION_STATE memories only
   - Sorted by recency

**Claude API Integration:**
```json
{
  "name": "retrieve_preferences",
  "description": "Retrieve user preferences and coding style guidelines",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {"type": "string"},
      "limit": {"type": "integer", "default": 5}
    }
  }
}
```

---

## Phase 3: Code Intelligence & Automation (Weeks 9-13)

### Phase 3 Overview
Implement AST parsing, code indexing, and adaptive retrieval.

---

## Phase 3.1: Code Parsing

### Task 3.1.1: Rust Tree-Sitter Integration
**File:** `rust_core/src/parsing.rs` (NEW)  
**Time:** 2 weeks  
**Dependencies:** Task 1.2.1  

**Supported Languages:**
- Python
- JavaScript/TypeScript
- Java
- Go
- Rust

**Extraction Logic:**
For each language, extract:
- Function/method signatures
- Class definitions
- Import statements
- Call graph information

**Performance Target:**
- Parse 1000 files in <30 seconds
- Extract 50K+ semantic units efficiently

---

### Task 3.1.2: Semantic Unit Chunking
**File:** `src/memory/semantic_chunking.py` (NEW)  
**Time:** 1 week  
**Dependencies:** Task 3.1.1  

**Unit Types:**
1. Functions (with signatures)
2. Classes (with methods)
3. Documentation blocks
4. Configuration blocks

**Metadata Per Unit:**
```python
{
    "type": "function",
    "name": "authenticate",
    "file_path": "auth.py",
    "language": "python",
    "start_line": 42,
    "end_line": 65,
    "dependencies": ["validate_token", "hash_password"],
    "signature": "def authenticate(username: str, password: str) -> bool:"
}
```

---

### Task 3.1.3: Incremental Indexing
**File:** `src/memory/incremental_indexer.py` (NEW)  
**Time:** 1 week  
**Dependencies:** Tasks 3.1.1, 3.1.2  

**Algorithm:**
1. Hash all files in project
2. Compare with previous hash
3. Process only changed files
4. Update Qdrant with new/modified units
5. Remove deleted units

**Performance Characteristics:**
- Cold index (first run): ~5-10s for 100 files
- Incremental update (1 file changed): <1s
- Debounce: 1000ms to avoid constant updates

---

### Task 3.1.4: File Watcher Service
**File:** `src/memory/file_watcher.py` (NEW)  
**Time:** 1 week  
**Dependencies:** Task 3.1.3  

**Implementation:**
- Use `watchdog` library for file system events
- Debounce rapid changes
- Async operation to avoid blocking
- Graceful startup/shutdown

**Configuration:**
```python
enable_file_watcher: bool = True  # Enable via config
watch_debounce_ms: int = 1000      # Debounce delay
```

---

## Phase 3.2: CLI Commands

### Task 3.2.1: Index Command
**File:** `src/cli/index_command.py` (NEW)  
**Time:** 0.5 weeks  
**Dependencies:** Tasks 3.1.3, 3.1.4  

**Command:**
```bash
python -m src.cli index /path/to/project [--debounce 1000]
```

**Output:**
```
Indexing /path/to/project...
  Python files: 45
  JS files: 12
  Semantic units found: 234
  New units: 198
  Updated units: 36
  Time: 8.3s
```

---

## Phase 3.3: Adaptive Retrieval Gate

### Task 3.3.1: Retrieval Prediction Model
**File:** `src/router/retrieval_predictor.py` (NEW)  
**Time:** 2 weeks  
**Dependencies:** Phase 2 completion  

**Model Type:**
- Lightweight heuristic (not ML model initially)
- Rule-based: query type → probability of benefit
- Trained on usage patterns (optional ML layer)

**Rules:**
```python
# Pseudo-code
rules = {
    "is_coding_question": 0.9,           # "How do I implement X?"
    "is_syntax_question": 0.85,          # "What's the syntax for Y?"
    "is_architecture_question": 0.8,     # "How does Z work?"
    "is_preference_query": 0.95,         # "What do I prefer?"
    "is_small_talk": 0.1,                # "Hi, how are you?"
    "is_general_knowledge": 0.3,         # "What is Python?"
}
```

**Performance:**
- Prediction time: <5ms
- Accuracy: >80% on held-out test set

---

### Task 3.3.2: Retrieval Gating Logic
**File:** `src/router/retrieval_gate.py` (NEW)  
**Time:** 1 week  
**Dependencies:** Task 3.3.1  

**Integration Points:**
1. Intercept `retrieve_*` tool calls
2. Run prediction model
3. If utility score < threshold (80%), skip Qdrant search
4. Return empty results

**Expected Savings:**
- 30-40% of queries skipped
- 70% latency improvement on skipped queries
- 40% token savings overall

---

## Phase 4: Documentation & Testing (Weeks 14-15)

### Task 4.1: Comprehensive Test Suite
**File:** `tests/` (ENHANCE)  
**Time:** 1 week  
**Dependencies:** All previous phases  

**Test Coverage Targets:**
- Unit tests: >85% coverage
- Integration tests: All major workflows
- Performance tests: Latency/throughput benchmarks
- Security tests: 50+ injection attack scenarios

**Test Categories:**
```
tests/
├── unit/
│   ├── test_models.py
│   ├── test_store.py
│   ├── test_embeddings.py
│   ├── test_validation.py
│   └── test_tools.py
├── integration/
│   ├── test_e2e_store_retrieve.py
│   ├── test_e2e_indexing.py
│   └── test_e2e_security.py
├── performance/
│   ├── benchmark_embeddings.py
│   ├── benchmark_retrieval.py
│   └── benchmark_indexing.py
└── security/
    ├── test_injection_attacks.py
    ├── test_readonly_mode.py
    └── test_access_control.py
```

---

### Task 4.2: Documentation
**File:** `docs/` (NEW)  
**Time:** 1 week  
**Dependencies:** All previous phases  

**Documentation Structure:**
```
docs/
├── ARCHITECTURE.md          # System design
├── API.md                   # API reference
├── SETUP.md                 # Installation guide
├── USAGE.md                 # User guide
├── DEVELOPMENT.md           # Development guide
├── SECURITY.md              # Security model
├── PERFORMANCE.md           # Benchmarks
└── TROUBLESHOOTING.md       # Common issues
```

---

## Dependency Graph & Execution Order

```
Phase 1.0.1 (Config) → 1.0.2 (Models)
                    ↓
            1.0.1, 1.0.2 → 1.1.3 (Store Interface)
                              ↓
            1.1.1 (Docker) → 1.1.2 (Qdrant) → 1.1.4 (Impl) → 1.1.5 (Migration)
                                                    ↑
                                            1.1.3, 1.1.4
            
1.2.1 (Rust) → 1.2.2 (Rust funcs) → 1.2.3 (Wrapper)
                                           ↓
                                     1.3.1 (Generator)
                                           ↓
                                     1.3.2 (Cache)
            
Phase 1 Complete → 2.1.1 (Validation) → 2.1.2 (ReadOnly) → 2.1.3 (Logger)
                ↓
                2.2.1 (Context) → 2.2.2 (Tools)
                
Phase 2 Complete → 3.1.1 (Parsing) → 3.1.2 (Chunking) → 3.1.3 (Incremental) → 3.1.4 (Watcher)
                ↓
                3.2.1 (CLI Index)
                
                3.3.1 (Predictor) → 3.3.2 (Gate)
                
Phase 3 Complete → 4.1 (Tests), 4.2 (Docs)
```

---

## Success Metrics

### Performance Targets
- Embedding generation: 100+ docs/sec
- Query latency: <50ms for 10K documents
- Indexing: 1000 files in <30 seconds
- Memory overhead: <2GB for typical workloads

### Reliability Targets
- 99.9% uptime (after Phase 1)
- Zero data loss during migration
- Graceful degradation when Qdrant unavailable

### Security Targets
- 100% input validation
- Zero SQL injection vulnerabilities
- All write operations blocked in read-only mode
- Security logging for audit trail

---

## Tools & Technologies

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.8+ |
| MCP SDK | mcp | 0.9+ |
| Vector DB | Qdrant | Latest |
| ORM | Pydantic | 2.0+ |
| Embeddings | sentence-transformers | 2.2+ |
| Rust Bridge | PyO3 | 0.21+ |
| Code Parsing | tree-sitter | 0.20+ |
| File Watching | watchdog | 3.0+ |
| Testing | pytest | 7.0+ |
| Docker | Docker Engine | 20.10+ |

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Qdrant unavailable | Fallback to SQLite, automatic retry |
| Rust compilation fails | Pure Python fallbacks for all Rust functions |
| Large file ingestion | Chunking + batch processing + progress reporting |
| Injection attacks | Multi-layer validation + allowlist + security logging |
| Embedding cache miss | Fallback to online generation |
| Migration data loss | Dual-write validation + rollback capability |

---

## Rollout Strategy

1. **Phase 1 (4 weeks):** Deploy to internal testing with read-only SQLite fallback
2. **Phase 2 (3 weeks):** Enable Qdrant in production, keep SQLite for fallback
3. **Phase 3 (5 weeks):** Enable code indexing for opt-in users
4. **Final (1 week):** Full rollout with adaptive retrieval

---

## Appendices

### A. Required Packages
```
# requirements.txt
anthropic>=0.18.0
sentence-transformers>=2.2.0
numpy>=1.24.0
mcp>=0.9.0
python-dotenv>=1.0.0
markdown>=3.4.0
qdrant-client>=2.7.0
watchdog>=3.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
```

### B. Python Version & Dependencies
- Python 3.8+: Core application
- PyO3 0.21+: Rust bridge
- sentence-transformers 2.2+: Embeddings
- qdrant-client 2.7+: Vector DB client

---

**Document Complete**
