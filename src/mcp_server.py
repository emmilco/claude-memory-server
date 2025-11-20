#!/usr/bin/env python3
"""
MCP Server entry point for Claude Memory RAG.

This is the MCP protocol wrapper around src/core/server.py.
All business logic is in src/core/server.py - this file just handles
the MCP protocol communication.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

# Ensure we can import from the project root
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print(
        "Error: mcp package not found. Install with: pip install mcp", file=sys.stderr
    )
    sys.exit(1)

# Import modern server implementation
from src.core.server import MemoryRAGServer
from src.config import get_config

# Initialize MCP server
app = Server("claude-memory-rag")
memory_server: MemoryRAGServer = None


@app.list_tools()
async def list_tools() -> List[Tool]:
    """
    List all available MCP tools.

    Returns the complete set of tools exposed by the modern MemoryRAGServer.
    """
    return [
        # Memory Management Tools
        Tool(
            name="store_memory",
            description="Store a memory with automatic context-level classification and deduplication",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Memory content"},
                    "category": {
                        "type": "string",
                        "enum": ["preference", "fact", "event", "workflow", "context"],
                        "description": "Memory category",
                    },
                    "importance": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Importance score (0.0-1.0)",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for categorization",
                    },
                },
                "required": ["content", "category"],
            },
        ),
        Tool(
            name="retrieve_memories",
            description="Retrieve relevant memories using semantic search with smart routing",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {
                        "type": "number",
                        "description": "Maximum results (default: 10)",
                    },
                    "min_relevance": {
                        "type": "number",
                        "description": "Minimum relevance score 0-1 (default: 0.0)",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_memories",
            description="List and browse memories with filtering and pagination",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["preference", "fact", "event", "workflow", "context"],
                    },
                    "context_level": {
                        "type": "string",
                        "enum": ["USER_PREFERENCE", "PROJECT_CONTEXT", "SESSION_STATE"],
                    },
                    "scope": {"type": "string", "enum": ["global", "project"]},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags (ANY match)",
                    },
                    "min_importance": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    "limit": {"type": "number", "minimum": 1, "maximum": 100},
                    "offset": {"type": "number", "minimum": 0},
                },
            },
        ),
        Tool(
            name="delete_memory",
            description="Delete a memory by ID",
            inputSchema={
                "type": "object",
                "properties": {"memory_id": {"type": "string"}},
                "required": ["memory_id"],
            },
        ),
        Tool(
            name="export_memories",
            description="Export memories to JSON or Markdown format",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_path": {"type": "string", "description": "File path to export to"},
                    "format": {"type": "string", "enum": ["json", "markdown"]},
                    "category": {"type": "string"},
                    "scope": {"type": "string"},
                },
            },
        ),
        Tool(
            name="import_memories",
            description="Import memories from JSON file with conflict resolution",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "conflict_mode": {
                        "type": "string",
                        "enum": ["skip", "overwrite", "merge"],
                    },
                },
                "required": ["file_path"],
            },
        ),
        # Code Search Tools
        Tool(
            name="search_code",
            description="Search indexed code semantically across functions and classes",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "project_name": {"type": "string", "description": "Project filter"},
                    "limit": {"type": "number", "description": "Max results (default: 5)"},
                    "file_pattern": {"type": "string", "description": "File path pattern"},
                    "language": {"type": "string", "description": "Language filter"},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="index_codebase",
            description="Index a codebase directory for semantic code search",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory_path": {"type": "string"},
                    "project_name": {"type": "string"},
                    "recursive": {"type": "boolean"},
                },
                "required": ["directory_path"],
            },
        ),
        Tool(
            name="find_similar_code",
            description="Find similar code snippets in the indexed codebase",
            inputSchema={
                "type": "object",
                "properties": {
                    "code_snippet": {"type": "string"},
                    "project_name": {"type": "string"},
                    "limit": {"type": "number"},
                },
                "required": ["code_snippet"],
            },
        ),
        Tool(
            name="search_all_projects",
            description="Search code across all opted-in projects",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "number"},
                    "search_mode": {
                        "type": "string",
                        "enum": ["semantic", "keyword", "hybrid"],
                    },
                },
                "required": ["query"],
            },
        ),
        # Cross-Project Tools
        Tool(
            name="opt_in_cross_project",
            description="Opt in a project for cross-project search",
            inputSchema={
                "type": "object",
                "properties": {"project_name": {"type": "string"}},
                "required": ["project_name"],
            },
        ),
        Tool(
            name="opt_out_cross_project",
            description="Opt out a project from cross-project search",
            inputSchema={
                "type": "object",
                "properties": {"project_name": {"type": "string"}},
                "required": ["project_name"],
            },
        ),
        Tool(
            name="list_opted_in_projects",
            description="List all projects opted in for cross-project search",
            inputSchema={"type": "object", "properties": {}},
        ),
        # Monitoring Tools
        Tool(
            name="get_performance_metrics",
            description="Get current performance metrics and historical averages",
            inputSchema={
                "type": "object",
                "properties": {
                    "include_history_days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 30,
                    }
                },
            },
        ),
        Tool(
            name="get_health_score",
            description="Get overall system health score with component breakdown",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_active_alerts",
            description="Get active system alerts with severity levels",
            inputSchema={
                "type": "object",
                "properties": {
                    "severity_filter": {
                        "type": "string",
                        "enum": ["CRITICAL", "WARNING", "INFO"],
                    }
                },
            },
        ),
        Tool(
            name="start_dashboard",
            description="Start the web dashboard server for visual monitoring and analytics",
            inputSchema={
                "type": "object",
                "properties": {
                    "port": {
                        "type": "integer",
                        "description": "Port to run dashboard on (default: 8080)",
                        "minimum": 1024,
                        "maximum": 65535,
                    },
                    "host": {
                        "type": "string",
                        "description": "Host to bind to (default: localhost)",
                    },
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle MCP tool calls by delegating to the modern server."""
    global memory_server

    try:
        # Route to appropriate server method
        if name == "store_memory":
            # Validate required arguments
            if "content" not in arguments:
                return [TextContent(type="text", text="Error: 'content' is required")]
            if "category" not in arguments:
                return [TextContent(type="text", text="Error: 'category' is required")]

            result = await memory_server.store_memory(
                content=arguments["content"],
                category=arguments["category"],
                importance=arguments.get("importance", 0.5),
                tags=arguments.get("tags", []),
            )
            return [
                TextContent(
                    type="text",
                    text=f"✅ Stored {arguments['category']} memory (ID: {result['memory_id']})\n"
                    f"Context Level: {result['context_level']}\n"
                    f"Status: {result['status']}",
                )
            ]

        elif name == "retrieve_memories":
            result = await memory_server.retrieve_memories(
                query=arguments["query"],
                limit=arguments.get("limit", 10),
                min_importance=arguments.get("min_relevance", 0.0),
            )

            if not result["results"]:
                return [TextContent(type="text", text="No relevant memories found.")]

            output = f"Found {result['total_found']} memories:\n\n"
            for i, mem in enumerate(result["results"], 1):
                memory = mem['memory']
                output += f"{i}. [{memory['category']}] {memory['content'][:100]}...\n"
                output += f"   Relevance: {mem['score']:.2%} | "
                output += f"Importance: {memory['importance']:.2f}\n\n"

            return [TextContent(type="text", text=output)]

        elif name == "list_memories":
            result = await memory_server.list_memories(
                category=arguments.get("category"),
                context_level=arguments.get("context_level"),
                scope=arguments.get("scope"),
                tags=arguments.get("tags"),
                min_importance=arguments.get("min_importance", 0.0),
                limit=arguments.get("limit", 20),
                offset=arguments.get("offset", 0),
            )

            output = f"Found {result['total_count']} memories (showing {result['returned_count']}):\n\n"
            for i, mem in enumerate(result["memories"], 1):
                output += f"{i}. [{mem['category']}] {mem['content'][:80]}...\n"
                output += f"   ID: {mem['memory_id']} | Importance: {mem['importance']:.2f}\n\n"

            return [TextContent(type="text", text=output)]

        elif name == "delete_memory":
            result = await memory_server.delete_memory(arguments["memory_id"])
            if result["status"] == "success":
                return [TextContent(type="text", text=f"✅ Memory deleted: {result['memory_id']}")]
            else:
                return [TextContent(type="text", text=f"❌ Memory not found: {result['memory_id']}")]

        elif name == "export_memories":
            result = await memory_server.export_memories(**arguments)
            return [
                TextContent(
                    type="text",
                    text=f"✅ Exported {result['count']} memories to {result.get('file_path', 'output')}",
                )
            ]

        elif name == "import_memories":
            result = await memory_server.import_memories(**arguments)
            return [
                TextContent(
                    type="text",
                    text=f"✅ Imported {result['created']} memories "
                    f"(updated: {result['updated']}, skipped: {result['skipped']})",
                )
            ]

        elif name == "search_code":
            result = await memory_server.search_code(**arguments)
            if not result["results"]:
                return [TextContent(type="text", text="No code found matching your query.")]

            output = f"✅ Found {result['total_found']} code snippets:\n\n"
            for i, code in enumerate(result["results"], 1):
                output += f"{i}. {code['unit_name']} ({code['unit_type']})\n"
                output += f"   File: {code['file_path']}:{code['start_line']}\n"
                output += f"   Relevance: {code['relevance_score']:.2%}\n\n"

            return [TextContent(type="text", text=output)]

        elif name == "index_codebase":
            result = await memory_server.index_codebase(**arguments)
            return [
                TextContent(
                    type="text",
                    text=f"✅ Indexed {result['files_indexed']} files "
                    f"({result['units_indexed']} semantic units) "
                    f"in {result['total_time_s']:.2f}s",
                )
            ]

        elif name == "find_similar_code":
            result = await memory_server.find_similar_code(**arguments)
            if not result["results"]:
                return [TextContent(type="text", text="No similar code found.")]

            output = f"✅ Found {result['total_found']} similar code snippets:\n\n"
            for i, code in enumerate(result["results"], 1):
                output += f"{i}. {code['unit_name']} - Similarity: {code['similarity_score']:.2%}\n"
                output += f"   File: {code['file_path']}\n\n"

            return [TextContent(type="text", text=output)]

        elif name == "search_all_projects":
            result = await memory_server.search_all_projects(**arguments)
            if not result["results"]:
                return [TextContent(type="text", text="No results found across projects.")]

            output = f"✅ Found {result['total_found']} results across {len(result['projects_searched'])} projects:\n\n"
            for i, code in enumerate(result["results"], 1):
                output += f"{i}. [{code['source_project']}] {code['unit_name']}\n"
                output += f"   Relevance: {code['relevance_score']:.2%}\n\n"

            return [TextContent(type="text", text=output)]

        elif name == "opt_in_cross_project":
            result = await memory_server.opt_in_cross_project(arguments["project_name"])
            status_msg = f"Project '{result['project_name']}' opted-in for cross-project search"
            if result['was_opted_in']:
                status_msg += " (already opted-in)"
            return [TextContent(type="text", text=f"✅ {status_msg}")]

        elif name == "opt_out_cross_project":
            result = await memory_server.opt_out_cross_project(arguments["project_name"])
            status_msg = f"Project '{result['project_name']}' opted-out from cross-project search"
            if not result.get('was_opted_in', True):
                status_msg += " (already opted-out)"
            return [TextContent(type="text", text=f"✅ {status_msg}")]

        elif name == "list_opted_in_projects":
            result = await memory_server.list_opted_in_projects()
            projects = result.get("opted_in_projects", [])
            if not projects:
                return [TextContent(type="text", text="No projects opted in for cross-project search.")]
            return [TextContent(type="text", text=f"Opted-in projects:\n" + "\n".join(f"  - {p}" for p in projects))]

        elif name == "get_performance_metrics":
            result = await memory_server.get_performance_metrics(
                include_history_days=arguments.get("include_history_days", 1)
            )
            current = result["current_metrics"]
            output = f"📊 Performance Metrics:\n\n"
            output += f"Avg Search Latency: {current['avg_search_latency_ms']:.2f}ms\n"
            output += f"Cache Hit Rate: {current['cache_hit_rate']:.1%}\n"
            output += f"Queries/Day: {current['queries_per_day']:.1f}\n"
            return [TextContent(type="text", text=output)]

        elif name == "get_health_score":
            result = await memory_server.get_health_score()
            # Result already has the right structure from src/core/server.py
            if isinstance(result, dict) and "health_score" in result:
                health = result["health_score"]
                output = f"💚 Health Score: {health['overall_score']}/100 ({health['status']})\n\n"
                output += f"Performance: {health['performance_score']}/100\n"
                output += f"Quality: {health['quality_score']}/100\n"
                return [TextContent(type="text", text=output)]
            else:
                return [TextContent(type="text", text=f"Unexpected health score format: {result}")]

        elif name == "get_active_alerts":
            result = await memory_server.get_active_alerts(
                severity_filter=arguments.get("severity_filter")
            )
            if result["total_alerts"] == 0:
                return [TextContent(type="text", text="✅ No active alerts")]

            output = f"🚨 {result['total_alerts']} active alerts:\n\n"
            for alert in result["alerts"][:5]:
                output += f"• {alert['severity']}: {alert['message']}\n"
            return [TextContent(type="text", text=output)]

        elif name == "start_dashboard":
            port = arguments.get("port", 8080)
            host = arguments.get("host", "localhost")
            result = await memory_server.start_dashboard(port=port, host=host)
            return [
                TextContent(
                    type="text",
                    text=f"✅ Dashboard server started at {result['url']}\n"
                    f"Process ID: {result['pid']}\n\n"
                    f"Open {result['url']} in your browser to view the dashboard.\n"
                    f"The server is running in the background."
                )
            ]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.exception(f"Error handling tool call: {name}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _startup_health_check(config, memory_server) -> bool:
    """
    Perform startup health check to validate system is ready.

    Returns:
        True if all checks pass, False otherwise
    """
    try:
        logger.info("Running startup health checks...")

        # Check 1: Storage backend connectivity
        logger.info(f"✓ Checking {config.storage_backend} connectivity...")
        try:
            # Test a simple operation
            await memory_server.store.get_stats()
            logger.info(f"✓ {config.storage_backend.upper()} connection successful")
        except Exception as e:
            logger.error(f"✗ {config.storage_backend.upper()} connection failed: {e}")
            logger.error("  → Try: docker-compose up -d (for Qdrant) or check SQLite path")
            return False

        # Check 2: Embedding model
        logger.info("✓ Checking embedding model...")
        try:
            test_embedding = await memory_server.embedding_generator.generate_embedding("test")
            if test_embedding and len(test_embedding) > 0:
                logger.info(f"✓ Embedding model loaded successfully ({len(test_embedding)} dims)")
            else:
                logger.error("✗ Embedding generation returned empty result")
                return False
        except Exception as e:
            logger.error(f"✗ Embedding model failed: {e}")
            logger.error("  → Try: pip install sentence-transformers")
            return False

        # Check 3: Required directories
        logger.info("✓ Checking required directories...")
        required_dirs = [
            config.get_expanded_path(config.sqlite_path).parent,
            config.get_expanded_path(config.embedding_cache_path).parent,
        ]
        for dir_path in required_dirs:
            if not dir_path.exists():
                logger.warning(f"  Creating directory: {dir_path}")
                dir_path.mkdir(parents=True, exist_ok=True)
        logger.info("✓ All required directories exist")

        logger.info("✅ All startup health checks passed!")
        return True

    except Exception as e:
        logger.error(f"✗ Startup health check failed: {e}")
        return False


async def main():
    """Initialize and run the MCP server."""
    global memory_server

    logger.info("Starting Claude Memory RAG MCP Server")

    # Initialize the modern server
    config = get_config()
    memory_server = MemoryRAGServer(config)

    # Fast initialization - defer expensive operations until after MCP is listening
    await memory_server.initialize(defer_preload=True)

    logger.info(f"Server initialized (project: {memory_server.project_name or 'global'})")
    logger.info(f"Storage backend: {config.storage_backend}")

    try:
        # Run MCP server - start listening BEFORE doing expensive health checks
        async with stdio_server() as (read_stream, write_stream):
            # Background task: Complete initialization and health checks
            async def complete_initialization():
                """Complete expensive initialization in the background."""
                try:
                    # Preload embedding model
                    logger.info("Background: Preloading embedding model...")
                    await memory_server.embedding_generator.initialize()
                    logger.info("Background: Embedding model ready")

                    # Collect initial metrics
                    if memory_server.metrics_collector:
                        logger.info("Background: Collecting initial metrics...")
                        try:
                            initial_metrics = await memory_server.metrics_collector.collect_metrics()
                            initial_metrics.health_score = memory_server._calculate_simple_health_score(initial_metrics)
                            memory_server.metrics_collector.store_metrics(initial_metrics)
                            logger.info(f"Background: Initial metrics collected (health: {initial_metrics.health_score}/100)")
                        except Exception as e:
                            logger.warning(f"Background: Failed to collect initial metrics: {e}")

                    # Perform startup health check
                    if not await _startup_health_check(config, memory_server):
                        logger.warning("⚠️ Startup health check failed - server running in degraded mode")
                        logger.warning("Some features may not work correctly. See docs/TROUBLESHOOTING.md")
                    else:
                        logger.info("✅ Background initialization complete - all systems ready")
                except Exception as e:
                    logger.error(f"Background initialization error: {e}")

            # Start background initialization (don't await - let it run in parallel)
            asyncio.create_task(complete_initialization())

            # Start serving MCP requests immediately
            await app.run(
                read_stream, write_stream, app.create_initialization_options()
            )
    finally:
        # Cleanup
        await memory_server.close()
        logger.info("Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
