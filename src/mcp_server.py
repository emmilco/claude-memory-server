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
from src.core.exceptions import (
    ValidationError,
    StorageError,
    RetrievalError,
    EmbeddingError,
    MemoryRAGError,
)

# Initialize MCP server
app = Server("claude-memory-rag")
memory_server: MemoryRAGServer = None
_init_task: asyncio.Task = None  # Track background initialization task for proper cleanup


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
                    "min_importance": {
                        "type": "number",
                        "description": "Minimum importance score 0-1 (default: 0.0)",
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
            name="delete_memories_by_query",
            description="Delete memories matching query filters. SAFETY: defaults to dry_run=True (preview only). Set dry_run=false to actually delete.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Filter by category (case-insensitive): preference, fact, event, workflow, context, code"},
                    "project_name": {"type": "string", "description": "Filter by project (use to clear entire project index)"},
                    "tags": {"type": "array", "items": {"type": "string"}, "description": "Filter by tags (matches ANY)"},
                    "date_from": {"type": "string", "description": "Delete memories created after this date (ISO format)"},
                    "date_to": {"type": "string", "description": "Delete memories created before this date (ISO format)"},
                    "min_importance": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": "Minimum importance threshold"},
                    "max_importance": {"type": "number", "minimum": 0.0, "maximum": 1.0, "description": "Maximum importance threshold"},
                    "lifecycle_state": {"type": "string", "description": "Filter by lifecycle state (case-insensitive): active, recent, archived, stale"},
                    "scope": {"type": "string", "description": "Filter by scope (case-insensitive): global, project, session"},
                    "context_level": {"type": "string", "description": "Filter by context level (case-insensitive): user_preference, project_context, session_state"},
                    "dry_run": {"type": "boolean", "description": "If true, preview only (default: true)", "default": True},
                    "max_count": {"type": "number", "minimum": 1, "maximum": 1000, "description": "Maximum memories to delete (default: 1000)"},
                },
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
            description=(
                "Search indexed code semantically across functions and classes. "
                "FEAT-056: Now supports advanced filtering (glob patterns, complexity, dates) and sorting."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "project_name": {"type": "string", "description": "Project filter"},
                    "limit": {"type": "number", "description": "Max results (default: 5)"},
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob pattern for file paths (e.g., '**/*.test.py', 'src/**/auth*.ts')"
                    },
                    "language": {"type": "string", "description": "Language filter"},
                    "search_mode": {
                        "type": "string",
                        "enum": ["semantic", "keyword", "hybrid"],
                        "description": "Search mode (default: semantic)"
                    },
                    # FEAT-058: Pattern matching parameters
                    "pattern": {
                        "type": "string",
                        "description": "Optional regex pattern or @preset:name for code pattern matching"
                    },
                    "pattern_mode": {
                        "type": "string",
                        "enum": ["filter", "boost", "require"],
                        "description": "How to apply pattern: filter, boost, or require (default: filter)"
                    },
                    # FEAT-056: Advanced filtering parameters
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Glob patterns to exclude (e.g., ['**/*.test.py', '**/generated/**'])"
                    },
                    "complexity_min": {
                        "type": "integer",
                        "description": "Minimum cyclomatic complexity"
                    },
                    "complexity_max": {
                        "type": "integer",
                        "description": "Maximum cyclomatic complexity"
                    },
                    "line_count_min": {
                        "type": "integer",
                        "description": "Minimum line count"
                    },
                    "line_count_max": {
                        "type": "integer",
                        "description": "Maximum line count"
                    },
                    "modified_after": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Filter by file modification time (ISO 8601 format)"
                    },
                    "modified_before": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Filter by file modification time (ISO 8601 format)"
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": ["relevance", "complexity", "size", "recency", "importance"],
                        "description": "Sort order (default: relevance)"
                    },
                    "sort_order": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "description": "Sort direction (default: desc)"
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="suggest_queries",
            description=(
                "Get contextual query suggestions based on indexed codebase and user intent. "
                "FEAT-057: Helps users overcome query formulation paralysis by suggesting effective queries."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "enum": ["implementation", "debugging", "learning", "exploration", "refactoring"],
                        "description": "User's current intent or task"
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Project to scope suggestions to"
                    },
                    "context": {
                        "type": "string",
                        "description": "Additional context from conversation"
                    },
                    "max_suggestions": {
                        "type": "integer",
                        "default": 8,
                        "description": "Maximum suggestions to return"
                    },
                },
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
        # Git History Tools
        Tool(
            name="search_git_commits",
            description="Search git commits with semantic search and filters",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Semantic search query over commit messages",
                    },
                    "repository_path": {
                        "type": "string",
                        "description": "Filter by repository path",
                    },
                    "author": {
                        "type": "string",
                        "description": "Filter by author email",
                    },
                    "since": {
                        "type": "string",
                        "description": "Start date (ISO format)",
                    },
                    "until": {
                        "type": "string",
                        "description": "End date (ISO format)",
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results (default: 100)",
                    },
                },
            },
        ),
        Tool(
            name="get_file_history",
            description="Get commit history for a specific file",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file",
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of commits (default: 100)",
                    },
                },
                "required": ["file_path"],
            },
        ),
        # Git Analysis Tools (FEAT-061)
        Tool(
            name="get_change_frequency",
            description="Calculate how often a file or function changes",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_or_function": {
                        "type": "string",
                        "description": "File path (e.g., 'src/auth.py') or function name",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Optional project filter",
                    },
                    "since": {
                        "type": "string",
                        "description": "Optional start date for analysis (e.g., '2024-01-01', 'last month')",
                    },
                },
                "required": ["file_or_function"],
            },
        ),
        Tool(
            name="get_churn_hotspots",
            description="Find files with highest change frequency (churn hotspots)",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Optional project filter",
                    },
                    "limit": {
                        "type": "number",
                        "description": "Max results (default: 10)",
                    },
                    "min_changes": {
                        "type": "number",
                        "description": "Minimum changes to qualify (default: 5)",
                    },
                    "days": {
                        "type": "number",
                        "description": "Analysis window in days (default: 90)",
                    },
                },
            },
        ),
        Tool(
            name="get_recent_changes",
            description="Get recent file modifications with context",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Optional project filter",
                    },
                    "days": {
                        "type": "number",
                        "description": "Look back period (default: 30)",
                    },
                    "limit": {
                        "type": "number",
                        "description": "Max results (default: 50)",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Optional file filter (e.g., 'src/api/*.py')",
                    },
                },
            },
        ),
        Tool(
            name="blame_search",
            description="Find who wrote code matching a pattern (git blame integration)",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Code pattern or natural language query",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Optional project filter",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Optional file filter (e.g., 'src/auth/*.py')",
                    },
                    "limit": {
                        "type": "number",
                        "description": "Max results (default: 20)",
                    },
                },
                "required": ["pattern"],
            },
        ),
        Tool(
            name="get_code_authors",
            description="Get contributors for a file with their contribution counts",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file",
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of commits to analyze (default: 100)",
                    },
                },
                "required": ["file_path"],
            },
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
        # Call Graph / Structural Query Tools (FEAT-059)
        Tool(
            name="find_callers",
            description="Find all functions calling the specified function (supports transitive search)",
            inputSchema={
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string",
                        "description": "Function name to search for (qualified name, e.g., 'MyClass.method')",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Project to search in (defaults to current project)",
                    },
                    "include_indirect": {
                        "type": "boolean",
                        "description": "If true, include transitive callers (default: false)",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth for transitive search (default: 1)",
                        "minimum": 1,
                        "maximum": 10,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 50)",
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": ["function_name"],
            },
        ),
        Tool(
            name="find_callees",
            description="Find all functions called by the specified function (supports transitive search)",
            inputSchema={
                "type": "object",
                "properties": {
                    "function_name": {
                        "type": "string",
                        "description": "Function name to analyze (qualified name, e.g., 'MyClass.method')",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Project to search in (defaults to current project)",
                    },
                    "include_indirect": {
                        "type": "boolean",
                        "description": "If true, include transitive callees (default: false)",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth for transitive search (default: 1)",
                        "minimum": 1,
                        "maximum": 10,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 50)",
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": ["function_name"],
            },
        ),
        Tool(
            name="get_call_chain",
            description="Find call chains (paths) from one function to another",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_function": {
                        "type": "string",
                        "description": "Starting function (qualified name)",
                    },
                    "to_function": {
                        "type": "string",
                        "description": "Target function (qualified name)",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Project to search in (defaults to current project)",
                    },
                    "max_paths": {
                        "type": "integer",
                        "description": "Maximum number of paths to return (default: 5)",
                        "minimum": 1,
                        "maximum": 20,
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum path length to search (default: 10)",
                        "minimum": 1,
                        "maximum": 20,
                    },
                },
                "required": ["from_function", "to_function"],
            },
        ),
        Tool(
            name="find_implementations",
            description="Find all implementations of an interface/abstract class",
            inputSchema={
                "type": "object",
                "properties": {
                    "interface_name": {
                        "type": "string",
                        "description": "Interface/abstract class name to search for",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Project to search in (defaults to current project)",
                    },
                    "language": {
                        "type": "string",
                        "description": "Filter by language (e.g., 'python', 'javascript')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 50)",
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
                "required": ["interface_name"],
            },
        ),
        Tool(
            name="find_dependencies",
            description="Find all files that this file depends on (imports)",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path to analyze",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Project to search in (defaults to current project)",
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Maximum depth for dependency traversal (default: 1)",
                        "minimum": 1,
                        "maximum": 10,
                    },
                    "include_transitive": {
                        "type": "boolean",
                        "description": "If true, include transitive dependencies (default: false)",
                    },
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="find_dependents",
            description="Find all files that depend on this file (reverse dependencies)",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path to analyze",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Project to search in (defaults to current project)",
                    },
                    "depth": {
                        "type": "integer",
                        "description": "Maximum depth for reverse dependency traversal (default: 1)",
                        "minimum": 1,
                        "maximum": 10,
                    },
                    "include_transitive": {
                        "type": "boolean",
                        "description": "If true, include transitive dependents (default: false)",
                    },
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="list_opted_in_projects",
            description="List all projects that are opted in for cross-project search.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        # FEAT-020: Usage Pattern Analytics Tools
        Tool(
            name="get_usage_statistics",
            description="Get overall usage statistics including query counts, execution times, and code access patterns over a specified time period.",
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {
                        "type": "number",
                        "description": "Number of days to look back (1-365, default: 30)",
                        "minimum": 1,
                        "maximum": 365
                    }
                }
            }
        ),
        Tool(
            name="get_top_queries",
            description="Get most frequently executed queries with statistics including average results and execution time.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of queries to return (1-100, default: 10)",
                        "minimum": 1,
                        "maximum": 100
                    },
                    "days": {
                        "type": "number",
                        "description": "Number of days to look back (1-365, default: 30)",
                        "minimum": 1,
                        "maximum": 365
                    }
                }
            }
        ),
        Tool(
            name="get_frequently_accessed_code",
            description="Get most frequently accessed code files and functions with access counts and timestamps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of items to return (1-100, default: 10)",
                        "minimum": 1,
                        "maximum": 100
                    },
                    "days": {
                        "type": "number",
                        "description": "Number of days to look back (1-365, default: 30)",
                        "minimum": 1,
                        "maximum": 365
                    }
                }
            }
        )
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
                min_importance=arguments.get("min_importance", 0.0),
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

        elif name == "delete_memories_by_query":
            result = await memory_server.delete_memories_by_query(
                category=arguments.get("category"),
                project_name=arguments.get("project_name"),
                tags=arguments.get("tags"),
                date_from=arguments.get("date_from"),
                date_to=arguments.get("date_to"),
                min_importance=arguments.get("min_importance", 0.0),
                max_importance=arguments.get("max_importance", 1.0),
                lifecycle_state=arguments.get("lifecycle_state"),
                scope=arguments.get("scope"),
                context_level=arguments.get("context_level"),
                dry_run=arguments.get("dry_run", True),
                max_count=arguments.get("max_count", 1000),
            )

            # Format output
            if result["preview"]:
                output = f"🔍 PREVIEW MODE (dry_run=True)\n\n"
                output += f"Total matches: {result['total_matches']}\n"
                output += f"Will delete: {result['total_matches']} memories\n\n"
            else:
                output = f"✅ DELETION COMPLETE\n\n"
                output += f"Deleted: {result['deleted_count']} memories\n\n"

            output += "Breakdown by category:\n"
            for cat, count in result["breakdown_by_category"].items():
                output += f"  - {cat}: {count}\n"

            output += "\nBreakdown by project:\n"
            for proj, count in result["breakdown_by_project"].items():
                output += f"  - {proj}: {count}\n"

            if result["warnings"]:
                output += "\n⚠️  Warnings:\n"
                for warning in result["warnings"]:
                    output += f"  - {warning}\n"

            if result["preview"] and result["requires_confirmation"]:
                output += "\n⚠️  This operation requires confirmation due to the number of memories.\n"
                output += "Set dry_run=false to proceed with deletion.\n"

            return [TextContent(type="text", text=output)]

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
            # FEAT-056: Parse datetime strings for modified_after/modified_before
            from datetime import datetime
            if "modified_after" in arguments and isinstance(arguments["modified_after"], str):
                arguments["modified_after"] = datetime.fromisoformat(arguments["modified_after"])
            if "modified_before" in arguments and isinstance(arguments["modified_before"], str):
                arguments["modified_before"] = datetime.fromisoformat(arguments["modified_before"])

            result = await memory_server.search_code(**arguments)
            if not result["results"]:
                return [TextContent(type="text", text="No code found matching your query.")]

            output = f"✅ Found {result['total_found']} code snippets"
            # FEAT-056: Show applied filters
            if result.get("filters_applied"):
                output += f" (with {len(result['filters_applied'])} filters)"
            output += ":\n\n"

            for i, code in enumerate(result["results"], 1):
                output += f"{i}. {code['unit_name']} ({code['unit_type']})\n"
                output += f"   File: {code['file_path']}:{code['start_line']}\n"
                output += f"   Relevance: {code['relevance_score']:.2%}"
                # FEAT-056: Show complexity if available
                if "metadata" in code and code["metadata"].get("cyclomatic_complexity"):
                    output += f" | Complexity: {code['metadata']['cyclomatic_complexity']}"
                output += "\n\n"

            # FEAT-056: Show sort info if not default
            if result.get("sort_info") and result["sort_info"].get("sort_by") != "relevance":
                output += f"\n(Sorted by: {result['sort_info']['sort_by']} {result['sort_info']['sort_order']})\n"

            return [TextContent(type="text", text=output)]

        elif name == "suggest_queries":
            result = await memory_server.suggest_queries(**arguments)
            output = f"✅ Query Suggestions ({result['total_suggestions']} suggestions):\n\n"

            # Show indexed stats
            stats = result["indexed_stats"]
            output += f"Indexed: {stats.get('total_units', 0)} code units in {stats.get('total_files', 0)} files\n"
            if stats.get("languages"):
                langs = ", ".join(f"{lang} ({count})" for lang, count in list(stats["languages"].items())[:3])
                output += f"Languages: {langs}\n"
            output += "\n"

            # Group suggestions by category
            suggestions_by_cat = {}
            for suggestion in result["suggestions"]:
                cat = suggestion["category"]
                suggestions_by_cat.setdefault(cat, []).append(suggestion)

            # Display suggestions grouped by category
            category_names = {
                "template": "Intent-Based Suggestions",
                "project": "Project-Specific Suggestions",
                "domain": "Domain Presets",
                "general": "General Discovery"
            }

            for cat in ["template", "project", "domain", "general"]:
                if cat in suggestions_by_cat:
                    output += f"**{category_names[cat]}**:\n"
                    for suggestion in suggestions_by_cat[cat]:
                        output += f"  • \"{suggestion['query']}\"\n"
                        output += f"    {suggestion['description']}\n"
                    output += "\n"

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

        elif name == "search_git_commits":
            from datetime import datetime
            # Convert date strings to datetime if provided
            kwargs = {}
            if "query" in arguments:
                kwargs["query"] = arguments["query"]
            if "repository_path" in arguments:
                kwargs["repository_path"] = arguments["repository_path"]
            if "author" in arguments:
                kwargs["author"] = arguments["author"]
            if "since" in arguments:
                kwargs["since"] = datetime.fromisoformat(arguments["since"])
            if "until" in arguments:
                kwargs["until"] = datetime.fromisoformat(arguments["until"])
            if "limit" in arguments:
                kwargs["limit"] = arguments["limit"]

            result = await memory_server.search_git_commits(**kwargs)
            commits = result.get("commits", [])
            if not commits:
                return [TextContent(type="text", text="No commits found matching your criteria.")]

            output = f"Found {len(commits)} commit(s):\n\n"
            for i, commit in enumerate(commits[:10], 1):
                output += f"{i}. {commit['commit_hash'][:8]} - {commit['message'][:60]}\n"
                output += f"   Author: {commit['author_name']} <{commit['author_email']}>\n"
                output += f"   Date: {commit['author_date']}\n"
                if commit.get('repository_path'):
                    output += f"   Repo: {commit['repository_path']}\n"
                output += "\n"

            if len(commits) > 10:
                output += f"... and {len(commits) - 10} more commits\n"

            return [TextContent(type="text", text=output)]

        elif name == "get_file_history":
            result = await memory_server.get_file_history(
                file_path=arguments["file_path"],
                limit=arguments.get("limit", 100)
            )
            commits = result.get("commits", [])
            if not commits:
                return [TextContent(type="text", text=f"No commit history found for {arguments['file_path']}.")]

            output = f"Commit history for {arguments['file_path']}:\n\n"
            for i, commit in enumerate(commits[:10], 1):
                output += f"{i}. {commit['commit_hash'][:8]} - {commit['message'][:60]}\n"
                output += f"   Author: {commit['author_name']}\n"
                output += f"   Date: {commit['author_date']}\n\n"

            if len(commits) > 10:
                output += f"... and {len(commits) - 10} more commits\n"

            return [TextContent(type="text", text=output)]

        elif name == "get_change_frequency":
            result = await memory_server.get_change_frequency(**arguments)
            if result["total_changes"] == 0:
                return [TextContent(type="text", text=f"No changes found for {arguments['file_or_function']}.")]

            output = f"Change frequency for {result['file_path']}:\n\n"
            output += f"Total changes: {result['total_changes']}\n"
            output += f"Changes per week: {result['changes_per_week']:.2f}\n"
            output += f"Churn score: {result['churn_score']:.2f} ({result['interpretation']})\n"
            output += f"Time span: {result['time_span_days']:.1f} days\n"
            output += f"Unique authors: {result['unique_authors']}\n"
            output += f"Lines: +{result['total_lines_added']} -{result['total_lines_deleted']}\n"

            if result.get("first_change"):
                output += f"First change: {result['first_change']}\n"
            if result.get("last_change"):
                output += f"Last change: {result['last_change']}\n"

            return [TextContent(type="text", text=output)]

        elif name == "get_churn_hotspots":
            result = await memory_server.get_churn_hotspots(**arguments)
            hotspots = result.get("hotspots", [])

            if not hotspots:
                note = result.get("note", "")
                return [TextContent(type="text", text=f"No churn hotspots found. {note}")]

            output = f"Churn hotspots (last {result['analysis_period_days']} days):\n\n"
            for i, hotspot in enumerate(hotspots[:20], 1):
                output += f"{i}. {hotspot['file_path']}\n"
                output += f"   Score: {hotspot['churn_score']:.2f} ({hotspot['instability_indicator']})\n"
                output += f"   Changes: {hotspot['total_changes']} total, {hotspot['recent_changes_30d']} in 30d\n"
                output += f"   Avg change: {hotspot['avg_change_size']:.1f} lines\n"
                output += f"   Authors: {len(hotspot['authors'])}\n\n"

            return [TextContent(type="text", text=output)]

        elif name == "get_recent_changes":
            result = await memory_server.get_recent_changes(**arguments)
            changes = result.get("changes", [])

            if not changes:
                return [TextContent(type="text", text=f"No recent changes found in last {result['period_days']} days.")]

            output = f"Recent changes (last {result['period_days']} days):\n\n"
            for i, change in enumerate(changes[:20], 1):
                output += f"{i}. {change['commit_hash'][:8]} - {change['days_ago']}d ago\n"
                output += f"   {change['author']}\n"
                output += f"   {change['message'][:60]}\n"
                stats = change.get("stats", {})
                if stats:
                    output += f"   Files: {stats.get('files_changed', 0)}, "
                    output += f"+{stats.get('insertions', 0)} -{stats.get('deletions', 0)}\n"
                output += "\n"

            if result["total_changes"] > 20:
                output += f"... and {result['total_changes'] - 20} more changes\n"

            return [TextContent(type="text", text=output)]

        elif name == "blame_search":
            result = await memory_server.blame_search(**arguments)
            results = result.get("results", [])

            if not results:
                return [TextContent(type="text", text=f"No matches found for pattern: {result['pattern']}")]

            output = f"Blame search results for '{result['pattern']}':\n\n"
            for i, match in enumerate(results[:10], 1):
                output += f"{i}. {match['commit_hash'][:8]} - {match['author']}\n"
                output += f"   Date: {match['commit_date']}\n"
                output += f"   Message: {match['commit_message'][:60]}\n"
                output += f"   Relevance: {match['relevance']}\n\n"

            if result["total_matches"] > 10:
                output += f"... and {result['total_matches'] - 10} more matches\n"

            return [TextContent(type="text", text=output)]

        elif name == "get_code_authors":
            result = await memory_server.get_code_authors(**arguments)
            authors = result.get("authors", [])

            if not authors:
                return [TextContent(type="text", text=f"No authors found for {result['file_path']}.")]

            output = f"Code authors for {result['file_path']}:\n\n"
            for i, author in enumerate(authors[:10], 1):
                output += f"{i}. {author['author_name']} <{author['author_email']}>\n"
                output += f"   Commits: {author['commit_count']}\n"
                output += f"   Lines: +{author['lines_added']} -{author['lines_deleted']}\n"
                if author.get("first_commit"):
                    output += f"   First: {author['first_commit']}\n"
                if author.get("last_commit"):
                    output += f"   Last: {author['last_commit']}\n"
                output += "\n"

            if len(authors) > 10:
                output += f"... and {len(authors) - 10} more authors\n"

            return [TextContent(type="text", text=output)]

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

        # Call Graph / Structural Query Tools (FEAT-059)
        elif name == "find_callers":
            result = await memory_server.find_callers(
                function_name=arguments["function_name"],
                project_name=arguments.get("project_name"),
                include_indirect=arguments.get("include_indirect", False),
                max_depth=arguments.get("max_depth", 1),
                limit=arguments.get("limit", 50),
            )

            if result["total_count"] == 0:
                return [TextContent(type="text", text=f"No callers found for '{result['function_name']}'")]

            output = f"📞 Found {result['total_count']} caller(s) for '{result['function_name']}':\n\n"

            if result["direct_callers"]:
                output += "Direct Callers:\n"
                for i, caller in enumerate(result["direct_callers"][:10], 1):
                    output += f"{i}. {caller['qualified_name']}\n"
                    output += f"   File: {caller['file_path']}:{caller['line_range']}\n"
                    if caller['is_async']:
                        output += "   [async]\n"
                output += "\n"

            if result.get("indirect_callers"):
                output += f"Indirect Callers (depth {result['max_depth']}):\n"
                for i, caller in enumerate(result["indirect_callers"][:10], 1):
                    output += f"{i}. {caller['qualified_name']}\n"
                    output += f"   File: {caller['file_path']}:{caller['line_range']}\n"

            return [TextContent(type="text", text=output)]

        elif name == "find_callees":
            result = await memory_server.find_callees(
                function_name=arguments["function_name"],
                project_name=arguments.get("project_name"),
                include_indirect=arguments.get("include_indirect", False),
                max_depth=arguments.get("max_depth", 1),
                limit=arguments.get("limit", 50),
            )

            if result["total_count"] == 0:
                return [TextContent(type="text", text=f"No callees found for '{result['function_name']}'")]

            output = f"📞 Found {result['total_count']} callee(s) for '{result['function_name']}':\n\n"

            if result["direct_callees"]:
                output += "Direct Callees:\n"
                for i, callee in enumerate(result["direct_callees"][:10], 1):
                    output += f"{i}. {callee['qualified_name']}\n"
                    output += f"   File: {callee['file_path']}:{callee['line_range']}\n"
                    if callee['is_async']:
                        output += "   [async]\n"
                output += "\n"

            if result.get("indirect_callees"):
                output += f"Indirect Callees (depth {result['max_depth']}):\n"
                for i, callee in enumerate(result["indirect_callees"][:10], 1):
                    output += f"{i}. {callee['qualified_name']}\n"
                    output += f"   File: {callee['file_path']}:{callee['line_range']}\n"

            return [TextContent(type="text", text=output)]

        elif name == "get_call_chain":
            result = await memory_server.get_call_chain(
                from_function=arguments["from_function"],
                to_function=arguments["to_function"],
                project_name=arguments.get("project_name"),
                max_paths=arguments.get("max_paths", 5),
                max_depth=arguments.get("max_depth", 10),
            )

            if result["path_count"] == 0:
                return [TextContent(type="text", text=f"No call path found from '{result['from_function']}' to '{result['to_function']}'")]

            output = f"🔗 Found {result['path_count']} call path(s) from '{result['from_function']}' to '{result['to_function']}':\n\n"

            for i, path_info in enumerate(result["paths"], 1):
                output += f"Path {i} (length: {path_info['length']}):\n"
                output += "  " + " → ".join(path_info['path']) + "\n\n"

                # Show file locations
                for detail in path_info['details']:
                    output += f"  • {detail['qualified_name']}\n"
                    output += f"    {detail['file_path']}:{detail['line_range']}\n"
                output += "\n"

            return [TextContent(type="text", text=output)]

        elif name == "find_implementations":
            result = await memory_server.find_implementations(
                interface_name=arguments["interface_name"],
                project_name=arguments.get("project_name"),
                language=arguments.get("language"),
                limit=arguments.get("limit", 50),
            )

            if result["total_count"] == 0:
                lang_str = f" in {result['language']}" if result.get('language') else ""
                return [TextContent(type="text", text=f"No implementations found for '{result['interface_name']}'{lang_str}")]

            output = f"🏗️ Found {result['total_count']} implementation(s) of '{result['interface_name']}':\n\n"

            for i, impl in enumerate(result["implementations"], 1):
                output += f"{i}. {impl['implementation_name']} [{impl['language']}]\n"
                output += f"   File: {impl['file_path']}\n"
                output += f"   Methods: {', '.join(impl['methods'][:5])}"
                if len(impl['methods']) > 5:
                    output += f" ... ({impl['method_count']} total)"
                output += "\n\n"

            return [TextContent(type="text", text=output)]

        elif name == "find_dependencies":
            result = await memory_server.find_dependencies(
                file_path=arguments["file_path"],
                project_name=arguments.get("project_name"),
                depth=arguments.get("depth", 1),
                include_transitive=arguments.get("include_transitive", False),
            )

            if result["total_count"] == 0:
                return [TextContent(type="text", text=f"No dependencies found for '{result['file_path']}'")]

            output = f"📦 Found {result['total_count']} dependenc(ies) for '{result['file_path']}':\n\n"

            if result["direct_dependencies"]:
                output += "Direct Dependencies:\n"
                for i, dep in enumerate(result["direct_dependencies"][:15], 1):
                    output += f"{i}. {dep['file_path']}\n"
                    output += f"   Type: {dep['import_type']} | Language: {dep['language']}\n"
                output += "\n"

            if result.get("transitive_dependencies"):
                output += f"Transitive Dependencies (depth {result['max_depth']}):\n"
                for i, dep in enumerate(result["transitive_dependencies"][:15], 1):
                    output += f"{i}. {dep['file_path']} (depth: {dep['depth']})\n"
                    output += f"   Type: {dep['import_type']}\n"

            return [TextContent(type="text", text=output)]

        elif name == "find_dependents":
            result = await memory_server.find_dependents(
                file_path=arguments["file_path"],
                project_name=arguments.get("project_name"),
                depth=arguments.get("depth", 1),
                include_transitive=arguments.get("include_transitive", False),
            )

            if result["total_count"] == 0:
                return [TextContent(type="text", text=f"No dependents found for '{result['file_path']}'")]

            output = f"📦 Found {result['total_count']} dependent(s) on '{result['file_path']}':\n\n"

            if result["direct_dependents"]:
                output += "Direct Dependents:\n"
                for i, dep in enumerate(result["direct_dependents"][:15], 1):
                    output += f"{i}. {dep['file_path']}\n"
                    output += f"   Type: {dep['import_type']} | Language: {dep['language']}\n"
                output += "\n"

            if result.get("transitive_dependents"):
                output += f"Transitive Dependents (depth {result['max_depth']}):\n"
                for i, dep in enumerate(result["transitive_dependents"][:15], 1):
                    output += f"{i}. {dep['file_path']} (depth: {dep['depth']})\n"
                    output += f"   Type: {dep['import_type']}\n"

            return [TextContent(type="text", text=output)]

        # FEAT-020: Usage Pattern Analytics Handlers
        elif name == "get_usage_statistics":
            days = arguments.get("days", 30)
            result = await memory_rag_server.get_usage_statistics(days=days)

            output = f"📊 Usage Statistics (Last {result['period_days']} days)\n\n"
            output += f"**Query Metrics:**\n"
            output += f"  • Total Queries: {result['total_queries']}\n"
            output += f"  • Unique Queries: {result['unique_queries']}\n"
            output += f"  • Avg Query Time: {result['avg_query_time_ms']:.2f}ms\n"
            output += f"  • Avg Results: {result['avg_result_count']:.1f}\n\n"
            output += f"**Code Access Metrics:**\n"
            output += f"  • Total Accesses: {result['total_code_accesses']}\n"
            output += f"  • Unique Files: {result['unique_files']}\n"
            output += f"  • Unique Functions: {result['unique_functions']}\n\n"
            if result['most_active_day']:
                output += f"**Most Active Day:** {result['most_active_day']} "
                output += f"({result['most_active_day_count']} queries)\n"

            return [TextContent(type="text", text=output)]

        elif name == "get_top_queries":
            limit = arguments.get("limit", 10)
            days = arguments.get("days", 30)
            result = await memory_rag_server.get_top_queries(limit=limit, days=days)

            output = f"🔍 Top {result['total_returned']} Queries (Last {result['period_days']} days)\n\n"

            if result['queries']:
                for i, query_stat in enumerate(result['queries'], 1):
                    output += f"{i}. **{query_stat['query']}**\n"
                    output += f"   • Count: {query_stat['count']}\n"
                    output += f"   • Avg Results: {query_stat['avg_result_count']:.1f}\n"
                    output += f"   • Avg Time: {query_stat['avg_execution_time_ms']:.2f}ms\n"
                    output += f"   • Last Used: {query_stat['last_used']}\n\n"
            else:
                output += "No queries found in the specified time period.\n"

            return [TextContent(type="text", text=output)]

        elif name == "get_frequently_accessed_code":
            limit = arguments.get("limit", 10)
            days = arguments.get("days", 30)
            result = await memory_rag_server.get_frequently_accessed_code(
                limit=limit, days=days
            )

            output = f"💻 Top {result['total_returned']} Accessed Code (Last {result['period_days']} days)\n\n"

            if result['code_items']:
                for i, code_stat in enumerate(result['code_items'], 1):
                    output += f"{i}. **{code_stat['file_path']}**"
                    if code_stat['function_name']:
                        output += f" :: {code_stat['function_name']}"
                    output += f"\n"
                    output += f"   • Access Count: {code_stat['access_count']}\n"
                    output += f"   • Last Accessed: {code_stat['last_accessed']}\n\n"
            else:
                output += "No code access records found in the specified time period.\n"

            return [TextContent(type="text", text=output)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except ValidationError as e:
        """Catch validation errors and preserve error code and solution."""
        logger.exception(f"Validation error in tool call: {name}")
        error_msg = f"[{e.error_code}] Validation Error: {str(e)}"
        if hasattr(e, 'solution') and e.solution:
            error_msg += f"\n\nSolution: {e.solution}"
        if hasattr(e, 'docs_url') and e.docs_url:
            error_msg += f"\nDocs: {e.docs_url}"
        return [TextContent(type="text", text=error_msg)]

    except StorageError as e:
        """Catch storage errors and preserve error code and solution."""
        logger.exception(f"Storage error in tool call: {name}")
        error_msg = f"[{e.error_code}] Storage Error: {str(e)}"
        if hasattr(e, 'solution') and e.solution:
            error_msg += f"\n\nSolution: {e.solution}"
        if hasattr(e, 'docs_url') and e.docs_url:
            error_msg += f"\nDocs: {e.docs_url}"
        return [TextContent(type="text", text=error_msg)]

    except RetrievalError as e:
        """Catch retrieval errors and preserve error code and solution."""
        logger.exception(f"Retrieval error in tool call: {name}")
        error_msg = f"[{e.error_code}] Retrieval Error: {str(e)}"
        if hasattr(e, 'solution') and e.solution:
            error_msg += f"\n\nSolution: {e.solution}"
        if hasattr(e, 'docs_url') and e.docs_url:
            error_msg += f"\nDocs: {e.docs_url}"
        return [TextContent(type="text", text=error_msg)]

    except EmbeddingError as e:
        """Catch embedding errors and preserve error code and solution."""
        logger.exception(f"Embedding error in tool call: {name}")
        error_msg = f"[{e.error_code}] Embedding Error: {str(e)}"
        if hasattr(e, 'solution') and e.solution:
            error_msg += f"\n\nSolution: {e.solution}"
        if hasattr(e, 'docs_url') and e.docs_url:
            error_msg += f"\nDocs: {e.docs_url}"
        return [TextContent(type="text", text=error_msg)]

    except MemoryRAGError as e:
        """Catch other MemoryRAG errors and preserve error code and solution."""
        logger.exception(f"MemoryRAG error in tool call: {name}")
        error_msg = f"[{e.error_code}] Error: {str(e)}"
        if hasattr(e, 'solution') and e.solution:
            error_msg += f"\n\nSolution: {e.solution}"
        if hasattr(e, 'docs_url') and e.docs_url:
            error_msg += f"\nDocs: {e.docs_url}"
        return [TextContent(type="text", text=error_msg)]

    except Exception as e:
        """Catch all remaining exceptions as fallback."""
        logger.exception(f"Unexpected error handling tool call: {name}")
        return [TextContent(type="text", text=f"Unexpected Error: {str(e)}")]


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
            # Test a simple operation - get all projects
            await memory_server.store.get_all_projects()
            logger.info(f"✓ {config.storage_backend.upper()} connection successful")
        except Exception as e:
            logger.error(f"✗ {config.storage_backend.upper()} connection failed: {e}")
            logger.error("  → Try: docker-compose up -d")
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

    # PERF-009: Set bounded default executor for asyncio.to_thread() calls
    # Without this, the default ThreadPoolExecutor grows unbounded, causing
    # virtual memory to balloon (each thread reserves ~8MB stack space on macOS).
    # Limit to 8 workers to cap memory usage while allowing reasonable concurrency.
    from concurrent.futures import ThreadPoolExecutor
    default_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="mcp_async_")
    asyncio.get_event_loop().set_default_executor(default_executor)
    logger.info("PERF-009: Set bounded default executor (max_workers=8)")

    # Initialize the modern server
    config = get_config()
    memory_server = MemoryRAGServer(config)

    # Fast initialization - defer expensive operations until after MCP is listening
    await memory_server.initialize(defer_preload=True, defer_auto_index=True)

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

                    # Start deferred auto-indexing (runs in background, non-blocking)
                    try:
                        await memory_server.start_deferred_auto_indexing()
                    except Exception as e:
                        logger.warning(f"Background: Auto-indexing failed: {e}")
                except Exception as e:
                    logger.error(f"Background initialization error: {e}")

            # Start background initialization (don't await - let it run in parallel)
            # Store the task reference for proper error handling and cleanup (BUG-056)
            global _init_task
            _init_task = asyncio.create_task(complete_initialization())

            # Add error callback to log exceptions from the background task
            def _on_init_task_done(task: asyncio.Task) -> None:
                """Log any exceptions that occur in the background initialization task."""
                if task.cancelled():
                    logger.info("Background initialization task was cancelled")
                    return

                try:
                    task.result()
                except Exception as e:
                    logger.error(f"Background initialization task failed with exception: {e}", exc_info=True)

            _init_task.add_done_callback(_on_init_task_done)

            # Start serving MCP requests immediately
            await app.run(
                read_stream, write_stream, app.create_initialization_options()
            )
    finally:
        # Cleanup background initialization task (BUG-056)
        # Note: _init_task already declared global above
        if _init_task and not _init_task.done():
            logger.info("Cancelling background initialization task...")
            _init_task.cancel()
            try:
                await _init_task
            except asyncio.CancelledError:
                logger.info("Background initialization task cancelled successfully")

        # Cleanup server
        await memory_server.close()
        # PERF-009: Shutdown the bounded default executor to release threads
        default_executor.shutdown(wait=False)
        logger.info("Server shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
