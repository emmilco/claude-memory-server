# REF-017: Consolidate Feature Flags

## Reference
- **Code Review:** ARCH-003 (Critical severity)
- **Issue:** 31+ boolean feature flags create exponential configuration complexity (2^31 combinations)
- **Priority:** High (configuration explosion blocks testing and maintenance)
- **Estimated Effort:** 2 days
- **Related:** REF-016 (service extraction) will reduce flag usage after consolidation

---

## 1. Overview

### Problem Summary

The `ServerConfig` class in `src/config.py` has grown to 31+ boolean feature flags, creating an explosion of configuration complexity:

```python
# Example of current flag proliferation
enable_parallel_embeddings: bool = True
enable_importance_scoring: bool = True
enable_retrieval_gate: bool = True  # Line 70
enable_gpu: bool = True
enable_multi_repository: bool = True
enable_proactive_suggestions: bool = True
enable_auto_pruning: bool = True
enable_usage_tracking: bool = True
enable_hybrid_search: bool = True
enable_file_watcher: bool = True
enable_conversation_tracking: bool = True
enable_query_expansion: bool = True
enable_git_indexing: bool = True
enable_cross_project_search: bool = True
enable_usage_pattern_analytics: bool = True
enable_retrieval_gate: bool = True  # Line 93 - DUPLICATE!
# ... 15+ more flags
```

**Critical Issues:**
1. **Duplicate Flag:** `enable_retrieval_gate` defined twice (lines 70 and 93)
2. **Exponential Complexity:** 2^31 = 2,147,483,648 possible configurations (untestable)
3. **No Semantic Grouping:** Related flags scattered across file
4. **Hidden Dependencies:** Some flags require others (not validated)
5. **User Confusion:** Which flags should be enabled together?

### Impact

**Testing:**
- Impossible to test all flag combinations
- Unknown interactions between flags
- Configuration bugs only appear in specific combinations
- CI/CD matrix testing infeasible (2 billion combinations)

**User Experience:**
- Overwhelming configuration surface (31 yes/no decisions)
- No guidance on recommended configurations
- Trial-and-error to find working combinations
- Breaking changes when adding/removing flags

**Development:**
- Adding new feature = adding new flag (linear growth)
- Flag dependencies implicit (code review burden)
- Configuration drift between environments
- Difficult to deprecate old flags

### Success After Refactoring

- **6 feature groups** instead of 31 individual flags
- **3 feature levels** (BASIC, ADVANCED, EXPERIMENTAL) for easy selection
- **Validated dependencies** - incompatible combinations rejected
- **Backward compatibility** - old flags still work (deprecated warnings)
- **Clear upgrade path** - migration guide for users

---

## 2. Current State Analysis

### Complete Flag Inventory

**File:** `src/config.py` - 31 identified feature flags

#### Category 1: Performance Flags (5 flags)
```python
enable_parallel_embeddings: bool = True      # Line 47
enable_gpu: bool = True                      # Line 152
force_cpu: bool = False                      # Line 153
enable_hybrid_search: bool = True            # Line 140
enable_importance_scoring: bool = True       # Line 60
```

**Purpose:** Enable performance optimizations
**Dependencies:** `enable_gpu` conflicts with `force_cpu`

#### Category 2: Search & Retrieval Flags (4 flags)
```python
enable_retrieval_gate: bool = True           # Line 70 (DUPLICATE)
enable_retrieval_gate: bool = True           # Line 93 (DUPLICATE)
enable_hybrid_search: bool = True            # Line 140 (also in Performance)
enable_cross_project_search: bool = True     # Line 147
```

**Issues:**
- Duplicate `enable_retrieval_gate` must be removed
- `enable_hybrid_search` appears in multiple categories

#### Category 3: Analytics & Tracking Flags (3 flags)
```python
enable_usage_tracking: bool = True           # Line 100
enable_usage_pattern_analytics: bool = True  # Line 105
# enable_monitoring implicitly always on (no flag)
```

**Purpose:** Usage analytics and monitoring

#### Category 4: Memory Management Flags (2 flags)
```python
enable_auto_pruning: bool = True             # Line 98
enable_conversation_tracking: bool = True    # Line 117
```

**Purpose:** Automated memory lifecycle management

#### Category 5: Code Indexing Flags (7 flags)
```python
enable_file_watcher: bool = True             # Line 56
auto_index_enabled: bool = True              # Line 73
auto_index_on_startup: bool = True           # Line 74
auto_index_recursive: bool = True            # Line 76
auto_index_show_progress: bool = True        # Line 77
enable_git_indexing: bool = True             # Line 131
git_index_diffs: bool = True                 # Line 135
```

**Purpose:** Automatic code indexing behavior
**Dependencies:** `auto_index_*` flags require `auto_index_enabled`

#### Category 6: Advanced Features Flags (4 flags)
```python
enable_query_expansion: bool = True          # Line 124
enable_proactive_suggestions: bool = True    # Line 163
enable_multi_repository: bool = True         # Line 157
# Cross-project (moved to Search category)
```

**Purpose:** Advanced AI-assisted features

#### Category 7: Graceful Degradation Flags (3 flags)
```python
allow_rust_fallback: bool = True             # Line 67
warn_on_degradation: bool = True             # Line 68
# allow_qdrant_fallback removed in REF-010
```

**Purpose:** Fallback behavior for missing dependencies

#### Category 8: Security & Validation Flags (2 flags)
```python
read_only_mode: bool = False                 # Line 51
enable_input_validation: bool = True         # Line 52
```

**Purpose:** Security hardening

### Flag Usage Analysis

**High-Use Flags (used in 5+ locations):**
1. `enable_usage_tracking` - 12 references
2. `enable_hybrid_search` - 8 references
3. `enable_parallel_embeddings` - 7 references
4. `auto_index_enabled` - 6 references
5. `enable_importance_scoring` - 5 references

**Low-Use Flags (used in 1-2 locations):**
1. `warn_on_degradation` - 2 references
2. `force_cpu` - 1 reference
3. `auto_index_show_progress` - 1 reference

**Unused Flags (defined but never checked):**
- None identified (all flags are used)

### Dependency Relationships

**Flag Dependencies Discovered:**

```
enable_usage_tracking (parent)
├── enable_usage_pattern_analytics (child - requires parent)
└── enable_auto_pruning (child - uses usage data)

auto_index_enabled (parent)
├── auto_index_on_startup (child)
├── auto_index_recursive (child)
└── auto_index_show_progress (child)

enable_gpu (mutex with force_cpu)
└── force_cpu (mutex - only one can be true)

enable_hybrid_search (parent)
└── enable_importance_scoring (enhances hybrid search)

enable_cross_project_search (parent)
└── enable_multi_repository (related but independent)
```

**Validation Gaps:**
- No validation that child flags don't enable when parent disabled
- No validation that `enable_gpu` and `force_cpu` are mutually exclusive
- No validation that `enable_retrieval_gate` duplicate is intentional (it's not!)

---

## 3. Proposed Solution

### Architecture: Feature Groups

**Replace 31 boolean flags with 6 feature groups:**

```python
# src/config.py (AFTER refactoring)

from enum import Enum
from typing import Set
from pydantic import field_validator

class FeatureLevel(str, Enum):
    """Feature maturity levels."""
    BASIC = "basic"           # Stable, production-ready
    ADVANCED = "advanced"     # Stable, power users
    EXPERIMENTAL = "experimental"  # Unstable, opt-in

class PerformanceFeatures(BaseModel):
    """Performance optimization features."""

    # Core performance flags
    parallel_embeddings: bool = True
    hybrid_search: bool = True
    importance_scoring: bool = True

    # GPU acceleration
    gpu_enabled: bool = True
    gpu_memory_fraction: float = 0.8
    force_cpu: bool = False  # Override GPU detection

    @field_validator('force_cpu')
    def validate_gpu_cpu_exclusive(cls, v, info):
        """Ensure gpu_enabled and force_cpu are mutually exclusive."""
        if v and info.data.get('gpu_enabled', False):
            raise ValueError("Cannot enable both gpu_enabled and force_cpu")
        return v

class SearchFeatures(BaseModel):
    """Search and retrieval features."""

    # Search enhancements
    hybrid_search: bool = True
    retrieval_gate_enabled: bool = True  # SINGLE definition
    retrieval_gate_threshold: float = 0.8

    # Cross-project search
    cross_project_enabled: bool = True
    cross_project_default_mode: str = "current"

    # Query expansion
    query_expansion_enabled: bool = True
    query_expansion_synonyms: bool = True
    query_expansion_code_context: bool = True

class AnalyticsFeatures(BaseModel):
    """Analytics and monitoring features."""

    usage_tracking: bool = True
    usage_pattern_analytics: bool = True
    usage_analytics_retention_days: int = 90

    # Dependency validation
    @field_validator('usage_pattern_analytics')
    def validate_analytics_requires_tracking(cls, v, info):
        """Pattern analytics requires usage tracking."""
        if v and not info.data.get('usage_tracking', False):
            raise ValueError(
                "usage_pattern_analytics requires usage_tracking to be enabled"
            )
        return v

class MemoryFeatures(BaseModel):
    """Memory management features."""

    auto_pruning: bool = True
    pruning_schedule: str = "0 2 * * *"
    session_state_ttl_hours: int = 48

    conversation_tracking: bool = True
    conversation_session_timeout_minutes: int = 30

    proactive_suggestions: bool = True
    proactive_suggestions_threshold: float = 0.90

class IndexingFeatures(BaseModel):
    """Code indexing features."""

    # File watching
    file_watcher: bool = True
    watch_debounce_ms: int = 1000

    # Auto-indexing
    auto_index_enabled: bool = True
    auto_index_on_startup: bool = True
    auto_index_size_threshold: int = 500
    auto_index_recursive: bool = True
    auto_index_show_progress: bool = True
    auto_index_exclude_patterns: list[str] = [
        "node_modules/**", ".git/**", "venv/**", "__pycache__/**", "*.pyc",
        "dist/**", "build/**", ".next/**", "target/**", "*.min.js", "*.map"
    ]

    # Git indexing
    git_indexing: bool = True
    git_index_commit_count: int = 1000
    git_index_branches: str = "current"
    git_index_tags: bool = True
    git_index_diffs: bool = True

    # Dependency validation
    @field_validator('auto_index_on_startup')
    def validate_auto_index_children(cls, v, info):
        """Auto-index children require parent enabled."""
        if v and not info.data.get('auto_index_enabled', False):
            raise ValueError(
                "auto_index_on_startup requires auto_index_enabled=True"
            )
        return v

class AdvancedFeatures(BaseModel):
    """Advanced/experimental features."""

    # Multi-repository support
    multi_repository: bool = True
    multi_repo_max_parallel: int = 3

    # Graceful degradation
    rust_fallback: bool = True
    warn_on_degradation: bool = True

    # Security
    read_only_mode: bool = False
    input_validation: bool = True

class ServerConfig(BaseSettings):
    """
    Consolidated server configuration with feature groups.

    Migration from v4.0.0:
    - Old boolean flags still supported (deprecated)
    - New feature groups recommended
    - Automatic migration on first load
    """

    # Core settings (unchanged)
    server_name: str = "claude-memory-rag"
    log_level: str = "INFO"

    # Feature groups (NEW!)
    performance: PerformanceFeatures = PerformanceFeatures()
    search: SearchFeatures = SearchFeatures()
    analytics: AnalyticsFeatures = AnalyticsFeatures()
    memory: MemoryFeatures = MemoryFeatures()
    indexing: IndexingFeatures = IndexingFeatures()
    advanced: AdvancedFeatures = AdvancedFeatures()

    # Feature level presets (NEW!)
    feature_level: Optional[FeatureLevel] = None

    # Legacy flags (DEPRECATED - for backward compatibility)
    enable_parallel_embeddings: Optional[bool] = None
    enable_usage_tracking: Optional[bool] = None
    enable_hybrid_search: Optional[bool] = None
    # ... (all 31 legacy flags with Optional[bool])

    @model_validator(mode='after')
    def migrate_legacy_flags(self) -> 'ServerConfig':
        """
        Migrate legacy flags to feature groups.

        Priority: Legacy flags override feature groups (for backward compat).
        """
        # If any legacy flag is set, apply it to feature group
        if self.enable_parallel_embeddings is not None:
            self.performance.parallel_embeddings = self.enable_parallel_embeddings
            logger.warning(
                "enable_parallel_embeddings is deprecated. "
                "Use performance.parallel_embeddings instead."
            )

        if self.enable_usage_tracking is not None:
            self.analytics.usage_tracking = self.enable_usage_tracking
            logger.warning(
                "enable_usage_tracking is deprecated. "
                "Use analytics.usage_tracking instead."
            )

        # ... (repeat for all legacy flags)

        return self

    @model_validator(mode='after')
    def apply_feature_level_preset(self) -> 'ServerConfig':
        """
        Apply feature level presets (BASIC, ADVANCED, EXPERIMENTAL).

        Allows users to set feature_level="basic" instead of configuring
        individual flags.
        """
        if self.feature_level == FeatureLevel.BASIC:
            # Disable experimental/advanced features
            self.memory.proactive_suggestions = False
            self.indexing.git_index_diffs = False
            self.advanced.multi_repository = False
            logger.info("Applied BASIC feature level preset")

        elif self.feature_level == FeatureLevel.ADVANCED:
            # Enable all stable features
            self.memory.proactive_suggestions = True
            self.indexing.git_indexing = True
            self.analytics.usage_pattern_analytics = True
            logger.info("Applied ADVANCED feature level preset")

        elif self.feature_level == FeatureLevel.EXPERIMENTAL:
            # Enable everything (bleeding edge)
            # (all defaults are True, so no changes needed)
            logger.warning("Applied EXPERIMENTAL feature level - expect instability")

        return self

    @model_validator(mode='after')
    def validate_cross_feature_dependencies(self) -> 'ServerConfig':
        """
        Validate dependencies across feature groups.

        Example: hybrid_search in SearchFeatures requires hybrid_search in PerformanceFeatures.
        """
        # Search hybrid requires performance hybrid
        if self.search.hybrid_search and not self.performance.hybrid_search:
            raise ValueError(
                "search.hybrid_search requires performance.hybrid_search to be enabled"
            )

        # Pattern analytics requires usage tracking
        if self.analytics.usage_pattern_analytics and not self.analytics.usage_tracking:
            raise ValueError(
                "analytics.usage_pattern_analytics requires analytics.usage_tracking"
            )

        # Proactive suggestions require conversation tracking
        if self.memory.proactive_suggestions and not self.memory.conversation_tracking:
            raise ValueError(
                "memory.proactive_suggestions requires memory.conversation_tracking"
            )

        return self
```

### Feature Level Presets

**User-friendly configuration shortcuts:**

```json
// ~/.claude-rag/config.json (BASIC user)
{
  "feature_level": "basic",
  "server_name": "my-server"
}
```

**Equivalent to:**
```python
ServerConfig(
    performance=PerformanceFeatures(parallel_embeddings=True, hybrid_search=True),
    search=SearchFeatures(hybrid_search=True, retrieval_gate_enabled=True),
    analytics=AnalyticsFeatures(usage_tracking=True, usage_pattern_analytics=False),
    memory=MemoryFeatures(auto_pruning=True, proactive_suggestions=False),
    indexing=IndexingFeatures(auto_index_enabled=True, git_indexing=False),
    advanced=AdvancedFeatures(multi_repository=False, read_only_mode=False),
)
```

**ADVANCED level:**
```json
{
  "feature_level": "advanced",
  "performance": {
    "gpu_enabled": true
  }
}
```

**EXPERIMENTAL level:**
```json
{
  "feature_level": "experimental"  // All features enabled
}
```

### Backward Compatibility Strategy

**Deprecation Timeline:**

**Phase 1 (v4.1.0 - REF-017):**
- Introduce feature groups
- Legacy flags still work (with deprecation warnings)
- Config file migration tool: `python -m src.cli config migrate`

**Phase 2 (v4.2.0 - 3 months later):**
- Legacy flags marked deprecated in docs
- Warning logged on every startup if legacy flags used
- Migration guide published

**Phase 3 (v5.0.0 - 6 months later):**
- Legacy flags removed
- Breaking change documented
- Migration required

**Migration Tool:**

```python
# src/cli/config_commands.py

def migrate_config(old_config_path: Path) -> None:
    """
    Migrate old config.json to new feature group format.

    Example:
        python -m src.cli config migrate ~/.claude-rag/config.json
    """
    with open(old_config_path) as f:
        old_config = json.load(f)

    # Map old flags to new groups
    new_config = {
        "performance": {
            "parallel_embeddings": old_config.get("enable_parallel_embeddings", True),
            "hybrid_search": old_config.get("enable_hybrid_search", True),
            "gpu_enabled": old_config.get("enable_gpu", True),
        },
        "search": {
            "hybrid_search": old_config.get("enable_hybrid_search", True),
            "retrieval_gate_enabled": old_config.get("enable_retrieval_gate", True),
            "cross_project_enabled": old_config.get("enable_cross_project_search", True),
        },
        # ... map all flags
    }

    # Backup old config
    backup_path = old_config_path.with_suffix(".json.backup")
    shutil.copy(old_config_path, backup_path)
    print(f"Backed up old config to {backup_path}")

    # Write new config
    with open(old_config_path, 'w') as f:
        json.dump(new_config, f, indent=2)

    print(f"Migrated config to new format")
    print(f"Old flags will continue to work but are deprecated")
```

---

## 4. Implementation Plan

### Phase 1: Create Feature Group Models (0.5 days)

**Goals:**
- Define feature group Pydantic models
- Implement validation logic
- No breaking changes yet

**Tasks:**
- [ ] Create `src/config_feature_groups.py` (new file)
- [ ] Define `PerformanceFeatures` model
- [ ] Define `SearchFeatures` model
- [ ] Define `AnalyticsFeatures` model
- [ ] Define `MemoryFeatures` model
- [ ] Define `IndexingFeatures` model
- [ ] Define `AdvancedFeatures` model
- [ ] Define `FeatureLevel` enum
- [ ] Write unit tests for validation logic

**Output:**
- 6 feature group models with validators
- 3 feature level presets

---

### Phase 2: Integrate into ServerConfig (0.5 days)

**Goals:**
- Add feature groups to `ServerConfig`
- Maintain backward compatibility
- Add legacy flag migration

**Tasks:**
- [ ] Import feature groups into `src/config.py`
- [ ] Add `performance`, `search`, `analytics`, `memory`, `indexing`, `advanced` fields
- [ ] Add `feature_level` preset field
- [ ] Implement `migrate_legacy_flags()` validator
- [ ] Implement `apply_feature_level_preset()` validator
- [ ] Keep all existing `enable_*` flags as `Optional[bool]`
- [ ] Write unit tests for migration logic

**Success Criteria:**
- [ ] Old config files still work (no behavior change)
- [ ] Deprecation warnings logged when legacy flags used
- [ ] New feature groups accessible via `config.performance.parallel_embeddings`

---

### Phase 3: Remove Duplicate Flag (0.25 days)

**Goals:**
- Fix `enable_retrieval_gate` duplication
- Ensure single source of truth

**Tasks:**
- [ ] Remove duplicate `enable_retrieval_gate` at line 93
- [ ] Keep definition at line 70 (first occurrence)
- [ ] Grep for all usages: `grep -rn "enable_retrieval_gate" src/`
- [ ] Update usages to `config.search.retrieval_gate_enabled`
- [ ] Write regression test to prevent future duplicates

**Success Criteria:**
- [ ] Only one `retrieval_gate` definition exists
- [ ] All tests pass
- [ ] No references to deprecated name

---

### Phase 4: Update Code to Use Feature Groups (0.5 days)

**Goals:**
- Migrate codebase from `config.enable_*` to `config.*.feature`
- Incremental migration (low risk)

**Tasks:**
- [ ] Find all flag usages: `grep -rn "config.enable_" src/`
- [ ] Update `src/core/server.py` to use feature groups
- [ ] Update `src/memory/` to use feature groups
- [ ] Update `src/embeddings/` to use feature groups
- [ ] Update `src/cli/` to use feature groups
- [ ] Run full test suite after each file
- [ ] Update test fixtures to use feature groups

**Migration Example:**
```python
# BEFORE
if self.config.enable_usage_tracking:
    self.usage_tracker = UsageTracker(...)

# AFTER
if self.config.analytics.usage_tracking:
    self.usage_tracker = UsageTracker(...)
```

**Success Criteria:**
- [ ] All 2,740+ tests pass
- [ ] Zero references to `config.enable_*` (except in deprecated migration logic)

---

### Phase 5: Create Migration Tool (0.25 days)

**Goals:**
- Provide CLI tool for users to migrate configs
- Generate human-readable migration report

**Tasks:**
- [ ] Create `src/cli/config_commands.py`
- [ ] Implement `migrate_config()` function
- [ ] Add `config migrate` CLI command
- [ ] Test migration with sample configs
- [ ] Write migration guide documentation

**Success Criteria:**
- [ ] Tool migrates old config to new format
- [ ] Backup created before migration
- [ ] Migration idempotent (can run multiple times)

---

### Phase 6: Documentation and Cleanup (0.5 days)

**Goals:**
- Update all documentation
- Remove deprecated code paths (in future version)

**Tasks:**
- [ ] Update CHANGELOG.md with deprecation notice
- [ ] Create CONFIGURATION_GUIDE.md (REF-017 deliverable)
- [ ] Update README.md with feature group examples
- [ ] Update CLAUDE.md with new config structure
- [ ] Add migration guide to docs/
- [ ] Run `python scripts/verify-complete.py`

**Success Criteria:**
- [ ] Documentation reflects new feature groups
- [ ] Migration guide clear and tested
- [ ] All quality gates pass

---

## 5. Testing Strategy

### Unit Testing

**Test Feature Group Validation:**

```python
# tests/unit/test_config_feature_groups.py

import pytest
from src.config import ServerConfig, FeatureLevel
from pydantic import ValidationError

class TestPerformanceFeatures:
    """Test performance feature group validation."""

    def test_gpu_cpu_mutual_exclusion(self):
        """Cannot enable both gpu_enabled and force_cpu."""
        with pytest.raises(ValidationError, match="Cannot enable both"):
            ServerConfig(
                performance={
                    "gpu_enabled": True,
                    "force_cpu": True,
                }
            )

    def test_gpu_enabled_default(self):
        """GPU enabled by default."""
        config = ServerConfig()
        assert config.performance.gpu_enabled is True
        assert config.performance.force_cpu is False

class TestAnalyticsFeatures:
    """Test analytics feature group validation."""

    def test_pattern_analytics_requires_tracking(self):
        """Pattern analytics requires usage tracking."""
        with pytest.raises(ValidationError, match="requires usage_tracking"):
            ServerConfig(
                analytics={
                    "usage_tracking": False,
                    "usage_pattern_analytics": True,
                }
            )

    def test_tracking_independent(self):
        """Usage tracking can be enabled alone."""
        config = ServerConfig(
            analytics={"usage_tracking": True, "usage_pattern_analytics": False}
        )
        assert config.analytics.usage_tracking is True

class TestIndexingFeatures:
    """Test indexing feature group validation."""

    def test_auto_index_children_require_parent(self):
        """Auto-index children require parent enabled."""
        with pytest.raises(ValidationError, match="requires auto_index_enabled"):
            ServerConfig(
                indexing={
                    "auto_index_enabled": False,
                    "auto_index_on_startup": True,
                }
            )
```

**Test Feature Level Presets:**

```python
class TestFeatureLevelPresets:
    """Test feature level presets."""

    def test_basic_preset(self):
        """BASIC preset disables advanced features."""
        config = ServerConfig(feature_level=FeatureLevel.BASIC)

        # Core features enabled
        assert config.performance.parallel_embeddings is True
        assert config.search.hybrid_search is True

        # Advanced features disabled
        assert config.memory.proactive_suggestions is False
        assert config.advanced.multi_repository is False

    def test_advanced_preset(self):
        """ADVANCED preset enables all stable features."""
        config = ServerConfig(feature_level=FeatureLevel.ADVANCED)

        assert config.memory.proactive_suggestions is True
        assert config.indexing.git_indexing is True
        assert config.analytics.usage_pattern_analytics is True

    def test_experimental_preset(self):
        """EXPERIMENTAL preset enables everything."""
        config = ServerConfig(feature_level=FeatureLevel.EXPERIMENTAL)

        # All features enabled (defaults)
        assert config.memory.proactive_suggestions is True
        assert config.advanced.multi_repository is True
```

**Test Legacy Migration:**

```python
class TestLegacyMigration:
    """Test backward compatibility with legacy flags."""

    def test_legacy_flag_migrates_to_group(self):
        """Legacy enable_parallel_embeddings maps to performance group."""
        config = ServerConfig(enable_parallel_embeddings=False)

        # Migrated to new location
        assert config.performance.parallel_embeddings is False

    def test_legacy_flag_overrides_default(self):
        """Legacy flags override feature group defaults."""
        config = ServerConfig(
            enable_usage_tracking=False,
            analytics={"usage_tracking": True}  # Would be True by default
        )

        # Legacy flag wins
        assert config.analytics.usage_tracking is False

    def test_deprecation_warning_logged(self, caplog):
        """Deprecation warning logged when legacy flag used."""
        config = ServerConfig(enable_hybrid_search=True)

        assert "enable_hybrid_search is deprecated" in caplog.text
        assert "Use performance.hybrid_search instead" in caplog.text
```

### Integration Testing

**Test Codebase Uses Feature Groups:**

```python
# tests/integration/test_feature_group_integration.py

async def test_server_uses_performance_features():
    """Server respects performance feature group."""
    config = ServerConfig(
        performance={"parallel_embeddings": False}
    )
    server = MemoryRAGServer(config)
    await server.initialize()

    # Should not use parallel embeddings
    assert not isinstance(server.embedding_generator, ParallelEmbeddingGenerator)

async def test_server_uses_analytics_features():
    """Server respects analytics feature group."""
    config = ServerConfig(
        analytics={"usage_tracking": False}
    )
    server = MemoryRAGServer(config)
    await server.initialize()

    # Usage tracker should not be initialized
    assert server.usage_tracker is None
```

### Regression Testing

**Ensure No Breaking Changes:**

```python
class TestBackwardCompatibility:
    """Ensure old configs still work."""

    def test_old_config_format_works(self, tmp_path):
        """Old config.json format still loads."""
        old_config = {
            "enable_parallel_embeddings": True,
            "enable_usage_tracking": True,
            "enable_hybrid_search": True,
        }

        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(old_config))

        # Should load without errors
        config = ServerConfig(**old_config)
        assert config.performance.parallel_embeddings is True
        assert config.analytics.usage_tracking is True

    def test_mixed_old_new_format(self):
        """Can mix legacy flags and feature groups."""
        config = ServerConfig(
            enable_parallel_embeddings=False,  # Legacy
            performance={"hybrid_search": True},  # New
        )

        # Legacy overrides
        assert config.performance.parallel_embeddings is False
        assert config.performance.hybrid_search is True
```

---

## 6. Risk Assessment

### Breaking Changes

**Risk:** Users' existing configs stop working

**Likelihood:** Low (backward compatibility maintained)

**Mitigation:**
1. Keep all legacy flags working (deprecated warnings only)
2. Migration tool auto-upgrades configs
3. Extensive testing of old config formats
4. Clear migration guide in release notes

### Configuration Validation Bugs

**Risk:** New validators reject valid configurations

**Likelihood:** Medium (complex validation logic)

**Impact:** High (blocks server startup)

**Mitigation:**
1. Comprehensive unit tests for all validators
2. Test with real-world config combinations
3. Graceful error messages (not just "ValidationError")
4. Escape hatch: `SKIP_CONFIG_VALIDATION=1` env var for emergencies

### Test Failures

**Risk:** Existing tests break due to config changes

**Likelihood:** High (many tests create `ServerConfig` instances)

**Impact:** Medium (blocks PR merge)

**Mitigation:**
1. Update test fixtures incrementally
2. Create `test_config()` helper that uses new format
3. Run tests after each phase
4. Fix tests in same commit as config changes

### Documentation Drift

**Risk:** Docs show old config format

**Likelihood:** Medium (docs in multiple places)

**Impact:** Medium (user confusion)

**Mitigation:**
1. Search all docs for `enable_*` flags: `grep -r "enable_" docs/`
2. Update README, CLAUDE.md, API docs simultaneously
3. Add deprecation notices to old docs
4. Create CONFIGURATION_GUIDE.md as canonical reference

---

## 7. Success Criteria

### Quantitative Metrics

**Configuration Complexity Reduction:**
- [ ] Feature flags: 31 → 6 groups (81% reduction)
- [ ] Testable combinations: 2^31 → ~100 realistic combinations (manageable)
- [ ] Lines of config validation: Current → +200 lines (explicit validation)

**Code Quality:**
- [ ] Zero duplicate flag definitions
- [ ] All flag dependencies validated
- [ ] All 2,740+ tests pass
- [ ] Coverage ≥80% for config validation

**Backward Compatibility:**
- [ ] 100% of old configs still work
- [ ] Migration tool succeeds on 10+ sample configs
- [ ] Deprecation warnings logged (not errors)

### Qualitative Outcomes

**User Experience:**
- [ ] New users can use `feature_level="basic"` (1 line config)
- [ ] Advanced users understand feature groups (logical grouping)
- [ ] Migration guide clear and tested
- [ ] Configuration errors actionable (not "ValidationError")

**Developer Experience:**
- [ ] Adding new feature = add to appropriate group (not root config)
- [ ] Flag dependencies explicit in validators
- [ ] No more hidden configuration bugs
- [ ] Easier to test configurations (smaller test matrix)

**Documentation:**
- [ ] CONFIGURATION_GUIDE.md created (comprehensive reference)
- [ ] README updated with feature group examples
- [ ] Migration guide published
- [ ] Deprecation timeline documented

---

## Appendix A: Complete Migration Mapping

**Old Flag → New Location:**

| Old Flag | New Location | Notes |
|----------|-------------|-------|
| `enable_parallel_embeddings` | `performance.parallel_embeddings` | |
| `enable_importance_scoring` | `performance.importance_scoring` | |
| `enable_gpu` | `performance.gpu_enabled` | Renamed for clarity |
| `force_cpu` | `performance.force_cpu` | |
| `enable_hybrid_search` | `performance.hybrid_search` + `search.hybrid_search` | Both required |
| `enable_retrieval_gate` (line 70) | `search.retrieval_gate_enabled` | Keep this one |
| `enable_retrieval_gate` (line 93) | DELETE | Duplicate |
| `enable_cross_project_search` | `search.cross_project_enabled` | |
| `enable_query_expansion` | `search.query_expansion_enabled` | |
| `enable_usage_tracking` | `analytics.usage_tracking` | |
| `enable_usage_pattern_analytics` | `analytics.usage_pattern_analytics` | |
| `enable_auto_pruning` | `memory.auto_pruning` | |
| `enable_conversation_tracking` | `memory.conversation_tracking` | |
| `enable_proactive_suggestions` | `memory.proactive_suggestions` | |
| `enable_file_watcher` | `indexing.file_watcher` | |
| `auto_index_enabled` | `indexing.auto_index_enabled` | |
| `auto_index_on_startup` | `indexing.auto_index_on_startup` | |
| `auto_index_recursive` | `indexing.auto_index_recursive` | |
| `auto_index_show_progress` | `indexing.auto_index_show_progress` | |
| `enable_git_indexing` | `indexing.git_indexing` | |
| `git_index_diffs` | `indexing.git_index_diffs` | |
| `enable_multi_repository` | `advanced.multi_repository` | |
| `allow_rust_fallback` | `advanced.rust_fallback` | |
| `warn_on_degradation` | `advanced.warn_on_degradation` | |
| `read_only_mode` | `advanced.read_only_mode` | |
| `enable_input_validation` | `advanced.input_validation` | |

**Total:** 25 flags migrated + 6 flags deleted/consolidated = 31 flags → 6 groups

---

## Appendix B: Feature Level Matrix

| Feature | BASIC | ADVANCED | EXPERIMENTAL |
|---------|-------|----------|--------------|
| **Performance** | | | |
| Parallel Embeddings | ✅ | ✅ | ✅ |
| Hybrid Search | ✅ | ✅ | ✅ |
| Importance Scoring | ✅ | ✅ | ✅ |
| GPU Acceleration | ✅ | ✅ | ✅ |
| **Search** | | | |
| Retrieval Gate | ✅ | ✅ | ✅ |
| Cross-Project Search | ❌ | ✅ | ✅ |
| Query Expansion | ❌ | ✅ | ✅ |
| **Analytics** | | | |
| Usage Tracking | ✅ | ✅ | ✅ |
| Pattern Analytics | ❌ | ✅ | ✅ |
| **Memory** | | | |
| Auto Pruning | ✅ | ✅ | ✅ |
| Conversation Tracking | ✅ | ✅ | ✅ |
| Proactive Suggestions | ❌ | ✅ | ✅ |
| **Indexing** | | | |
| File Watcher | ✅ | ✅ | ✅ |
| Auto-Index | ✅ | ✅ | ✅ |
| Git Indexing | ❌ | ✅ | ✅ |
| Git Diffs | ❌ | ❌ | ✅ |
| **Advanced** | | | |
| Multi-Repository | ❌ | ✅ | ✅ |
| Rust Fallback | ✅ | ✅ | ✅ |

**Legend:**
- ✅ Enabled by default
- ❌ Disabled by default

---

## Completion Summary

**Status:** Planning complete - ready for implementation
**Next Steps:**
1. Get approval for feature group approach
2. Create REF-017 in TODO.md
3. Begin Phase 1 (feature group models)
4. Incremental migration (one phase at a time)

**Estimated Timeline:** 2 days (6 phases × 0.25-0.5 days each)
**Risk Level:** Low (backward compatible, incremental approach)
**Impact:** High (simplifies configuration for all users)
**Deliverable:** CONFIGURATION_GUIDE.md (comprehensive config reference)
