# FEAT-040: Memory Update/Edit Operations

## TODO Reference
- **ID:** FEAT-040
- **TODO.md:** Lines 62-72
- **Priority:** CRITICAL 🔥🔥🔥🔥
- **Estimate:** 3-4 days

## Objective
Implement memory update functionality to complete the CRUD operations. Currently users can only Create, Read, and Delete memories - they cannot Update them. This is a fundamental gap in the memory lifecycle management.

## Current State

### What Exists
- `store_memory` - Create new memories
- `retrieve_memories` - Read memories via search
- `delete_memory` - Delete memories by ID
- Memory data structure with all fields (content, category, importance, tags, metadata)

### What's Missing
- `update_memory` - Modify existing memories
- Partial update support (update only specific fields)
- Embedding regeneration on content changes
- Version history tracking (optional)
- Concurrent update handling

### The Problem
**Use case:** "I changed my mind about preferring tabs over spaces"

**Current workflow (broken):**
1. Search for the preference memory
2. Copy the memory ID
3. Delete the old memory
4. Create a new memory with updated content
5. **Problems:**
   - Loses memory ID (breaks references)
   - Loses creation timestamp (loses history)
   - Loses provenance data (who created it, when)
   - No audit trail of changes
   - Memory importance/trust score reset

**Desired workflow:**
1. `update_memory(memory_id, content="I prefer spaces over tabs")`
2. Memory updates in place, preserving ID and history

## Implementation Plan

### Phase 1: Core Update Infrastructure (Day 1, ~6 hours)

#### 1.1 Define Update Request Model
**File:** `src/core/models.py`

```python
@dataclass
class UpdateMemoryRequest:
    """Request to update an existing memory."""

    memory_id: str  # Required

    # Optional fields - only update if provided
    content: Optional[str] = None
    category: Optional[MemoryCategory] = None
    importance: Optional[float] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    context_level: Optional[ContextLevel] = None

    # Update behavior flags
    preserve_timestamps: bool = True  # Keep created_at, update modified_at
    regenerate_embedding: bool = True  # Auto-regenerate if content changes

    def validate(self) -> None:
        """Validate update request."""
        if not self.memory_id:
            raise ValidationError("memory_id is required")

        # Validate at least one field is being updated
        update_fields = [
            self.content, self.category, self.importance,
            self.tags, self.metadata, self.context_level
        ]
        if all(field is None for field in update_fields):
            raise ValidationError("At least one field must be updated")

        # Validate field values
        if self.content is not None:
            if not (1 <= len(self.content) <= 50000):
                raise ValidationError("Content must be 1-50000 characters")

        if self.importance is not None:
            if not (0.0 <= self.importance <= 1.0):
                raise ValidationError("Importance must be 0.0-1.0")

        # Validate tags
        if self.tags is not None:
            for tag in self.tags:
                if not isinstance(tag, str) or len(tag) > 50:
                    raise ValidationError("Tags must be strings <= 50 chars")


@dataclass
class UpdateMemoryResponse:
    """Response from memory update."""

    memory_id: str
    status: str  # "updated"
    updated_fields: List[str]  # Fields that were changed
    embedding_regenerated: bool
    previous_version: Optional[Dict[str, Any]] = None  # For audit trail
    updated_at: str  # ISO timestamp
```

#### 1.2 Add Update Method to Memory Stores
**File:** `src/store/memory_store.py` (interface)

```python
class MemoryStore(ABC):
    """Abstract base class for memory storage backends."""

    # ... existing methods ...

    @abstractmethod
    async def update_memory(
        self,
        memory_id: str,
        updates: Dict[str, Any],
        regenerate_embedding: bool = True
    ) -> MemoryUnit:
        """
        Update an existing memory.

        Args:
            memory_id: ID of memory to update
            updates: Dictionary of fields to update
            regenerate_embedding: Whether to regenerate embedding if content changed

        Returns:
            Updated MemoryUnit

        Raises:
            StorageError: If memory not found or update fails
        """
        pass

    @abstractmethod
    async def get_memory_by_id(self, memory_id: str) -> Optional[MemoryUnit]:
        """
        Retrieve a specific memory by ID.

        Args:
            memory_id: ID of memory to retrieve

        Returns:
            MemoryUnit if found, None otherwise
        """
        pass
```

### Phase 2: Qdrant Backend Implementation (Day 1-2, ~6 hours)

#### 2.1 Implement Update in QdrantStore
**File:** `src/store/qdrant_store.py`

```python
async def update_memory(
    self,
    memory_id: str,
    updates: Dict[str, Any],
    regenerate_embedding: bool = True
) -> MemoryUnit:
    """Update an existing memory in Qdrant."""

    # 1. Retrieve existing memory
    existing = await self.get_memory_by_id(memory_id)
    if not existing:
        raise StorageError(f"Memory {memory_id} not found")

    # 2. Apply updates to create new version
    updated_data = {
        "memory_id": memory_id,
        "content": updates.get("content", existing.content),
        "category": updates.get("category", existing.category),
        "importance": updates.get("importance", existing.importance),
        "tags": updates.get("tags", existing.tags),
        "metadata": updates.get("metadata", existing.metadata),
        "context_level": updates.get("context_level", existing.context_level),
        "scope": updates.get("scope", existing.scope),
        "project_name": updates.get("project_name", existing.project_name),
        "created_at": existing.created_at,  # Preserve
        "updated_at": datetime.now(UTC),  # Update
        "last_accessed": existing.last_accessed,
    }

    # 3. Regenerate embedding if content changed
    new_embedding = existing.embedding  # Default to existing
    if "content" in updates and regenerate_embedding:
        content_changed = updates["content"] != existing.content
        if content_changed:
            new_embedding = await self.embedding_generator.generate_embedding(
                updates["content"]
            )

    updated_data["embedding"] = new_embedding

    # 4. Create MemoryUnit
    updated_memory = MemoryUnit(**updated_data)

    # 5. Update in Qdrant (use upsert with same ID)
    collection_name = self._get_collection_name(updated_memory.scope)

    try:
        self.client.upsert(
            collection_name=collection_name,
            points=[
                models.PointStruct(
                    id=memory_id,
                    vector=new_embedding,
                    payload={
                        "content": updated_memory.content,
                        "category": updated_memory.category.value,
                        "context_level": updated_memory.context_level.value,
                        "importance": updated_memory.importance,
                        "tags": updated_memory.tags,
                        "metadata": updated_memory.metadata,
                        "project_name": updated_memory.project_name,
                        "scope": updated_memory.scope.value,
                        "created_at": updated_memory.created_at.isoformat(),
                        "updated_at": updated_memory.updated_at.isoformat(),
                        "last_accessed": updated_memory.last_accessed.isoformat() if updated_memory.last_accessed else None,
                    }
                )
            ]
        )

        logger.info(f"Updated memory {memory_id}")
        return updated_memory

    except Exception as e:
        logger.error(f"Failed to update memory {memory_id}: {e}")
        raise StorageError(f"Failed to update memory: {e}")


async def get_memory_by_id(self, memory_id: str) -> Optional[MemoryUnit]:
    """Retrieve a specific memory by ID from Qdrant."""

    # Try global collection first
    for collection in ["global_memories", "project_memories"]:
        try:
            result = self.client.retrieve(
                collection_name=collection,
                ids=[memory_id]
            )

            if result and len(result) > 0:
                point = result[0]
                return self._point_to_memory_unit(point)

        except Exception as e:
            logger.debug(f"Memory {memory_id} not in {collection}: {e}")
            continue

    return None
```

### Phase 3: SQLite Backend Implementation (Day 2, ~4 hours)

#### 3.1 Implement Update in SQLiteStore
**File:** `src/store/sqlite_store.py`

```python
async def update_memory(
    self,
    memory_id: str,
    updates: Dict[str, Any],
    regenerate_embedding: bool = True
) -> MemoryUnit:
    """Update an existing memory in SQLite."""

    # 1. Retrieve existing memory
    existing = await self.get_memory_by_id(memory_id)
    if not existing:
        raise StorageError(f"Memory {memory_id} not found")

    # 2. Build update SQL
    update_fields = []
    params = []

    if "content" in updates:
        update_fields.append("content = ?")
        params.append(updates["content"])

        # Regenerate embedding if content changed
        if regenerate_embedding and updates["content"] != existing.content:
            embedding = await self.embedding_generator.generate_embedding(
                updates["content"]
            )
            update_fields.append("embedding = ?")
            params.append(self._serialize_embedding(embedding))

    if "category" in updates:
        update_fields.append("category = ?")
        params.append(updates["category"].value)

    if "importance" in updates:
        update_fields.append("importance = ?")
        params.append(updates["importance"])

    if "tags" in updates:
        update_fields.append("tags = ?")
        params.append(json.dumps(updates["tags"]))

    if "metadata" in updates:
        update_fields.append("metadata = ?")
        params.append(json.dumps(updates["metadata"]))

    if "context_level" in updates:
        update_fields.append("context_level = ?")
        params.append(updates["context_level"].value)

    # Always update modified timestamp
    update_fields.append("updated_at = ?")
    params.append(datetime.now(UTC).isoformat())

    # Add memory_id for WHERE clause
    params.append(memory_id)

    # 3. Execute update
    sql = f"""
        UPDATE memories
        SET {', '.join(update_fields)}
        WHERE memory_id = ?
    """

    async with aiosqlite.connect(self.db_path) as db:
        await db.execute(sql, params)
        await db.commit()

    # 4. Retrieve updated memory
    updated = await self.get_memory_by_id(memory_id)
    if not updated:
        raise StorageError(f"Failed to retrieve updated memory {memory_id}")

    logger.info(f"Updated memory {memory_id}")
    return updated


async def get_memory_by_id(self, memory_id: str) -> Optional[MemoryUnit]:
    """Retrieve a specific memory by ID from SQLite."""

    sql = "SELECT * FROM memories WHERE memory_id = ?"

    async with aiosqlite.connect(self.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, (memory_id,)) as cursor:
            row = await cursor.fetchone()

            if row:
                return self._row_to_memory_unit(dict(row))
            return None
```

### Phase 4: MCP Tool Implementation (Day 2-3, ~4 hours)

#### 4.1 Add update_memory to Server
**File:** `src/core/server.py`

```python
async def update_memory(
    self,
    memory_id: str,
    content: Optional[str] = None,
    category: Optional[str] = None,
    importance: Optional[float] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    context_level: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update an existing memory.

    Args:
        memory_id: ID of memory to update (required)
        content: New content (optional)
        category: New category (optional)
        importance: New importance score 0.0-1.0 (optional)
        tags: New tags list (optional)
        metadata: New metadata dict (optional)
        context_level: New context level (optional)

    Returns:
        {
            "memory_id": str,
            "status": "updated",
            "updated_fields": List[str],
            "embedding_regenerated": bool,
            "updated_at": ISO timestamp
        }

    Raises:
        ReadOnlyError: If server is in read-only mode
        ValidationError: If inputs are invalid
        StorageError: If memory not found or update fails
    """
    if self.config.read_only_mode:
        raise ReadOnlyError("Cannot update memories in read-only mode")

    # Build update request
    updates = {}
    updated_fields = []

    if content is not None:
        # Validate and sanitize
        content = self.validator.sanitize_content(content)
        self.validator.validate_content(content)
        updates["content"] = content
        updated_fields.append("content")

    if category is not None:
        cat = MemoryCategory(category)
        updates["category"] = cat
        updated_fields.append("category")

    if importance is not None:
        if not (0.0 <= importance <= 1.0):
            raise ValidationError("importance must be 0.0-1.0")
        updates["importance"] = importance
        updated_fields.append("importance")

    if tags is not None:
        # Validate tags
        for tag in tags:
            if not isinstance(tag, str) or len(tag) > 50:
                raise ValidationError("Tags must be strings <= 50 chars")
        updates["tags"] = tags
        updated_fields.append("tags")

    if metadata is not None:
        # Sanitize metadata
        metadata = self.validator.sanitize_metadata(metadata)
        updates["metadata"] = metadata
        updated_fields.append("metadata")

    if context_level is not None:
        cl = ContextLevel(context_level)
        updates["context_level"] = cl
        updated_fields.append("context_level")

    # Validate at least one field is being updated
    if not updates:
        raise ValidationError("At least one field must be provided for update")

    # Perform update
    try:
        regenerate_embedding = "content" in updates
        updated_memory = await self.store.update_memory(
            memory_id=memory_id,
            updates=updates,
            regenerate_embedding=regenerate_embedding
        )

        # Update stats
        self.stats["memories_updated"] = self.stats.get("memories_updated", 0) + 1

        return {
            "memory_id": memory_id,
            "status": "updated",
            "updated_fields": updated_fields,
            "embedding_regenerated": regenerate_embedding,
            "updated_at": updated_memory.updated_at.isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to update memory {memory_id}: {e}")
        raise


async def get_memory_by_id(self, memory_id: str) -> Dict[str, Any]:
    """
    Retrieve a specific memory by its ID.

    Args:
        memory_id: ID of memory to retrieve

    Returns:
        {
            "memory": MemoryUnit dict,
            "found": bool
        }

    Raises:
        ValidationError: If memory_id is invalid format
    """
    # Validate UUID format
    try:
        uuid.UUID(memory_id)
    except ValueError:
        raise ValidationError(f"Invalid memory_id format: {memory_id}")

    memory = await self.store.get_memory_by_id(memory_id)

    if memory:
        return {
            "memory": {
                "memory_id": memory.memory_id,
                "content": memory.content,
                "category": memory.category.value,
                "context_level": memory.context_level.value,
                "importance": memory.importance,
                "tags": memory.tags,
                "metadata": memory.metadata,
                "scope": memory.scope.value,
                "project_name": memory.project_name,
                "created_at": memory.created_at.isoformat(),
                "updated_at": memory.updated_at.isoformat(),
                "last_accessed": memory.last_accessed.isoformat() if memory.last_accessed else None,
            },
            "found": True
        }
    else:
        return {
            "memory": None,
            "found": False
        }
```

#### 4.2 Register MCP Tools
**File:** `src/mcp_server.py`

```python
{
    "name": "update_memory",
    "description": "Update an existing memory (content, category, importance, tags, etc.)",
    "inputSchema": {
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "string",
                "description": "ID of memory to update"
            },
            "content": {
                "type": "string",
                "description": "New content (optional)"
            },
            "category": {
                "type": "string",
                "enum": ["preference", "fact", "event", "workflow", "context"],
                "description": "New category (optional)"
            },
            "importance": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "New importance score (optional)"
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "New tags list (optional)"
            },
            "metadata": {
                "type": "object",
                "description": "New metadata (optional)"
            },
            "context_level": {
                "type": "string",
                "enum": ["USER_PREFERENCE", "PROJECT_CONTEXT", "SESSION_STATE"],
                "description": "New context level (optional)"
            }
        },
        "required": ["memory_id"]
    }
},
{
    "name": "get_memory_by_id",
    "description": "Retrieve a specific memory by its ID",
    "inputSchema": {
        "type": "object",
        "properties": {
            "memory_id": {
                "type": "string",
                "description": "ID of memory to retrieve"
            }
        },
        "required": ["memory_id"]
    }
}
```

### Phase 5: Testing (Day 3, ~6 hours)

#### 5.1 Unit Tests
**File:** `tests/unit/test_memory_update.py` (~30 tests)

```python
class TestMemoryUpdate:
    """Test memory update functionality."""

    # Basic updates
    async def test_update_content(self):
        """Test updating memory content."""
        pass

    async def test_update_importance(self):
        """Test updating importance score."""
        pass

    async def test_update_tags(self):
        """Test updating tags."""
        pass

    async def test_update_multiple_fields(self):
        """Test updating multiple fields at once."""
        pass

    # Embedding regeneration
    async def test_embedding_regenerated_on_content_change(self):
        """Test that embedding is regenerated when content changes."""
        pass

    async def test_embedding_not_regenerated_on_metadata_change(self):
        """Test that embedding is NOT regenerated for non-content changes."""
        pass

    # Preservation
    async def test_preserves_memory_id(self):
        """Test that memory ID is preserved."""
        pass

    async def test_preserves_created_at(self):
        """Test that created_at timestamp is preserved."""
        pass

    async def test_updates_modified_at(self):
        """Test that updated_at timestamp is updated."""
        pass

    # Validation
    async def test_invalid_memory_id(self):
        """Test error on invalid memory ID."""
        pass

    async def test_memory_not_found(self):
        """Test error when memory doesn't exist."""
        pass

    async def test_no_fields_provided(self):
        """Test error when no update fields provided."""
        pass

    async def test_invalid_importance_range(self):
        """Test error on importance out of range."""
        pass

    async def test_content_too_long(self):
        """Test error on content > 50KB."""
        pass

    # Edge cases
    async def test_update_to_same_value(self):
        """Test updating to the same value (no-op but succeeds)."""
        pass

    async def test_partial_update(self):
        """Test updating only one field leaves others unchanged."""
        pass

    async def test_update_in_read_only_mode(self):
        """Test that update fails in read-only mode."""
        pass

    # Backend-specific tests
    async def test_update_qdrant_backend(self):
        """Test update with Qdrant backend."""
        pass

    async def test_update_sqlite_backend(self):
        """Test update with SQLite backend."""
        pass
```

#### 5.2 Integration Tests
**File:** `tests/integration/test_memory_lifecycle.py`

```python
class TestMemoryLifecycle:
    """Test complete memory CRUD lifecycle."""

    async def test_create_update_retrieve_delete(self):
        """Test full lifecycle: create → update → retrieve → delete."""
        # Create memory
        memory_id = await server.store_memory(
            content="I prefer tabs",
            category="preference"
        )

        # Update memory
        await server.update_memory(
            memory_id=memory_id,
            content="I prefer spaces"
        )

        # Retrieve and verify
        result = await server.get_memory_by_id(memory_id)
        assert result["memory"]["content"] == "I prefer spaces"

        # Delete
        await server.delete_memory(memory_id)

        # Verify deleted
        result = await server.get_memory_by_id(memory_id)
        assert result["found"] is False

    async def test_update_affects_search_results(self):
        """Test that updates affect semantic search results."""
        pass

    async def test_concurrent_updates(self):
        """Test handling of concurrent updates to same memory."""
        pass
```

### Phase 6: Documentation (Day 4, ~2 hours)

#### 6.1 Update API.md
Add new tools documentation:

```markdown
### update_memory

Update an existing memory's content, category, importance, tags, or metadata.

**Input Schema:**
```json
{
  "memory_id": "550e8400-e29b-41d4-a716-446655440000",
  "content": "I prefer spaces over tabs for Python code",
  "importance": 0.9,
  "tags": ["python", "code-style", "preferences"]
}
```

**Response:**
```json
{
  "memory_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "updated",
  "updated_fields": ["content", "importance", "tags"],
  "embedding_regenerated": true,
  "updated_at": "2025-11-17T14:30:00Z"
}
```

**Key Features:**
- Partial updates supported (only specify fields you want to change)
- Preserves memory ID and creation timestamp
- Automatically regenerates embedding when content changes
- Updates modification timestamp
- Validates all inputs

**Validation:**
- memory_id must be valid UUID format
- At least one field must be provided
- content: 1-50,000 characters
- importance: 0.0-1.0
- tags: array of strings, max 50 chars each
```

#### 6.2 Update USAGE.md
Add usage examples:

```markdown
## Updating Memories

### Update Content
```python
# Change your mind about a preference
await server.update_memory(
    memory_id="550e8400-...",
    content="I now prefer spaces over tabs"
)
```

### Update Importance
```python
# Increase importance of a memory
await server.update_memory(
    memory_id="550e8400-...",
    importance=0.9
)
```

### Update Multiple Fields
```python
# Update multiple fields at once
await server.update_memory(
    memory_id="550e8400-...",
    content="Updated content",
    tags=["new", "tags"],
    importance=0.8
)
```

### Get Memory Before Update
```python
# Retrieve current state
result = await server.get_memory_by_id("550e8400-...")
if result["found"]:
    memory = result["memory"]

    # Update based on current state
    await server.update_memory(
        memory_id=memory["memory_id"],
        importance=memory["importance"] + 0.1
    )
```
```

## Files to Create

1. `tests/unit/test_memory_update.py` (~500 lines) - Unit tests
2. `tests/integration/test_memory_lifecycle.py` (~200 lines) - Integration tests

## Files to Modify

1. `src/core/models.py` - Add UpdateMemoryRequest, UpdateMemoryResponse
2. `src/store/memory_store.py` - Add abstract update_memory, get_memory_by_id
3. `src/store/qdrant_store.py` - Implement update_memory, get_memory_by_id
4. `src/store/sqlite_store.py` - Implement update_memory, get_memory_by_id
5. `src/core/server.py` - Add update_memory, get_memory_by_id MCP tools
6. `src/mcp_server.py` - Register new MCP tools
7. `docs/API.md` - Document update_memory and get_memory_by_id
8. `docs/USAGE.md` - Add usage examples

## Success Criteria

- [ ] update_memory MCP tool implemented and working
- [ ] get_memory_by_id MCP tool implemented and working
- [ ] Both Qdrant and SQLite backends support update
- [ ] Embedding regeneration works correctly
- [ ] Timestamps handled properly (preserve created_at, update updated_at)
- [ ] 30+ unit tests passing
- [ ] Integration tests passing
- [ ] 95%+ test coverage
- [ ] Documentation complete
- [ ] No regression in existing tests

## Security Considerations

1. **Validation:** All inputs validated before update
2. **Read-Only Mode:** Updates blocked in read-only mode
3. **Sanitization:** Content and metadata sanitized
4. **Audit Trail:** updated_at timestamp provides change tracking
5. **Concurrency:** Last-write-wins strategy (document this)

## Performance Impact

- **Update latency:** ~10-50ms (Qdrant), ~5-20ms (SQLite)
- **Embedding regeneration:** +50-100ms if content changed
- **Memory overhead:** Minimal (no in-memory caching)
- **Storage:** No additional storage (in-place update)

## Open Questions

1. **Version history?** Should we keep previous versions?
   - **Decision:** Not for MVP. Add in follow-up if requested (FEAT-049)

2. **Optimistic locking?** Handle concurrent updates?
   - **Decision:** Last-write-wins for MVP. Document this behavior.

3. **Partial embedding updates?** Update only changed sections?
   - **Decision:** Always regenerate full embedding. Simpler and more accurate.

4. **Bulk updates?** Update multiple memories at once?
   - **Decision:** Single-memory updates for MVP. Bulk in FEAT-043.

## Implementation Notes

- Preserve ALL metadata on update (provenance, trust scores, etc.)
- Log all updates for debugging
- Use transactions where possible (SQLite)
- Handle missing memories gracefully with clear error messages

## Completion Checklist

- [ ] UpdateMemoryRequest model defined
- [ ] UpdateMemoryResponse model defined
- [ ] update_memory added to MemoryStore interface
- [ ] get_memory_by_id added to MemoryStore interface
- [ ] update_memory implemented in QdrantStore
- [ ] get_memory_by_id implemented in QdrantStore
- [ ] update_memory implemented in SQLiteStore
- [ ] get_memory_by_id implemented in SQLiteStore
- [ ] update_memory MCP tool implemented in server
- [ ] get_memory_by_id MCP tool implemented in server
- [ ] MCP tools registered in mcp_server.py
- [ ] Unit tests written and passing (30+)
- [ ] Integration tests written and passing
- [ ] Documentation updated (API.md, USAGE.md)
- [ ] Manual testing completed
- [ ] Code review completed
- [ ] CHANGELOG.md updated
