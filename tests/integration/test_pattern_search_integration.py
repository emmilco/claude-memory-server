"""Integration tests for pattern-based code search (FEAT-058)."""

import pytest
from pathlib import Path

from src.core.server import MemoryRAGServer
from src.config import ServerConfig
from src.memory.incremental_indexer import IncrementalCodeIndexer


# Sample code files for testing
SAMPLE_ERROR_HANDLER = '''
def process_data(data):
    """Process incoming data with error handling."""
    try:
        result = validate(data)
        return result
    except:
        # TODO: Add specific exception handling
        log_error("Validation failed")
        return None
'''

SAMPLE_AUTH_CODE = '''
def authenticate_user(username, password):
    """Authenticate user with credentials."""
    # Security check
    if not username or not password:
        raise ValueError("Missing credentials")

    api_key = get_api_key()
    secret_token = generate_token(username, password)

    return verify_credentials(api_key, secret_token)
'''

SAMPLE_CONFIG_CODE = '''
class Config:
    """Application configuration."""
    DATABASE_URL = "postgresql://localhost/db"
    API_KEY = "hardcoded_key_123"  # FIXME: Move to environment
    SECRET_KEY = "super_secret"

    def __init__(self):
        self.password = "admin123"  # TODO: Remove hardcoded password
'''

SAMPLE_CLEAN_CODE = '''
def calculate_total(items):
    """Calculate total price of items."""
    total = 0
    for item in items:
        total += item.price
    return total
'''


class TestPatternSearchIntegration:
    """Integration tests for pattern-based search."""

    @pytest.fixture
    async def server_with_indexed_code(self, tmp_path):
        """Create server with indexed sample code."""
        # Create sample files
        error_file = tmp_path / "error_handler.py"
        error_file.write_text(SAMPLE_ERROR_HANDLER)

        auth_file = tmp_path / "auth.py"
        auth_file.write_text(SAMPLE_AUTH_CODE)

        config_file = tmp_path / "config.py"
        config_file.write_text(SAMPLE_CONFIG_CODE)

        clean_file = tmp_path / "calculator.py"
        clean_file.write_text(SAMPLE_CLEAN_CODE)

        # Create and initialize server
        config = ServerConfig(
            storage_backend="qdrant",
            qdrant_url="http://localhost:6333",
        )
        server = MemoryRAGServer(config)
        await server.initialize()

        # Index the code
        indexer = IncrementalCodeIndexer(
            store=server.store,
            embedding_generator=server.embedding_generator,
            config=server.config,
        )

        await indexer.index_directory(
            directory=str(tmp_path),
            project_name="test-patterns",
            file_extensions=[".py"],
        )

        yield server

        # Cleanup
        if server.store:
            await server.store.close()

    @pytest.mark.asyncio
    async def test_filter_mode_bare_except(self, server_with_indexed_code):
        """Test filter mode finds bare except blocks."""
        server = server_with_indexed_code

        results = await server.search_code(
            query="error handling",
            pattern="@preset:bare_except",
            pattern_mode="filter",
            project_name="test-patterns",
            limit=10
        )

        assert results["status"] == "success"
        assert len(results["results"]) > 0

        # All results should have pattern metadata
        for result in results["results"]:
            assert result["pattern_matched"] is True
            assert result["pattern_match_count"] >= 1
            assert len(result["pattern_match_locations"]) >= 1
            # Should contain bare except
            assert "except:" in result["code"]

    @pytest.mark.asyncio
    async def test_boost_mode_security_keywords(self, server_with_indexed_code):
        """Test boost mode ranks security keywords higher."""
        server = server_with_indexed_code

        results = await server.search_code(
            query="authentication and credentials",
            pattern="@preset:security_keywords",
            pattern_mode="boost",
            project_name="test-patterns",
            limit=10
        )

        assert results["status"] == "success"
        assert len(results["results"]) > 0

        # Results with pattern matches should be ranked higher
        pattern_matched_results = [
            r for r in results["results"]
            if r.get("pattern_matched", False)
        ]
        non_matched_results = [
            r for r in results["results"]
            if not r.get("pattern_matched", False)
        ]

        # If we have both types, matched should rank higher
        if pattern_matched_results and non_matched_results:
            assert pattern_matched_results[0]["relevance_score"] >= non_matched_results[0]["relevance_score"]

    @pytest.mark.asyncio
    async def test_require_mode_strict_matching(self, server_with_indexed_code):
        """Test require mode only returns results matching both conditions."""
        server = server_with_indexed_code

        results = await server.search_code(
            query="configuration settings",
            pattern="@preset:TODO_comments",
            pattern_mode="require",
            project_name="test-patterns",
            limit=10
        )

        assert results["status"] == "success"

        # All results MUST have pattern match
        for result in results["results"]:
            assert result.get("pattern_matched") is True
            assert "TODO" in result["code"] or "FIXME" in result["code"]

    @pytest.mark.asyncio
    async def test_custom_regex_pattern(self, server_with_indexed_code):
        """Test custom regex pattern."""
        server = server_with_indexed_code

        results = await server.search_code(
            query="security and authentication",
            pattern=r"(password|secret|api_key)",
            pattern_mode="filter",
            project_name="test-patterns",
            limit=10
        )

        assert results["status"] == "success"
        assert len(results["results"]) > 0

        # All results should contain at least one of the keywords
        for result in results["results"]:
            content_lower = result["code"].lower()
            assert any(kw in content_lower for kw in ["password", "secret", "api_key"])

    @pytest.mark.asyncio
    async def test_pattern_match_locations(self, server_with_indexed_code):
        """Test that pattern match locations are correct."""
        server = server_with_indexed_code

        results = await server.search_code(
            query="error handling",
            pattern="@preset:bare_except",
            pattern_mode="filter",
            project_name="test-patterns",
            limit=1
        )

        assert len(results["results"]) > 0
        result = results["results"][0]

        assert "pattern_match_locations" in result
        locations = result["pattern_match_locations"]
        assert len(locations) > 0

        # Each location should have required fields
        for loc in locations:
            assert "line" in loc
            assert "column" in loc
            assert "text" in loc
            assert loc["text"] == "except:"

    @pytest.mark.asyncio
    async def test_no_pattern_no_metadata(self, server_with_indexed_code):
        """Test that no pattern metadata is added without pattern."""
        server = server_with_indexed_code

        results = await server.search_code(
            query="error handling",
            project_name="test-patterns",
            limit=10
        )

        assert results["status"] == "success"

        # No pattern metadata should be present
        for result in results["results"]:
            assert "pattern_matched" not in result
            assert "pattern_match_count" not in result
            assert "pattern_match_locations" not in result

    @pytest.mark.asyncio
    async def test_invalid_pattern_mode(self, server_with_indexed_code):
        """Test that invalid pattern mode raises error."""
        server = server_with_indexed_code

        with pytest.raises(Exception, match="Invalid pattern_mode"):
            await server.search_code(
                query="test",
                pattern="test",
                pattern_mode="invalid",
                project_name="test-patterns"
            )

    @pytest.mark.asyncio
    async def test_invalid_pattern(self, server_with_indexed_code):
        """Test that invalid regex pattern raises error."""
        server = server_with_indexed_code

        with pytest.raises(Exception, match="Invalid regex pattern"):
            await server.search_code(
                query="test",
                pattern=r"(?P<invalid",  # Invalid regex
                pattern_mode="filter",
                project_name="test-patterns"
            )

    @pytest.mark.asyncio
    async def test_unknown_preset(self, server_with_indexed_code):
        """Test that unknown preset raises error."""
        server = server_with_indexed_code

        with pytest.raises(Exception, match="Unknown pattern preset"):
            await server.search_code(
                query="test",
                pattern="@preset:nonexistent",
                pattern_mode="filter",
                project_name="test-patterns"
            )

    @pytest.mark.asyncio
    async def test_filter_mode_no_matches(self, server_with_indexed_code):
        """Test filter mode with pattern that doesn't match anything."""
        server = server_with_indexed_code

        results = await server.search_code(
            query="code",
            pattern=r"nonexistent_pattern_xyz123",
            pattern_mode="filter",
            project_name="test-patterns",
            limit=10
        )

        # Should return success but with no results
        assert results["status"] == "success"
        assert len(results["results"]) == 0

    @pytest.mark.asyncio
    async def test_combined_with_file_pattern(self, server_with_indexed_code):
        """Test pattern matching combined with file_pattern filter."""
        server = server_with_indexed_code

        results = await server.search_code(
            query="configuration",
            pattern="@preset:security_keywords",
            pattern_mode="filter",
            file_pattern="**/config.py",
            project_name="test-patterns",
            limit=10
        )

        assert results["status"] == "success"

        # All results should be from config.py and match security keywords
        for result in results["results"]:
            assert "config.py" in result["file_path"]
            assert result.get("pattern_matched") is True

    @pytest.mark.asyncio
    async def test_combined_with_language_filter(self, server_with_indexed_code):
        """Test pattern matching combined with language filter."""
        server = server_with_indexed_code

        results = await server.search_code(
            query="code",
            pattern="@preset:TODO_comments",
            pattern_mode="filter",
            language="python",
            project_name="test-patterns",
            limit=10
        )

        assert results["status"] == "success"

        # All results should be Python and have TODO comments
        for result in results["results"]:
            assert result["language"].lower() == "python"
            assert result.get("pattern_matched") is True

    @pytest.mark.asyncio
    async def test_pattern_match_count_accuracy(self, server_with_indexed_code):
        """Test that pattern match count is accurate."""
        server = server_with_indexed_code

        results = await server.search_code(
            query="configuration",
            pattern="@preset:security_keywords",
            pattern_mode="filter",
            project_name="test-patterns",
            limit=10
        )

        assert len(results["results"]) > 0

        for result in results["results"]:
            # Count should match actual occurrences
            content = result["code"]
            count = result["pattern_match_count"]

            # Verify by counting manually
            import re
            from src.search.pattern_matcher import PATTERN_PRESETS
            pattern = PATTERN_PRESETS["security_keywords"]
            actual_count = len(re.findall(pattern, content, re.MULTILINE | re.DOTALL))
            assert count == actual_count

    @pytest.mark.asyncio
    async def test_performance_overhead(self, server_with_indexed_code):
        """Test that pattern matching adds minimal overhead."""
        server = server_with_indexed_code

        # Search without pattern
        import time
        start = time.time()
        results_no_pattern = await server.search_code(
            query="error handling",
            project_name="test-patterns",
            limit=10
        )
        time_no_pattern = (time.time() - start) * 1000

        # Search with pattern
        start = time.time()
        results_with_pattern = await server.search_code(
            query="error handling",
            pattern="@preset:bare_except",
            pattern_mode="filter",
            project_name="test-patterns",
            limit=10
        )
        time_with_pattern = (time.time() - start) * 1000

        # Pattern matching should add <10ms overhead
        overhead = time_with_pattern - time_no_pattern
        assert overhead < 10  # Less than 10ms overhead

        # Both should succeed
        assert results_no_pattern["status"] == "success"
        assert results_with_pattern["status"] == "success"
