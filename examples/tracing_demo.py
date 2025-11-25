#!/usr/bin/env python3
"""
Demonstration of distributed tracing functionality.

This script shows how operation IDs are automatically generated and propagated
through async function calls, making it easy to trace requests through the system.

Run with: python examples/tracing_demo.py
"""

import asyncio
import logging
from src.core.tracing import new_operation, get_operation_id, get_logger, traced

# Configure logging to show operation IDs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create context-aware loggers for different modules
server_logger = get_logger("server")
db_logger = get_logger("database")
cache_logger = get_logger("cache")


async def simulate_database_query(query: str):
    """Simulate a database query - operation ID propagates automatically."""
    db_logger.info(f"Executing query: {query}")
    await asyncio.sleep(0.1)  # Simulate query time
    db_logger.info("Query completed successfully")
    return {"results": [1, 2, 3]}


async def simulate_cache_lookup(key: str):
    """Simulate a cache lookup - operation ID propagates automatically."""
    cache_logger.info(f"Looking up cache key: {key}")
    await asyncio.sleep(0.05)  # Simulate cache lookup
    cache_logger.info("Cache miss")
    return None


@traced
async def handle_request(request_data: str):
    """
    Handle a request with automatic operation ID tracking.

    The @traced decorator automatically:
    1. Generates a unique operation ID
    2. Sets it in the context
    3. Cleans up after the request completes
    """
    server_logger.info(f"Received request: {request_data}")

    # Check cache first
    cache_result = await simulate_cache_lookup(request_data)

    if not cache_result:
        # Cache miss - query database
        db_result = await simulate_database_query(f"SELECT * WHERE data='{request_data}'")
        server_logger.info(f"Database returned {len(db_result['results'])} results")

    server_logger.info("Request completed successfully")
    return "success"


async def main():
    """Run the demonstration."""
    print("=" * 80)
    print("Distributed Tracing Demonstration")
    print("=" * 80)
    print()
    print("Each request below will have a unique operation ID (8 chars) that appears")
    print("in ALL log messages for that request, making it easy to trace the flow.")
    print()
    print("-" * 80)

    # Simulate 3 concurrent requests
    print("\n🔹 Simulating 3 concurrent requests...\n")

    results = await asyncio.gather(
        handle_request("user_data_1"),
        handle_request("user_data_2"),
        handle_request("user_data_3"),
    )

    print("\n" + "-" * 80)
    print("\n✅ All requests completed!")
    print()
    print("Notice how each request has its own operation ID that appears in")
    print("ALL related log messages (server, cache, database).")
    print()
    print("In production, you can grep logs by operation ID:")
    print("  $ grep '[abc12345]' application.log")
    print()
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
