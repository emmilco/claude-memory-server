#!/usr/bin/env python3
"""Quick evaluation test with fixed code."""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.server import MemoryRAGServer
from src.config import get_config

async def test_question(server, query, description):
    """Test a single question."""
    print(f"\n{'='*60}")
    print(f"Q: {description}")
    print(f"Query: {query}")
    print('='*60)

    start = time.time()
    result = await server.search_code(
        query=query,
        project_name="claude-memory-server",
        limit=5,
        search_mode="semantic"
    )
    elapsed = time.time() - start

    print(f"Time: {elapsed:.2f}s")
    print(f"Found: {result['total_found']} results")
    print(f"Quality: {result.get('quality', 'N/A')}")

    if result['results']:
        print("\nTop 3 results:")
        for i, r in enumerate(result['results'][:3], 1):
            print(f"{i}. {r['unit_name']} ({r['unit_type']}) - {r['file_path']}:{r['start_line']}")
            print(f"   Relevance: {r['relevance_score']:.0%}")
    else:
        print("No results found")
        print(f"Suggestions: {result.get('suggestions', [])}")

    return result

async def main():
    config = get_config()
    server = MemoryRAGServer(config=config)
    await server.initialize()

    # Test questions
    questions = [
        ("parallel embedding multiprocess", "How does parallel embedding work?"),
        ("incremental cache", "How does incremental caching work?"),
        ("file watcher watch changes", "Where is file watching implemented?"),
        ("MCP tool registration", "Where are MCP tools registered?"),
        ("duplicate detection", "Where is duplicate detection?"),
    ]

    results = []
    for query, desc in questions:
        result = await test_question(server, query, desc)
        results.append((desc, result))

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    total_found = sum(r['total_found'] for _, r in results)
    avg_results = total_found / len(results)
    success_rate = sum(1 for _, r in results if r['total_found'] > 0) / len(results) * 100

    print(f"Questions tested: {len(results)}")
    print(f"Success rate: {success_rate:.0f}%")
    print(f"Avg results per query: {avg_results:.1f}")

    await server.close()

if __name__ == "__main__":
    asyncio.run(main())
