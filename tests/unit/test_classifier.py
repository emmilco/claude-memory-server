"""Tests for context level classifier."""

import pytest
from src.memory.classifier import (
    ContextLevelClassifier,
    get_classifier,
    classify_content,
)
from src.core.models import ContextLevel, MemoryCategory


class TestContextLevelClassifier:
    """Test the ContextLevelClassifier."""

    def test_classifier_initialization(self):
        """Test that classifier can be initialized."""
        classifier = ContextLevelClassifier()
        assert classifier is not None
        assert len(classifier.user_patterns) > 0
        assert len(classifier.project_patterns) > 0
        assert len(classifier.session_patterns) > 0

    def test_classify_user_preference(self):
        """Test classification of user preference content."""
        classifier = ContextLevelClassifier()

        examples = [
            "I prefer Python over JavaScript for backend development",
            "My favorite editor is VS Code",
            "I always use type hints in Python",
            "Never use semicolons unless required",
            "I like to use functional programming when possible",
        ]

        for content in examples:
            result = classifier.classify(content, MemoryCategory.PREFERENCE)
            assert (
                result == ContextLevel.USER_PREFERENCE
            ), f"Failed for: {content}"

    def test_classify_project_context(self):
        """Test classification of project context content."""
        classifier = ContextLevelClassifier()

        examples = [
            "This project uses FastAPI for the REST API",
            "Our codebase follows the MVC architecture pattern",
            "The project is configured with Docker for deployment",
            "We use pytest for testing",
            "This project has a dependency on SQLAlchemy",
        ]

        for content in examples:
            result = classifier.classify(content, MemoryCategory.FACT)
            assert (
                result == ContextLevel.PROJECT_CONTEXT
            ), f"Failed for: {content}"

    def test_classify_session_state(self):
        """Test classification of session state content."""
        classifier = ContextLevelClassifier()

        examples = [
            "Currently working on the authentication module",
            "Just finished implementing the user registration feature",
            "Working on fixing the bug in the payment processor today",
            "About to start refactoring the database layer",
            "In progress: adding unit tests for the API endpoints",
        ]

        for content in examples:
            result = classifier.classify(content, MemoryCategory.EVENT)
            assert result == ContextLevel.SESSION_STATE, f"Failed for: {content}"

    def test_category_based_defaults(self):
        """Test that category affects classification."""
        classifier = ContextLevelClassifier()

        # Ambiguous content should default based on category
        ambiguous = "Using Python version 3.9"

        # With PREFERENCE category, should lean towards user preference
        result1 = classifier.classify(ambiguous, MemoryCategory.PREFERENCE)

        # With FACT category, should lean towards project context
        result2 = classifier.classify(ambiguous, MemoryCategory.FACT)

        # With EVENT category, should lean towards session state
        result3 = classifier.classify(ambiguous, MemoryCategory.EVENT)

        # All should be different or at least some should differ
        # (This is a heuristic, so we allow for some flexibility)
        results = {result1, result2, result3}
        assert len(results) >= 2, "Category should influence classification"

    def test_code_content_classification(self):
        """Test that code-related content is classified as project context."""
        classifier = ContextLevelClassifier()

        code_examples = [
            "The User class is defined in models.py",
            "The authenticate function takes username and password",
            "Import the database module from sqlalchemy",
        ]

        for content in code_examples:
            result = classifier.classify(content, MemoryCategory.FACT)
            # Code content should usually be project context
            assert result == ContextLevel.PROJECT_CONTEXT, f"Failed for: {content}"

    def test_classify_batch(self):
        """Test batch classification."""
        classifier = ContextLevelClassifier()

        items = [
            ("I prefer tabs over spaces", MemoryCategory.PREFERENCE),
            ("This project uses React for the frontend", MemoryCategory.FACT),
            ("Currently debugging the login flow", MemoryCategory.EVENT),
        ]

        results = classifier.classify_batch(items)

        assert len(results) == 3
        assert results[0] == ContextLevel.USER_PREFERENCE
        assert results[1] == ContextLevel.PROJECT_CONTEXT
        assert results[2] == ContextLevel.SESSION_STATE

    def test_get_classification_confidence(self):
        """Test confidence score retrieval."""
        classifier = ContextLevelClassifier()

        content = "I prefer using async/await in Python"
        category = MemoryCategory.PREFERENCE

        confidence = classifier.get_classification_confidence(content, category)

        assert isinstance(confidence, dict)
        assert len(confidence) == 3
        assert ContextLevel.USER_PREFERENCE in confidence
        assert ContextLevel.PROJECT_CONTEXT in confidence
        assert ContextLevel.SESSION_STATE in confidence

        # Scores should sum to approximately 1.0
        total = sum(confidence.values())
        assert 0.99 <= total <= 1.01, f"Scores should sum to 1.0, got {total}"

        # User preference should have highest confidence
        assert confidence[ContextLevel.USER_PREFERENCE] > confidence[ContextLevel.PROJECT_CONTEXT]
        assert confidence[ContextLevel.USER_PREFERENCE] > confidence[ContextLevel.SESSION_STATE]

    def test_default_for_category(self):
        """Test default classification for each category."""
        classifier = ContextLevelClassifier()

        # Empty content should use category defaults
        empty_content = ""

        result_pref = classifier.classify(empty_content, MemoryCategory.PREFERENCE)
        result_fact = classifier.classify(empty_content, MemoryCategory.FACT)
        result_event = classifier.classify(empty_content, MemoryCategory.EVENT)

        # These should use category-based defaults
        assert result_pref == ContextLevel.USER_PREFERENCE
        assert result_fact == ContextLevel.PROJECT_CONTEXT
        assert result_event == ContextLevel.SESSION_STATE


class TestGlobalClassifier:
    """Test global classifier functions."""

    def test_get_classifier_singleton(self):
        """Test that get_classifier returns a singleton."""
        classifier1 = get_classifier()
        classifier2 = get_classifier()

        assert classifier1 is classifier2

    def test_classify_content_convenience_function(self):
        """Test the convenience function."""
        result = classify_content(
            "I prefer using type hints in Python", MemoryCategory.PREFERENCE
        )

        assert result == ContextLevel.USER_PREFERENCE


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_content(self):
        """Test classification of empty content."""
        classifier = ContextLevelClassifier()

        result = classifier.classify("", MemoryCategory.FACT)
        assert result in [
            ContextLevel.USER_PREFERENCE,
            ContextLevel.PROJECT_CONTEXT,
            ContextLevel.SESSION_STATE,
        ]

    def test_very_short_content(self):
        """Test classification of very short content."""
        classifier = ContextLevelClassifier()

        result = classifier.classify("Python", MemoryCategory.PREFERENCE)
        # Should still produce a valid result
        assert result in [
            ContextLevel.USER_PREFERENCE,
            ContextLevel.PROJECT_CONTEXT,
            ContextLevel.SESSION_STATE,
        ]

    def test_mixed_signals(self):
        """Test content with mixed signals."""
        classifier = ContextLevelClassifier()

        # Content that could be both preference and project
        content = "I prefer this project to use FastAPI for the backend"

        result = classifier.classify(content, MemoryCategory.PREFERENCE)
        # With PREFERENCE category, user preference should win
        assert result == ContextLevel.USER_PREFERENCE

    def test_case_insensitivity(self):
        """Test that classification is case-insensitive."""
        classifier = ContextLevelClassifier()

        content1 = "I PREFER PYTHON"
        content2 = "i prefer python"
        content3 = "I prefer Python"

        result1 = classifier.classify(content1, MemoryCategory.PREFERENCE)
        result2 = classifier.classify(content2, MemoryCategory.PREFERENCE)
        result3 = classifier.classify(content3, MemoryCategory.PREFERENCE)

        # All should classify the same way
        assert result1 == result2 == result3 == ContextLevel.USER_PREFERENCE


class TestRealWorldExamples:
    """Test with real-world examples."""

    def test_coding_preference(self):
        """Test coding preference classification."""
        classifier = ContextLevelClassifier()

        examples = [
            "I always write docstrings for public functions",
            "My convention is to use snake_case for variables",
            "I usually put imports at the top of the file",
        ]

        for content in examples:
            result = classifier.classify(content, MemoryCategory.PREFERENCE)
            assert result == ContextLevel.USER_PREFERENCE

    def test_project_architecture(self):
        """Test project architecture classification."""
        classifier = ContextLevelClassifier()

        examples = [
            "This codebase uses a layered architecture with controllers, services, and repositories",
            "The project framework is built on Django with PostgreSQL",
            "Our deployment environment uses Kubernetes",
        ]

        for content in examples:
            result = classifier.classify(content, MemoryCategory.FACT)
            assert result == ContextLevel.PROJECT_CONTEXT

    def test_current_work(self):
        """Test current work classification."""
        classifier = ContextLevelClassifier()

        examples = [
            "Today I'm refactoring the authentication system",
            "Currently investigating a performance issue in the database queries",
            "Just finished adding error handling to the API endpoints",
        ]

        for content in examples:
            result = classifier.classify(content, MemoryCategory.EVENT)
            assert result == ContextLevel.SESSION_STATE


def test_classifier_coverage_summary():
    """Report on classifier test coverage."""
    print("\n" + "=" * 70)
    print("CONTEXT CLASSIFIER TEST COVERAGE")
    print("=" * 70)
    print("✓ Classifier initialization")
    print("✓ User preference classification")
    print("✓ Project context classification")
    print("✓ Session state classification")
    print("✓ Category-based defaults")
    print("✓ Code content classification")
    print("✓ Batch classification")
    print("✓ Confidence scoring")
    print("✓ Global classifier singleton")
    print("✓ Edge cases (empty, short, mixed signals)")
    print("✓ Case insensitivity")
    print("✓ Real-world examples")
    print("=" * 70 + "\n")

    # This test always passes
    assert True
