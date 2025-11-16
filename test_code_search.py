#!/usr/bin/env python3
"""Test code search functionality end-to-end."""

import asyncio
import logging
from pathlib import Path

from src.core.server import MemoryRAGServer
from src.config import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_code_search():
    """Test code search end-to-end."""

    # Initialize server
    config = get_config()
    server = MemoryRAGServer(config)
    await server.initialize()

    try:
        # Test 1: Index the src/core directory
        logger.info("=" * 60)
        logger.info("TEST 1: Indexing codebase")
        logger.info("=" * 60)

        src_dir = Path(__file__).parent / "src" / "core"

        index_result = await server.index_codebase(
            directory_path=str(src_dir),
            project_name="claude-memory-server",
            recursive=False,
        )

        logger.info(f"✅ Indexing complete:")
        logger.info(f"  - Files indexed: {index_result['files_indexed']}")
        logger.info(f"  - Units indexed: {index_result['units_indexed']}")
        logger.info(f"  - Time: {index_result['total_time_s']:.2f}s")
        logger.info("")

        # Test 2: Search for memory-related code
        logger.info("=" * 60)
        logger.info("TEST 2: Searching for 'memory storage and retrieval'")
        logger.info("=" * 60)

        search_result = await server.search_code(
            query="memory storage and retrieval",
            project_name="claude-memory-server",
            limit=3,
        )

        logger.info(f"✅ Search complete:")
        logger.info(f"  - Results found: {search_result['total_found']}")
        logger.info(f"  - Query time: {search_result['query_time_ms']:.2f}ms")
        logger.info("")

        for i, result in enumerate(search_result['results'], 1):
            logger.info(f"Result {i}:")
            logger.info(f"  Name: {result['unit_name']}")
            logger.info(f"  Type: {result['unit_type']}")
            logger.info(f"  File: {result['file_path']}:{result['start_line']}-{result['end_line']}")
            logger.info(f"  Language: {result['language']}")
            logger.info(f"  Relevance: {result['relevance_score']:.2%}")
            logger.info("")

        # Test 3: Search for server initialization code
        logger.info("=" * 60)
        logger.info("TEST 3: Searching for 'server initialization'")
        logger.info("=" * 60)

        search_result2 = await server.search_code(
            query="server initialization and setup",
            project_name="claude-memory-server",
            limit=3,
        )

        logger.info(f"✅ Search complete:")
        logger.info(f"  - Results found: {search_result2['total_found']}")
        logger.info(f"  - Query time: {search_result2['query_time_ms']:.2f}ms")
        logger.info("")

        for i, result in enumerate(search_result2['results'], 1):
            logger.info(f"Result {i}:")
            logger.info(f"  Name: {result['unit_name']}")
            logger.info(f"  Type: {result['unit_type']}")
            logger.info(f"  File: {Path(result['file_path']).name}:{result['start_line']}")
            logger.info(f"  Relevance: {result['relevance_score']:.2%}")
            logger.info("")

        # Test 4: Search with language filter
        logger.info("=" * 60)
        logger.info("TEST 4: Searching with Python language filter")
        logger.info("=" * 60)

        search_result3 = await server.search_code(
            query="embedding generation",
            project_name="claude-memory-server",
            language="python",
            limit=2,
        )

        logger.info(f"✅ Search complete:")
        logger.info(f"  - Results found: {search_result3['total_found']}")
        logger.info("")

        logger.info("=" * 60)
        logger.info("ALL TESTS PASSED! ✅")
        logger.info("=" * 60)

    finally:
        await server.close()


if __name__ == "__main__":
    asyncio.run(test_code_search())
