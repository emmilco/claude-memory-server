"""Unit tests for TimeEstimator."""

import pytest
import tempfile
from pathlib import Path

from src.memory.time_estimator import TimeEstimator
from src.memory.indexing_metrics import IndexingMetricsStore


@pytest.fixture
def db_path():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def metrics_store(db_path):
    """Create metrics store."""
    return IndexingMetricsStore(db_path)


@pytest.fixture
def estimator(metrics_store):
    """Create time estimator."""
    return TimeEstimator(metrics_store)


def test_estimate_with_no_history(estimator):
    """Test estimate with no historical data uses default."""
    min_time, max_time = estimator.estimate_indexing_time(100)

    # Should use default 100ms per file
    assert min_time == 100 * 0.1 * 0.8  # 8 seconds
    assert max_time == 100 * 0.1 * 1.5  # 15 seconds


def test_estimate_with_history(estimator, metrics_store):
    """Test estimate with historical data."""
    # Store some historical data (50ms per file)
    metrics_store.store_metrics(100, 5.0)  # 5 seconds for 100 files = 50ms/file

    min_time, max_time = estimator.estimate_indexing_time(200)

    # Should use 50ms per file from history
    expected_base = 200 * 0.05  # 10 seconds
    assert min_time == pytest.approx(expected_base * 0.8)
    assert max_time == pytest.approx(expected_base * 1.5)


def test_estimate_project_specific(estimator, metrics_store):
    """Test project-specific estimates."""
    # Store metrics for different projects
    metrics_store.store_metrics(100, 5.0, project_name="fast-project")
    metrics_store.store_metrics(100, 20.0, project_name="slow-project")

    # Fast project should have faster estimate
    fast_min, fast_max = estimator.estimate_indexing_time(100, project_name="fast-project")
    slow_min, slow_max = estimator.estimate_indexing_time(100, project_name="slow-project")

    assert fast_max < slow_min  # Fast project should be clearly faster


def test_calculate_eta(estimator):
    """Test ETA calculation."""
    # 50 files done in 10 seconds = 0.2s per file
    # 50 files remaining = 10 seconds ETA
    eta = estimator.calculate_eta(
        files_completed=50,
        files_total=100,
        elapsed_seconds=10.0,
    )

    assert eta == pytest.approx(10.0)


def test_calculate_eta_no_progress(estimator):
    """Test ETA with no progress returns 0."""
    eta = estimator.calculate_eta(
        files_completed=0,
        files_total=100,
        elapsed_seconds=0.0,
    )

    assert eta == 0.0


def test_suggest_optimizations_node_modules(estimator):
    """Test optimization suggestions for node_modules."""
    file_paths = [f"src/file{i}.js" for i in range(10)]
    file_paths += [f"node_modules/pkg/file{i}.js" for i in range(100)]

    suggestions = estimator.suggest_optimizations(file_paths, 50.0)

    assert len(suggestions) > 0
    assert any("node_modules" in s for s in suggestions)


def test_suggest_optimizations_tests(estimator):
    """Test optimization suggestions for test files."""
    file_paths = [f"src/file{i}.js" for i in range(10)]
    file_paths += [f"tests/test{i}.js" for i in range(100)]

    suggestions = estimator.suggest_optimizations(file_paths, 50.0)

    assert len(suggestions) > 0
    assert any("test" in s.lower() for s in suggestions)


def test_suggest_optimizations_quick_indexing(estimator):
    """Test no suggestions for quick indexing."""
    file_paths = [f"src/file{i}.js" for i in range(10)]

    suggestions = estimator.suggest_optimizations(file_paths, 5.0)

    # Should not suggest optimizations for quick jobs
    assert len(suggestions) == 0


def test_format_time_seconds(estimator):
    """Test time formatting for seconds."""
    assert estimator.format_time(45) == "45s"


def test_format_time_minutes(estimator):
    """Test time formatting for minutes."""
    assert estimator.format_time(90) == "1m 30s"
    assert estimator.format_time(120) == "2m"


def test_format_time_hours(estimator):
    """Test time formatting for hours."""
    assert estimator.format_time(3600) == "1h"
    assert estimator.format_time(3900) == "1h 5m"


def test_format_estimate_range(estimator):
    """Test estimate range formatting."""
    # Same unit
    result = estimator.format_estimate_range(30, 45)
    assert "30s" in result and "45s" in result

    # Different units
    result = estimator.format_estimate_range(50, 90)
    assert "50s" in result and "1m 30s" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
