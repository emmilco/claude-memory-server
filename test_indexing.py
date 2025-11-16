#!/usr/bin/env python3
"""Quick test script for incremental indexing."""

import asyncio
import logging
from pathlib import Path

from src.memory.incremental_indexer import IncrementalIndexer
from src.store.qdrant_store import QdrantMemoryStore
from src.embeddings.generator import EmbeddingGenerator
from src.config import ServerConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def main():
    """Test indexing on a small directory."""
    # Use a small test directory
    test_dir = Path("src/core")  # Index the src/core directory

    print(f"\nIndexing directory: {test_dir}")
    print("=" * 60)

    # Create config with test collection
    config = ServerConfig(
        qdrant_collection_name="test_code_index",
        embedding_model="all-MiniLM-L6-v2",
    )

    # Create components
    store = QdrantMemoryStore(config)
    embedding_gen = EmbeddingGenerator(config)

    indexer = IncrementalIndexer(
        store=store,
        embedding_generator=embedding_gen,
        config=config,
        project_name="claude-memory-test",
    )

    try:
        # Initialize
        await indexer.initialize()

        # Index directory
        result = await indexer.index_directory(
            test_dir,
            recursive=True,
            show_progress=True,
        )

        print("\n" + "=" * 60)
        print("INDEXING RESULTS")
        print("=" * 60)
        print(f"Total files found: {result['total_files']}")
        print(f"Files indexed: {result['indexed_files']}")
        print(f"Files skipped: {result['skipped_files']}")
        print(f"Total semantic units: {result['total_units']}")

        if result['failed_files']:
            print(f"\nFailed files: {result['failed_files']}")

        print("=" * 60)

        # Test semantic search
        print("\n" + "=" * 60)
        print("TESTING SEMANTIC SEARCH")
        print("=" * 60)

        query = "memory storage and retrieval"
        print(f"\nQuery: '{query}'")

        query_embedding = await embedding_gen.generate(query)
        from src.core.models import SearchFilters, MemoryScope

        filters = SearchFilters(
            scope=MemoryScope.PROJECT,
            project_name="claude-memory-test",
        )

        results = await store.retrieve(
            query_embedding=query_embedding,
            filters=filters,
            limit=5,
        )

        print(f"\nFound {len(results)} relevant code units:\n")

        for i, (memory, score) in enumerate(results, 1):
            # Access nested metadata
            meta = memory.metadata if hasattr(memory, 'metadata') else {}
            unit_name = meta.get('unit_name', 'unknown')
            unit_type = meta.get('unit_type', 'unknown')
            file_path = meta.get('file_path', 'unknown')
            start_line = meta.get('start_line', 0)

            print(f"{i}. {unit_name} ({unit_type})")
            print(f"   File: {Path(file_path).name}:{start_line}")
            print(f"   Score: {score:.4f}")
            print(f"   Preview: {memory.content[:100]}...")
            print()

        print("=" * 60)

    finally:
        # Cleanup
        await indexer.close()

        # Delete test collection
        if store.client:
            try:
                store.client.delete_collection(config.qdrant_collection_name)
                print("\nTest collection cleaned up.")
            except:
                pass


if __name__ == "__main__":
    asyncio.run(main())
