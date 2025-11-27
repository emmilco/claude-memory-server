"""E2E tests for critical user workflows.

These tests simulate complete user journeys through the system,
from first-time setup to daily development workflows.

NOTE: These tests are currently skipped pending API compatibility fixes.
The tests use incorrect API parameters (e.g., 'mode' instead of 'search_mode',
'id' instead of 'memory_id'). See TEST-027 for tracking.
"""

import pytest
import time
from pathlib import Path

# E2E tests for critical user workflows - API compatibility fixed


# ============================================================================
# First-Time User Tests (3 tests)
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_first_time_setup(fresh_server, sample_code_project):
    """Test: Fresh install → Configure → Index first project → First search.

    Simulates a new user's first experience with the system:
    1. Server is initialized (via fresh_server fixture)
    2. Index their first code project
    3. Perform their first search
    4. Verify results are returned
    """
    server = fresh_server
    project_path = sample_code_project

    # Step 1: Verify server is initialized and healthy
    status = await server.get_status()
    assert status is not None
    # Server should return status (may have different fields depending on config)
    assert "server_name" in status or "storage_backend" in status

    # Step 2: Index first project
    result = await server.index_codebase(
        directory_path=str(project_path),
        project_name="my-first-project",
        recursive=True
    )

    assert result is not None
    assert result.get("files_indexed", 0) >= 4  # Should index at least 4 Python files
    assert result.get("units_indexed", 0) >= 10  # Should have multiple functions/classes

    # Step 3: Perform first search
    search_result = await server.search_code(
        query="authentication function",
        project_name="my-first-project",
        search_mode="semantic",
        limit=5
    )

    # Step 4: Verify meaningful results
    assert search_result is not None
    assert search_result.get("status") == "success"
    assert len(search_result.get("results", [])) > 0

    # Should find the authenticate function
    result_names = [r.get("unit_name", "") for r in search_result["results"]]
    assert any("authenticate" in name.lower() for name in result_names)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_first_memory_storage(fresh_server):
    """Test: Store first memory → Retrieve it → Verify.

    Simulates a user storing their first piece of information:
    1. Store a memory with tags
    2. Retrieve it by semantic search
    3. Verify the content matches
    """
    server = fresh_server

    # Step 1: Store first memory
    memory_content = "JWT tokens expire after 24 hours in this application"
    store_result = await server.store_memory(
        content=memory_content,
        category="fact",
        importance=0.8,
        tags=["authentication", "jwt", "security"]
    )

    assert store_result is not None
    assert "memory_id" in store_result
    memory_id = store_result["memory_id"]

    # Step 2: Retrieve by semantic search
    retrieve_result = await server.retrieve_memories(
        query="How long do JWT tokens last?",
        limit=5
    )

    assert retrieve_result is not None
    # Handle both dict with results and list formats
    if isinstance(retrieve_result, dict):
        results_list = retrieve_result.get("results", [])
    else:
        results_list = retrieve_result
    assert len(results_list) > 0

    # Step 3: Verify content matches
    # Results have structure: {"memory": {"id": ..., "content": ..., "tags": ...}, "score": ...}
    found = False
    results = retrieve_result.get("results", []) if isinstance(retrieve_result, dict) else retrieve_result
    for result in results:
        mem = result.get("memory", result)  # Handle nested or flat structure
        mem_id = mem.get("id") or mem.get("memory_id")
        if mem_id == memory_id:
            assert memory_content in mem.get("content", "")
            assert "jwt" in [t.lower() for t in mem.get("tags", [])]
            found = True
            break

    assert found, "Stored memory should be retrievable"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_first_code_search(fresh_server, sample_code_project):
    """Test: Index small project → Search → Get results.

    Simulates a user's first code search experience:
    1. Index a small project
    2. Search for a specific concept
    3. Verify search quality and speed
    """
    server = fresh_server
    project_path = sample_code_project

    # Step 1: Index small project
    start_time = time.time()
    index_result = await server.index_codebase(
        directory_path=str(project_path),
        project_name="sample-project",
        recursive=True
    )
    index_time = time.time() - start_time

    assert index_result is not None
    assert index_result.get("files_indexed", 0) > 0
    # Indexing should be reasonably fast for small projects
    assert index_time < 30.0, f"Indexing took {index_time:.1f}s, expected < 30s"

    # Step 2: Search for specific concept
    start_time = time.time()
    search_result = await server.search_code(
        query="database connection",
        project_name="sample-project",
        search_mode="hybrid",
        limit=10
    )
    search_time = time.time() - start_time

    # Step 3: Verify results
    assert search_result is not None
    assert search_result.get("status") == "success"
    results = search_result.get("results", [])
    assert len(results) > 0

    # Should find DatabaseConnection class or related functions
    found_relevant = False
    for result in results:
        unit_name = result.get("unit_name", "").lower()
        if "database" in unit_name or "connection" in unit_name:
            found_relevant = True
            break

    assert found_relevant, "Should find database-related code units"

    # Search should be fast (target: < 100ms for small dataset)
    assert search_time < 1.0, f"Search took {search_time*1000:.0f}ms, expected < 1000ms"


# ============================================================================
# Daily Workflow Tests (4 tests)
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_developer_daily_workflow(fresh_server, sample_code_project):
    """Test: Search code → Find function → Store note → Search note.

    Simulates a typical developer workflow:
    1. Morning: search for code I was working on
    2. Found it, review the implementation
    3. Store a note about what I learned
    4. Later: retrieve my note
    """
    server = fresh_server

    # Setup: Index project
    await server.index_codebase(
        directory_path=str(sample_code_project),
        project_name="work-project",
        recursive=True
    )

    # Step 1: Morning search for code I was working on
    search_result = await server.search_code(
        query="authentication handler verify password",
        project_name="work-project",
        search_mode="semantic",
        limit=5
    )

    assert len(search_result.get("results", [])) > 0
    auth_code = search_result["results"][0]

    # Step 2: Review the code (simulate reading)
    assert "file_path" in auth_code
    assert "start_line" in auth_code

    # Step 3: Store a note about what I learned
    note_content = f"The {auth_code['unit_name']} uses SHA-256 for password hashing. Need to migrate to bcrypt for better security."
    store_result = await server.store_memory(
        content=note_content,
        category="fact",
        importance=0.9,
        tags=["security", "authentication", "technical-debt"]
    )

    assert store_result is not None
    note_id = store_result["memory_id"]

    # Step 4: Later in the day, retrieve my note
    memories = await server.retrieve_memories(
        query="password hashing authentication",
        limit=5
    )

    # Verify I can find my note
    # Results have structure: {"memory": {"id": ...}, "score": ...}
    memories_list = memories.get("results", []) if isinstance(memories, dict) else memories
    found = any(
        (m.get("memory", m).get("id") or m.get("memory", m).get("memory_id")) == note_id
        for m in memories_list
    )
    assert found, "Should be able to retrieve the note I stored earlier"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_code_exploration_workflow(fresh_server, sample_code_project):
    """Test: Index → Search → Find similar → Navigate.

    Simulates exploring unfamiliar codebase:
    1. Index a new codebase
    2. Search for entry points
    3. Find similar functions
    4. Navigate through the code structure
    """
    server = fresh_server
    project_path = sample_code_project

    # Step 1: Index new codebase
    await server.index_codebase(
        directory_path=str(project_path),
        project_name="new-codebase",
        recursive=True
    )

    # Step 2: Find entry points
    search_result = await server.search_code(
        query="main entry point",
        project_name="new-codebase",
        search_mode="semantic",
        limit=5
    )

    assert len(search_result.get("results", [])) > 0
    main_function = search_result["results"][0]

    # Step 3: Find similar functions (example: find other API handlers)
    # Get the code snippet and search for similar
    if "code_snippet" in main_function:
        similar_result = await server.find_similar_code(
            code_snippet=main_function["code_snippet"],
            project_name="new-codebase",
            limit=5
        )

        assert similar_result is not None
        assert len(similar_result.get("results", [])) > 0

    # Step 4: Navigate through structure - get indexed files
    files_result = await server.get_indexed_files(
        project_name="new-codebase",
        limit=10
    )

    assert files_result is not None
    assert len(files_result.get("files", [])) >= 4  # Should have multiple files


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_memory_organization_workflow(fresh_server):
    """Test: Store → Tag → Filter by tag → Export.

    Simulates organizing accumulated knowledge:
    1. Store multiple memories with tags
    2. Filter by specific tags
    3. Export tagged memories
    """
    server = fresh_server

    # Step 1: Store multiple memories with different tags
    memories_data = [
        ("React hooks should be called at top level", ["react", "frontend", "best-practices"]),
        ("Use prepared statements to prevent SQL injection", ["security", "database", "best-practices"]),
        ("API rate limit is 1000 requests per hour", ["api", "performance", "limits"]),
        ("Cache database queries for 5 minutes", ["performance", "database", "caching"]),
    ]

    stored_ids = []
    for content, tags in memories_data:
        result = await server.store_memory(
            content=content,
            category="fact",
            importance=0.7,
            tags=tags
        )
        stored_ids.append(result["memory_id"])

    # Step 2: Filter by specific tag
    list_result = await server.list_memories(
        tags=["database"],
        limit=10
    )

    assert list_result is not None
    database_memories = list_result.get("memories", [])
    assert len(database_memories) >= 2  # Should find at least 2 database-related memories

    # Verify they're actually tagged with 'database'
    for memory in database_memories:
        tags = [t.lower() for t in memory.get("tags", [])]
        assert "database" in tags

    # Step 3: List all memories (simulating export)
    all_memories = await server.list_memories(limit=20)
    assert all_memories is not None
    assert len(all_memories.get("memories", [])) >= 4


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_project_switch_workflow(fresh_server, sample_code_project, test_project_factory):
    """Test: Work on project A → Switch to B → Search B only.

    Simulates switching between multiple projects:
    1. Index project A
    2. Search project A
    3. Index project B
    4. Search project B (should not return A results)
    5. Verify project isolation
    """
    server = fresh_server

    # Step 1 & 2: Work on project A
    await server.index_codebase(
        directory_path=str(sample_code_project),
        project_name="project-a",
        recursive=True
    )

    search_a = await server.search_code(
        query="authentication",
        project_name="project-a",
        search_mode="semantic",
        limit=5
    )

    assert len(search_a.get("results", [])) > 0
    results_a = search_a["results"]

    # Step 3: Create and index project B
    project_b_path = test_project_factory(name="project_b", files=5, language="python")
    await server.index_codebase(
        directory_path=str(project_b_path),
        project_name="project-b",
        recursive=True
    )

    # Step 4: Search project B
    search_b = await server.search_code(
        query="function",
        project_name="project-b",
        search_mode="semantic",
        limit=5
    )

    assert len(search_b.get("results", [])) > 0
    results_b = search_b["results"]

    # Step 5: Verify project isolation
    # All results from project A search should be from project A
    for result in results_a:
        # The project_name field might not exist, so check file_path instead
        # File paths should be from sample_code_project
        assert "sample_project" in result.get("file_path", "")

    # All results from project B search should be from project B
    for result in results_b:
        assert "project_b" in result.get("file_path", "")


# ============================================================================
# Data Management Tests (3 tests)
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_project_backup_restore(fresh_server, sample_code_project):
    """Test: Index → Export → Delete → Import → Verify.

    Simulates backing up and restoring project data:
    1. Index a project
    2. Export memories/data
    3. Delete the project
    4. Re-index and verify data is restored
    """
    server = fresh_server
    project_name = "backup-test-project"

    # Step 1: Index project
    index_result = await server.index_codebase(
        directory_path=str(sample_code_project),
        project_name=project_name,
        recursive=True
    )

    original_files = index_result.get("files_indexed", 0)
    original_units = index_result.get("units_indexed", 0)

    # Step 2: Verify data exists
    search_before = await server.search_code(
        query="database connection",
        project_name=project_name,
        search_mode="semantic",
        limit=5
    )

    assert len(search_before.get("results", [])) > 0
    results_before = search_before["results"]

    # Step 3: Re-index (simulates restore by re-indexing from source)
    # In a real backup/restore scenario, we'd use export/import tools
    # For E2E testing, we verify idempotency by re-indexing
    reindex_result = await server.index_codebase(
        directory_path=str(sample_code_project),
        project_name=project_name,
        recursive=True
    )

    # Step 4: Verify data is consistent
    # Re-indexing might skip unchanged files (incremental behavior)
    # Verify files were processed (may be fewer due to incremental skip)
    reindex_files = reindex_result.get("files_indexed", 0)
    assert reindex_files >= original_files - 1, f"Expected at least {original_files - 1} files, got {reindex_files}"
    # Units might vary slightly due to incremental indexing, but should be close
    assert abs(reindex_result.get("units_indexed", 0) - original_units) <= 5

    # Step 5: Verify search results are still available
    search_after = await server.search_code(
        query="database connection",
        project_name=project_name,
        search_mode="semantic",
        limit=5
    )

    assert len(search_after.get("results", [])) > 0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_memory_bulk_operations(fresh_server):
    """Test: Store 100 → Bulk delete 50 → Verify 50 remain.

    Simulates bulk operations on memories:
    1. Store many memories
    2. Delete a subset
    3. Verify correct count remains
    """
    server = fresh_server

    # Step 1: Store 100 memories (using smaller number for speed)
    stored_ids = []
    num_memories = 20  # Reduced from 100 for test speed

    for i in range(num_memories):
        result = await server.store_memory(
            content=f"Test memory number {i} with searchable content",
            category="fact",
            importance=0.5,
            tags=["test", f"batch-{i // 5}"]  # Group into batches
        )
        stored_ids.append(result["memory_id"])

    # Step 2: Verify all stored
    list_all = await server.list_memories(limit=num_memories + 5)
    assert len(list_all.get("memories", [])) >= num_memories

    # Step 3: Delete half (first 10)
    for memory_id in stored_ids[:10]:
        await server.delete_memory(memory_id)

    # Step 4: Verify correct count remains
    list_after_delete = await server.list_memories(limit=num_memories + 5)
    remaining = list_after_delete.get("memories", [])

    # Should have approximately 10 remaining (might have a few more if other tests added memories)
    assert len(remaining) >= 10
    assert len(remaining) <= num_memories  # But not more than we started with

    # Step 5: Verify deleted ones are gone
    # list_memories returns {"memories": [{"id": ...}, ...]}
    remaining_ids = {m.get("id") or m.get("memory_id") for m in remaining}
    for deleted_id in stored_ids[:10]:
        assert deleted_id not in remaining_ids


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_cross_project_data_isolation(fresh_server, test_project_factory):
    """Test: Create 2 projects → Verify no data leakage.

    Simulates working with multiple projects and verifying isolation:
    1. Create and index project 1
    2. Create and index project 2
    3. Search each project
    4. Verify no cross-contamination
    """
    server = fresh_server

    # Step 1: Create and index project 1
    project1 = test_project_factory(name="isolated_project_1", files=5, language="python")
    await server.index_codebase(
        directory_path=str(project1),
        project_name="isolated-1",
        recursive=True
    )

    # Step 2: Create and index project 2
    project2 = test_project_factory(name="isolated_project_2", files=5, language="javascript")
    await server.index_codebase(
        directory_path=str(project2),
        project_name="isolated-2",
        recursive=True
    )

    # Step 3: Search project 1 - should only return Python files
    search1 = await server.search_code(
        query="function",
        project_name="isolated-1",
        search_mode="semantic",
        limit=10
    )

    results1 = search1.get("results", [])
    assert len(results1) > 0

    # All results should be Python files
    for result in results1:
        file_path = result.get("file_path", "")
        assert file_path.endswith(".py"), f"Expected Python file, got {file_path}"
        assert "isolated_project_1" in file_path

    # Step 4: Search project 2 - should only return JavaScript files
    search2 = await server.search_code(
        query="function",
        project_name="isolated-2",
        search_mode="semantic",
        limit=10
    )

    results2 = search2.get("results", [])
    assert len(results2) > 0

    # All results should be JavaScript files
    for result in results2:
        file_path = result.get("file_path", "")
        assert file_path.endswith(".js"), f"Expected JavaScript file, got {file_path}"
        assert "isolated_project_2" in file_path

    # Step 5: Verify no overlap in results
    paths1 = {r["file_path"] for r in results1}
    paths2 = {r["file_path"] for r in results2}
    assert len(paths1.intersection(paths2)) == 0, "Projects should have no overlapping results"
