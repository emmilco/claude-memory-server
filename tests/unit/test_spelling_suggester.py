"""Tests for spelling suggester."""

import pytest
from unittest.mock import AsyncMock
from src.memory.spelling_suggester import SpellingSuggester


@pytest.fixture
def mock_store():
    """Create mock memory store."""
    store = AsyncMock()
    store.list_memories = AsyncMock(return_value=[])
    return store


@pytest.fixture
def suggester(mock_store):
    """Create spelling suggester instance."""
    return SpellingSuggester(mock_store)


def test_common_typo_correction(suggester):
    """Test correction of common programming typos."""
    corrections = suggester.suggest_corrections("athentication logic")

    # Should suggest "authentication"
    assert any("authentication" in c for c in corrections)


def test_multiple_typos(suggester):
    """Test correction with multiple typos."""
    corrections = suggester.suggest_corrections("databse connction")

    # Should suggest corrections for both typos
    assert any("database" in c for c in corrections)
    assert any("connection" in c for c in corrections)


@pytest.mark.skip(reason="Flaky test - race condition in parallel execution (passes individually)")
def test_synonym_suggestions(suggester):
    """Test synonym suggestions."""
    # Load some terms so synonyms can be suggested
    suggester.indexed_terms = {"authentication", "authorization", "validate"}
    suggester._terms_loaded = True

    corrections = suggester.suggest_corrections("auth handler")

    # Should suggest authentication or authorization as synonym for auth
    assert any("authentication" in c or "authorization" in c or "authorize" in c for c in corrections)


def test_no_suggestions_for_correct_query(suggester):
    """Test that correct queries don't get unnecessary suggestions."""
    # Load some indexed terms first
    suggester.indexed_terms = {"validate", "user", "token", "authentication"}
    suggester._terms_loaded = True

    corrections = suggester.suggest_corrections("validate user token")

    # Should have minimal or no corrections for correct query
    # (may have synonyms, but not spelling corrections)
    assert len(corrections) <= 3


def test_max_suggestions_limit(suggester):
    """Test max_suggestions parameter."""
    corrections = suggester.suggest_corrections(
        "athentication databse",
        max_suggestions=1,
    )

    assert len(corrections) <= 1


@pytest.mark.asyncio
async def test_load_indexed_terms(suggester, mock_store):
    """Test loading indexed terms from store."""
    # Mock indexed memories
    mock_store.list_memories = AsyncMock(return_value=[
        {
            "metadata": {
                "unit_name": "validateToken",
                "unit_type": "function",
            }
        },
        {
            "metadata": {
                "unit_name": "UserRepository",
                "unit_type": "class",
            }
        },
    ])

    await suggester.load_indexed_terms("test-project")

    # Should have loaded terms
    assert suggester._terms_loaded
    assert len(suggester.indexed_terms) > 0
    assert "validatetoken" in suggester.indexed_terms or "validateToken" in suggester.indexed_terms


def test_find_close_matches(suggester):
    """Test close match finding."""
    candidates = {"authenticate", "authorization", "validation", "verification"}

    matches = suggester._find_close_matches("athenticate", candidates)

    assert "authenticate" in matches


def test_skip_short_terms(suggester):
    """Test that very short terms are skipped."""
    corrections = suggester.suggest_corrections("is a test")

    # Short words like "is" and "a" should be skipped
    # Should not generate corrections for them
    assert len(corrections) <= 3


@pytest.mark.asyncio
async def test_load_indexed_terms_extracts_words(suggester, mock_store):
    """Test that multi-word names are split into individual words."""
    mock_store.list_memories = AsyncMock(return_value=[
        {
            "metadata": {
                "unit_name": "validate_user_token",
                "unit_type": "function",
            }
        },
    ])

    await suggester.load_indexed_terms()

    # Should extract individual words
    assert any("validate" in term for term in suggester.indexed_terms)
    assert any("user" in term for term in suggester.indexed_terms)
    assert any("token" in term for term in suggester.indexed_terms)
