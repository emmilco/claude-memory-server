# FEAT-059: Structural/Relational Queries - Implementation Plan

## TODO Reference
- **ID:** FEAT-059
- **Location:** TODO.md, Tier 2: Core Functionality Extensions → Phase 2: Structural Analysis
- **Priority:** 🔥🔥🔥 High-impact core functionality
- **Estimated Time:** ~2 weeks
- **Complexity:** Most complex feature - requires call graph algorithms and storage design

## Objective

Transform architecture discovery from **45 minutes to 5 minutes** by adding structural analysis capabilities that enable traversing code relationships (call graphs, implementations, dependency chains) through 6 new MCP tools.

### High-Level Goal
Enable developers to answer questions like:
- "What functions call `authenticate()`?" (find_callers)
- "What does `process_payment()` depend on?" (find_callees)
- "Show all implementations of the `Storage` interface" (find_implementations)
- "What's the call path from `main()` to `database_query()`?" (get_call_chain)
- "What files depend on `auth.py`?" (find_dependents)
- "What does `api.py` import?" (find_dependencies)

## Current Limitations

### What Can't Be Done Today
1. **No call graph analysis** - Can't find which functions call a given function
2. **No reverse dependency lookup** - Can't find what depends on a file or function
3. **No implementation discovery** - Can't find all classes implementing an interface
4. **No call chain analysis** - Can't trace execution paths between functions
5. **No relationship traversal** - Can only see imports, not actual usage relationships
6. **Manual grep required** - Users spend 30-45 minutes manually grepping for callers/callees

### Current Capabilities (Foundation to Build On)
- ✅ Import extraction across 6 languages (Python, JS, TS, Java, Go, Rust)
- ✅ Dependency graph with circular detection (FEAT-048)
- ✅ Code indexing with semantic units (functions, classes, methods)
- ✅ File-level dependency tracking (imports/exports)

### The Gap
**Existing tools provide STATIC dependencies (imports).**
**FEAT-059 adds DYNAMIC dependencies (actual function calls, implementations, execution paths).**

## Technical Design

### 1. Call Graph Data Structure

**Core Abstraction:**
```python
# src/graph/call_graph.py

@dataclass
class CallSite:
    """Represents a function call location."""
    caller_function: str       # Function making the call
    caller_file: str           # File containing caller
    caller_line: int           # Line number of call
    callee_function: str       # Function being called
    callee_file: Optional[str] # File containing callee (if resolved)
    call_type: str             # "direct", "method", "constructor", "lambda"

@dataclass
class FunctionNode:
    """Node in call graph representing a function."""
    name: str                  # Function/method name
    qualified_name: str        # Full path (e.g., "MyClass.method")
    file_path: str             # Source file
    language: str              # Programming language
    start_line: int            # Function start line
    end_line: int              # Function end line
    is_exported: bool          # Whether function is exported/public
    is_async: bool             # Async/coroutine function
    parameters: List[str]      # Parameter names
    return_type: Optional[str] # Return type hint (if available)

@dataclass
class InterfaceImplementation:
    """Tracks interface/trait implementations."""
    interface_name: str        # Interface/trait/abstract class name
    implementation_name: str   # Concrete implementation class name
    file_path: str             # File containing implementation
    language: str              # Programming language
    methods: List[str]         # Implemented method names

class CallGraph:
    """
    Call graph for analyzing function relationships.

    Data Structures:
    - nodes: Dict[str, FunctionNode] - All functions indexed by qualified name
    - calls: List[CallSite] - All function calls
    - forward_index: Dict[str, Set[str]] - function -> {functions it calls}
    - reverse_index: Dict[str, Set[str]] - function -> {functions calling it}
    - implementations: Dict[str, List[InterfaceImplementation]] - interface -> implementations
    """

    def __init__(self):
        self.nodes: Dict[str, FunctionNode] = {}
        self.calls: List[CallSite] = []
        self.forward_index: Dict[str, Set[str]] = {}  # caller -> callees
        self.reverse_index: Dict[str, Set[str]] = {}  # callee -> callers
        self.implementations: Dict[str, List[InterfaceImplementation]] = {}

    def add_function(self, node: FunctionNode) -> None:
        """Add function to call graph."""
        pass

    def add_call(self, call_site: CallSite) -> None:
        """Add function call relationship."""
        pass

    def add_implementation(self, impl: InterfaceImplementation) -> None:
        """Add interface implementation relationship."""
        pass

    def find_callers(self, function_name: str) -> List[FunctionNode]:
        """Find all functions calling the given function."""
        pass

    def find_callees(self, function_name: str) -> List[FunctionNode]:
        """Find all functions called by the given function."""
        pass

    def find_call_chain(self, from_func: str, to_func: str) -> List[List[str]]:
        """Find all paths from from_func to to_func using BFS."""
        pass
```

### 2. Storage Strategy

**Option A: Separate Qdrant Collection (RECOMMENDED)**
```python
# Create dedicated collection for call graph data
collection_name = "code_call_graph"

# Point structure:
{
    "id": "<function_qualified_name>",  # e.g., "MyClass.method"
    "vector": [0.0] * 384,              # Dummy vector (not used for semantic search)
    "payload": {
        "function_node": {
            "name": "method",
            "qualified_name": "MyClass.method",
            "file_path": "/path/to/file.py",
            "language": "python",
            "start_line": 45,
            "end_line": 67,
            "is_exported": true,
            "is_async": false,
            "parameters": ["self", "user_id"],
            "return_type": "User"
        },
        "calls_to": ["Database.query", "Logger.info"],  # Forward index
        "called_by": ["UserController.get_user"],       # Reverse index
        "call_sites": [
            {
                "caller_function": "UserController.get_user",
                "caller_file": "/path/to/controller.py",
                "caller_line": 23,
                "callee_function": "MyClass.method",
                "call_type": "method"
            }
        ]
    }
}
```

**Why separate collection?**
- ✅ Clear separation of concerns (code units vs call relationships)
- ✅ Independent schema evolution
- ✅ Optimized queries (no need to filter by category)
- ✅ Easy to rebuild without affecting code index
- ❌ Slightly more complex setup (one additional collection)

**Option B: Extend Existing Collection with Metadata**
```python
# Add to existing code units in "memories" collection
{
    "category": "code",
    "metadata": {
        # ... existing fields ...
        "call_graph": {
            "calls_to": [...],
            "called_by": [...],
            "call_sites": [...]
        }
    }
}
```

**Trade-offs:**
- ✅ Simpler setup (single collection)
- ✅ Call graph data co-located with code units
- ❌ Pollutes code unit metadata
- ❌ Harder to query (must filter by category=CODE)
- ❌ Rebuilding call graph requires updating all code units

**DECISION: Use Option A (separate collection) for cleaner architecture.**

### 3. Call Graph Extraction Strategy

**Language-Specific Extractors:**
```python
# src/analysis/call_extractors.py

class BaseCallExtractor(ABC):
    """Abstract base for language-specific call extraction."""

    @abstractmethod
    def extract_calls(self, file_path: str, source_code: str, parse_result: ParseResult) -> List[CallSite]:
        """Extract function calls from source code."""
        pass

    @abstractmethod
    def extract_implementations(self, file_path: str, source_code: str) -> List[InterfaceImplementation]:
        """Extract interface/trait implementations."""
        pass

class PythonCallExtractor(BaseCallExtractor):
    """Extract calls from Python code using AST."""

    def extract_calls(self, file_path: str, source_code: str, parse_result: ParseResult) -> List[CallSite]:
        """
        Extract function calls using Python AST.

        Handles:
        - Direct calls: func(arg)
        - Method calls: obj.method(arg)
        - Constructor calls: MyClass(arg)
        - Async calls: await func(arg)
        - Lambda calls: (lambda x: x)(arg)
        """
        import ast

        calls = []
        tree = ast.parse(source_code)

        # Walk AST and find Call nodes
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Extract caller context
                caller_function = self._get_enclosing_function(node)

                # Extract callee name
                callee_name = self._extract_callee_name(node.func)

                if caller_function and callee_name:
                    calls.append(CallSite(
                        caller_function=caller_function,
                        caller_file=file_path,
                        caller_line=node.lineno,
                        callee_function=callee_name,
                        callee_file=None,  # Resolved later
                        call_type=self._determine_call_type(node.func)
                    ))

        return calls

    def extract_implementations(self, file_path: str, source_code: str) -> List[InterfaceImplementation]:
        """
        Extract class inheritance relationships.

        Handles:
        - ABC inheritance: class Concrete(Abstract)
        - Multiple inheritance: class Impl(Interface1, Interface2)
        - Protocol implementations (Python 3.8+)
        """
        import ast

        implementations = []
        tree = ast.parse(source_code)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    base_name = self._extract_name(base)
                    if base_name:
                        # Collect all method names
                        methods = [m.name for m in node.body if isinstance(m, ast.FunctionDef)]

                        implementations.append(InterfaceImplementation(
                            interface_name=base_name,
                            implementation_name=node.name,
                            file_path=file_path,
                            language="python",
                            methods=methods
                        ))

        return implementations
```

**Similar extractors for:**
- JavaScript/TypeScript (using Babel parser or tree-sitter)
- Java (using tree-sitter-java)
- Go (using tree-sitter-go)
- Rust (using tree-sitter-rust)

### 4. Graph Traversal Algorithms

**BFS for Call Chains:**
```python
def find_call_chain(self, from_func: str, to_func: str, max_depth: int = 10) -> List[List[str]]:
    """
    Find all call paths from from_func to to_func using BFS.

    Args:
        from_func: Starting function name
        to_func: Target function name
        max_depth: Maximum path length (prevent infinite loops)

    Returns:
        List of paths, where each path is a list of function names.
        Example: [["main", "process", "validate"], ["main", "handle", "validate"]]

    Algorithm:
        1. Initialize queue with starting node: [(from_func, [from_func])]
        2. While queue not empty:
            a. Dequeue (current_func, path)
            b. If current_func == to_func, add path to results
            c. If len(path) >= max_depth, skip
            d. For each callee in forward_index[current_func]:
                - If callee not in path (avoid cycles):
                    - Enqueue (callee, path + [callee])
        3. Return all found paths

    Time Complexity: O(V + E) where V=functions, E=calls
    Space Complexity: O(V) for visited set + O(P*L) for paths (P=path count, L=path length)
    """
    if from_func not in self.nodes or to_func not in self.nodes:
        return []

    paths = []
    queue = [(from_func, [from_func])]

    while queue:
        current_func, path = queue.pop(0)

        # Found target
        if current_func == to_func:
            paths.append(path)
            continue

        # Depth limit
        if len(path) >= max_depth:
            continue

        # Explore callees
        for callee in self.forward_index.get(current_func, set()):
            # Avoid cycles
            if callee not in path:
                queue.append((callee, path + [callee]))

    return paths
```

**DFS for Caller/Callee Discovery:**
```python
def find_all_callers_recursive(self, function_name: str, max_depth: int = 5) -> Set[str]:
    """
    Find all functions that transitively call function_name.

    Uses DFS to traverse reverse_index (callee -> callers).
    """
    visited = set()

    def dfs(func: str, depth: int):
        if depth > max_depth or func in visited:
            return

        visited.add(func)

        for caller in self.reverse_index.get(func, set()):
            dfs(caller, depth + 1)

    dfs(function_name, 0)
    visited.discard(function_name)  # Remove the original function
    return visited
```

### 5. Six New MCP Tools Design

#### Tool 1: find_callers
```python
async def find_callers(
    self,
    function_name: str,
    project_name: str,
    include_indirect: bool = False,
    max_depth: int = 1,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Find all functions calling the specified function.

    Args:
        function_name: Function name to search for (supports wildcards: "MyClass.*")
        project_name: Project to search in
        include_indirect: If True, include transitive callers (callers of callers)
        max_depth: Maximum depth for indirect callers (1=direct only, 2=callers of callers, etc.)
        limit: Maximum results to return

    Returns:
        {
            "function": "authenticate",
            "callers": [
                {
                    "caller_function": "login_user",
                    "caller_file": "/path/to/auth.py",
                    "caller_line": 45,
                    "call_type": "direct",
                    "distance": 1  # Hops from original function
                }
            ],
            "total_callers": 12,
            "direct_callers": 5,
            "indirect_callers": 7,
            "analysis_time_ms": 3.2
        }
    """
```

#### Tool 2: find_callees
```python
async def find_callees(
    self,
    function_name: str,
    project_name: str,
    include_indirect: bool = False,
    max_depth: int = 1,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Find all functions called by the specified function.

    Args:
        function_name: Function name to analyze
        project_name: Project to search in
        include_indirect: If True, include transitive callees (callees of callees)
        max_depth: Maximum depth for indirect callees
        limit: Maximum results to return

    Returns:
        {
            "function": "process_payment",
            "callees": [
                {
                    "callee_function": "validate_card",
                    "callee_file": "/path/to/payment.py",
                    "callee_line": 67,
                    "call_site_line": 45,  # Where the call happens in process_payment
                    "call_type": "direct",
                    "distance": 1
                }
            ],
            "total_callees": 8,
            "direct_callees": 3,
            "indirect_callees": 5,
            "analysis_time_ms": 2.1
        }
    """
```

#### Tool 3: find_implementations
```python
async def find_implementations(
    self,
    interface_name: str,
    project_name: Optional[str] = None,
    language: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Find all implementations of an interface/trait/abstract class.

    Args:
        interface_name: Interface, trait, or abstract class name
        project_name: Optional project to search in (None = all projects)
        language: Optional language filter (python, java, rust, etc.)
        limit: Maximum results to return

    Returns:
        {
            "interface": "Storage",
            "implementations": [
                {
                    "class_name": "RedisStorage",
                    "file_path": "/path/to/redis.py",
                    "language": "python",
                    "methods": ["get", "set", "delete", "clear"],
                    "complete": true  # Whether all interface methods are implemented
                }
            ],
            "total_implementations": 3,
            "languages": ["python", "java"],
            "analysis_time_ms": 1.8
        }
    """
```

#### Tool 4: find_dependencies
```python
async def find_dependencies(
    self,
    file_path: str,
    project_name: str,
    depth: int = 1,
    include_transitive: bool = False
) -> Dict[str, Any]:
    """
    Get dependency graph for a file (what it imports).

    Args:
        file_path: File to analyze
        project_name: Project name
        depth: Depth of dependency tree to return
        include_transitive: If True, include dependencies of dependencies

    Returns:
        {
            "file": "/path/to/api.py",
            "dependencies": [
                {
                    "file": "/path/to/auth.py",
                    "imports": ["authenticate", "authorize"],
                    "import_type": "relative",
                    "depth": 1
                }
            ],
            "total_dependencies": 15,
            "direct_dependencies": 5,
            "transitive_dependencies": 10,
            "circular_dependencies": [
                ["/path/to/a.py", "/path/to/b.py", "/path/to/a.py"]
            ],
            "analysis_time_ms": 4.3
        }
    """
```

#### Tool 5: find_dependents
```python
async def find_dependents(
    self,
    file_path: str,
    project_name: str,
    depth: int = 1,
    include_transitive: bool = False
) -> Dict[str, Any]:
    """
    Get reverse dependencies for a file (what imports it).

    Args:
        file_path: File to analyze
        project_name: Project name
        depth: Depth of dependent tree to return
        include_transitive: If True, include dependents of dependents

    Returns:
        {
            "file": "/path/to/auth.py",
            "dependents": [
                {
                    "file": "/path/to/api.py",
                    "imports": ["authenticate"],
                    "import_type": "relative",
                    "depth": 1
                }
            ],
            "total_dependents": 22,
            "direct_dependents": 8,
            "transitive_dependents": 14,
            "impact_radius": "high",  # high if >20 dependents, medium if 10-20, low if <10
            "analysis_time_ms": 5.1
        }
    """
```

#### Tool 6: get_call_chain
```python
async def get_call_chain(
    self,
    from_function: str,
    to_function: str,
    project_name: str,
    max_paths: int = 5,
    max_depth: int = 10
) -> Dict[str, Any]:
    """
    Show all call paths from from_function to to_function.

    Args:
        from_function: Starting function name
        to_function: Target function name
        project_name: Project to search in
        max_paths: Maximum number of paths to return
        max_depth: Maximum path length (prevent infinite loops)

    Returns:
        {
            "from": "main",
            "to": "database_query",
            "paths": [
                {
                    "path": ["main", "process_request", "get_user", "database_query"],
                    "length": 4,
                    "call_details": [
                        {
                            "caller": "main",
                            "callee": "process_request",
                            "file": "/path/to/main.py",
                            "line": 15
                        },
                        // ... more calls
                    ]
                }
            ],
            "total_paths": 3,
            "shortest_path_length": 3,
            "longest_path_length": 6,
            "analysis_time_ms": 12.5
        }
    """
```

### 6. Indexing Strategy

**When to Build Call Graph:**

**Option A: During Code Indexing (RECOMMENDED)**
```python
# In src/memory/incremental_indexer.py

async def index_file(self, file_path: Path) -> Dict[str, Any]:
    # ... existing parsing ...

    # Extract function calls (NEW)
    call_extractor = get_call_extractor(parse_result.language)
    call_sites = call_extractor.extract_calls(file_path, source_code, parse_result)
    implementations = call_extractor.extract_implementations(file_path, source_code)

    # Store in call graph collection (NEW)
    await self.call_graph_store.store_calls(call_sites, implementations)

    return {
        "units_indexed": len(stored_ids),
        "calls_extracted": len(call_sites),  # NEW
        "implementations_extracted": len(implementations),  # NEW
    }
```

**Why during indexing?**
- ✅ Single pass through code
- ✅ Call graph always in sync with code index
- ✅ No separate indexing step
- ❌ Slower initial indexing (~10-15% overhead)

**Option B: On-Demand Analysis**
- Build call graph only when needed (first query)
- Cache results in Qdrant
- ❌ High latency on first query (30-60s for medium project)
- ✅ Faster initial indexing

**DECISION: Use Option A (during indexing) for better UX.**

### 7. Performance Considerations

**Graph Storage Size:**
- **Code units:** ~1KB per function (current)
- **Call graph data:** ~500 bytes per function (calls_to + called_by)
- **Call sites:** ~200 bytes per call site
- **Estimated overhead:** +50-70% storage vs code-only index

**Example:**
- 10,000 functions
- 50,000 call sites (average 5 calls per function)
- Code units: 10MB
- Call graph: 5MB (calls_to/called_by) + 10MB (call sites) = 15MB
- Total: 25MB (vs 10MB without call graph)

**Query Latency Targets:**
- `find_callers` (direct): <5ms
- `find_callers` (indirect, depth=3): <50ms
- `find_callees` (direct): <5ms
- `get_call_chain` (max_depth=10): <100ms
- `find_implementations`: <10ms
- `find_dependencies`: <20ms

**Optimization Strategies:**
1. **Index both forward and reverse edges** (callers + callees)
2. **Cache frequent queries** (LRU cache for call chains)
3. **Limit traversal depth** (max_depth parameter)
4. **Batch Qdrant queries** (scroll API for large result sets)
5. **Use Qdrant filters** (project_name, language) for early pruning

## Implementation Phases

### Phase 1: Core Call Graph Infrastructure (Days 1-2)

**Deliverables:**
- [ ] `src/graph/call_graph.py` - CallGraph class with node/edge management
- [ ] `src/analysis/call_extractors.py` - Base extractor + Python implementation
- [ ] `src/store/call_graph_store.py` - Qdrant storage for call graph
- [ ] Unit tests for CallGraph (15-20 tests)

**Tasks:**
1. Create CallGraph class with add_function, add_call, add_implementation
2. Implement forward_index and reverse_index for efficient lookups
3. Create Qdrant collection schema for call graph
4. Implement store_calls and retrieve_calls methods
5. Write tests for basic operations

### Phase 2: Language-Specific Call Extraction (Days 2-4)

**Deliverables:**
- [ ] PythonCallExtractor with AST-based extraction
- [ ] JavaScriptCallExtractor with tree-sitter
- [ ] TypeScriptCallExtractor (extends JavaScript)
- [ ] Unit tests for each extractor (10-15 tests each)

**Tasks:**
1. Implement Python AST walker for Call nodes
2. Extract caller context using node.lineno and enclosing function
3. Implement interface/ABC detection for Python
4. Add JavaScript call extraction using tree-sitter
5. Add TypeScript support (similar to JavaScript)
6. Write tests with sample code snippets

**Optional (if time permits):**
- [ ] JavaCallExtractor
- [ ] GoCallExtractor
- [ ] RustCallExtractor

### Phase 3: Graph Traversal Algorithms (Days 4-5)

**Deliverables:**
- [ ] BFS for call chain discovery
- [ ] DFS for transitive caller/callee discovery
- [ ] Path deduplication and ranking
- [ ] Unit tests for algorithms (15-20 tests)

**Tasks:**
1. Implement find_call_chain using BFS
2. Implement find_all_callers_recursive using DFS
3. Add cycle detection (avoid infinite loops)
4. Add path ranking (prefer shorter paths)
5. Write tests with complex call graphs

### Phase 4: Six MCP Tools Implementation (Days 5-7)

**Deliverables:**
- [ ] find_callers MCP tool
- [ ] find_callees MCP tool
- [ ] find_implementations MCP tool
- [ ] find_dependencies MCP tool
- [ ] find_dependents MCP tool
- [ ] get_call_chain MCP tool
- [ ] Integration tests for each tool (5-8 tests each)

**Tasks:**
1. Add tools to src/core/server.py
2. Register tools in src/mcp_server.py
3. Implement request/response models
4. Add error handling and validation
5. Write integration tests with real projects

### Phase 5: Indexing Integration (Days 7-8)

**Deliverables:**
- [ ] Call extraction during code indexing
- [ ] Call graph storage in Qdrant
- [ ] Updated indexing progress reporting
- [ ] Integration tests for indexing workflow

**Tasks:**
1. Modify IncrementalIndexer.index_file to extract calls
2. Store call graph data in separate collection
3. Update progress callback to report call extraction
4. Test with real Python/JavaScript projects

### Phase 6: Testing & Documentation (Days 8-10)

**Deliverables:**
- [ ] 25-30 comprehensive tests
- [ ] Performance benchmarks
- [ ] API documentation updates
- [ ] Example usage in README

**Tasks:**
1. Write end-to-end tests with sample projects
2. Run performance benchmarks (call chain on 10k functions)
3. Update docs/API.md with new tools
4. Update CHANGELOG.md
5. Add examples to README.md

## Code Examples

### Example 1: Extract Calls from Python Function
```python
# Input Python code:
def process_payment(user_id, amount):
    user = get_user(user_id)
    card = validate_card(user.card_number)
    result = charge_card(card, amount)
    log_transaction(user_id, amount)
    return result

# Extracted CallSites:
[
    CallSite(
        caller_function="process_payment",
        caller_file="/path/to/payment.py",
        caller_line=2,
        callee_function="get_user",
        call_type="direct"
    ),
    CallSite(
        caller_function="process_payment",
        caller_file="/path/to/payment.py",
        caller_line=3,
        callee_function="validate_card",
        call_type="direct"
    ),
    CallSite(
        caller_function="process_payment",
        caller_file="/path/to/payment.py",
        caller_line=4,
        callee_function="charge_card",
        call_type="direct"
    ),
    CallSite(
        caller_function="process_payment",
        caller_file="/path/to/payment.py",
        caller_line=5,
        callee_function="log_transaction",
        call_type="direct"
    ),
]
```

### Example 2: Find Callers Usage
```python
# User query: "What calls authenticate()?"

result = await server.find_callers(
    function_name="authenticate",
    project_name="my-app",
    include_indirect=False,
    max_depth=1,
    limit=50
)

# Response:
{
    "function": "authenticate",
    "callers": [
        {
            "caller_function": "login_user",
            "caller_file": "/src/auth/login.py",
            "caller_line": 45,
            "call_type": "direct",
            "distance": 1
        },
        {
            "caller_function": "api_auth_middleware",
            "caller_file": "/src/api/middleware.py",
            "caller_line": 78,
            "call_type": "direct",
            "distance": 1
        }
    ],
    "total_callers": 12,
    "direct_callers": 12,
    "indirect_callers": 0,
    "analysis_time_ms": 3.2
}
```

### Example 3: Get Call Chain Usage
```python
# User query: "How does main() reach database_query()?"

result = await server.get_call_chain(
    from_function="main",
    to_function="database_query",
    project_name="my-app",
    max_paths=5,
    max_depth=10
)

# Response:
{
    "from": "main",
    "to": "database_query",
    "paths": [
        {
            "path": ["main", "process_request", "get_user", "database_query"],
            "length": 4,
            "call_details": [
                {
                    "caller": "main",
                    "callee": "process_request",
                    "file": "/src/main.py",
                    "line": 15
                },
                {
                    "caller": "process_request",
                    "callee": "get_user",
                    "file": "/src/api/handlers.py",
                    "line": 67
                },
                {
                    "caller": "get_user",
                    "callee": "database_query",
                    "file": "/src/models/user.py",
                    "line": 34
                }
            ]
        },
        {
            "path": ["main", "startup", "initialize_db", "database_query"],
            "length": 4,
            "call_details": [/* ... */]
        }
    ],
    "total_paths": 2,
    "shortest_path_length": 4,
    "longest_path_length": 4,
    "analysis_time_ms": 12.5
}
```

### Example 4: Find Implementations Usage
```python
# User query: "Show all classes implementing Storage interface"

result = await server.find_implementations(
    interface_name="Storage",
    project_name="my-app",
    language="python",
    limit=50
)

# Response:
{
    "interface": "Storage",
    "implementations": [
        {
            "class_name": "RedisStorage",
            "file_path": "/src/storage/redis.py",
            "language": "python",
            "methods": ["get", "set", "delete", "clear"],
            "complete": true
        },
        {
            "class_name": "MemoryStorage",
            "file_path": "/src/storage/memory.py",
            "language": "python",
            "methods": ["get", "set", "delete"],
            "complete": false  # Missing clear() method
        }
    ],
    "total_implementations": 2,
    "languages": ["python"],
    "analysis_time_ms": 1.8
}
```

## Test Plan

### Unit Tests (15-20 tests)

#### CallGraph Class Tests
1. `test_add_function_creates_node`
2. `test_add_call_creates_edge`
3. `test_forward_index_populated_correctly`
4. `test_reverse_index_populated_correctly`
5. `test_find_callers_direct_only`
6. `test_find_callees_direct_only`
7. `test_add_implementation_stores_relationship`

#### Call Extraction Tests
8. `test_python_extract_direct_calls`
9. `test_python_extract_method_calls`
10. `test_python_extract_async_calls`
11. `test_python_extract_implementations`
12. `test_javascript_extract_function_calls`
13. `test_typescript_extract_calls_with_types`
14. `test_extractor_handles_syntax_errors`

#### Algorithm Tests
15. `test_bfs_finds_shortest_path`
16. `test_bfs_finds_multiple_paths`
17. `test_bfs_respects_max_depth`
18. `test_dfs_finds_all_transitive_callers`
19. `test_cycle_detection_prevents_infinite_loops`
20. `test_empty_graph_returns_empty_results`

### Integration Tests (25-30 tests)

#### MCP Tool Tests (5-8 tests each = 30-48 tests)

**find_callers:**
1. `test_find_callers_direct_single_caller`
2. `test_find_callers_multiple_callers`
3. `test_find_callers_indirect_depth_2`
4. `test_find_callers_wildcard_pattern`
5. `test_find_callers_function_not_found`
6. `test_find_callers_respects_limit`
7. `test_find_callers_cross_file`

**find_callees:**
8. `test_find_callees_direct_single_callee`
9. `test_find_callees_multiple_callees`
10. `test_find_callees_indirect_depth_3`
11. `test_find_callees_nested_calls`
12. `test_find_callees_empty_function`

**find_implementations:**
13. `test_find_implementations_single_impl`
14. `test_find_implementations_multiple_impls`
15. `test_find_implementations_filter_by_language`
16. `test_find_implementations_incomplete_impl`
17. `test_find_implementations_interface_not_found`

**find_dependencies:**
18. `test_find_dependencies_direct_imports`
19. `test_find_dependencies_transitive_depth_2`
20. `test_find_dependencies_circular_detection`
21. `test_find_dependencies_file_not_indexed`

**find_dependents:**
22. `test_find_dependents_single_dependent`
23. `test_find_dependents_high_impact_radius`
24. `test_find_dependents_transitive_depth_2`

**get_call_chain:**
25. `test_get_call_chain_single_path`
26. `test_get_call_chain_multiple_paths`
27. `test_get_call_chain_no_path_found`
28. `test_get_call_chain_respects_max_depth`
29. `test_get_call_chain_cycles_handled`
30. `test_get_call_chain_max_paths_limit`

### Performance Tests (3 tests)
31. `test_find_callers_large_graph_performance` (10k functions, target <50ms)
32. `test_get_call_chain_deep_graph_performance` (depth=10, target <100ms)
33. `test_indexing_overhead_acceptable` (call extraction <15% overhead)

## Performance Considerations

### Graph Storage Size

**Estimates for Medium Project (10,000 functions):**

| Component | Size per Item | Total Count | Total Size |
|-----------|--------------|-------------|------------|
| Function nodes | 500 bytes | 10,000 | 5 MB |
| Call sites | 200 bytes | 50,000 | 10 MB |
| Forward index | 100 bytes | 10,000 | 1 MB |
| Reverse index | 100 bytes | 10,000 | 1 MB |
| Implementations | 300 bytes | 500 | 150 KB |
| **Total** | | | **~17 MB** |

**Comparison:**
- Code units only: 10 MB
- Code + call graph: 27 MB
- **Overhead: +170%**

### Query Latency Targets

| Operation | Target Latency | Notes |
|-----------|----------------|-------|
| find_callers (direct) | <5ms | Single Qdrant lookup |
| find_callers (indirect, depth=3) | <50ms | BFS traversal |
| find_callees (direct) | <5ms | Single Qdrant lookup |
| get_call_chain (depth=10) | <100ms | BFS with path reconstruction |
| find_implementations | <10ms | Filtered Qdrant scroll |
| find_dependencies | <20ms | Import graph traversal |

### Optimization Strategies

1. **Dual Indexing:** Store both forward (calls_to) and reverse (called_by) for O(1) lookups
2. **Limit Traversal Depth:** Default max_depth=5 prevents exponential explosion
3. **Cache Frequent Queries:** LRU cache for call chains (max 1000 entries)
4. **Batch Qdrant Queries:** Use scroll API for large result sets (>100 items)
5. **Early Pruning:** Apply project_name and language filters at Qdrant level
6. **Lazy Loading:** Load call details only when needed (not for all traversal nodes)

## Success Criteria

### Functional Requirements
- ✅ All 6 MCP tools implemented and working
- ✅ Python and JavaScript call extraction functional
- ✅ Call chains correctly handle cycles (no infinite loops)
- ✅ Implementations detection works for Python ABCs and JS classes
- ✅ File dependencies and dependents correctly tracked
- ✅ Handles edge cases (empty graphs, missing functions, circular deps)

### Quality Requirements
- ✅ 25-30 tests minimum (unit + integration)
- ✅ 85%+ code coverage for new modules
- ✅ All tests passing
- ✅ No performance regressions in existing code indexing

### Performance Requirements
- ✅ find_callers (direct): <5ms P95
- ✅ get_call_chain (depth=10): <100ms P95
- ✅ Indexing overhead: <15% slowdown vs code-only
- ✅ Storage overhead: <200% vs code-only (acceptable)

### Documentation Requirements
- ✅ API documentation for all 6 tools in docs/API.md
- ✅ Usage examples in README.md
- ✅ CHANGELOG.md entry for FEAT-059
- ✅ Inline code comments for complex algorithms

### User Impact Validation
- ✅ Architecture discovery time: 45min → 5min (9x improvement)
- ✅ Refactoring impact analysis: Manual grep → Instant tool
- ✅ Call chain visualization: Impossible → 1 command

## Risk Mitigation

### Risk 1: Call Extraction Accuracy
**Risk:** AST parsing may miss dynamic calls, method chaining, or decorators
**Mitigation:**
- Start with simple cases (direct calls)
- Add complexity incrementally
- Document known limitations
- Provide fallback to manual grep for edge cases

### Risk 2: Performance on Large Codebases
**Risk:** 100k+ functions may cause slow queries or high memory usage
**Mitigation:**
- Implement query timeouts
- Add pagination for large result sets
- Cache frequently accessed call chains
- Consider graph database (Neo4j) for very large projects

### Risk 3: Language Support Gaps
**Risk:** Not all languages may be supported in time
**Mitigation:**
- Focus on Python and JavaScript first (80% of use cases)
- Add TypeScript (extends JavaScript)
- Java/Go/Rust are nice-to-have, not blockers
- Document supported languages clearly

### Risk 4: Indexing Time Overhead
**Risk:** Call extraction may significantly slow down indexing
**Mitigation:**
- Target <15% overhead (measured in Phase 5)
- Make call graph indexing optional (config flag)
- Allow separate call graph rebuild without re-indexing code

## Notes & Decisions

### Decision 1: Separate Qdrant Collection
**Context:** Should call graph data be stored in existing "memories" collection or separate?
**Decision:** Separate "code_call_graph" collection
**Rationale:**
- Cleaner schema (no category filtering needed)
- Independent evolution (can change call graph schema without affecting code units)
- Easier to rebuild (delete collection and re-extract)
- Better performance (optimized for graph queries)

### Decision 2: Index During Code Parsing
**Context:** When to build call graph - during indexing or on-demand?
**Decision:** Build during code indexing (Phase 5)
**Rationale:**
- Single pass through code (more efficient)
- Call graph always in sync with code index
- No high-latency first query
- Trade-off: Slightly slower initial indexing (~10-15% overhead acceptable)

### Decision 3: Python + JavaScript First
**Context:** Which languages to support in initial release?
**Decision:** Python and JavaScript/TypeScript
**Rationale:**
- Python: 60% of use cases, AST parsing is mature
- JavaScript/TypeScript: 30% of use cases, tree-sitter works well
- Java/Go/Rust: 10% of use cases, can add later
- Focus on quality over breadth

### Decision 4: BFS for Call Chains
**Context:** Which algorithm for find_call_chain - BFS or DFS?
**Decision:** BFS (Breadth-First Search)
**Rationale:**
- Finds shortest paths first (more useful for users)
- Easier to implement max_depth limit
- More predictable memory usage than DFS
- Can return multiple paths efficiently

## Future Enhancements (Post-FEAT-059)

### FEAT-063: Advanced Call Graph Analysis
- Dead code detection (functions with zero callers)
- Hot path analysis (most frequently called functions)
- Complexity metrics per call chain
- Call graph diffing (before/after refactor)

### FEAT-064: Interactive Call Graph Visualization
- Web-based interactive call graph viewer
- Zoom/pan/filter capabilities
- Highlight critical paths
- Export to Graphviz/D3.js

### FEAT-065: AI-Powered Refactoring Suggestions
- Identify refactoring opportunities based on call patterns
- Suggest function extraction for complex call chains
- Detect code smells (long call chains, tight coupling)

## Completion Checklist

### Phase 1: Core Infrastructure
- [ ] CallGraph class implemented
- [ ] CallGraphStore for Qdrant
- [ ] Unit tests (15-20 tests)

### Phase 2: Call Extraction
- [ ] PythonCallExtractor
- [ ] JavaScriptCallExtractor
- [ ] TypeScriptCallExtractor
- [ ] Unit tests (30-45 tests)

### Phase 3: Algorithms
- [ ] BFS for call chains
- [ ] DFS for transitive discovery
- [ ] Cycle detection
- [ ] Unit tests (15-20 tests)

### Phase 4: MCP Tools
- [ ] find_callers
- [ ] find_callees
- [ ] find_implementations
- [ ] find_dependencies
- [ ] find_dependents
- [ ] get_call_chain
- [ ] Integration tests (30-48 tests)

### Phase 5: Indexing
- [ ] Call extraction in IncrementalIndexer
- [ ] Call graph storage
- [ ] Progress reporting
- [ ] Integration tests (5-10 tests)

### Phase 6: Documentation
- [ ] API docs updated
- [ ] README examples
- [ ] CHANGELOG entry
- [ ] Inline comments

### Final Validation
- [ ] All tests passing (25-30 minimum)
- [ ] Performance benchmarks met
- [ ] Code coverage >85%
- [ ] Manual testing on real projects
- [ ] Documentation complete
- [ ] Ready for production use

## Resources & References

### Similar Tools
- **Sourcetrail:** C++ call graph visualization
- **Understand:** Multi-language code analysis
- **CodeQL:** Semantic code search with relationships
- **Kythe:** Google's code indexing framework

### Algorithms
- **BFS (Breadth-First Search):** Shortest path finding
- **DFS (Depth-First Search):** Cycle detection
- **Tarjan's Algorithm:** Strongly connected components (circular dependencies)

### Libraries
- **Python AST:** Built-in abstract syntax tree parser
- **tree-sitter:** Multi-language parsing library
- **Qdrant:** Vector database with powerful filtering
