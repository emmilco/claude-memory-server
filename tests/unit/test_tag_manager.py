"""Unit tests for TagManager."""

import pytest
import tempfile
from pathlib import Path

from src.tagging.tag_manager import TagManager
from src.tagging.models import TagCreate
from src.core.exceptions import ValidationError, StorageError


@pytest.fixture
def db_path():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
        yield f.name
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def tag_manager(db_path):
    """Create TagManager instance."""
    return TagManager(db_path)


def test_create_root_tag(tag_manager):
    """Test creating a root-level tag."""
    tag_create = TagCreate(name="python")
    tag = tag_manager.create_tag(tag_create)

    assert tag.name == "python"
    assert tag.full_path == "python"
    assert tag.level == 0
    assert tag.parent_id is None


def test_create_nested_tag(tag_manager):
    """Test creating a nested tag."""
    # Create parent
    parent = tag_manager.create_tag(TagCreate(name="language"))

    # Create child
    child_create = TagCreate(name="python", parent_id=parent.id)
    child = tag_manager.create_tag(child_create)

    assert child.name == "python"
    assert child.full_path == "language/python"
    assert child.level == 1
    assert child.parent_id == parent.id


def test_create_deep_hierarchy(tag_manager):
    """Test creating a 4-level deep hierarchy."""
    level0 = tag_manager.create_tag(TagCreate(name="language"))
    level1 = tag_manager.create_tag(TagCreate(name="python", parent_id=level0.id))
    level2 = tag_manager.create_tag(TagCreate(name="async", parent_id=level1.id))
    level3 = tag_manager.create_tag(TagCreate(name="patterns", parent_id=level2.id))

    assert level3.full_path == "language/python/async/patterns"
    assert level3.level == 3


def test_hierarchy_depth_limit(tag_manager):
    """Test that hierarchy depth is limited to 4 levels."""
    level0 = tag_manager.create_tag(TagCreate(name="a"))
    level1 = tag_manager.create_tag(TagCreate(name="b", parent_id=level0.id))
    level2 = tag_manager.create_tag(TagCreate(name="c", parent_id=level1.id))
    level3 = tag_manager.create_tag(TagCreate(name="d", parent_id=level2.id))

    # Attempting to create level 4 should fail
    with pytest.raises(ValidationError, match="hierarchy cannot exceed 4 levels"):
        tag_manager.create_tag(TagCreate(name="e", parent_id=level3.id))


def test_duplicate_tag_path(tag_manager):
    """Test that duplicate tag paths are rejected."""
    tag_manager.create_tag(TagCreate(name="python"))

    with pytest.raises(StorageError, match="Tag already exists"):
        tag_manager.create_tag(TagCreate(name="python"))


def test_get_tag_by_id(tag_manager):
    """Test retrieving a tag by ID."""
    created = tag_manager.create_tag(TagCreate(name="python"))
    retrieved = tag_manager.get_tag(created.id)

    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.name == "python"


def test_get_tag_by_path(tag_manager):
    """Test retrieving a tag by full path."""
    parent = tag_manager.create_tag(TagCreate(name="language"))
    child = tag_manager.create_tag(TagCreate(name="python", parent_id=parent.id))

    retrieved = tag_manager.get_tag_by_path("language/python")

    assert retrieved is not None
    assert retrieved.id == child.id


def test_list_root_tags(tag_manager):
    """Test listing root-level tags."""
    tag_manager.create_tag(TagCreate(name="python"))
    tag_manager.create_tag(TagCreate(name="javascript"))

    tags = tag_manager.list_tags(parent_id=None)

    assert len(tags) == 2
    assert {tag.name for tag in tags} == {"python", "javascript"}


def test_list_tags_by_prefix(tag_manager):
    """Test listing tags by path prefix."""
    lang = tag_manager.create_tag(TagCreate(name="language"))
    tag_manager.create_tag(TagCreate(name="python", parent_id=lang.id))
    tag_manager.create_tag(TagCreate(name="javascript", parent_id=lang.id))

    # Create other top-level tag
    tag_manager.create_tag(TagCreate(name="framework"))

    tags = tag_manager.list_tags(prefix="language/")

    assert len(tags) == 2
    assert all(tag.full_path.startswith("language/") for tag in tags)


def test_get_ancestors(tag_manager):
    """Test getting ancestor tags."""
    level0 = tag_manager.create_tag(TagCreate(name="language"))
    level1 = tag_manager.create_tag(TagCreate(name="python", parent_id=level0.id))
    level2 = tag_manager.create_tag(TagCreate(name="async", parent_id=level1.id))

    ancestors = tag_manager.get_ancestors(level2.id)

    assert len(ancestors) == 2
    assert ancestors[0].name == "language"
    assert ancestors[1].name == "python"


def test_get_descendants(tag_manager):
    """Test getting descendant tags."""
    parent = tag_manager.create_tag(TagCreate(name="language"))
    child1 = tag_manager.create_tag(TagCreate(name="python", parent_id=parent.id))
    child2 = tag_manager.create_tag(TagCreate(name="javascript", parent_id=parent.id))
    grandchild = tag_manager.create_tag(TagCreate(name="async", parent_id=child1.id))

    descendants = tag_manager.get_descendants(parent.id)

    assert len(descendants) == 3
    desc_names = {tag.name for tag in descendants}
    assert desc_names == {"python", "javascript", "async"}


def test_delete_tag_without_descendants(tag_manager):
    """Test deleting a tag without descendants."""
    tag = tag_manager.create_tag(TagCreate(name="python"))

    tag_manager.delete_tag(tag.id)

    assert tag_manager.get_tag(tag.id) is None


def test_delete_tag_with_descendants_no_cascade(tag_manager):
    """Test that deleting a tag with descendants requires cascade."""
    parent = tag_manager.create_tag(TagCreate(name="language"))
    tag_manager.create_tag(TagCreate(name="python", parent_id=parent.id))

    with pytest.raises(ValidationError, match="descendants"):
        tag_manager.delete_tag(parent.id, cascade=False)


def test_delete_tag_with_cascade(tag_manager):
    """Test deleting a tag with all its descendants."""
    parent = tag_manager.create_tag(TagCreate(name="language"))
    child = tag_manager.create_tag(TagCreate(name="python", parent_id=parent.id))

    tag_manager.delete_tag(parent.id, cascade=True)

    assert tag_manager.get_tag(parent.id) is None
    assert tag_manager.get_tag(child.id) is None


def test_merge_tags(tag_manager):
    """Test merging two tags."""
    source = tag_manager.create_tag(TagCreate(name="js"))
    target = tag_manager.create_tag(TagCreate(name="javascript"))

    # Tag a memory with source
    tag_manager.tag_memory("memory-123", source.id)

    # Merge source into target
    tag_manager.merge_tags(source.id, target.id)

    # Source tag should be deleted
    assert tag_manager.get_tag(source.id) is None

    # Memory should now be tagged with target
    memory_tags = tag_manager.get_memory_tags("memory-123")
    assert len(memory_tags) == 1
    assert memory_tags[0].id == target.id


def test_tag_memory(tag_manager):
    """Test associating a tag with a memory."""
    tag = tag_manager.create_tag(TagCreate(name="python"))

    tag_manager.tag_memory("memory-123", tag.id, confidence=0.95, auto_generated=True)

    # Verify association
    memory_tags = tag_manager.get_memory_tags("memory-123")
    assert len(memory_tags) == 1
    assert memory_tags[0].id == tag.id


def test_untag_memory(tag_manager):
    """Test removing a tag from a memory."""
    tag = tag_manager.create_tag(TagCreate(name="python"))
    tag_manager.tag_memory("memory-123", tag.id)

    tag_manager.untag_memory("memory-123", tag.id)

    memory_tags = tag_manager.get_memory_tags("memory-123")
    assert len(memory_tags) == 0


def test_get_or_create_tag_existing(tag_manager):
    """Test get_or_create_tag with existing tag."""
    existing = tag_manager.create_tag(TagCreate(name="python"))

    result = tag_manager.get_or_create_tag("python")

    assert result.id == existing.id


def test_get_or_create_tag_new_hierarchy(tag_manager):
    """Test get_or_create_tag creating a new hierarchy."""
    result = tag_manager.get_or_create_tag("language/python/async")

    assert result.full_path == "language/python/async"
    assert result.level == 2

    # Verify parent hierarchy was created
    parent = tag_manager.get_tag_by_path("language/python")
    assert parent is not None
    grandparent = tag_manager.get_tag_by_path("language")
    assert grandparent is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
