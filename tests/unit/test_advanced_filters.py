"""Tests for advanced memory search filters (FEAT-042)."""

import pytest
from datetime import datetime, timedelta, UTC
from src.core.models import (
    AdvancedSearchFilters,
    QueryRequest,
    SearchFilters,
    MemoryCategory,
    LifecycleState,
    ProvenanceSource,
)


class TestAdvancedSearchFilters:
    """Test advanced search filters model."""

    def test_create_basic_advanced_filters(self):
        """Test creating basic advanced filters."""
        filters = AdvancedSearchFilters()
        assert filters.created_after is None
        assert filters.created_before is None
        assert filters.tags_any is None
        assert filters.tags_all is None
        assert filters.tags_none is None

    def test_date_range_filters(self):
        """Test date range filtering."""
        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)

        filters = AdvancedSearchFilters(
            created_after=week_ago,
            created_before=now
        )

        assert filters.created_after == week_ago
        assert filters.created_before == now

    def test_tag_logic_filters(self):
        """Test tag logic filters (ANY, ALL, NONE)."""
        filters = AdvancedSearchFilters(
            tags_any=["python", "javascript"],
            tags_all=["backend", "api"],
            tags_none=["deprecated", "legacy"]
        )

        assert filters.tags_any == ["python", "javascript"]
        assert filters.tags_all == ["backend", "api"]
        assert filters.tags_none == ["deprecated", "legacy"]

    def test_tag_normalization(self):
        """Test that tags are normalized to lowercase."""
        filters = AdvancedSearchFilters(
            tags_any=["Python", "  JavaScript  "],
            tags_all=["Backend", "API"],
            tags_none=["DEPRECATED"]
        )

        assert filters.tags_any == ["python", "javascript"]
        assert filters.tags_all == ["backend", "api"]
        assert filters.tags_none == ["deprecated"]

    def test_lifecycle_filtering(self):
        """Test lifecycle state filtering."""
        filters = AdvancedSearchFilters(
            lifecycle_states=[LifecycleState.ACTIVE, LifecycleState.RECENT]
        )

        assert len(filters.lifecycle_states) == 2
        assert LifecycleState.ACTIVE in filters.lifecycle_states
        assert LifecycleState.RECENT in filters.lifecycle_states

    def test_category_exclusions(self):
        """Test category exclusions."""
        filters = AdvancedSearchFilters(
            exclude_categories=[MemoryCategory.EVENT, MemoryCategory.CONTEXT]
        )

        assert len(filters.exclude_categories) == 2
        assert MemoryCategory.EVENT in filters.exclude_categories

    def test_project_exclusions(self):
        """Test project exclusions."""
        filters = AdvancedSearchFilters(
            exclude_projects=["old-project", "archived-project"]
        )

        assert len(filters.exclude_projects) == 2
        assert "old-project" in filters.exclude_projects

    def test_provenance_filtering(self):
        """Test provenance filtering."""
        filters = AdvancedSearchFilters(
            min_trust_score=0.8,
            source=ProvenanceSource.USER_EXPLICIT
        )

        assert filters.min_trust_score == 0.8
        assert filters.source == ProvenanceSource.USER_EXPLICIT

    def test_min_trust_score_validation(self):
        """Test min_trust_score validation."""
        # Valid range
        filters = AdvancedSearchFilters(min_trust_score=0.0)
        assert filters.min_trust_score == 0.0

        filters = AdvancedSearchFilters(min_trust_score=1.0)
        assert filters.min_trust_score == 1.0

class TestQueryRequestWithAdvancedFilters:
    """Test QueryRequest integration with advanced filters."""

    def test_query_request_with_advanced_filters(self):
        """Test QueryRequest accepts advanced filters."""
        adv_filters = AdvancedSearchFilters(
            tags_any=["python"],
            min_trust_score=0.7
        )

        request = QueryRequest(
            query="test query",
            limit=10,
            advanced_filters=adv_filters
        )

        assert request.advanced_filters is not None
        assert request.advanced_filters.tags_any == ["python"]
        assert request.advanced_filters.min_trust_score == 0.7

    def test_query_request_without_advanced_filters(self):
        """Test QueryRequest without advanced filters."""
        request = QueryRequest(
            query="test query",
            limit=10
        )

        assert request.advanced_filters is None


class TestSearchFiltersWithAdvancedFilters:
    """Test SearchFilters integration with advanced filters."""

    def test_search_filters_with_advanced_filters(self):
        """Test SearchFilters accepts advanced filters."""
        adv_filters = AdvancedSearchFilters(
            created_after=datetime.now(UTC) - timedelta(days=30)
        )

        filters = SearchFilters(
            category=MemoryCategory.FACT,
            min_importance=0.5,
            advanced_filters=adv_filters
        )

        assert filters.advanced_filters is not None
        assert filters.category == MemoryCategory.FACT

    def test_search_filters_to_dict_with_advanced(self):
        """Test SearchFilters.to_dict() includes advanced filters."""
        adv_filters = AdvancedSearchFilters(
            tags_any=["test"]
        )

        filters = SearchFilters(
            category=MemoryCategory.FACT,
            advanced_filters=adv_filters
        )

        filter_dict = filters.to_dict()
        assert "category" in filter_dict
        assert "advanced_filters" in filter_dict
        assert filter_dict["advanced_filters"] == adv_filters


class TestAdvancedFiltersUseCases:
    """Test realistic use cases for advanced filters."""

    def test_use_case_recent_python_memories(self):
        """Test filtering for recent Python memories."""
        week_ago = datetime.now(UTC) - timedelta(days=7)

        filters = AdvancedSearchFilters(
            created_after=week_ago,
            tags_all=["python"]
        )

        assert filters.created_after == week_ago
        assert filters.tags_all == ["python"]

    def test_use_case_exclude_deprecated(self):
        """Test excluding deprecated memories."""
        filters = AdvancedSearchFilters(
            tags_none=["deprecated", "legacy"],
            lifecycle_states=[LifecycleState.ACTIVE, LifecycleState.RECENT]
        )

        assert "deprecated" in filters.tags_none
        assert LifecycleState.ACTIVE in filters.lifecycle_states

    def test_use_case_high_trust_user_explicit(self):
        """Test high-trust user-explicit memories."""
        filters = AdvancedSearchFilters(
            min_trust_score=0.9,
            source=ProvenanceSource.USER_EXPLICIT,
            lifecycle_states=[LifecycleState.ACTIVE]
        )

        assert filters.min_trust_score == 0.9
        assert filters.source == ProvenanceSource.USER_EXPLICIT

    def test_use_case_complex_tag_logic(self):
        """Test complex tag logic (AND/OR/NOT)."""
        filters = AdvancedSearchFilters(
            tags_any=["python", "javascript", "typescript"],  # Any of these
            tags_all=["backend"],  # Must have this
            tags_none=["deprecated"]  # Must not have this
        )

        assert len(filters.tags_any) == 3
        assert len(filters.tags_all) == 1
        assert len(filters.tags_none) == 1

    def test_use_case_date_range_with_category(self):
        """Test date range combined with category exclusions."""
        month_ago = datetime.now(UTC) - timedelta(days=30)

        filters = AdvancedSearchFilters(
            created_after=month_ago,
            exclude_categories=[MemoryCategory.EVENT, MemoryCategory.CONTEXT]
        )

        assert filters.created_after == month_ago
        assert len(filters.exclude_categories) == 2

    def test_use_case_multi_project_exclusion(self):
        """Test excluding multiple projects."""
        filters = AdvancedSearchFilters(
            exclude_projects=["old-proj-1", "old-proj-2", "archived"]
        )

        assert len(filters.exclude_projects) == 3
        assert "old-proj-1" in filters.exclude_projects

    def test_use_case_accessed_recently(self):
        """Test filtering by recent access time."""
        day_ago = datetime.now(UTC) - timedelta(days=1)

        filters = AdvancedSearchFilters(
            accessed_after=day_ago
        )

        assert filters.accessed_after == day_ago

    def test_use_case_updated_in_range(self):
        """Test filtering by update time range."""
        week_ago = datetime.now(UTC) - timedelta(days=7)
        today = datetime.now(UTC)

        filters = AdvancedSearchFilters(
            updated_after=week_ago,
            updated_before=today
        )

        assert filters.updated_after == week_ago
        assert filters.updated_before == today


class TestFilterCombinations:
    """Test various filter combinations."""

    def test_all_date_filters_combined(self):
        """Test all date filters combined."""
        now = datetime.now(UTC)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        filters = AdvancedSearchFilters(
            created_after=week_ago,
            created_before=now,
            updated_after=day_ago,
            accessed_after=day_ago
        )

        assert filters.created_after == week_ago
        assert filters.updated_after == day_ago
        assert filters.accessed_after == day_ago

    def test_all_tag_logic_combined(self):
        """Test all tag logic filters combined."""
        filters = AdvancedSearchFilters(
            tags_any=["python", "java"],
            tags_all=["backend", "api"],
            tags_none=["deprecated", "old"]
        )

        assert len(filters.tags_any) == 2
        assert len(filters.tags_all) == 2
        assert len(filters.tags_none) == 2

    def test_all_filter_types_combined(self):
        """Test combining all filter types."""
        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)

        filters = AdvancedSearchFilters(
            created_after=week_ago,
            tags_any=["python"],
            tags_none=["deprecated"],
            lifecycle_states=[LifecycleState.ACTIVE],
            exclude_categories=[MemoryCategory.EVENT],
            exclude_projects=["old-project"],
            min_trust_score=0.8,
            source=ProvenanceSource.USER_EXPLICIT
        )

        # Verify all filters are set
        assert filters.created_after == week_ago
        assert filters.tags_any == ["python"]
        assert filters.tags_none == ["deprecated"]
        assert len(filters.lifecycle_states) == 1
        assert len(filters.exclude_categories) == 1
        assert len(filters.exclude_projects) == 1
        assert filters.min_trust_score == 0.8
        assert filters.source == ProvenanceSource.USER_EXPLICIT
