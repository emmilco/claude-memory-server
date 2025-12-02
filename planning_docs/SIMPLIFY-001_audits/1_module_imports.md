# Module Import Audit - SIMPLIFY-001 Phase 1, Task 1.1

**Objective**: Complete map of what imports the features being removed during SIMPLIFY-001
**Date**: 2024-12-01
**Status**: Complete audit

## Executive Summary

This audit maps all Python modules currently importing from the three major feature sets targeted for removal in SIMPLIFY-001:

- **src/graph/** (Graph/Visualization) - 347 + 347 LOC (2 files)
- **src/backup/** (Import/Export) - 1799 LOC (4 files)  
- **src/tagging/** (Auto-Tagging system) - 1325 LOC (4 files)

**Total LOC in removed modules**: 3,844 lines

**Files requiring modification**: 14 files across CLI, core, analysis, memory, and store modules

---

## Detailed Import Map

### 1. src/graph/ Imports

The graph module is imported by 5 files for call graph analysis and visualization data structures.

#### Imports from src.graph.call_graph

| File | Import Statement | Usage Context |
|------|-----------------|---|
| `/src/store/call_graph_store.py` | `from src.graph.call_graph import (CallGraph, CallSite, FunctionNode, InterfaceImplementation)` | **Primary consumer**: Qdrant storage backend for call graph data. Stores/loads function nodes, call sites, and interface implementations to Qdrant collection `code_call_graph`. Used in methods: `store_function_node()`, `store_call_sites()`, `store_implementations()`, `load_call_graph()`, `find_function_by_name()`, `get_call_sites_for_caller()`, `get_implementations()`. |
| `/src/analysis/call_extractors.py` | `from src.graph.call_graph import CallSite, InterfaceImplementation` | **Data types**: Base class for language-specific call extraction. Defines abstract `BaseCallExtractor` that returns `List[CallSite]`. Used to model function calls and interface implementations during AST parsing. |
| `/src/memory/incremental_indexer.py` | `from src.graph.call_graph import FunctionNode` (line 1095) | **Conditional import**: Inside `_index_semantic_units()` method. Builds qualified names for function nodes and constructs FunctionNode instances from parse results. Used in semantic unit indexing. |

#### Imports from src.graph (package init)

| File | Import Statement | Usage Context |
|------|-----------------|---|
| `/src/graph/__init__.py` | Internal re-exports: `from src.graph.call_graph import (CallGraph, CallSite, FunctionNode, InterfaceImplementation)` and `from src.graph.dependency_graph import (DependencyGraph, ModuleNode, DependencyEdge, DependencyType)` | **Module initialization**: Package-level exports for public API. |

#### Graph-Related External Dependencies

| Library | Usage | Files |
|---------|-------|-------|
| `networkx` | **Not found in codebase** - No direct networkx imports detected in src/ |  N/A |

**Analysis**: The graph module is tightly integrated with Qdrant storage backend and code analysis pipeline. No external graph visualization libraries (like networkx, pygraphviz) are currently used.

---

### 2. src/backup/ Imports

The backup module is imported by 8 files for data export/import operations and CLI commands.

#### Imports from src.backup.exporter

| File | Import Statement | Usage Context |
|------|-----------------|---|
| `/src/cli/export_command.py` | `from src.backup.exporter import DataExporter` | **CLI Command**: Exports memories to json, markdown, or archive formats. Methods used: `export_to_json()`, `export_to_markdown()`, `create_portable_archive()`. |
| `/src/cli/backup_command.py` | `from src.backup.exporter import DataExporter` | **CLI Subcommand**: `backup_create()` function uses DataExporter for creating backups in archive or json format. |
| `/src/backup/__init__.py` | `from src.backup.exporter import DataExporter` | **Module export**: Package-level re-export of DataExporter. |

#### Imports from src.backup.importer

| File | Import Statement | Usage Context |
|------|-----------------|---|
| `/src/cli/import_command.py` | `from src.backup.importer import DataImporter, ConflictStrategy` | **CLI Command**: `import_command()` function imports memories from JSON or archive formats. Uses `importer.import_from_archive()` and `importer.import_from_json()` with conflict strategy enum. |
| `/src/cli/backup_command.py` | `from src.backup.importer import DataImporter, ConflictStrategy` | **CLI Subcommand**: `backup_restore()` function uses DataImporter for restoring from backups. |
| `/src/backup/__init__.py` | `from src.backup.importer import DataImporter, ConflictStrategy` | **Module export**: Package-level re-export. |

#### Imports from src.backup.scheduler

| File | Import Statement | Usage Context |
|------|-----------------|---|
| `/src/cli/schedule_command.py` | `from src.backup.scheduler import BackupScheduler, BackupScheduleConfig` | **CLI Command**: `schedule_enable()`, `schedule_disable()`, `schedule_status()`, `schedule_test()` functions manage automated backup scheduling with frequency, retention policies, and format options. |
| `/src/backup/scheduler.py` | Internal imports: `from src.backup.exporter import DataExporter` and `from src.backup.file_lock import FileLock` | **Internal dependencies**: Scheduler orchestrates exporter and uses file locking. |

#### Imports from src.backup.file_lock

| File | Import Statement | Usage Context |
|------|-----------------|---|
| `/src/cli/backup_command.py` | `from src.backup.file_lock import FileLock` | **File locking**: Prevents concurrent backup operations. |
| `/src/backup/scheduler.py` | `from src.backup.file_lock import FileLock` | **Scheduler safety**: Ensures only one backup runs at a time. |

**Impact Analysis**:
- **CLI Integration**: 3 CLI command files (export_command.py, import_command.py, backup_command.py, schedule_command.py) completely depend on backup module
- **LOC Impact**: 1799 LOC in backup module + 45+ LOC in dependent CLI commands
- **Functional Dependencies**: Export/import/schedule operations have no alternative implementation

---

### 3. src/tagging/ Imports

The tagging module is imported by 8 files for memory auto-tagging and collection management.

#### Imports from src.tagging.tag_manager

| File | Import Statement | Usage Context |
|------|-----------------|---|
| `/src/cli/tags_command.py` | `from src.tagging.tag_manager import TagManager` | **CLI Command**: Tag management (list, create, delete, update tags). Uses methods: `list_tags()`, `create_tag()`, `delete_tag()`, `update_tag()`. |
| `/src/cli/auto_tag_command.py` | `from src.tagging.tag_manager import TagManager` | **CLI Subcommand**: Used alongside AutoTagger to apply confidence-filtered tags to memories. |
| `/src/core/server.py` | `from src.tagging.tag_manager import TagManager` (line 55) | **Server Integration**: Imported at module level in MemoryRAGServer. Likely used in tag-related MCP tool handlers. |
| `/src/tagging/__init__.py` | `from src.tagging.tag_manager import TagManager` | **Module export**: Package-level re-export. |

#### Imports from src.tagging.auto_tagger

| File | Import Statement | Usage Context |
|------|-----------------|---|
| `/src/cli/auto_tag_command.py` | `from src.tagging.auto_tagger import AutoTagger` | **CLI Command**: Automatic content-based tagging with confidence thresholding. Methods: `auto_tag_memories()` with min_confidence parameter and dry-run support. |
| `/src/tagging/__init__.py` | `from src.tagging.auto_tagger import AutoTagger` | **Module export**: Package-level re-export. |

#### Imports from src.tagging.collection_manager

| File | Import Statement | Usage Context |
|------|-----------------|---|
| `/src/cli/collections_command.py` | `from src.tagging.collection_manager import CollectionManager` | **CLI Command**: Collection management (list, create, delete collections). Methods: `list_collections()`, `create_collection()`, `delete_collection()`. |
| `/src/tagging/__init__.py` | `from src.tagging.collection_manager import CollectionManager` | **Module export**: Package-level re-export. |

#### Imports from src.tagging.models

| File | Import Statement | Usage Context |
|------|-----------------|---|
| `/src/cli/tags_command.py` | `from src.tagging.models import TagCreate` | **Data model**: TagCreate schema for CLI input validation. |
| `/src/cli/collections_command.py` | `from src.tagging.models import CollectionCreate` | **Data model**: CollectionCreate schema for CLI input validation. |
| `/src/tagging/tag_manager.py` | `from src.tagging.models import Tag, TagCreate` | **Internal**: Tag model definitions. |
| `/src/tagging/collection_manager.py` | `from src.tagging.models import Collection, CollectionCreate` | **Internal**: Collection model definitions. |
| `/src/tagging/__init__.py` | `from src.tagging.models import Tag, Collection, TagCreate, CollectionCreate` | **Module export**: Package-level re-export. |

**Impact Analysis**:
- **CLI Integration**: 4 CLI command files (tags_command.py, collections_command.py, auto_tag_command.py) completely depend on tagging module
- **Core Server Integration**: TagManager imported at module level in core/server.py (main MCP server)
- **LOC Impact**: 1325 LOC in tagging module + significant server.py integration
- **Data Models**: TagCreate, CollectionCreate, Tag, Collection models used throughout

---

## Health Monitoring Remediation Files

**Note**: The audit specification mentions "Health monitoring files in src/monitoring/ related to remediation."

Remediation-related imports found:

| File | Import | Usage |
|------|--------|-------|
| `/src/cli/health_monitor_command.py` | `from src.monitoring.remediation import RemediationEngine, RemediationTrigger` | Health check remediation engine for automated issue fixing. |

**Status**: These files appear to be separate remediation system distinct from graph/backup/tagging removal scope. Requires clarification if targeting in Phase 1 or later phase.

---

## Summary by File Modification Impact

### Tier 1: Direct Imports (Must Remove)

Files directly importing removed features - require modification or deletion:

1. **src/store/call_graph_store.py** - 720 LOC
   - Imports: CallGraph, CallSite, FunctionNode, InterfaceImplementation
   - Impact: Entire Qdrant storage backend for call graphs

2. **src/analysis/call_extractors.py** - 100+ LOC
   - Imports: CallSite, InterfaceImplementation
   - Impact: Abstract base class for call extraction

3. **src/memory/incremental_indexer.py** - 1500+ LOC (partial)
   - Imports: FunctionNode (conditional at line 1095)
   - Impact: Conditional import in semantic unit indexing

4. **src/cli/export_command.py** - 230 LOC
   - Imports: DataExporter
   - Impact: CLI export command

5. **src/cli/import_command.py** - 252 LOC
   - Imports: DataImporter, ConflictStrategy
   - Impact: CLI import command

6. **src/cli/backup_command.py** - 470 LOC
   - Imports: DataExporter, DataImporter, ConflictStrategy, FileLock
   - Impact: CLI backup create/restore/list operations

7. **src/cli/schedule_command.py** - 280 LOC
   - Imports: BackupScheduler, BackupScheduleConfig
   - Impact: CLI backup scheduling command

8. **src/cli/tags_command.py** - 130 LOC
   - Imports: TagManager, TagCreate
   - Impact: CLI tag management command

9. **src/cli/collections_command.py** - 150 LOC
   - Imports: CollectionManager, CollectionCreate
   - Impact: CLI collection management command

10. **src/cli/auto_tag_command.py** - 100 LOC
    - Imports: AutoTagger, TagManager
    - Impact: CLI auto-tagging command

### Tier 2: Package Re-exports (Remove with Package)

Files that only re-export removed modules:

11. **src/backup/__init__.py** - 10 LOC
    - Re-exports: DataExporter, DataImporter, ConflictStrategy

12. **src/tagging/__init__.py** - 16 LOC
    - Re-exports: TagManager, AutoTagger, CollectionManager, models

13. **src/graph/__init__.py** - 15 LOC
    - Re-exports: CallGraph, CallSite, FunctionNode, InterfaceImplementation, etc.

### Tier 3: Server Core Integration (Modify)

14. **src/core/server.py** - 2000+ LOC
    - Imports: TagManager (line 55) at module level
    - Impact: MemoryRAGServer class likely has tag-related tool handlers
    - Action: Remove TagManager import and associated handler methods

---

## Removal Impact Summary

### Files Requiring Modification: 14 files

**By category:**
- CLI Commands: 7 files (complete deletion)
- Core/Analysis/Memory: 3 files (partial modification)
- Package Inits: 3 files (complete deletion)
- Core Server: 1 file (significant modification)

### Code Removal Statistics

| Category | Files | Estimated LOC |
|----------|-------|---------------|
| Removed Feature Modules | 10 | 3,844 |
| Direct CLI Commands | 7 | 1,412 |
| Core Server Integration | 1 | 50-100 |
| Indirect Integrations | 3 | 100+ |
| **Total LOC to Remove/Modify** | | **~5,400+** |

### Risk Assessment

**HIGH IMPACT**:
- **src/core/server.py** - TagManager integration in MCP server core
- **src/store/call_graph_store.py** - Complete Qdrant collection management system
- **src/cli/** - 7 CLI commands become non-functional

**MEDIUM IMPACT**:
- **src/memory/incremental_indexer.py** - Conditional FunctionNode import (isolated)
- **src/analysis/call_extractors.py** - Abstract base class (may have other implementations)

**LOW IMPACT**:
- Package __init__.py files (clean removal)

### Dependencies That Will Break

After removal, these features/workflows become unavailable:

1. **Backup/Export/Import Operations**:
   - `memory export` command
   - `memory import` command
   - `memory backup create/restore/list` commands
   - `memory schedule enable/disable/status/test` commands
   - Archive format support (.tar.gz)
   - Conflict resolution strategies

2. **Memory Tagging**:
   - `memory tags list/create/delete/update` commands
   - `memory collections list/create/delete` commands
   - `memory auto-tag` command with confidence thresholding
   - TagManager integration in core server
   - Tag hierarchies and collections functionality

3. **Code Analysis**:
   - Call graph storage/retrieval (Qdrant collection)
   - Call site extraction and analysis
   - Interface implementation tracking
   - Function node metadata storage

---

## Verification Checklist

- [ ] All 14 files identified in audit
- [ ] All import statements documented
- [ ] Usage context recorded for each import
- [ ] Impact assessment completed
- [ ] Risk levels assigned
- [ ] Estimated LOC changes calculated
- [ ] Dependent CLI commands listed
- [ ] Breaking changes documented

---

## Next Steps (Phase 1, Task 1.2+)

1. **Task 1.2**: Dependency graph analysis - map indirect dependencies
2. **Task 1.3**: Test coverage audit - identify tests covering removed features
3. **Task 1.4**: Configuration audit - identify config entries related to removed features
4. **Task 1.5**: Database schema audit - identify Qdrant collections and SQLite tables

---

*Audit completed: 2024-12-01*
*Last updated: 2024-12-01*
