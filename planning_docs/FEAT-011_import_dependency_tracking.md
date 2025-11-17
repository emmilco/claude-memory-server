# FEAT-011: Import/Dependency Tracking

## TODO Reference
- TODO.md: "Import/dependency tracking - Extract import statements, build dependency graph, track usage relationships"
- Category: Tier 3 - Core Functionality Extensions
- Impact: Enables multi-hop queries, architectural understanding

## Objective
Implement comprehensive import and dependency tracking across all supported languages to enable:
- Dependency graph visualization
- "Find all usages" queries
- Multi-hop relationship traversal
- Architectural understanding
- Impact analysis for changes

## Current State
- Parser extracts functions and classes
- No import extraction
- No dependency tracking
- No relationship graph

## Implementation Plan

### Phase 1: Import Extraction
- [ ] Create `src/memory/import_extractor.py` module
- [ ] Add regex/tree-sitter patterns for each language:
  - Python: `import`, `from ... import`
  - JavaScript/TypeScript: `import`, `require`, dynamic imports
  - Java: `import`
  - Go: `import`
  - Rust: `use`, `mod`
- [ ] Extract import metadata: source module, imported items, import type
- [ ] Store imports as metadata on semantic units

### Phase 2: Dependency Graph
- [ ] Create `src/memory/dependency_graph.py` module
- [ ] Build file-to-file dependency graph
- [ ] Build symbol-to-symbol dependency graph (function/class usage)
- [ ] Store relationships in database (new table or metadata)
- [ ] Efficient graph traversal methods

### Phase 3: Query Interface
- [ ] Add MCP tool: `get_dependencies(file_path)` - what does this file depend on?
- [ ] Add MCP tool: `get_dependents(file_path)` - what depends on this file?
- [ ] Add MCP tool: `find_import_path(source, target)` - path through dependency graph
- [ ] Add to code search results: show related files via imports

### Phase 4: Storage Schema
- [ ] Option 1: Store as metadata on MemoryUnit (simple, denormalized)
- [ ] Option 2: New table `dependencies` with (source_file, target_file, import_type, line_number)
- [ ] Option 3: Graph database (future enhancement)
- [ ] Decision: Start with Option 1, migrate to Option 2 if needed

## Implementation Details

### Import Patterns by Language

**Python:**
```python
import os
import sys as system
from pathlib import Path
from typing import List, Dict
from . import local_module
from ..parent import something
```

**JavaScript/TypeScript:**
```javascript
import { foo } from './module'
import * as lib from 'library'
import React from 'react'
const fs = require('fs')
```

**Java:**
```java
import java.util.List;
import static java.util.Collections.*;
```

**Go:**
```go
import "fmt"
import (
    "os"
    "path/filepath"
)
```

**Rust:**
```rust
use std::collections::HashMap;
use crate::models::{User, Post};
mod internal_module;
```

### Data Structure

```python
@dataclass
class ImportInfo:
    """Represents an import statement."""
    source_file: str  # File containing the import
    imported_module: str  # Module being imported
    imported_items: List[str]  # Specific items (if any)
    import_type: str  # "import", "from_import", "require", "use"
    line_number: int
    is_relative: bool  # Relative vs absolute import
    alias: Optional[str]  # Import alias if any
```

### Metadata Storage

Add to MemoryUnit metadata:
```python
{
    "imports": [
        {
            "module": "pathlib",
            "items": ["Path"],
            "line": 5,
            "type": "from_import"
        },
        ...
    ],
    "exported_symbols": ["MyClass", "helper_function"],
    "depends_on_files": ["/path/to/dep1.py", "/path/to/dep2.py"],
    "used_by_files": ["/path/to/user1.py"]
}
```

## Test Cases

### Unit Tests (`tests/unit/test_import_extractor.py`)
- [ ] Extract Python imports (various forms)
- [ ] Extract JavaScript/TypeScript imports
- [ ] Extract Java imports
- [ ] Extract Go imports
- [ ] Extract Rust imports
- [ ] Handle import aliases
- [ ] Handle relative imports
- [ ] Handle wildcard imports
- [ ] Handle multi-line imports

### Integration Tests (`tests/integration/test_dependency_graph.py`)
- [ ] Build dependency graph for sample project
- [ ] Query dependencies (what does X depend on?)
- [ ] Query dependents (what depends on X?)
- [ ] Find import paths between files
- [ ] Detect circular dependencies
- [ ] Handle missing files gracefully

### End-to-End Test
- [ ] Index sample multi-file project
- [ ] Verify imports are extracted
- [ ] Query dependency relationships
- [ ] Verify results match actual imports

## Success Criteria
- [ ] All import types extracted for all 6 languages
- [ ] Dependency graph built and queryable
- [ ] MCP tools return accurate results
- [ ] 85%+ test coverage
- [ ] Documentation updated
- [ ] Performance: <5ms overhead per file during indexing

## Notes & Decisions
- Start with Python-level extraction (no Rust changes needed initially)
- Use tree-sitter for accurate extraction where possible
- Fall back to regex for simpler cases
- Store in metadata first, can migrate to separate table later
- Focus on file-level dependencies first, symbol-level later

## Progress Tracking
- [ ] Phase 1: Import Extraction
- [ ] Phase 2: Dependency Graph
- [ ] Phase 3: Query Interface
- [ ] Phase 4: Testing
- [ ] Documentation & Commit
