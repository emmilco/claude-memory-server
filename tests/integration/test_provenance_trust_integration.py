"""Integration tests for FEAT-034: Memory Provenance & Trust Signals."""

import pytest
import pytest_asyncio
import asyncio
import uuid
from datetime import datetime, UTC, timedelta

from src.config import ServerConfig
from src.store.qdrant_store import QdrantMemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.memory.provenance_tracker import ProvenanceTracker
from src.memory.trust_signals import TrustSignalGenerator
from src.core.models import (
    MemoryUnit,
    MemoryCategory,
    ContextLevel,
    MemoryScope,
    ProvenanceSource,
    MemoryProvenance,
)


@pytest_asyncio.fixture
async def test_store(qdrant_client, unique_qdrant_collection):
    """Create a test memory store with pooled collection.

    Uses the session-scoped qdrant_client and unique_qdrant_collection
    fixtures from conftest.py to leverage collection pooling and prevent
    Qdrant deadlocks during parallel test execution.
    """
    config = ServerConfig(
        storage_backend="qdrant",
        qdrant_url="http://localhost:6333",
        qdrant_collection_name=unique_qdrant_collection,
    )

    store = QdrantMemoryStore(config)
    await store.initialize()
    yield store

    # Cleanup
    await store.close()
    # Collection cleanup handled by unique_qdrant_collection autouse fixture


@pytest.fixture
def embedding_gen():
    """Create embedding generator."""
    return EmbeddingGenerator()


@pytest_asyncio.fixture
async def tracker(test_store):
    """Create provenance tracker."""
    return ProvenanceTracker(test_store)


@pytest_asyncio.fixture
async def trust_gen(test_store):
    """Create trust signal generator."""
    return TrustSignalGenerator(test_store)


@pytest.mark.asyncio
async def test_end_to_end_provenance_tracking(test_store, tracker, embedding_gen):
    """Test complete provenance tracking workflow."""
    # 1. Create memory with provenance
    provenance = await tracker.capture_provenance(
        content="I prefer React for frontend development",
        source=ProvenanceSource.USER_EXPLICIT,
        context={"user_id": "test_user", "conversation_id": "conv_123"},
    )

    assert provenance.source == ProvenanceSource.USER_EXPLICIT
    assert provenance.created_by == "test_user"
    assert provenance.confidence == 0.9  # USER_EXPLICIT default
    assert not provenance.verified

    # 2. Store memory with provenance
    embedding = await embedding_gen.generate("I prefer React for frontend development")
    memory_id = await test_store.store(
        content="I prefer React for frontend development",
        embedding=embedding,
        metadata={
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "project_name": None,
            "importance": 0.8,
            "tags": ["frontend", "react"],
            "metadata": {},
            "provenance": provenance.model_dump(),
        },
    )

    # 3. Retrieve and verify provenance is stored
    retrieved = await test_store.get_by_id(memory_id)
    assert retrieved is not None
    assert retrieved.provenance.source == ProvenanceSource.USER_EXPLICIT
    assert retrieved.provenance.confidence == 0.9

    # 4. Verify memory
    success = await tracker.verify_memory(
        memory_id, verified=True, user_notes="Confirmed preference"
    )
    assert success

    # 5. Check verification updated confidence
    verified = await test_store.get_by_id(memory_id)
    assert verified.provenance.verified is True
    assert verified.provenance.confidence >= 0.9  # Should have bonus
    assert verified.provenance.last_confirmed is not None


@pytest.mark.asyncio
async def test_trust_signals_generation(test_store, trust_gen, embedding_gen):
    """Test trust signal generation for search results."""
    # 1. Create memory with good provenance
    provenance = MemoryProvenance(
        source=ProvenanceSource.USER_EXPLICIT,
        created_by="user",
        confidence=0.9,
        verified=True,
        last_confirmed=datetime.now(UTC) - timedelta(days=2),
    )

    embedding = await embedding_gen.generate("Use TypeScript for type safety")
    memory_id = await test_store.store(
        content="Use TypeScript for type safety",
        embedding=embedding,
        metadata={
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "project_name": "my-app",
            "importance": 0.8,
            "tags": ["typescript"],
            "metadata": {"access_count": 15},
            "provenance": provenance.model_dump(),
        },
    )

    # 2. Retrieve memory
    memory = await test_store.get_by_id(memory_id)

    # 3. Generate trust signals
    query = "typescript best practices"
    score = 0.85
    rank = 1

    trust_signals = await trust_gen.explain_result(memory, query, score, rank)

    # 4. Verify trust signals
    assert trust_signals.trust_score > 0.8  # Should have high trust
    assert trust_signals.confidence_level in ["excellent", "good"]
    assert len(trust_signals.why_shown) > 0

    # Should mention key factors
    why_text = " ".join(trust_signals.why_shown)
    assert "semantic match" in why_text.lower() or "match" in why_text.lower()
    assert "project" in why_text.lower() or "current project" in why_text.lower()


@pytest.mark.asyncio
async def test_confidence_calculation_factors(test_store, tracker, embedding_gen):
    """Test that confidence calculation considers all factors."""
    # Create memory with various factors
    provenance = MemoryProvenance(
        source=ProvenanceSource.DOCUMENTATION,  # 0.85 base
        created_by="code_docs",
        confidence=0.85,
        verified=True,  # +0.15 bonus
        last_confirmed=datetime.now(UTC) - timedelta(days=10),  # Recent bonus
    )

    embedding = await embedding_gen.generate("Use strict mode in TypeScript")
    memory_id = await test_store.store(
        content="Use strict mode in TypeScript",
        embedding=embedding,
        metadata={
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "project_name": None,
            "importance": 0.7,
            "tags": ["typescript"],
            "metadata": {"access_count": 12},  # Frequent access bonus
            "created_at": datetime.now(UTC) - timedelta(days=30),  # Age factor
            "provenance": provenance.model_dump(),
        },
    )

    # Retrieve and calculate confidence
    memory = await test_store.get_by_id(memory_id)
    confidence = await tracker.calculate_confidence(memory)

    # Should have high confidence due to multiple positive factors
    assert confidence >= 0.85
    assert confidence <= 1.0


@pytest.mark.asyncio
async def test_low_confidence_memory_detection(test_store, tracker, embedding_gen):
    """Test finding memories needing verification."""
    # Create low-confidence memory
    provenance = MemoryProvenance(
        source=ProvenanceSource.IMPORTED,  # 0.5 base
        created_by="import",
        confidence=0.5,
        verified=False,
    )

    embedding = await embedding_gen.generate("Some old preference")
    memory_id = await test_store.store(
        content="Some old preference",
        embedding=embedding,
        metadata={
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "project_name": None,
            "importance": 0.5,
            "tags": [],
            "metadata": {},
            "created_at": datetime.now(UTC) - timedelta(days=100),  # Old
            "provenance": provenance.model_dump(),
        },
    )

    # Find low-confidence memories
    low_confidence = await tracker.get_low_confidence_memories(threshold=0.6, limit=10)

    # Should find our low-confidence memory
    found = any(m.id == memory_id for m in low_confidence)
    assert found
