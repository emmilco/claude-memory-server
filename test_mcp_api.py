#!/usr/bin/env python3
"""
Comprehensive MCP API test script.

Tests all MCP tools end-to-end without requiring Claude Code.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.server import MemoryRAGServer
from src.config import get_config


async def test_memory_lifecycle():
    """Test complete memory lifecycle: store, retrieve, list, delete."""
    print("\n" + "="*60)
    print("TEST: Memory Lifecycle")
    print("="*60)

    config = get_config()
    server = MemoryRAGServer(config)
    await server.initialize()

    test_results = []

    # Test 1: Store a preference memory
    print("\n1. Storing preference memory...")
    try:
        result = await server.store_memory(
            content="I prefer Python for backend development",
            category="preference",
            importance=0.8,
            tags=["python", "backend"]
        )
        memory_id = result.get("memory_id")
        print(f"   ✓ Stored memory ID: {memory_id}")
        test_results.append(("Store Memory", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        test_results.append(("Store Memory", False, str(e)))
        return test_results

    # Test 2: Retrieve the memory
    print("\n2. Retrieving memory with semantic search...")
    try:
        results = await server.retrieve_memories(
            query="What programming language does the user prefer?",
            limit=5
        )
        found = any("python" in r.get("content", "").lower() for r in results.get("memories", []))
        if found:
            print(f"   ✓ Found memory in {len(results.get('memories', []))} results")
        else:
            print(f"   ⚠ Memory not found in semantic search results")
        test_results.append(("Retrieve Memory", found, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        test_results.append(("Retrieve Memory", False, str(e)))

    # Test 3: List memories by category
    print("\n3. Listing memories by category...")
    try:
        results = await server.list_memories(
            category="preference",
            limit=10
        )
        count = results.get("total", 0)
        print(f"   ✓ Found {count} preference memories")
        test_results.append(("List Memories", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        test_results.append(("List Memories", False, str(e)))

    # Test 4: Delete the memory
    print("\n4. Deleting memory...")
    try:
        result = await server.delete_memory(memory_id=memory_id)
        if result.get("success"):
            print(f"   ✓ Deleted memory {memory_id}")
            test_results.append(("Delete Memory", True, None))
        else:
            print(f"   ⚠ Delete returned success=False")
            test_results.append(("Delete Memory", False, "success=False"))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        test_results.append(("Delete Memory", False, str(e)))

    return test_results


async def test_code_search():
    """Test code indexing and search."""
    print("\n" + "="*60)
    print("TEST: Code Search")
    print("="*60)

    config = get_config()
    server = MemoryRAGServer(config)
    await server.initialize()

    test_results = []

    # Test 1: Index the src directory
    print("\n1. Indexing codebase...")
    try:
        result = await server.index_codebase(
            path=str(project_root / "src" / "core"),
            project_name="test-project"
        )
        files_indexed = result.get("files_indexed", 0)
        units_indexed = result.get("semantic_units", 0)
        print(f"   ✓ Indexed {files_indexed} files, {units_indexed} semantic units")
        test_results.append(("Index Codebase", files_indexed > 0, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        test_results.append(("Index Codebase", False, str(e)))
        return test_results

    # Test 2: Search for code
    print("\n2. Searching code...")
    try:
        results = await server.search_code(
            query="memory storage",
            project_name="test-project",
            limit=5
        )
        found = results.get("results", [])
        print(f"   ✓ Found {len(found)} code results")
        for i, r in enumerate(found[:3], 1):
            print(f"      {i}. {r.get('file_path', 'unknown')}:{r.get('start_line', 0)}")
        test_results.append(("Search Code", len(found) > 0, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        test_results.append(("Search Code", False, str(e)))

    return test_results


async def test_multi_project():
    """Test multi-project support."""
    print("\n" + "="*60)
    print("TEST: Multi-Project Support")
    print("="*60)

    config = get_config()
    server = MemoryRAGServer(config)
    await server.initialize()

    test_results = []

    # Test 1: Search across all projects
    print("\n1. Searching across all projects...")
    try:
        results = await server.search_all_projects(
            query="server initialization",
            limit=10
        )
        project_count = len(results.get("projects", {}))
        print(f"   ✓ Searched {project_count} projects")
        test_results.append(("Search All Projects", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        test_results.append(("Search All Projects", False, str(e)))

    # Test 2: Opt in/out of cross-project search
    print("\n2. Testing opt-in/opt-out...")
    try:
        # Opt out
        result = await server.opt_out_project("test-project")
        if result.get("success"):
            print(f"   ✓ Opted out test-project")

        # Opt in
        result = await server.opt_in_project("test-project")
        if result.get("success"):
            print(f"   ✓ Opted in test-project")

        test_results.append(("Opt In/Out", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        test_results.append(("Opt In/Out", False, str(e)))

    return test_results


async def test_health_monitoring():
    """Test health monitoring features."""
    print("\n" + "="*60)
    print("TEST: Health Monitoring")
    print("="*60)

    config = get_config()
    server = MemoryRAGServer(config)
    await server.initialize()

    test_results = []

    # Test 1: Get health score
    print("\n1. Getting health score...")
    try:
        result = await server.get_health_score()
        score = result.get("overall_score", 0)
        print(f"   ✓ Health score: {score:.2f}")
        test_results.append(("Health Score", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        test_results.append(("Health Score", False, str(e)))

    # Test 2: Get active alerts
    print("\n2. Getting active alerts...")
    try:
        result = await server.get_active_alerts()
        count = result.get("count", 0)
        print(f"   ✓ Active alerts: {count}")
        test_results.append(("Active Alerts", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        test_results.append(("Active Alerts", False, str(e)))

    # Test 3: Get performance metrics
    print("\n3. Getting performance metrics...")
    try:
        result = await server.get_performance_metrics()
        avg_latency = result.get("avg_latency_ms", 0)
        print(f"   ✓ Avg latency: {avg_latency:.2f}ms")
        test_results.append(("Performance Metrics", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        test_results.append(("Performance Metrics", False, str(e)))

    return test_results


async def test_statistics():
    """Test statistics and status tools."""
    print("\n" + "="*60)
    print("TEST: Statistics")
    print("="*60)

    config = get_config()
    server = MemoryRAGServer(config)
    await server.initialize()

    test_results = []

    # Test 1: Get statistics
    print("\n1. Getting statistics...")
    try:
        result = await server.get_stats()
        memories = result.get("memories", {})
        code = result.get("code", {})
        print(f"   ✓ Memories: {memories.get('total', 0)}")
        print(f"   ✓ Code units: {code.get('total_units', 0)}")
        test_results.append(("Statistics", True, None))
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        test_results.append(("Statistics", False, str(e)))

    return test_results


def print_summary(all_results):
    """Print test summary."""
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    total = sum(len(results) for results in all_results.values())
    passed = sum(
        sum(1 for _, success, _ in results if success)
        for results in all_results.values()
    )
    failed = total - passed

    print(f"\nTotal tests: {total}")
    print(f"Passed: {passed} ({passed/total*100:.1f}%)")
    print(f"Failed: {failed}")

    if failed > 0:
        print("\n❌ FAILED TESTS:")
        for category, results in all_results.items():
            for name, success, error in results:
                if not success:
                    print(f"   • {category}: {name}")
                    if error:
                        print(f"      Error: {error}")

    print("\n" + "="*60)
    return failed == 0


async def main():
    """Run all tests."""
    print("\n🧪 Claude Memory RAG Server - Comprehensive API Test")
    print("=" * 60)

    all_results = {}

    # Run all test suites
    try:
        all_results["Memory Lifecycle"] = await test_memory_lifecycle()
    except Exception as e:
        print(f"\n❌ Memory Lifecycle test suite failed: {e}")
        all_results["Memory Lifecycle"] = []

    try:
        all_results["Code Search"] = await test_code_search()
    except Exception as e:
        print(f"\n❌ Code Search test suite failed: {e}")
        all_results["Code Search"] = []

    try:
        all_results["Multi-Project"] = await test_multi_project()
    except Exception as e:
        print(f"\n❌ Multi-Project test suite failed: {e}")
        all_results["Multi-Project"] = []

    try:
        all_results["Health Monitoring"] = await test_health_monitoring()
    except Exception as e:
        print(f"\n❌ Health Monitoring test suite failed: {e}")
        all_results["Health Monitoring"] = []

    try:
        all_results["Statistics"] = await test_statistics()
    except Exception as e:
        print(f"\n❌ Statistics test suite failed: {e}")
        all_results["Statistics"] = []

    # Print summary
    success = print_summary(all_results)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
