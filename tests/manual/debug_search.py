#!/usr/bin/env python3
"""Debug search_code to understand why it returns empty results."""

import asyncio
import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.core.server import MemoryRAGServer
from src.config import get_config


async def main():
    config = get_config()
    server = MemoryRAGServer(config=config)
    await server.initialize()

    # Try search_code
    print("Testing search_code...")
    result = await server.search_code(
        query="duplicate detector find duplicates",
        project_name="claude-memory-server",
        limit=5,
    )

    print(f"\nStatus: {result['status']}")
    print(f"Total found: {result['total_found']}")
    print(f"Results count: {len(result['results'])}")

    if result["results"]:
        print("\nFirst result:")
        print(result["results"][0])
    else:
        print("\nNo results returned")
        print(f"Quality: {result.get('quality')}")
        print(f"Suggestions: {result.get('suggestions')}")

    # Also try direct retrieve to compare
    print("\n" + "=" * 50)
    print("Testing direct store.retrieve...")

    from src.core.models import SearchFilters, MemoryScope, MemoryCategory, ContextLevel

    query_embedding = await server._get_embedding("duplicate detector find duplicates")
    filters = SearchFilters(
        scope=MemoryScope.PROJECT,
        project_name="claude-memory-server",
        category=MemoryCategory.CONTEXT,
        context_level=ContextLevel.PROJECT_CONTEXT,
        tags=["code"],
    )

    raw_results = await server.store.retrieve(
        query_embedding=query_embedding,
        filters=filters,
        limit=5,
    )

    print(f"\nRaw results count: {len(raw_results)}")
    for i, (memory, score) in enumerate(raw_results[:3], 1):
        print(f"\n{i}. Score: {score:.4f}")
        print(f"   Content preview: {memory.content[:100]}...")
        print(f"   Metadata: {memory.metadata}")

    await server.close()


if __name__ == "__main__":
    asyncio.run(main())
