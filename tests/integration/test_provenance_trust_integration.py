"""Integration tests for FEAT-034: Memory Provenance & Trust Signals."""

import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, UTC, timedelta

from src.config import get_config
from src.store.sqlite_store import SQLiteMemoryStore
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
async def test_store():
    """Create a test memory store."""
    config = get_config()
    config.storage_backend = "sqlite"
    config.sqlite_path = ":memory:"  # In-memory database for tests

    store = SQLiteMemoryStore(config)
    await store.initialize()
    yield store
    # Cleanup handled by in-memory DB


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


@pytest.mark.skip(reason="Relationship detection functionality removed (see CHANGELOG 2025-11-20)")
@pytest.mark.asyncio
async def test_contradiction_detection_workflow(test_store, embedding_gen):
    """Test contradiction detection between memories. DEPRECATED: Relationship functionality removed."""
    # 1. Create first preference
    embedding1 = await embedding_gen.generate("I prefer Vue.js for frontend")
    mem1_id = await test_store.store(
        content="I prefer Vue.js for frontend",
        embedding=embedding1,
        metadata={
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "project_name": None,
            "importance": 0.7,
            "tags": ["frontend"],
            "metadata": {},
            "created_at": datetime.now(UTC) - timedelta(days=90),  # 90 days ago
            "provenance": MemoryProvenance(
                source=ProvenanceSource.USER_EXPLICIT, created_by="user"
            ).model_dump(),
        },
    )

    # 2. Create contradicting preference
    embedding2 = await embedding_gen.generate("I prefer React for frontend")
    mem2_id = await test_store.store(
        content="I prefer React for frontend",
        embedding=embedding2,
        metadata={
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "project_name": None,
            "importance": 0.8,
            "tags": ["frontend"],
            "metadata": {},
            "created_at": datetime.now(UTC),  # Today
            "provenance": MemoryProvenance(
                source=ProvenanceSource.USER_EXPLICIT, created_by="user"
            ).model_dump(),
        },
    )

    # 3. Detect contradictions
    mem1 = await test_store.get_by_id(mem1_id)
    mem2 = await test_store.get_by_id(mem2_id)

    contradictions = await detector.detect_contradictions(mem2, [mem1])

    # Should detect contradiction due to framework conflict
    assert len(contradictions) > 0
    contradiction = contradictions[0]
    assert contradiction.relationship_type == RelationshipType.CONTRADICTS
    assert contradiction.source_memory_id == mem2_id
    assert contradiction.target_memory_id == mem1_id


@pytest.mark.skip(reason="Relationship detection functionality removed (see CHANGELOG 2025-11-20)")
@pytest.mark.asyncio
async def test_duplicate_detection_workflow(test_store, embedding_gen):
    """Test duplicate detection between similar memories. DEPRECATED: Relationship functionality removed."""
    # 1. Create original memory
    content = "Always use async/await for asynchronous operations in JavaScript"
    embedding1 = await embedding_gen.generate(content)
    mem1_id = await test_store.store(
        content=content,
        embedding=embedding1,
        metadata={
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "project_name": None,
            "importance": 0.7,
            "tags": ["javascript"],
            "metadata": {},
            "provenance": MemoryProvenance(
                source=ProvenanceSource.USER_EXPLICIT, created_by="user"
            ).model_dump(),
        },
    )

    # 2. Create very similar memory (duplicate)
    similar_content = "I prefer async/await for async operations in JavaScript"
    embedding2 = await embedding_gen.generate(similar_content)
    mem2_id = await test_store.store(
        content=similar_content,
        embedding=embedding2,
        metadata={
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "project_name": None,
            "importance": 0.7,
            "tags": ["javascript"],
            "metadata": {},
            "provenance": MemoryProvenance(
                source=ProvenanceSource.USER_EXPLICIT, created_by="user"
            ).model_dump(),
        },
    )

    # 3. Detect duplicates
    mem2 = await test_store.get_by_id(mem2_id)
    duplicates = await detector.detect_duplicates(mem2, similarity_threshold=0.65)

    # Should find the similar memory as a duplicate
    assert len(duplicates) > 0
    duplicate = duplicates[0]
    assert duplicate.relationship_type == RelationshipType.DUPLICATE
    assert duplicate.confidence >= 0.65  # Match our detection threshold


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


@pytest.mark.skip(reason="Relationship detection functionality removed (see CHANGELOG 2025-11-20)")
@pytest.mark.asyncio
async def test_relationship_storage_and_retrieval(test_store, embedding_gen):
    """Test storing and retrieving relationships. DEPRECATED: Relationship functionality removed."""
    # 1. Create two related memories
    embedding1 = await embedding_gen.generate("Use React hooks for state management")
    mem1_id = await test_store.store(
        content="Use React hooks for state management",
        embedding=embedding1,
        metadata={
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "project_name": None,
            "importance": 0.7,
            "tags": ["react"],
            "metadata": {},
            "provenance": MemoryProvenance(
                source=ProvenanceSource.USER_EXPLICIT, created_by="user"
            ).model_dump(),
        },
    )

    embedding2 = await embedding_gen.generate("Avoid class components in React")
    mem2_id = await test_store.store(
        content="Avoid class components in React",
        embedding=embedding2,
        metadata={
            "category": MemoryCategory.PREFERENCE.value,
            "context_level": ContextLevel.USER_PREFERENCE.value,
            "scope": MemoryScope.GLOBAL.value,
            "project_name": None,
            "importance": 0.7,
            "tags": ["react"],
            "metadata": {},
            "provenance": MemoryProvenance(
                source=ProvenanceSource.USER_EXPLICIT, created_by="user"
            ).model_dump(),
        },
    )

    # 2. Detect and store relationship
    mem1 = await test_store.get_by_id(mem1_id)
    mem2 = await test_store.get_by_id(mem2_id)

    relationship = await detector.detect_support(mem1, mem2)
    if relationship:
        await test_store.store_relationship(relationship)

        # 3. Retrieve relationships
        relationships = await test_store.get_relationships(mem1_id)
        assert len(relationships) > 0


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
