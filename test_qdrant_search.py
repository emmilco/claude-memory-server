#!/usr/bin/env python3
"""Test semantic search with Qdrant backend."""
import os
# Set environment variables BEFORE any imports
os.environ['CLAUDE_RAG_STORAGE_BACKEND'] = 'qdrant'
os.environ['CLAUDE_RAG_ALLOW_QDRANT_FALLBACK'] = 'false'

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.core.server import MemoryRAGServer
from src.config import get_config

async def test_search(server, query, description):
    """Test a search query."""
    print(f"\n{'='*70}")
    print(f"Query: {query}")
    print(f"Question: {description}")
    print('='*70)

    start = time.time()
    result = await server.search_code(
        query=query,
        project_name="claude-memory-server",
        limit=5
    )
    elapsed = time.time() - start

    print(f"⏱️  Time: {elapsed:.3f}s")
    print(f"📊 Found: {result['total_found']} results")
    print(f"✨ Quality: {result.get('quality', 'N/A')}")
    print(f"🎯 Search mode: {result.get('search_mode', 'N/A')}")

    if result['results']:
        print(f"\n🔍 Top results:")
        for i, r in enumerate(result['results'][:5], 1):
            file_name = r['file_path'].split('/')[-1]
            print(f"  {i}. [{r['relevance_score']:.2%}] {r['unit_name']} ({r['unit_type']})")
            print(f"     📄 {file_name}:{r['start_line']}")
            if i <= 2:  # Show snippet for top 2
                code_preview = r['code'][:150].replace('\n', ' ')
                print(f"     💬 {code_preview}...")
    else:
        print(f"\n❌ No results")
        print(f"💡 Suggestions: {result.get('suggestions', [])}")

    return result

async def main():
    config = get_config()
    server = MemoryRAGServer(config=config)
    await server.initialize()

    print("=" * 70)
    print("🚀 QDRANT SEMANTIC SEARCH EVALUATION")
    print("=" * 70)
    print(f"Backend: {server.store.__class__.__name__}")

    # Test queries
    queries = [
        ("parallel embedding generation", "How does parallel embedding work?"),
        ("duplicate detection find duplicates", "Where is duplicate detection implemented?"),
        ("incremental cache", "How does caching work?"),
        ("MCP tool registration", "Where are MCP tools registered?"),
        ("file watching implementation", "How does file watching work?"),
    ]

    results = []
    for query, desc in queries:
        result = await test_search(server, query, desc)
        results.append((desc, result))

    # Summary
    print(f"\n{'='*70}")
    print("📈 SUMMARY")
    print('='*70)

    total_found = sum(r['total_found'] for _, r in results)
    avg_found = total_found / len(results)
    success_rate = sum(1 for _, r in results if r['total_found'] > 0) / len(results) * 100

    # Check if scores are diverse (not all 0.70)
    all_scores = []
    for _, r in results:
        if r['results']:
            all_scores.extend([res['relevance_score'] for res in r['results']])

    unique_scores = len(set(all_scores))
    scores_diverse = unique_scores > 2  # More than just 0.70

    print(f"Questions tested: {len(results)}")
    print(f"Success rate: {success_rate:.0f}%")
    print(f"Avg results per query: {avg_found:.1f}")
    print(f"Unique relevance scores: {unique_scores}")
    print(f"Semantic search working: {'✅ YES' if scores_diverse else '❌ NO (all scores same)'}")

    if all_scores:
        print(f"Score range: {min(all_scores):.2%} - {max(all_scores):.2%}")

    await server.close()

if __name__ == "__main__":
    asyncio.run(main())
