#!/usr/bin/env python3
"""Comprehensive end-to-end testing of all MCP server features."""

import asyncio
import time
from pathlib import Path
from src.core.server import MemoryRAGServer
from src.config import get_config


class FeatureTester:
    def __init__(self):
        self.config = get_config()
        self.server = None
        self.test_results = []

    async def initialize(self):
        """Initialize the server."""
        print("=" * 80)
        print("INITIALIZING MCP SERVER")
        print("=" * 80)
        self.server = MemoryRAGServer(config=self.config)
        await self.server.initialize()
        print("✅ Server initialized successfully\n")

    def log_result(self, test_name: str, status: str, details: str = ""):
        """Log test result."""
        self.test_results.append(
            {"test": test_name, "status": status, "details": details}
        )
        symbol = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{symbol} {test_name}: {status}")
        if details:
            print(f"   {details}")

    async def test_code_search(self):
        """Test code search with all modes."""
        print("\n" + "=" * 80)
        print("TEST 1: CODE SEARCH (Semantic, Keyword, Hybrid)")
        print("=" * 80)

        try:
            # Test semantic search
            print("\n1a. Semantic Search: 'parallel embedding generation'")
            start = time.time()
            results = await self.server.search_code(
                query="parallel embedding generation",
                project_name="claude-memory-server",
                mode="semantic",
                limit=5,
            )
            latency = (time.time() - start) * 1000

            if results and len(results.get("results", [])) > 0:
                self.log_result(
                    "Semantic Search",
                    "PASS",
                    f"Found {len(results['results'])} results in {latency:.1f}ms",
                )
                for i, r in enumerate(results["results"][:2], 1):
                    print(
                        f"   Result {i}: {r.get('file_path', 'N/A')} - {r.get('unit_name', 'N/A')} (score: {r.get('score', 0):.3f})"
                    )
            else:
                self.log_result("Semantic Search", "FAIL", "No results returned")

            # Test keyword search
            print("\n1b. Keyword Search: 'MemoryCategory'")
            start = time.time()
            results = await self.server.search_code(
                query="MemoryCategory",
                project_name="claude-memory-server",
                mode="keyword",
                limit=5,
            )
            latency = (time.time() - start) * 1000

            if results and len(results.get("results", [])) > 0:
                self.log_result(
                    "Keyword Search",
                    "PASS",
                    f"Found {len(results['results'])} results in {latency:.1f}ms",
                )
            else:
                self.log_result("Keyword Search", "FAIL", "No results returned")

            # Test hybrid search
            print("\n1c. Hybrid Search: 'indexing code files'")
            start = time.time()
            results = await self.server.search_code(
                query="indexing code files",
                project_name="claude-memory-server",
                mode="hybrid",
                limit=5,
            )
            latency = (time.time() - start) * 1000

            if results and len(results.get("results", [])) > 0:
                self.log_result(
                    "Hybrid Search",
                    "PASS",
                    f"Found {len(results['results'])} results in {latency:.1f}ms",
                )
            else:
                self.log_result("Hybrid Search", "FAIL", "No results returned")

        except Exception as e:
            self.log_result("Code Search", "FAIL", f"Error: {e}")

    async def test_memory_management(self):
        """Test memory storage and retrieval."""
        print("\n" + "=" * 80)
        print("TEST 2: MEMORY MANAGEMENT")
        print("=" * 80)

        try:
            # Store a memory
            print("\n2a. Store Memory")
            memory_result = await self.server.store_memory(
                content="This is a test memory for E2E testing",
                category="fact",
                importance=0.8,
                tags=["test", "e2e", "automated"],
            )

            if memory_result and memory_result.get("id"):
                memory_id = memory_result["id"]
                self.log_result(
                    "Store Memory",
                    "PASS",
                    f"Memory stored with ID: {memory_id[:16]}...",
                )

                # Retrieve memories
                print("\n2b. Retrieve Memories")
                results = await self.server.retrieve_memories(
                    query="test memory", limit=5
                )

                if results and len(results) > 0:
                    self.log_result(
                        "Retrieve Memories", "PASS", f"Found {len(results)} memories"
                    )
                else:
                    self.log_result("Retrieve Memories", "FAIL", "No memories found")

                # List all memories
                print("\n2c. List Memories")
                list_result = await self.server.list_memories(limit=10, offset=0)

                if list_result:
                    total = list_result.get("total", 0)
                    returned = len(list_result.get("memories", []))
                    self.log_result(
                        "List Memories", "PASS", f"Total: {total}, Returned: {returned}"
                    )
                else:
                    self.log_result("List Memories", "FAIL", "No result")

            else:
                self.log_result("Store Memory", "FAIL", "Failed to store memory")

        except Exception as e:
            self.log_result("Memory Management", "FAIL", f"Error: {e}")

    async def test_project_management(self):
        """Test project management tools."""
        print("\n" + "=" * 80)
        print("TEST 3: PROJECT MANAGEMENT")
        print("=" * 80)

        try:
            # Get status
            print("\n3a. Get Status")
            status = await self.server.get_status()

            if status:
                self.log_result(
                    "Get Status",
                    "PASS",
                    f"Projects: {status.get('total_projects', 0)}, Files: {status.get('total_indexed_files', 0)}",
                )
                print(f"   Backend: {status.get('storage_backend', 'N/A')}")
                print(f"   Total units: {status.get('total_indexed_units', 0)}")
            else:
                self.log_result("Get Status", "FAIL", "No status returned")

            # Get indexed files
            print("\n3b. Get Indexed Files")
            files_result = await self.server.get_indexed_files(
                project_name="claude-memory-server", limit=5
            )

            if files_result and files_result.get("files"):
                self.log_result(
                    "Get Indexed Files",
                    "PASS",
                    f"Found {len(files_result['files'])} files",
                )
                for f in files_result["files"][:2]:
                    print(
                        f"   {f.get('file_path', 'N/A')} - {f.get('unit_count', 0)} units"
                    )
            else:
                self.log_result("Get Indexed Files", "FAIL", "No files returned")

            # List indexed units
            print("\n3c. List Indexed Units")
            units_result = await self.server.list_indexed_units(
                project_name="claude-memory-server", limit=5, unit_type="function"
            )

            if units_result and units_result.get("units"):
                self.log_result(
                    "List Indexed Units",
                    "PASS",
                    f"Found {len(units_result['units'])} functions",
                )
                for u in units_result["units"][:2]:
                    print(
                        f"   {u.get('unit_name', 'N/A')} in {u.get('file_path', 'N/A')}"
                    )
            else:
                self.log_result("List Indexed Units", "FAIL", "No units returned")

        except Exception as e:
            self.log_result("Project Management", "FAIL", f"Error: {e}")

    async def test_cross_project_search(self):
        """Test cross-project search."""
        print("\n" + "=" * 80)
        print("TEST 4: CROSS-PROJECT SEARCH")
        print("=" * 80)

        try:
            # Opt in projects for cross-project search
            print("\n4a. Opt-in Projects")
            await self.server.opt_in_cross_project("claude-memory-server")
            await self.server.opt_in_cross_project("agentic-sdlc")
            self.log_result("Opt-in Projects", "PASS", "Both projects opted in")

            # List opted-in projects
            print("\n4b. List Opted-in Projects")
            opted_result = await self.server.list_opted_in_projects()

            if opted_result and opted_result.get("projects"):
                self.log_result(
                    "List Opted-in Projects",
                    "PASS",
                    f"Found {len(opted_result['projects'])} opted-in projects",
                )
            else:
                self.log_result("List Opted-in Projects", "FAIL", "No projects")

            # Search across all projects
            print("\n4c. Search All Projects")
            results = await self.server.search_all_projects(
                query="async function", limit=5
            )

            if results and results.get("results"):
                self.log_result(
                    "Search All Projects",
                    "PASS",
                    f"Found {len(results['results'])} results across projects",
                )
                for r in results["results"][:2]:
                    print(
                        f"   {r.get('project_name', 'N/A')}: {r.get('unit_name', 'N/A')}"
                    )
            else:
                self.log_result("Search All Projects", "FAIL", "No results")

        except Exception as e:
            self.log_result("Cross-Project Search", "FAIL", f"Error: {e}")

    async def test_dependency_analysis(self):
        """Test dependency analysis tools."""
        print("\n" + "=" * 80)
        print("TEST 5: DEPENDENCY ANALYSIS")
        print("=" * 80)

        try:
            # Get file dependencies
            print("\n5a. Get File Dependencies")
            deps = await self.server.get_file_dependencies(
                project_name="claude-memory-server", file_path="src/core/server.py"
            )

            if deps and deps.get("dependencies"):
                self.log_result(
                    "Get File Dependencies",
                    "PASS",
                    f"Found {len(deps['dependencies'])} dependencies",
                )
                for d in deps["dependencies"][:3]:
                    print(f"   {d}")
            else:
                self.log_result("Get File Dependencies", "FAIL", "No dependencies")

            # Get dependency stats
            print("\n5b. Get Dependency Stats")
            stats = await self.server.get_dependency_stats(
                project_name="claude-memory-server"
            )

            if stats:
                self.log_result(
                    "Get Dependency Stats",
                    "PASS",
                    f"Total files: {stats.get('total_files', 0)}",
                )
                print(f"   Most imported: {stats.get('most_imported_file', 'N/A')}")
            else:
                self.log_result("Get Dependency Stats", "FAIL", "No stats")

        except Exception as e:
            self.log_result("Dependency Analysis", "FAIL", f"Error: {e}")

    async def test_performance(self):
        """Test search performance."""
        print("\n" + "=" * 80)
        print("TEST 6: PERFORMANCE METRICS")
        print("=" * 80)

        try:
            # Run 10 searches and measure latency
            print("\n6a. Search Latency Test (10 searches)")
            latencies = []

            for i in range(10):
                start = time.time()
                await self.server.search_code(
                    query="function test",
                    project_name="claude-memory-server",
                    mode="semantic",
                    limit=5,
                )
                latency = (time.time() - start) * 1000
                latencies.append(latency)

            avg_latency = sum(latencies) / len(latencies)
            p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

            self.log_result(
                "Search Latency",
                "PASS" if avg_latency < 100 else "WARN",
                f"Avg: {avg_latency:.1f}ms, P95: {p95_latency:.1f}ms",
            )

        except Exception as e:
            self.log_result("Performance Test", "FAIL", f"Error: {e}")

    async def test_re_indexing(self):
        """Test re-indexing functionality."""
        print("\n" + "=" * 80)
        print("TEST 7: RE-INDEXING")
        print("=" * 80)

        try:
            print("\n7a. Re-index Project")
            # Create a small test directory to re-index
            test_dir = Path("./src/core")

            result = await self.server.index_codebase(
                directory=str(test_dir), project_name="test-reindex", recursive=False
            )

            if result:
                self.log_result(
                    "Re-index Project",
                    "PASS",
                    f"Indexed {result.get('files_indexed', 0)} files",
                )
            else:
                self.log_result("Re-index Project", "FAIL", "No result")

        except Exception as e:
            self.log_result("Re-indexing", "FAIL", f"Error: {e}")

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)

        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["status"] == "PASS")
        failed = sum(1 for r in self.test_results if r["status"] == "FAIL")
        warned = sum(1 for r in self.test_results if r["status"] == "WARN")

        print(f"\nTotal Tests: {total}")
        print(f"✅ Passed: {passed} ({passed/total*100:.1f}%)")
        print(f"❌ Failed: {failed} ({failed/total*100:.1f}%)")
        print(f"⚠️  Warnings: {warned} ({warned/total*100:.1f}%)")

        if failed > 0:
            print("\nFailed Tests:")
            for r in self.test_results:
                if r["status"] == "FAIL":
                    print(f"  ❌ {r['test']}: {r['details']}")

        print("\n" + "=" * 80)


async def main():
    """Run all tests."""
    tester = FeatureTester()

    try:
        await tester.initialize()
        await tester.test_code_search()
        await tester.test_memory_management()
        await tester.test_project_management()
        await tester.test_cross_project_search()
        await tester.test_dependency_analysis()
        await tester.test_performance()
        await tester.test_re_indexing()

        tester.print_summary()

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
