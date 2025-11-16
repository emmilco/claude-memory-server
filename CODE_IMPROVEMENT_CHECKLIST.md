# Implementation Tracking Checklist: Claude Code Local Performance Server

**Target:** Achieve high-performance, context-aware memory services in a local, individual developer environment.

---

## Phase 0: Foundation & Migration (F/M)
**Goal:** Establish Python/Rust core and Qdrant local database connection.

| Status | ID | Task Description |
|---|---|---|
| [ ] | F/M 0.1 | Rewrite core TypeScript server logic into Python using the Python MCP SDK. |
| [ ] | F/M 0.2 | Implement scripts/instructions for local Qdrant setup (Docker or binary). |
| [ ] | F/M 0.3 | Implement the `QdrantMemoryStore` Python class for all vector database interactions. |
| [ ] | F/M 0.4 | Set up the Python-to-Rust bridge (`PyO3`) for performance-critical components. |
| [ ] | F/M 0.5 | Integrate high-speed embedding generation engine (local model or Rust component). |

---

## Phase 1: Performance, Security, and Context Segregation (P/S/C)
**Goal:** Secure the system and implement Multi-Level Memory for efficiency.

| Status | ID | Task Description |
|---|---|---|
| [ ] | P/S/C 1.1 | Fully migrate all `Store` and `Find` operations to Qdrant, replacing all SQLite/FTS5 logic. |
| [ ] | P/S/C 1.2 | Implement strict Pydantic and allow-list validation on all input payloads (Enhanced Security I-3). |
| [ ] | P/S/C 1.3 | Implement `--read-only` CLI flag and logic for restricted database access (Enhanced Security I-3). |
| [ ] | P/S/C 1.4 | Augment the `MemoryUnit` schema with the mandatory `context_level` field (Multi-Level Memory I-2). |
| [ ] | P/S/C 1.5 | Define and expose new MCP tools (e.g., `RetrievePreferences`) that enforce context-level filters (Multi-Level Memory I-2). |

---

## Phase 2: Code Intelligence and Automation (C/A)
**Goal:** Implement Code Structure Awareness using Rust and establish zero-friction context ingestion.

| Status | ID | Task Description |
|---|---|---|
| [ ] | C/A 2.1 | Implement core Rust parser (`tree-sitter`) for semantic unit chunking (Code Indexing II-1). |
| [ ] | C/A 2.2 | Implement Rust logic to extract and serialize structural metadata (signatures, dependencies) (Code Indexing II-1). |
| [ ] | C/A 2.3 | Implement Python logic for file delta tracking and incremental indexing updates (Code Indexing II-1). |
| [ ] | C/A 2.4 | Implement the `mcp-server index <path>` manual CLI command (Index Automation II-2). |
| [ ] | C/A 2.5 | Implement the optional file watcher daemon to automatically trigger incremental indexing on file save events (Index Automation II-2). |

---

## Phase 3: Adaptive Efficiency (A/E)
**Goal:** Integrate the Selective Retrieval gate to save tokens and latency.

| Status | ID | Task Description |
|---|---|---|
| [ ] | A/E 3.1 | Implement the lightweight heuristic or classification model for context utility prediction (Selective Retrieval II-3). |
| [ ] | A/E 3.2 | Modify the `Memory.Find` API to run the prediction model and skip Qdrant search if utility is low (Retrieval Gating II-3). |
| [ ] | A/E 3.3 | Finalize installation, deployment, and API documentation for all Python and Rust components. |
```