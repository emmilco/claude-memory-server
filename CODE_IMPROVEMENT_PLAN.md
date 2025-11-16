# Implementation Plan: Claude Code Local Performance Server (Python/Rust Hybrid)

**Project Goal:** Rewrite the existing MCP memory server in a Python/Rust hybrid architecture to optimize for local performance, code-awareness, and efficient context delivery, adhering strictly to the individual, local-first mandate.

**Target Stack:** Python (Application Logic, MCP Integration), Rust (Performance-Critical Modules, AST Parsing), Qdrant (Dedicated Local Vector Database), PyO3 (Python-Rust Bridge).

---

## Phase 0: Foundational Architecture & Language Migration

This phase establishes the new language foundation, sets up the local high-performance database, and creates the inter-language performance bridge.

| ID | Component | Language | Implementation Details | Rationale / Citation |
|---|---|---|---|---|
| **0.1** | **Core Server Rewrite** | Python | Rewrite the existing TypeScript server logic using the official Python MCP SDK. Define the core application structure and use Pydantic for API schema validation. | Python offers a rich ecosystem for data science and LLM tools, facilitating rapid development and integration.[1] |
| **0.2** | **Qdrant Local Setup** | Shell/Python | Implement setup scripts (e.g., using Docker Compose or a direct binary executor) to initialize a single, local instance of the Qdrant vector database. Configure the collection with high-performance HNSW indexing. | Qdrant is optimized for low-latency, high-throughput vector search on local CPUs, providing a significant performance uplift over file-based databases for RAG.[2, 3] |
| **0.3** | **Qdrant Service Connector** | Python | Implement a dedicated `QdrantMemoryStore` class that adheres to the MCP `MemoryStore` interface. This class handles all vector and payload CRUD operations using the `qdrant-client` library. | Decouples persistence logic from the application logic, essential for modular RAG architecture.[4] |
| **0.4** | **Python-Rust Bridge** | Rust (via PyO3) | Establish the performance bridge using `PyO3`. Create a base Rust crate (`mcp_performance_core`) that exposes functions for computationally intensive tasks back to Python. | Rust acts as Python's "performance co-pilot," delivering C-level speed and memory safety for CPU-bound tasks.[1, 5] |
| **0.5** | **Initial Embedding Engine** | Rust/Python | Implement the embedding generation process within the Rust core for maximum performance, or integrate a high-speed local model runner (like Ollama or a dedicated library) via Python. | Performance-critical component that benefits heavily from Rust's speed for matrix operations.[1] |

---

## Phase 1: Performance, Security, and Context Segregation (I-1, I-3, I-2)

This phase addresses critical security hardening and integrates the new Multi-Level Memory model to improve context quality and token efficiency.

| ID | Feature | Implementation Details | Rationale / Citation |
|---|---|---|---|
| **1.1** | **Migration to Qdrant** (I-1) | Rewrite all `Store` and `Find` logic to utilize Qdrant entirely. Ensure the current hybrid search (semantic + keyword) is replicated by running vector similarity search combined with Qdrant's payload-based filtering or full-text indexing capabilities. | Required to achieve the necessary retrieval speed and latency for a seamless developer experience.[3] |
| **1.2** | **Enhanced Input Sanitation** (I-3) | Implement strict Pydantic validation on all incoming MCP payloads. Use explicit allow-lists for all query parameters and metadata fields to prevent arbitrary input from reaching the database query layer. | Mitigates the critical security risk of SQL injection and stored prompt injection identified in previous SQLite MCP reference implementations.[6] |
| **1.3** | **Least Privilege/Read-Only** (I-3) | Implement a configurable `--read-only` CLI flag. When active, the Qdrant client must be instantiated with credentials or configurations that restrict all `Store` and `Delete` operations, providing the most robust defense against prompt injection and data alteration.[6] | |
| **1.4** | **Multi-Level Schema** (I-2) | Augment the `MemoryUnit` schema with a mandatory `context_level` field, categorized as: `USER_PREFERENCE`, `PROJECT_CONTEXT`, or `SESSION_STATE`. | Enables systematic context management and pruning, drastically reducing token usage and improving latency by only injecting relevant context.[7, 8] |
| **1.5** | **Filtered Retrieval Tools** (I-2) | Define and expose new, specific MCP tool endpoints (e.g., `Memory.RetrievePreferences`, `Memory.RetrieveProjectFacts`). These tools must automatically enforce the corresponding `context_level` as a mandatory payload filter during the Qdrant search. | Allows Claude Code to request context precisely, reducing context overflow and improving relevance.[9] |

---

## Phase 2: Code Intelligence and Automation (II-1, II-2)

This phase integrates code-structure awareness, the highest-value feature for engineers, and builds the non-friction context synchronization layer.

| ID | Feature | Implementation Details | Rationale / Citation |
|---|---|---|---|
| **2.1** | **AST Parsing Core** (II-1) | Implement the core parser in Rust using the `tree-sitter` library. This module is responsible for analyzing source code and identifying logical **semantic units** (functions, classes, methods), rather than fixed token chunks.[10] | Rust is necessary for the performance and reliability required for this high-complexity, CPU-intensive static analysis.[1, 11] |
| **2.2** | **Structural Metadata Extractor** (II-1) | Within the Rust parser, extract and serialize structural metadata for each semantic unit: function signature, language, full file path, and, optionally, basic dependency/call-graph information (RepoGraph principles).[12] | This metadata is indexed alongside the vector embedding, enabling the RLCG (Repository-Level Code Generation) capability by providing context on global semantic consistency.[13, 12] |
| **2.3** | **Incremental Indexing Logic** (II-1) | Implement a Python service that uses file system checks (hashes or timestamps) to identify file deltas. Only changed semantic units are sent to the Rust core for re-processing and subsequent upsert/replacement in Qdrant. | Manages local CPU consumption and ensures index updates are fast and non-blocking.[14] |
| **2.4** | **CLI Index Command** (II-2) | Implement a simple Python CLI command (`mcp-server index <path>`) that uses the incremental indexing logic (2.3) for on-demand context updates. | Provides a low-friction manual trigger for context updates, respecting the user's workflow preference.[15] |
| **2.5** | **File Watcher Daemon** (II-2) | Implement an optional, low-footprint daemon (using libraries like `watchdog`) that monitors the project directory for save/modify events and triggers the incremental indexer automatically. | Ensures the memory index is perpetually current without user interaction, minimizing developer friction.[15, 16] |

---

## Phase 3: Adaptive Efficiency (II-3)

This final phase implements the adaptive retrieval gate, the most effective way to conserve tokens and reduce latency.

| ID | Feature | Implementation Details | Rationale / Citation |
|---|---|---|---|
| **3.1** | **Selective Retrieval Heuristic** (II-3) | Implement a lightweight classification model or heuristic engine in Python. This component analyzes the user query and session state (e.g., current file/line context) to predict whether external RAG is likely to improve the output quality. | This step must be extremely fast and local, running *before* the expensive Qdrant vector search.[17, 18] |
| **3.2** | **Retrieval Gating Logic** (II-3) | Modify the `Memory.Find` API handler to run the prediction model (3.1). If the predicted utility score is below a defined confidence threshold (e.g., 80% likelihood of benefit), the Qdrant search is skipped entirely, and an empty result is returned to Claude. | Avoiding unnecessary retrieval can speed up inference by up to 70% on tasks where context is not needed, dramatically saving Claude API tokens and reducing latency.[19, 18] |
| **3.3** | **Final Packaging & Docs** | Finalize project structure, write comprehensive installation guides (including Qdrant setup), and create detailed API documentation for both Python and Rust components. | |
