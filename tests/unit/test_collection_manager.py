"""Unit tests for CollectionManager."""

import pytest
import tempfile
from pathlib import Path

from src.tagging.collection_manager import CollectionManager
from src.tagging.models import CollectionCreate
from src.core.exceptions import ValidationError, StorageError


@pytest.fixture
def db_path():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def collection_manager(db_path):
    """Create CollectionManager instance."""
    return CollectionManager(db_path)


def test_create_collection(collection_manager):
    """Test creating a collection."""
    collection_create = CollectionCreate(
        name="Python Patterns",
        description="Python coding patterns",
    )
    collection = collection_manager.create_collection(collection_create)

    assert collection.name == "Python Patterns"
    assert collection.description == "Python coding patterns"
    assert collection.auto_generated is False


def test_create_collection_with_tag_filter(collection_manager):
    """Test creating a collection with tag filter."""
    tag_filter = {"tags": ["python", "async"], "op": "AND"}

    collection_create = CollectionCreate(
        name="Python Async",
        tag_filter=tag_filter,
    )
    collection = collection_manager.create_collection(collection_create)

    assert collection.tag_filter == tag_filter


def test_duplicate_collection_name(collection_manager):
    """Test that duplicate collection names are rejected."""
    collection_manager.create_collection(CollectionCreate(name="Python"))

    with pytest.raises(StorageError, match="Collection already exists"):
        collection_manager.create_collection(CollectionCreate(name="Python"))


def test_get_collection_by_id(collection_manager):
    """Test retrieving a collection by ID."""
    created = collection_manager.create_collection(CollectionCreate(name="Python"))
    retrieved = collection_manager.get_collection(created.id)

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.name == "Python"


def test_get_collection_by_name(collection_manager):
    """Test retrieving a collection by name."""
    created = collection_manager.create_collection(CollectionCreate(name="Python"))
    retrieved = collection_manager.get_collection_by_name("Python")

    assert retrieved is not None
    assert retrieved.id == created.id


def test_list_collections(collection_manager):
    """Test listing all collections."""
    collection_manager.create_collection(CollectionCreate(name="Python"))
    collection_manager.create_collection(CollectionCreate(name="JavaScript"))

    collections = collection_manager.list_collections()

    assert len(collections) == 2
    names = {col.name for col in collections}
    assert names == {"Python", "JavaScript"}


def test_add_to_collection(collection_manager):
    """Test adding memories to a collection."""
    collection = collection_manager.create_collection(CollectionCreate(name="Python"))

    memory_ids = ["mem-1", "mem-2", "mem-3"]
    collection_manager.add_to_collection(collection.id, memory_ids)

    # Verify memories were added
    retrieved_ids = collection_manager.get_collection_memories(collection.id)
    assert set(retrieved_ids) == set(memory_ids)


def test_add_duplicate_memory_to_collection(collection_manager):
    """Test that adding the same memory twice doesn't create duplicates."""
    collection = collection_manager.create_collection(CollectionCreate(name="Python"))

    collection_manager.add_to_collection(collection.id, ["mem-1"])
    collection_manager.add_to_collection(collection.id, ["mem-1"])

    retrieved_ids = collection_manager.get_collection_memories(collection.id)
    assert len(retrieved_ids) == 1


def test_remove_from_collection(collection_manager):
    """Test removing memories from a collection."""
    collection = collection_manager.create_collection(CollectionCreate(name="Python"))

    memory_ids = ["mem-1", "mem-2", "mem-3"]
    collection_manager.add_to_collection(collection.id, memory_ids)

    # Remove one memory
    collection_manager.remove_from_collection(collection.id, ["mem-2"])

    retrieved_ids = collection_manager.get_collection_memories(collection.id)
    assert set(retrieved_ids) == {"mem-1", "mem-3"}


def test_delete_collection(collection_manager):
    """Test deleting a collection."""
    collection = collection_manager.create_collection(CollectionCreate(name="Python"))

    # Add memories
    collection_manager.add_to_collection(collection.id, ["mem-1", "mem-2"])

    # Delete collection
    collection_manager.delete_collection(collection.id)

    # Collection should be gone
    assert collection_manager.get_collection(collection.id) is None

    # Memories should be removed
    retrieved_ids = collection_manager.get_collection_memories(collection.id)
    assert len(retrieved_ids) == 0


def test_auto_generate_collections(collection_manager):
    """Test auto-generating collections from patterns."""
    collections = collection_manager.auto_generate_collections()

    assert len(collections) > 0

    # Check for expected collections
    names = {col.name for col in collections}
    assert "Python Async Patterns" in names
    assert "React Components" in names

    # Verify they are marked as auto-generated
    for col in collections:
        assert col.auto_generated is True
        assert col.tag_filter is not None


def test_auto_generate_collections_idempotent(collection_manager):
    """Test that auto-generate doesn't create duplicates."""
    # First generation
    collections1 = collection_manager.auto_generate_collections()

    # Second generation
    collections2 = collection_manager.auto_generate_collections()

    # Second call should return empty list (all exist)
    assert len(collections2) == 0

    # Total should still be from first generation
    all_collections = collection_manager.list_collections()
    assert len(all_collections) == len(collections1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
