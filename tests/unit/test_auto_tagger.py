"""Unit tests for AutoTagger."""

import pytest
from src.tagging.auto_tagger import AutoTagger


def test_auto_tagger_initialization():
    """Test AutoTagger initialization."""
    tagger = AutoTagger(min_confidence=0.7)
    assert tagger.min_confidence == 0.7


def test_detect_languages_python():
    """Test Python language detection."""
    tagger = AutoTagger()
    content = "import asyncio\nasync def main():\n    await task()"

    tags = tagger._detect_languages(content)

    assert "python" in tags
    assert tags["python"] > 0.5


def test_detect_languages_javascript():
    """Test JavaScript language detection."""
    tagger = AutoTagger()
    content = "const myFunc = () => {\n  let x = 5;\n  return x;\n}"

    tags = tagger._detect_languages(content)

    assert "javascript" in tags
    assert tags["javascript"] > 0.5


def test_detect_frameworks_react():
    """Test React framework detection."""
    tagger = AutoTagger()
    content = "import React from 'react';\nconst App = () => {\n  const [state, setState] = useState();\n  return <div>Hello</div>;\n}"

    tags = tagger._detect_frameworks(content)

    assert "react" in tags
    assert tags["react"] > 0.6


def test_detect_frameworks_fastapi():
    """Test FastAPI framework detection."""
    tagger = AutoTagger()
    content = "from fastapi import FastAPI, Depends\napp = FastAPI()\n@app.get('/users')\nasync def get_users():\n    pass"

    tags = tagger._detect_frameworks(content)

    assert "fastapi" in tags
    assert tags["fastapi"] > 0.6


def test_detect_patterns_async():
    """Test async pattern detection."""
    tagger = AutoTagger()
    content = "async function fetchData() { await Promise.all([...]) }"

    tags = tagger._detect_patterns(content)

    assert "async" in tags
    assert tags["async"] > 0.5


def test_detect_domains_database():
    """Test database domain detection."""
    tagger = AutoTagger()
    content = "SELECT * FROM users WHERE id = 1;\nINSERT INTO table VALUES (...)"

    tags = tagger._detect_domains(content)

    assert "database" in tags
    assert tags["database"] > 0.5


def test_extract_keywords():
    """Test keyword extraction."""
    tagger = AutoTagger()
    content = "authentication system using JWT tokens for secure API access"

    keywords = tagger._extract_keywords(content)

    assert len(keywords) > 0
    # Should extract longer, meaningful words
    assert any(len(word) >= 4 for word in keywords)


def test_extract_tags_comprehensive():
    """Test comprehensive tag extraction."""
    tagger = AutoTagger()
    content = """
    import asyncio
    from fastapi import FastAPI

    app = FastAPI()

    async def process_data():
        await database.query("SELECT * FROM users")
    """

    tags = tagger.extract_tags(content, max_tags=10)

    # Should detect Python, FastAPI, database
    tag_names = [tag for tag, _ in tags]
    assert "python" in tag_names
    assert "fastapi" in tag_names
    # Database or async should be detected
    assert "database" in tag_names or "async" in tag_names


def test_infer_hierarchical_tags_python():
    """Test hierarchical tag inference for Python."""
    tagger = AutoTagger()
    flat_tags = ["python", "async"]

    hierarchical = tagger.infer_hierarchical_tags(flat_tags)

    assert "language/python" in hierarchical
    assert "language/python/async" in hierarchical
    assert "pattern/async" in hierarchical


def test_infer_hierarchical_tags_react():
    """Test hierarchical tag inference for React."""
    tagger = AutoTagger()
    flat_tags = ["react", "javascript"]

    hierarchical = tagger.infer_hierarchical_tags(flat_tags)

    assert "framework/react" in hierarchical
    assert "language/javascript" in hierarchical


def test_confidence_filtering():
    """Test that tags below min_confidence are filtered out."""
    tagger = AutoTagger(min_confidence=0.9)
    content = "simple code"

    tags = tagger.extract_tags(content)

    # With very high confidence threshold, should get few/no tags
    assert len(tags) <= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
