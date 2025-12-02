# Test & Fixture Audit - SIMPLIFY-001

## Summary

- **Test files to remove:** 19
- **Test files to modify:** 4
- **Fixtures to remove:** 12
- **Estimated tests being removed:** 370

## Test Files to REMOVE

### tests/unit/

| File | Test Count | Description |
|------|------------|-------------|
| test_auto_tagger.py | 12 | Auto-tagging tests |
| test_backup_export.py | 4 | Backup export tests |
| test_backup_import.py | 4 | Backup import tests |
| test_archive_export_import.py | 18 | Archive compression tests |
| test_tag_manager.py | 13 | Tag manager tests |
| test_token_analytics.py | 13 | Token analytics tests |
| test_services/test_analytics_service.py | 41 | Analytics service tests |
| test_dependency_graph_generator.py | 20 | Dependency graph tests |
| test_dependency_graph.py | 26 | Dependency graph tests |
| test_get_dependency_graph.py | 16 | Dependency graph tests |
| test_graph_visualization.py | 37 | Graph visualization tests |
| test_graph_formatters.py | 31 | Graph formatting tests |
| graph/test_call_graph.py | 31 | Call graph tests |
| graph/test_call_graph_edge_cases.py | 28 | Call graph edge cases |
| store/test_call_graph_store.py | 16 | Call graph store tests |
| store/test_call_graph_store_edge_cases.py | 22 | Call graph store edge cases |

**Unit Tests Total: 332 tests across 16 files**

### tests/integration/

| File | Test Count | Description |
|------|------------|-------------|
| test_call_graph_indexing.py | 7 | Call graph indexing integration |
| test_call_graph_tools.py | 18 | Call graph tools integration |
| test_tagging_system.py | 13 | Tagging system integration |

**Integration Tests Total: 38 tests across 3 files**

**Total: 370 tests across 19 files**

## Test Files to MODIFY

| File | Tests | Changes Needed |
|------|-------|----------------|
| test_collection_manager.py | 12 | Remove tagging imports |
| test_session_summary.py | 3 | Remove analytics imports |
| test_structural_queries.py | 24 | Remove graph imports |
| test_usage_pattern_tracker.py | 29 | Remove analytics imports |

## Fixtures to REMOVE

### From test files being deleted:
| Fixture | File | Type |
|---------|------|------|
| temp_store | test_backup_export.py | pytest_asyncio |
| temp_store | test_backup_import.py | pytest_asyncio |
| sample_archive | test_archive_export_import.py | pytest_asyncio |
| temp_dirs | test_archive_export_import.py | pytest |
| compressor | test_archive_export_import.py | pytest |
| importer_compressor | test_archive_export_import.py | pytest |
| exporter | test_archive_export_import.py | pytest |
| importer | test_archive_export_import.py | pytest |
| simple_graph | test_dependency_graph_generator.py | pytest |
| circular_graph | test_dependency_graph_generator.py | pytest |

## Fixtures to KEEP

| Fixture | File | Reason |
|---------|------|--------|
| qdrant_client | tests/conftest.py | Used by core tests |
| unique_qdrant_collection | tests/conftest.py | Used by core tests |
| mock_embedding_cache | tests/conftest.py | Used by memory/search tests |
| mock_embeddings | tests/conftest.py | Used by core tests |

## Impact by Category

| Category | Files | Tests | LOC |
|----------|-------|-------|-----|
| Graph/Visualization | 13 | 215 | ~4,373 |
| Backup/Export/Import | 3 | 26 | ~926 |
| Tagging | 3 | 28 | ~652 |
| Analytics | 3 | 67 | ~984 |
| **TOTAL** | **19** | **370** | **~7,810** |

## Removal Checklist

### Unit Tests to DELETE
- [ ] tests/unit/test_auto_tagger.py
- [ ] tests/unit/test_backup_export.py
- [ ] tests/unit/test_backup_import.py
- [ ] tests/unit/test_archive_export_import.py
- [ ] tests/unit/test_tag_manager.py
- [ ] tests/unit/test_token_analytics.py
- [ ] tests/unit/test_services/test_analytics_service.py
- [ ] tests/unit/test_dependency_graph_generator.py
- [ ] tests/unit/test_dependency_graph.py
- [ ] tests/unit/test_get_dependency_graph.py
- [ ] tests/unit/test_graph_visualization.py
- [ ] tests/unit/test_graph_formatters.py
- [ ] tests/unit/graph/test_call_graph.py
- [ ] tests/unit/graph/test_call_graph_edge_cases.py
- [ ] tests/unit/store/test_call_graph_store.py
- [ ] tests/unit/store/test_call_graph_store_edge_cases.py

### Integration Tests to DELETE
- [ ] tests/integration/test_call_graph_indexing.py
- [ ] tests/integration/test_call_graph_tools.py
- [ ] tests/integration/test_tagging_system.py

### Tests to MODIFY
- [ ] tests/unit/test_collection_manager.py
- [ ] tests/unit/test_session_summary.py
- [ ] tests/unit/test_structural_queries.py
- [ ] tests/unit/test_usage_pattern_tracker.py

### Conftest Updates
- [ ] Review tests/conftest.py for orphaned fixtures
- [ ] Review tests/unit/conftest.py if needed
