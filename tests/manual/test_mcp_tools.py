#!/usr/bin/env python3
"""Test script for MCP tools."""

import asyncio
import pytest
from src.core.server import MemoryRAGServer
from src.config import get_config

@pytest.mark.asyncio
async def test_code_search():
    """Test code search functionality."""
    config = get_config()
    server = MemoryRAGServer(config=config)
    await server.initialize()

    print("=" * 80)
    print("Testing Code Search")
    print("=" * 80)

    # Test semantic search
    print("\n1. SEMANTIC SEARCH: Finding 'embedding generation'")
    results = await server.code_search(
        query="embedding generation",
        project_name="claude-memory-server",
        mode="semantic",
        limit=5
    )
    print(f"Found {len(results.get('results', []))} results")
    for i, result in enumerate(results.get('results', [])[:3], 1):
        print(f"\n  Result {i}:")
        print(f"    File: {result.get('file_path', 'N/A')}")
        print(f"    Score: {result.get('score', 0):.3f}")
        print(f"    Type: {result.get('unit_type', 'N/A')}")
        print(f"    Name: {result.get('unit_name', 'N/A')}")

    # Test keyword search
    print("\n\n2. KEYWORD SEARCH: Finding 'MemoryCategory'")
    results = await server.code_search(
        query="MemoryCategory",
        project_name="claude-memory-server",
        mode="keyword",
        limit=5
    )
    print(f"Found {len(results.get('results', []))} results")
    for i, result in enumerate(results.get('results', [])[:3], 1):
        print(f"\n  Result {i}:")
        print(f"    File: {result.get('file_path', 'N/A')}")
        print(f"    Unit: {result.get('unit_name', 'N/A')}")

    # Test hybrid search
    print("\n\n3. HYBRID SEARCH: Finding 'parallel embedding'")
    results = await server.code_search(
        query="parallel embedding",
        project_name="claude-memory-server",
        mode="hybrid",
        limit=5
    )
    print(f"Found {len(results.get('results', []))} results")
    for i, result in enumerate(results.get('results', [])[:3], 1):
        print(f"\n  Result {i}:")
        print(f"    File: {result.get('file_path', 'N/A')}")
        print(f"    Score: {result.get('score', 0):.3f}")

    print("\n" + "=" * 80)

@pytest.mark.asyncio
async def test_memory_tools():
    """Test memory management tools."""
    config = get_config()
    server = MemoryRAGServer(config=config)
    await server.initialize()

    print("=" * 80)
    print("Testing Memory Tools")
    print("=" * 80)

    # Test store_memory
    print("\n1. STORE MEMORY")
    memory_id = await server.store_memory(
        content="Testing memory storage functionality",
        category="fact",
        importance=0.8,
        tags=["test", "mcp"]
    )
    print(f"Stored memory with ID: {memory_id}")

    # Test search_memories
    print("\n2. SEARCH MEMORIES")
    results = await server.search_memories(
        query="testing memory",
        limit=5
    )
    print(f"Found {len(results)} memories")
    for i, memory in enumerate(results[:3], 1):
        print(f"\n  Memory {i}:")
        print(f"    Content: {memory.get('content', 'N/A')[:60]}...")
        print(f"    Category: {memory.get('category', 'N/A')}")
        print(f"    Score: {memory.get('score', 0):.3f}")

    # Test get_memory_stats
    print("\n3. MEMORY STATS")
    stats = await server.get_memory_stats()
    print(f"  Total memories: {stats.get('total_memories', 0)}")
    print(f"  Categories: {stats.get('categories', {})}")
    print(f"  Lifecycle states: {stats.get('lifecycle_states', {})}")

    print("\n" + "=" * 80)

@pytest.mark.asyncio
async def test_project_tools():
    """Test project management tools."""
    config = get_config()
    server = MemoryRAGServer(config=config)
    await server.initialize()

    print("=" * 80)
    print("Testing Project Tools")
    print("=" * 80)

    # Test list_projects
    print("\n1. LIST PROJECTS")
    projects = await server.list_projects()
    print(f"Found {len(projects)} projects:")
    for project in projects:
        print(f"\n  Project: {project.get('name', 'N/A')}")
        print(f"    Files: {project.get('file_count', 0)}")
        print(f"    Units: {project.get('unit_count', 0)}")
        print(f"    Path: {project.get('path', 'N/A')}")

    # Test get_indexed_projects
    print("\n2. GET INDEXED PROJECTS DETAILS")
    result = await server.get_indexed_projects()
    print(f"  Total projects: {result.get('total_projects', 0)}")
    print(f"  Total files: {result.get('total_files', 0)}")
    print(f"  Total units: {result.get('total_units', 0)}")

    print("\n" + "=" * 80)

async def main():
    """Run all tests."""
    try:
        await test_code_search()
        await test_memory_tools()
        await test_project_tools()
        print("\n✅ All MCP tool tests completed successfully!")
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
