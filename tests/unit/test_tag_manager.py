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


@pytest.mark.parametrize(
    "hierarchy_path,expected_level",
    [
        (["python"], 0),
        (["language", "python"], 1),
        (["language", "python", "async"], 2),
        (["language", "python", "async", "patterns"], 3),
    ],
    ids=["root", "nested", "deep_3", "deep_4"],
)
def test_create_tag_hierarchy(tag_manager, hierarchy_path, expected_level):
    """Test creating tag hierarchies at different levels."""
    parent_id = None
    created_tag = None

    # Create hierarchy
    for name in hierarchy_path:
        tag_create = TagCreate(name=name, parent_id=parent_id)
        created_tag = tag_manager.create_tag(tag_create)
        parent_id = created_tag.id

    # Verify final tag
    assert created_tag.name == hierarchy_path[-1]
    assert created_tag.full_path == "/".join(hierarchy_path)
    assert created_tag.level == expected_level

    if expected_level == 0:
        assert created_tag.parent_id is None


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


@pytest.mark.parametrize(
    "tag_path,retrieval_method",
    [
        ("python", "by_id"),
        ("language/python", "by_path"),
    ],
    ids=["get_by_id", "get_by_path"],
)
def test_get_tag(tag_manager, tag_path, retrieval_method):
    """Test retrieving tags by ID or path."""
    # Create hierarchy if needed
    parts = tag_path.split("/")
    parent_id = None
    created_tag = None

    for name in parts:
        tag_create = TagCreate(name=name, parent_id=parent_id)
        created_tag = tag_manager.create_tag(tag_create)
        parent_id = created_tag.id

    # Retrieve tag
    if retrieval_method == "by_id":
        retrieved = tag_manager.get_tag(created_tag.id)
        assert retrieved is not None
        assert retrieved.id == created_tag.id
        assert retrieved.name == parts[-1]
    else:  # by_path
        retrieved = tag_manager.get_tag_by_path(tag_path)
        assert retrieved is not None
        assert retrieved.id == created_tag.id


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
    tag_manager.create_tag(TagCreate(name="javascript", parent_id=parent.id))
    tag_manager.create_tag(TagCreate(name="async", parent_id=child1.id))

    descendants = tag_manager.get_descendants(parent.id)

    assert len(descendants) == 3
    desc_names = {tag.name for tag in descendants}
    assert desc_names == {"python", "javascript", "async"}


@pytest.mark.parametrize(
    "has_children,cascade,should_succeed",
    [
        (False, False, True),
        (True, False, False),
        (True, True, True),
    ],
    ids=["no_children", "with_children_no_cascade", "with_children_cascade"],
)
def test_delete_tag(tag_manager, has_children, cascade, should_succeed):
    """Test deleting tags with various scenarios."""
    parent = tag_manager.create_tag(TagCreate(name="language"))
    child = None

    if has_children:
        child = tag_manager.create_tag(TagCreate(name="python", parent_id=parent.id))

    if should_succeed:
        tag_manager.delete_tag(parent.id, cascade=cascade)
        assert tag_manager.get_tag(parent.id) is None
        if child:
            assert tag_manager.get_tag(child.id) is None
    else:
        with pytest.raises(ValidationError, match="descendants"):
            tag_manager.delete_tag(parent.id, cascade=cascade)


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


@pytest.mark.parametrize(
    "operation,expected_count",
    [
        ("tag", 1),
        ("tag_then_untag", 0),
    ],
    ids=["tag_memory", "untag_memory"],
)
def test_memory_tagging(tag_manager, operation, expected_count):
    """Test tagging and untagging memories."""
    tag = tag_manager.create_tag(TagCreate(name="python"))

    if operation == "tag":
        tag_manager.tag_memory(
            "memory-123", tag.id, confidence=0.95, auto_generated=True
        )
    elif operation == "tag_then_untag":
        tag_manager.tag_memory("memory-123", tag.id)
        tag_manager.untag_memory("memory-123", tag.id)

    memory_tags = tag_manager.get_memory_tags("memory-123")
    assert len(memory_tags) == expected_count
    if expected_count > 0:
        assert memory_tags[0].id == tag.id


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
