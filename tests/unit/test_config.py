"""Unit tests for configuration module."""

import pytest
import os
from pathlib import Path
from src.config import ServerConfig, get_config, set_config


def test_config_defaults():
    """Test that configuration loads with default values."""
    import os
    config = ServerConfig()
    assert config.server_name == "claude-memory-rag"
    assert config.log_level == "INFO"
    assert config.storage_backend == "qdrant"  # REF-010: Qdrant is now required for semantic search
    # Check qdrant_url - either default or from environment (for isolated test runner)
    expected_url = os.getenv("CLAUDE_RAG_QDRANT_URL", "http://localhost:6333")
    assert config.qdrant_url == expected_url
    assert config.embedding_batch_size == 128  # Larger batches for MPS GPU acceleration
    assert config.embedding_model == "all-mpnet-base-v2"  # 768 dims, better quality
    # REF-017: Check feature group instead of legacy flat field
    assert config.advanced.read_only_mode is False


def test_config_from_env(monkeypatch):
    """Test that configuration loads from environment variables."""
    monkeypatch.setenv("CLAUDE_RAG_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("CLAUDE_RAG_QDRANT_URL", "http://custom:6333")

    config = ServerConfig()
    assert config.log_level == "DEBUG"
    assert config.qdrant_url == "http://custom:6333"


def test_config_storage_backend_validation():
    """Test that storage backend only accepts valid values."""
    # Valid backend (only qdrant is supported after REF-010)
    config1 = ServerConfig(storage_backend="qdrant")
    assert config1.storage_backend == "qdrant"

    # SQLite is no longer supported (REF-010)
    with pytest.raises(Exception):  # Pydantic validation error
        ServerConfig(storage_backend="sqlite")

    # Invalid backend should raise validation error
    with pytest.raises(Exception):  # Pydantic validation error
        ServerConfig(storage_backend="invalid")


def test_path_expansion():
    """Test that paths are expanded correctly."""
    # Test with embedding cache path (SQLite removed in REF-010)
    config = ServerConfig(embedding_cache_path="~/.claude-rag/test_cache.db")
    expanded_path = Path(config.embedding_cache_path).expanduser()
    assert isinstance(expanded_path, Path)
    assert "~" not in str(expanded_path)


def test_global_config():
    """Test global configuration singleton."""
    config1 = get_config()
    config2 = get_config()
    assert config1 is config2

    # Test setting custom config
    custom_config = ServerConfig(server_name="custom-server")
    set_config(custom_config)
    assert get_config().server_name == "custom-server"


def test_embedding_cache_settings():
    """Test embedding cache configuration."""
    config = ServerConfig()
    assert config.embedding_cache_enabled is True
    assert config.embedding_cache_ttl_days == 30
    assert "embedding_cache.db" in config.embedding_cache_path


def test_security_settings():
    """Test security-related configuration."""
    config = ServerConfig()
    # REF-017: Check feature group instead of legacy flat field
    assert config.advanced.input_validation is True
    assert config.max_memory_size_bytes == 10240


# REF-017: New tests for feature groups
def test_feature_groups_exist():
    """Test that all feature groups are initialized."""
    config = ServerConfig()
    assert config.performance is not None
    assert config.search is not None
    assert config.analytics is not None
    assert config.memory is not None
    assert config.indexing is not None
    assert config.advanced is not None


def test_performance_features():
    """Test performance feature group."""
    config = ServerConfig()
    assert config.performance.parallel_embeddings is True
    assert config.performance.hybrid_search is True
    assert config.performance.importance_scoring is True
    assert config.performance.gpu_enabled is True
    assert config.performance.force_cpu is False


def test_search_features():
    """Test search feature group."""
    config = ServerConfig()
    assert config.search.hybrid_search is True
    assert config.search.retrieval_gate_enabled is True
    assert config.search.cross_project_enabled is True
    assert config.search.query_expansion_enabled is True


def test_analytics_features():
    """Test analytics feature group."""
    config = ServerConfig()
    assert config.analytics.usage_tracking is True
    assert config.analytics.usage_pattern_analytics is True
    assert config.analytics.usage_analytics_retention_days == 90


def test_memory_features():
    """Test memory feature group."""
    config = ServerConfig()
    assert config.memory.auto_pruning is True
    assert config.memory.conversation_tracking is True
    assert config.memory.proactive_suggestions is True
    assert config.memory.session_state_ttl_hours == 48


def test_indexing_features():
    """Test indexing feature group."""
    config = ServerConfig()
    assert config.indexing.file_watcher is True
    # Note: auto_index_enabled might be False depending on environment/config file
    assert config.indexing.auto_index_enabled is not None
    assert config.indexing.git_indexing is True


def test_advanced_features():
    """Test advanced feature group."""
    config = ServerConfig()
    assert config.advanced.multi_repository is True
    assert config.advanced.rust_fallback is True
    assert config.advanced.warn_on_degradation is True
    assert config.advanced.read_only_mode is False
    assert config.advanced.input_validation is True


def test_gpu_cpu_mutual_exclusion():
    """Test that gpu_enabled and force_cpu cannot both be True."""
    with pytest.raises(Exception):  # Pydantic validation error
        ServerConfig(performance={"gpu_enabled": True, "force_cpu": True})


def test_analytics_dependency_validation():
    """Test that pattern analytics requires usage tracking."""
    with pytest.raises(Exception):  # Pydantic validation error
        ServerConfig(analytics={"usage_tracking": False, "usage_pattern_analytics": True})


def test_feature_level_presets():
    """Test feature level presets work correctly."""
    from src.config import FeatureLevel

    # Basic preset
    basic_config = ServerConfig(feature_level=FeatureLevel.BASIC)
    assert basic_config.memory.proactive_suggestions is False
    assert basic_config.advanced.multi_repository is False

    # Advanced preset
    advanced_config = ServerConfig(feature_level=FeatureLevel.ADVANCED)
    assert advanced_config.memory.proactive_suggestions is True
    assert advanced_config.indexing.git_indexing is True


def test_feature_group_customization():
    """Test that feature groups can be customized."""
    config = ServerConfig(
        performance={"parallel_embeddings": False, "gpu_enabled": False},
        search={"cross_project_enabled": False}
    )
    assert config.performance.parallel_embeddings is False
    assert config.performance.gpu_enabled is False
    assert config.search.cross_project_enabled is False


# UX-051: Configuration Validation Tests
class TestRankingWeightValidation:
    """Tests for ranking weight validation (UX-051)."""

    def test_ranking_weights_must_sum_to_one(self):
        """Test that ranking weights must sum to 1.0."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(
                ranking_weight_similarity=0.5,
                ranking_weight_recency=0.5,
                ranking_weight_usage=0.5  # Sum = 1.5, should fail
            )

        error_msg = str(exc_info.value)
        assert "must sum to 1.0" in error_msg
        assert "1.500" in error_msg  # Shows the actual sum

    def test_ranking_weights_cannot_be_negative(self):
        """Test that ranking weights cannot be negative."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(
                ranking_weight_similarity=1.2,
                ranking_weight_recency=-0.1,
                ranking_weight_usage=-0.1
            )

        error_msg = str(exc_info.value)
        assert "cannot be negative" in error_msg

    def test_error_shows_current_values(self):
        """Test that error message shows current weight values."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(
                ranking_weight_similarity=0.65,
                ranking_weight_recency=0.20,
                ranking_weight_usage=0.20  # Sum = 1.05
            )

        error_msg = str(exc_info.value)
        assert "similarity: 0.65" in error_msg
        assert "recency: 0.2" in error_msg or "recency: 0.20" in error_msg
        assert "usage: 0.2" in error_msg or "usage: 0.20" in error_msg
        assert "Suggestion" in error_msg

    def test_exact_one_accepted(self):
        """Test that weights summing to exactly 1.0 are accepted."""
        config = ServerConfig(
            ranking_weight_similarity=0.6,
            ranking_weight_recency=0.2,
            ranking_weight_usage=0.2
        )
        assert config.ranking_weight_similarity == 0.6
        assert config.ranking_weight_recency == 0.2
        assert config.ranking_weight_usage == 0.2

    def test_tolerance_allows_small_errors(self):
        """Test that small floating point errors within tolerance are accepted."""
        # Within ±0.01 tolerance (edge case: exactly at boundary)
        config = ServerConfig(
            ranking_weight_similarity=0.605,
            ranking_weight_recency=0.200,
            ranking_weight_usage=0.195  # Sum = 1.0 (within tolerance)
        )
        assert config.ranking_weight_similarity == 0.605

        config2 = ServerConfig(
            ranking_weight_similarity=0.595,
            ranking_weight_recency=0.205,
            ranking_weight_usage=0.200  # Sum = 1.0 (within tolerance)
        )
        assert config2.ranking_weight_similarity == 0.595

    def test_outside_tolerance_rejected(self):
        """Test that errors outside tolerance are rejected."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            ServerConfig(
                ranking_weight_similarity=0.62,
                ranking_weight_recency=0.20,
                ranking_weight_usage=0.20  # Sum = 1.02, outside tolerance
            )


class TestProbabilityThresholdValidation:
    """Tests for probability threshold validation (UX-051)."""

    def test_retrieval_gate_threshold_must_be_probability(self):
        """Test that retrieval_gate_threshold must be in [0.0, 1.0]."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(search={"retrieval_gate_threshold": 1.5})

        error_msg = str(exc_info.value)
        assert "must be between 0.0 and 1.0" in error_msg
        assert "1.5" in error_msg

    def test_hybrid_search_alpha_must_be_probability(self):
        """Test that hybrid_search_alpha must be in [0.0, 1.0]."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(hybrid_search_alpha=-0.1)

        error_msg = str(exc_info.value)
        assert "must be between 0.0 and 1.0" in error_msg

    def test_proactive_suggestions_threshold_must_be_probability(self):
        """Test that proactive_suggestions_threshold must be in [0.0, 1.0]."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(memory={"proactive_suggestions_threshold": 1.5})

        error_msg = str(exc_info.value)
        assert "must be between 0.0 and 1.0" in error_msg

    def test_query_expansion_threshold_must_be_probability(self):
        """Test that query_expansion_similarity_threshold must be in [0.0, 1.0]."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(query_expansion_similarity_threshold=2.0)

        error_msg = str(exc_info.value)
        assert "must be between 0.0 and 1.0" in error_msg

    def test_valid_thresholds_accepted(self):
        """Test that valid threshold values are accepted."""
        config = ServerConfig(
            hybrid_search_alpha=0.7,
            query_expansion_similarity_threshold=0.6,
            search={"retrieval_gate_threshold": 0.8},
            memory={"proactive_suggestions_threshold": 0.9}
        )
        assert config.hybrid_search_alpha == 0.7
        assert config.query_expansion_similarity_threshold == 0.6
        assert config.search.retrieval_gate_threshold == 0.8
        assert config.memory.proactive_suggestions_threshold == 0.9

    def test_boundary_values_accepted(self):
        """Test that boundary values 0.0 and 1.0 are accepted."""
        config = ServerConfig(
            hybrid_search_alpha=0.0,
            query_expansion_similarity_threshold=1.0
        )
        assert config.hybrid_search_alpha == 0.0
        assert config.query_expansion_similarity_threshold == 1.0


class TestInterdependencyValidation:
    """Tests for feature interdependency validation (UX-051)."""

    def test_hybrid_alpha_requires_hybrid_enabled(self):
        """Test that custom hybrid_search_alpha requires hybrid search enabled."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(
                search={"hybrid_search": False},
                performance={"hybrid_search": False},
                hybrid_search_alpha=0.7  # Not default (0.5)
            )

        error_msg = str(exc_info.value)
        assert "hybrid_search_alpha" in error_msg
        assert "hybrid_search=False" in error_msg

    def test_importance_weights_require_scoring_enabled(self):
        """Test that custom importance weights require importance scoring enabled."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(
                performance={"importance_scoring": False},
                importance_complexity_weight=2.0  # Not default (1.0)
            )

        error_msg = str(exc_info.value)
        assert "Importance weights are customized" in error_msg
        assert "importance_scoring=False" in error_msg

    def test_query_expansion_options_require_expansion_enabled(self):
        """Test that custom query expansion options require expansion enabled."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(
                search={
                    "query_expansion_enabled": False,
                    "query_expansion_max_synonyms": 5  # Not default (2)
                }
            )

        error_msg = str(exc_info.value)
        assert "Query expansion options are customized" in error_msg
        assert "query_expansion_enabled=False" in error_msg

    def test_retrieval_gate_threshold_requires_gate_enabled(self):
        """Test that custom retrieval_gate_threshold requires gate enabled."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(
                search={
                    "retrieval_gate_enabled": False,
                    "retrieval_gate_threshold": 0.9  # Not default (0.8)
                }
            )

        error_msg = str(exc_info.value)
        assert "retrieval_gate_threshold" in error_msg
        assert "retrieval_gate_enabled=False" in error_msg

    def test_valid_dependencies_accepted(self):
        """Test that valid feature dependencies are accepted."""
        config = ServerConfig(
            search={"hybrid_search": True, "retrieval_gate_threshold": 0.9},
            performance={"hybrid_search": True, "importance_scoring": True},
            hybrid_search_alpha=0.7,
            importance_complexity_weight=2.0
        )
        assert config.hybrid_search_alpha == 0.7
        assert config.importance_complexity_weight == 2.0

    def test_default_values_with_disabled_features_accepted(self):
        """Test that default values are accepted even when features are disabled."""
        config = ServerConfig(
            search={"hybrid_search": False, "query_expansion_enabled": False},
            performance={"importance_scoring": False}
        )
        # Should not raise because values are defaults
        assert config.hybrid_search_alpha == 0.5  # default
        assert config.importance_complexity_weight == 1.0  # default

    def test_multiple_issues_reported_together(self):
        """Test that multiple dependency issues are reported together."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(
                search={
                    "hybrid_search": False,
                    "retrieval_gate_enabled": False,
                    "retrieval_gate_threshold": 0.9
                },
                performance={"hybrid_search": False},
                hybrid_search_alpha=0.7
            )

        error_msg = str(exc_info.value)
        # Should mention both issues
        assert "hybrid_search_alpha" in error_msg or "retrieval_gate_threshold" in error_msg


class TestValidationErrorMessages:
    """Tests for validation error message quality (UX-051)."""

    def test_ranking_weight_error_is_actionable(self):
        """Test that ranking weight errors explain how to fix the issue."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(
                ranking_weight_similarity=1.0,
                ranking_weight_recency=0.05,
                ranking_weight_usage=0.0
            )

        error_msg = str(exc_info.value)
        assert "Current values:" in error_msg
        assert "similarity:" in error_msg
        assert "Suggestion:" in error_msg

    def test_threshold_error_explains_range(self):
        """Test that threshold errors explain the valid range."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(search={"retrieval_gate_threshold": 1.5})

        error_msg = str(exc_info.value)
        assert "0.0 and 1.0" in error_msg
        assert "threshold" in error_msg.lower() or "similarity" in error_msg.lower()

    def test_interdependency_error_suggests_fix(self):
        """Test that interdependency errors suggest how to fix."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            ServerConfig(
                search={"hybrid_search": False},
                performance={"hybrid_search": False},
                hybrid_search_alpha=0.7
            )

        error_msg = str(exc_info.value)
        assert "Either" in error_msg  # Suggests alternatives
