#!/usr/bin/env python3
"""MCP Server for Claude Memory + RAG system."""

import os
import sys
import asyncio
import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# MCP SDK
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("Error: mcp package not found. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Our components
from database import MemoryDatabase
from embeddings import EmbeddingGenerator
from memory import MemoryManager
from doc_ingestion import DocumentationIngester
from router import SmartRouter


class MemoryRAGServer:
    """MCP Server that provides memory and documentation tools to Claude Code."""

    def __init__(self):
        # Initialize memory directory
        memory_dir = Path.home() / ".claude-rag"
        memory_dir.mkdir(exist_ok=True)

        db_path = memory_dir / "memory.db"

        logger.info("Initializing Claude Memory + RAG Server")
        logger.info(f"Database: {db_path}")

        # Initialize all components
        self.db = MemoryDatabase(str(db_path))
        self.embedder = EmbeddingGenerator()
        self.project_name = self._detect_project()
        self.memory_manager = MemoryManager(self.db, self.embedder, self.project_name)
        self.doc_ingester = DocumentationIngester(self.db, self.embedder)
        self.router = SmartRouter()

        logger.info(f"Current project: {self.project_name or 'global'}")

    def _detect_project(self) -> Optional[str]:
        """Detect current project from git repository."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--show-toplevel'],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                project_path = result.stdout.strip()
                return Path(project_path).name
        except subprocess.TimeoutExpired:
            logger.warning("Git command timed out while detecting project")
        except FileNotFoundError:
            logger.debug("Git command not found")
        except Exception as e:
            logger.debug(f"Failed to detect git project: {e}")
        return None

    async def store_memory(
        self,
        content: str,
        category: str,
        importance: float = 0.5,
        scope: Optional[str] = None
    ) -> Dict[str, Any]:
        """Store a memory."""
        # Determine scope if not provided
        if scope is None:
            # Auto-determine: preferences/workflows � global, others � project
            if category in ['preference', 'workflow']:
                scope = 'global'
            else:
                scope = 'project' if self.project_name else 'global'

        project_name = self.project_name if scope == 'project' else None

        # Generate embedding
        embedding = self.embedder.generate(content)

        # Extract tags
        tags = self.memory_manager._extract_tags(content)

        # Store in database
        memory_id = self.db.store_memory(
            content=content,
            category=category,
            memory_type='memory',
            scope=scope,
            project_name=project_name,
            embedding=embedding,
            tags=tags,
            importance=importance
        )

        return {
            "memory_id": memory_id,
            "content": content,
            "category": category,
            "scope": scope,
            "project_name": project_name,
            "importance": importance,
            "tags": tags
        }

    async def retrieve_memories(
        self,
        query: str,
        limit: int = 10,
        include_docs: bool = True
    ) -> List[Dict]:
        """Retrieve relevant memories and/or docs using smart routing."""
        if include_docs:
            # Use smart routing
            results = self.router.route_query(
                query,
                self.db,
                self.embedder,
                limit,
                self.project_name
            )
        else:
            # Memories only
            query_embedding = self.embedder.generate(query)
            results = self.db.retrieve_similar_memories(
                query_embedding,
                limit=limit,
                filters={'memory_type': 'memory'},
                min_importance=0.2
            )

        return results

    async def search_all(
        self,
        query: str,
        limit: int = 20,
        filter_type: Optional[str] = None
    ) -> List[Dict]:
        """Explicit search across all content."""
        query_embedding = self.embedder.generate(query)

        filters = {}
        if filter_type:
            filters['memory_type'] = filter_type

        return self.db.retrieve_similar_memories(
            query_embedding,
            limit=limit,
            filters=filters,
            min_importance=0.0
        )

    async def ingest_docs(
        self,
        path: str = ".",
        patterns: Optional[List[str]] = None,
        recursive: bool = True,
        force: bool = False
    ) -> Dict:
        """Ingest documentation from directory."""
        if patterns is None:
            patterns = ["*.md", "README.md", "docs/**/*.md"]

        project_name = self.project_name or "global"

        result = self.doc_ingester.ingest_directory(
            path=path,
            project_name=project_name,
            patterns=patterns,
            recursive=recursive,
            force=force
        )

        return result

    async def delete_memory(self, memory_id: int) -> Dict[str, Any]:
        """Delete a memory by ID."""
        success = self.db.delete_memory(memory_id)
        return {
            "success": success,
            "memory_id": memory_id,
            "message": f"Memory {memory_id} deleted" if success else f"Memory {memory_id} not found"
        }

    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about stored memories and docs."""
        stats = self.db.get_stats()
        stats['current_project'] = self.project_name
        return stats

    async def show_context(self, query: str = "") -> Dict[str, Any]:
        """Show what memories/docs would be retrieved for a query."""
        if query:
            results = await self.retrieve_memories(query, limit=10)
        else:
            results = self.db.get_recent_memories(limit=5, hours=24)

        formatted = self.router.format_results(results)

        return {
            "results": results,
            "formatted": formatted,
            "count": len(results)
        }

    async def search_code(
        self,
        query: str,
        project_name: Optional[str] = None,
        limit: int = 5,
        file_pattern: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Search indexed code semantically.

        This uses the new architecture from src/core/server.py
        """
        from src.core.server import MemoryRAGServer as NewServer
        from src.config import get_config

        # Create new server instance
        config = get_config()
        new_server = NewServer(config)
        await new_server.initialize()

        try:
            result = await new_server.search_code(
                query=query,
                project_name=project_name,
                limit=limit,
                file_pattern=file_pattern,
                language=language,
            )
            return result
        finally:
            await new_server.close()

    async def index_codebase(
        self,
        directory_path: str,
        project_name: Optional[str] = None,
        recursive: bool = True,
    ) -> Dict[str, Any]:
        """
        Index a codebase directory for semantic code search.

        This uses the new architecture from src/core/server.py
        """
        from src.core.server import MemoryRAGServer as NewServer
        from src.config import get_config

        # Create new server instance
        config = get_config()
        new_server = NewServer(config)
        await new_server.initialize()

        try:
            result = await new_server.index_codebase(
                directory_path=directory_path,
                project_name=project_name,
                recursive=recursive,
            )
            return result
        finally:
            await new_server.close()

    async def find_similar_code(
        self,
        code_snippet: str,
        project_name: Optional[str] = None,
        limit: int = 10,
        file_pattern: Optional[str] = None,
        language: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Find similar code snippets in the indexed codebase.

        This uses the new architecture from src/core/server.py
        """
        from src.core.server import MemoryRAGServer as NewServer
        from src.config import get_config

        # Create new server instance
        config = get_config()
        new_server = NewServer(config)
        await new_server.initialize()

        try:
            result = await new_server.find_similar_code(
                code_snippet=code_snippet,
                project_name=project_name,
                limit=limit,
                file_pattern=file_pattern,
                language=language,
            )
            return result
        finally:
            await new_server.close()

    async def search_all_projects(
        self,
        query: str,
        limit: int = 10,
        file_pattern: Optional[str] = None,
        language: Optional[str] = None,
        search_mode: str = "semantic",
    ) -> Dict[str, Any]:
        """
        Search code across all opted-in projects.

        This uses the new architecture from src/core/server.py
        """
        from src.core.server import MemoryRAGServer as NewServer
        from src.config import get_config

        # Create new server instance
        config = get_config()
        new_server = NewServer(config)
        await new_server.initialize()

        try:
            result = await new_server.search_all_projects(
                query=query,
                limit=limit,
                file_pattern=file_pattern,
                language=language,
                search_mode=search_mode,
            )
            return result
        finally:
            await new_server.close()

    async def opt_in_cross_project(self, project_name: str) -> Dict[str, Any]:
        """Opt in a project for cross-project search."""
        from src.core.server import MemoryRAGServer as NewServer
        from src.config import get_config

        config = get_config()
        new_server = NewServer(config)
        await new_server.initialize()

        try:
            if new_server.cross_project_consent:
                new_server.cross_project_consent.opt_in_project(project_name)
                return {
                    "status": "success",
                    "message": f"Project '{project_name}' opted in for cross-project search",
                    "opted_in_projects": list(new_server.cross_project_consent.get_opted_in_projects())
                }
            else:
                return {
                    "status": "disabled",
                    "message": "Cross-project search is disabled in configuration"
                }
        finally:
            await new_server.close()

    async def opt_out_cross_project(self, project_name: str) -> Dict[str, Any]:
        """Opt out a project from cross-project search."""
        from src.core.server import MemoryRAGServer as NewServer
        from src.config import get_config

        config = get_config()
        new_server = NewServer(config)
        await new_server.initialize()

        try:
            if new_server.cross_project_consent:
                new_server.cross_project_consent.opt_out_project(project_name)
                return {
                    "status": "success",
                    "message": f"Project '{project_name}' opted out from cross-project search",
                    "opted_in_projects": list(new_server.cross_project_consent.get_opted_in_projects())
                }
            else:
                return {
                    "status": "disabled",
                    "message": "Cross-project search is disabled in configuration"
                }
        finally:
            await new_server.close()

    async def list_opted_in_projects(self) -> Dict[str, Any]:
        """List all projects opted in for cross-project search."""
        from src.core.server import MemoryRAGServer as NewServer
        from src.config import get_config

        config = get_config()
        new_server = NewServer(config)
        await new_server.initialize()

        try:
            if new_server.cross_project_consent:
                opted_in = new_server.cross_project_consent.get_opted_in_projects()
                return {
                    "status": "success",
                    "opted_in_projects": list(opted_in),
                    "count": len(opted_in)
                }
            else:
                return {
                    "status": "disabled",
                    "message": "Cross-project search is disabled in configuration",
                    "opted_in_projects": [],
                    "count": 0
                }
        finally:
            await new_server.close()


# Initialize MCP server
app = Server("claude-memory-rag")
memory_rag_server = MemoryRAGServer()


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available memory and documentation tools."""
    return [
        Tool(
            name="store_memory",
            description="Store a memory (preference, fact, event, workflow, or context). Automatically detects if global or project-specific.",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The memory content to store"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["preference", "fact", "event", "workflow", "context"],
                        "description": "Type of memory"
                    },
                    "importance": {
                        "type": "number",
                        "description": "Importance score 0.0-1.0 (default: 0.5)",
                        "minimum": 0.0,
                        "maximum": 1.0
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["global", "project"],
                        "description": "Memory scope (auto-detected if omitted)"
                    }
                },
                "required": ["content", "category"]
            }
        ),
        Tool(
            name="retrieve_memories",
            description="Retrieve relevant memories and/or documentation using smart routing. Automatically determines if query is personal or technical.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum results (default: 10)"
                    },
                    "include_docs": {
                        "type": "boolean",
                        "description": "Include documentation in search (default: true)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="ingest_docs",
            description="Ingest markdown documentation from the current directory or specified path. Scans for README, *.md files, and docs/ folder.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory to scan (default: current directory)"
                    },
                    "patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Glob patterns for files (default: ['*.md', 'README.md', 'docs/**/*.md'])"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Scan subdirectories (default: true)"
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force re-ingestion of unchanged files (default: false)"
                    }
                }
            }
        ),
        Tool(
            name="search_all",
            description="Search all memories and documentation explicitly (bypasses smart routing).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum results (default: 20)"
                    },
                    "filter_type": {
                        "type": "string",
                        "enum": ["memory", "documentation"],
                        "description": "Filter by type (optional)"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="delete_memory",
            description="Delete a memory or documentation entry by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "number",
                        "description": "ID of the memory to delete"
                    }
                },
                "required": ["memory_id"]
            }
        ),
        Tool(
            name="list_memories",
            description="List and browse memories with filtering, sorting, and pagination. Useful for seeing what memories exist without searching.",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["preference", "fact", "event", "workflow", "context"],
                        "description": "Filter by category (optional)"
                    },
                    "context_level": {
                        "type": "string",
                        "enum": ["USER_PREFERENCE", "PROJECT_CONTEXT", "SESSION_STATE"],
                        "description": "Filter by context level (optional)"
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["global", "project"],
                        "description": "Filter by scope (optional)"
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Filter by project name (optional)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags - matches ANY tag (optional)"
                    },
                    "min_importance": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Minimum importance (default: 0.0)"
                    },
                    "max_importance": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Maximum importance (default: 1.0)"
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Filter created_at >= date (ISO format, e.g., '2025-01-01T00:00:00') (optional)"
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Filter created_at <= date (ISO format) (optional)"
                    },
                    "sort_by": {
                        "type": "string",
                        "enum": ["created_at", "updated_at", "importance"],
                        "description": "Sort field (default: created_at)"
                    },
                    "sort_order": {
                        "type": "string",
                        "enum": ["asc", "desc"],
                        "description": "Sort order (default: desc)"
                    },
                    "limit": {
                        "type": "number",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Max results to return (default: 20)"
                    },
                    "offset": {
                        "type": "number",
                        "minimum": 0,
                        "description": "Results to skip for pagination (default: 0)"
                    }
                }
            }
        ),
        Tool(
            name="export_memories",
            description="Export memories to JSON or Markdown format with optional filtering. Supports file output or returns content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "File path to write export (optional, if omitted returns content as string)"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["json", "markdown"],
                        "description": "Export format (default: json)"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["preference", "fact", "event", "workflow", "context"],
                        "description": "Filter by category (optional)"
                    },
                    "context_level": {
                        "type": "string",
                        "enum": ["USER_PREFERENCE", "PROJECT_CONTEXT", "SESSION_STATE"],
                        "description": "Filter by context level (optional)"
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["global", "project"],
                        "description": "Filter by scope (optional)"
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Filter by project name (optional)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by tags (optional)"
                    },
                    "min_importance": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Minimum importance (default: 0.0)"
                    },
                    "max_importance": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Maximum importance (default: 1.0)"
                    },
                    "date_from": {
                        "type": "string",
                        "description": "Filter created_at >= date (ISO format) (optional)"
                    },
                    "date_to": {
                        "type": "string",
                        "description": "Filter created_at <= date (ISO format) (optional)"
                    }
                }
            }
        ),
        Tool(
            name="import_memories",
            description="Import memories from JSON file with conflict resolution (skip, overwrite, or merge existing memories).",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to JSON file to import"
                    },
                    "conflict_mode": {
                        "type": "string",
                        "enum": ["skip", "overwrite", "merge"],
                        "description": "How to handle existing memories: skip (keep existing), overwrite (replace), merge (update non-null fields) (default: skip)"
                    },
                    "format": {
                        "type": "string",
                        "enum": ["json"],
                        "description": "File format (auto-detected from extension if not provided)"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="get_stats",
            description="Get statistics about stored memories and documentation.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="show_context",
            description="Show what memories/docs are currently being used (for debugging).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optional query to test retrieval"
                    }
                }
            }
        ),
        Tool(
            name="search_code",
            description="Search indexed code semantically. Searches through functions and classes to find relevant code snippets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'authentication logic', 'database connection')"
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Optional project name filter (uses current project if not specified)"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results (default: 5)"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Optional file path pattern filter (e.g., '*/auth/*')"
                    },
                    "language": {
                        "type": "string",
                        "description": "Optional language filter (e.g., 'python', 'javascript')"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="index_codebase",
            description="Index a codebase directory for semantic code search. Parses all supported source files and extracts functions/classes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "Path to directory to index"
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Project name for scoping (uses directory name if not specified)"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to recursively index subdirectories (default: true)"
                    }
                },
                "required": ["directory_path"]
            }
        ),
        Tool(
            name="find_similar_code",
            description="Find similar code snippets in the indexed codebase. Useful for finding duplicates, similar implementations, or code patterns.",
            inputSchema={
                "type": "object",
                "properties": {
                    "code_snippet": {
                        "type": "string",
                        "description": "The code snippet to find similar matches for"
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Optional project name filter (uses current project if not specified)"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results (default: 10)"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Optional file path pattern filter (e.g., '*/auth/*')"
                    },
                    "language": {
                        "type": "string",
                        "description": "Optional language filter (e.g., 'python', 'javascript')"
                    }
                },
                "required": ["code_snippet"]
            }
        ),
        Tool(
            name="search_all_projects",
            description="Search code across all opted-in projects. Finds similar implementations across your codebase for learning and code reuse.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'authentication logic', 'database connection')"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of results across all projects (default: 10)"
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Optional file path pattern filter (e.g., '*/auth/*')"
                    },
                    "language": {
                        "type": "string",
                        "description": "Optional language filter (e.g., 'python', 'javascript')"
                    },
                    "search_mode": {
                        "type": "string",
                        "description": "Search mode: 'semantic', 'keyword', or 'hybrid' (default: 'semantic')"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="opt_in_cross_project",
            description="Opt in a project for cross-project search. Required for privacy-respecting cross-project learning.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project name to opt in for cross-project search"
                    }
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="opt_out_cross_project",
            description="Opt out a project from cross-project search.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "Project name to opt out from cross-project search"
                    }
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="list_opted_in_projects",
            description="List all projects that are opted in for cross-project search.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""
    try:
        if name == "store_memory":
            result = await memory_rag_server.store_memory(
                content=arguments["content"],
                category=arguments["category"],
                importance=arguments.get("importance", 0.5),
                scope=arguments.get("scope")
            )
            return [TextContent(
                type="text",
                text=f" Stored {result['category']} memory (ID: {result['memory_id']})\n"
                     f"Scope: {result['scope']}\n"
                     f"Project: {result['project_name'] or 'global'}\n"
                     f"Importance: {result['importance']}\n"
                     f"Content: {result['content']}\n"
                     f"Tags: {', '.join(result['tags'])}"
            )]

        elif name == "retrieve_memories":
            results = await memory_rag_server.retrieve_memories(
                query=arguments["query"],
                limit=arguments.get("limit", 10),
                include_docs=arguments.get("include_docs", True)
            )

            if not results:
                return [TextContent(type="text", text="No relevant information found.")]

            formatted = memory_rag_server.router.format_results(results)
            return [TextContent(type="text", text=f"Found {len(results)} results:\n\n{formatted}")]

        elif name == "ingest_docs":
            result = await memory_rag_server.ingest_docs(
                path=arguments.get("path", "."),
                patterns=arguments.get("patterns"),
                recursive=arguments.get("recursive", True),
                force=arguments.get("force", False)
            )

            output = f" Documentation Ingestion Complete\n\n"
            output += f"Files processed: {result['files_processed']}\n"
            output += f"Total chunks created: {result['total_chunks']}\n"
            output += f"Skipped (unchanged): {result['skipped']}\n"

            if result['errors']:
                output += f"\nErrors:\n"
                for error in result['errors']:
                    output += f"  - {error}\n"

            return [TextContent(type="text", text=output)]

        elif name == "search_all":
            results = await memory_rag_server.search_all(
                query=arguments["query"],
                limit=arguments.get("limit", 20),
                filter_type=arguments.get("filter_type")
            )

            if not results:
                return [TextContent(type="text", text="No results found.")]

            formatted = memory_rag_server.router.format_results(results)
            return [TextContent(type="text", text=f"Search results ({len(results)}):\n\n{formatted}")]

        elif name == "delete_memory":
            result = await memory_rag_server.delete_memory(
                memory_id=int(arguments["memory_id"])
            )

            if result["success"]:
                return [TextContent(type="text", text=f" {result['message']}")]
            else:
                return [TextContent(type="text", text=f" {result['message']}")]

        elif name == "get_memory_by_id":
            from src.core.server import MemoryRAGServer as NewServer
            from src.config import get_config

            config = get_config()
            new_server = NewServer(config)
            await new_server.initialize()

            try:
                result = await new_server.get_memory_by_id(
                    memory_id=arguments["memory_id"]
                )

                if result["status"] == "not_found":
                    return [TextContent(type="text", text=f"Memory not found: {result['message']}")]

                memory = result["memory"]
                output = f"Memory Retrieved\n\n"
                output += f"**ID:** {memory['id']}\n"
                output += f"**Content:** {memory['content']}\n"
                output += f"**Category:** {memory['category']}\n"
                output += f"**Context Level:** {memory['context_level']}\n"
                output += f"**Scope:** {memory['scope']}\n"
                if memory.get('project_name'):
                    output += f"**Project:** {memory['project_name']}\n"
                output += f"**Importance:** {memory['importance']}\n"
                output += f"**Created:** {memory['created_at']}\n"
                output += f"**Updated:** {memory['updated_at']}\n"
                if memory.get('tags'):
                    output += f"**Tags:** {', '.join(memory['tags'])}\n"
                if memory.get('metadata'):
                    output += f"**Metadata:** {memory['metadata']}\n"

                return [TextContent(type="text", text=output)]
            finally:
                await new_server.close()

        elif name == "update_memory":
            from src.core.server import MemoryRAGServer as NewServer
            from src.config import get_config

            config = get_config()
            new_server = NewServer(config)
            await new_server.initialize()

            try:
                result = await new_server.update_memory(
                    memory_id=arguments["memory_id"],
                    content=arguments.get("content"),
                    category=arguments.get("category"),
                    importance=arguments.get("importance"),
                    tags=arguments.get("tags"),
                    metadata=arguments.get("metadata"),
                    context_level=arguments.get("context_level"),
                    preserve_timestamps=arguments.get("preserve_timestamps", True),
                    regenerate_embedding=arguments.get("regenerate_embedding", True),
                )

                if result["status"] == "not_found":
                    return [TextContent(type="text", text=f"Memory not found: {result['message']}")]

                output = f"Memory Updated\n\n"
                output += f"**Memory ID:** {result['memory_id']}\n"
                output += f"**Updated Fields:** {', '.join(result['updated_fields'])}\n"
                output += f"**Embedding Regenerated:** {'Yes' if result['embedding_regenerated'] else 'No'}\n"
                output += f"**Updated At:** {result['updated_at']}\n"

                return [TextContent(type="text", text=output)]
            finally:
                await new_server.close()


        elif name == "list_memories":
            result = await memory_rag_server.list_memories(
                category=arguments.get("category"),
                context_level=arguments.get("context_level"),
                scope=arguments.get("scope"),
                project_name=arguments.get("project_name"),
                tags=arguments.get("tags"),
                min_importance=arguments.get("min_importance", 0.0),
                max_importance=arguments.get("max_importance", 1.0),
                date_from=arguments.get("date_from"),
                date_to=arguments.get("date_to"),
                sort_by=arguments.get("sort_by", "created_at"),
                sort_order=arguments.get("sort_order", "desc"),
                limit=arguments.get("limit", 20),
                offset=arguments.get("offset", 0)
            )

            memories = result["memories"]
            total = result["total_count"]
            returned = result["returned_count"]
            has_more = result["has_more"]

            if returned == 0:
                output = "No memories found matching the criteria.\n"
            else:
                output = f"Found {total} total memories (showing {returned})\n\n"

                for i, mem in enumerate(memories, 1):
                    output += f"{i}. [{mem['category']}] {mem['content'][:100]}...\n"
                    output += f"   ID: {mem['memory_id']} | Importance: {mem['importance']:.2f}\n"
                    output += f"   Created: {mem['created_at']}\n"
                    if mem.get('tags'):
                        output += f"   Tags: {', '.join(mem['tags'])}\n"
                    output += "\n"

                if has_more:
                    next_offset = result["offset"] + returned
                    output += f"More results available. Use offset={next_offset} to see next page.\n"

            return [TextContent(type="text", text=output)]

        elif name == "export_memories":
            result = await memory_rag_server.export_memories(
                output_path=arguments.get("output_path"),
                format=arguments.get("format", "json"),
                category=arguments.get("category"),
                context_level=arguments.get("context_level"),
                scope=arguments.get("scope"),
                project_name=arguments.get("project_name"),
                tags=arguments.get("tags"),
                min_importance=arguments.get("min_importance", 0.0),
                max_importance=arguments.get("max_importance", 1.0),
                date_from=arguments.get("date_from"),
                date_to=arguments.get("date_to")
            )

            output = f"✅ Export Complete\n\n"
            output += f"**Format:** {result['format']}\n"
            output += f"**Memories Exported:** {result['count']}\n"

            if "file_path" in result:
                output += f"**File Path:** {result['file_path']}\n"
            else:
                output += f"\n**Content Preview:**\n```\n{result['content'][:500]}...\n```\n"

            return [TextContent(type="text", text=output)]

        elif name == "import_memories":
            result = await memory_rag_server.import_memories(
                file_path=arguments.get("file_path"),
                conflict_mode=arguments.get("conflict_mode", "skip"),
                format=arguments.get("format")
            )

            status_emoji = "✅" if result["status"] == "success" else "⚠️"
            output = f"{status_emoji} Import Complete\n\n"
            output += f"**Status:** {result['status']}\n"
            output += f"**Total Processed:** {result['total_processed']}\n"
            output += f"**Created:** {result['created']}\n"
            output += f"**Updated:** {result['updated']}\n"
            output += f"**Skipped:** {result['skipped']}\n"

            if result.get("errors"):
                output += f"\n**Errors ({len(result['errors'])}):**\n"
                for error in result['errors'][:10]:  # Show first 10 errors
                    output += f"  - {error}\n"
                if len(result['errors']) > 10:
                    output += f"  ... and {len(result['errors']) - 10} more errors\n"

            return [TextContent(type="text", text=output)]

        elif name == "get_stats":
            stats = await memory_rag_server.get_stats()

            output = "Memory & Documentation Statistics:\n\n"
            output += f"Total entries: {stats['total']}\n\n"

            output += "By type:\n"
            for type_name, count in stats.get('by_type', {}).items():
                output += f"  - {type_name}: {count}\n"

            output += "\nBy category:\n"
            for cat, count in stats.get('by_category', {}).items():
                output += f"  - {cat}: {count}\n"

            output += "\nBy scope:\n"
            for scope, count in stats.get('by_scope', {}).items():
                output += f"  - {scope}: {count}\n"

            if stats.get('by_project'):
                output += "\nBy project:\n"
                for proj, count in stats['by_project'].items():
                    output += f"  - {proj}: {count}\n"

            output += f"\nCurrent project: {stats['current_project'] or 'none (global)'}"

            return [TextContent(type="text", text=output)]

        elif name == "show_context":
            context = await memory_rag_server.show_context(
                query=arguments.get("query", "")
            )

            output = f"Current Context ({context['count']} entries):\n\n"
            output += context['formatted']

            return [TextContent(type="text", text=output)]

        elif name == "search_code":
            results = await memory_rag_server.search_code(
                query=arguments["query"],
                project_name=arguments.get("project_name"),
                limit=arguments.get("limit", 5),
                file_pattern=arguments.get("file_pattern"),
                language=arguments.get("language")
            )

            if not results["results"]:
                return [TextContent(type="text", text="No code found matching your query.")]

            output = f"✅ Code Search Results ({results['total_found']} found)\n\n"
            output += f"Query: '{results['query']}'\n"
            output += f"Project: {results['project_name']}\n"
            output += f"Search time: {results['query_time_ms']:.2f}ms\n\n"

            for i, result in enumerate(results["results"], 1):
                output += f"## {i}. {result['unit_name']} ({result['unit_type']})\n\n"
                output += f"**File:** `{result['file_path']}`:{result['start_line']}-{result['end_line']}\n"
                output += f"**Language:** {result['language']}\n"
                output += f"**Relevance:** {result['relevance_score']:.2%}\n\n"
                if result['signature']:
                    output += f"**Signature:**\n```{result['language']}\n{result['signature']}\n```\n\n"
                output += f"**Code:**\n```{result['language']}\n{result['code']}\n```\n\n"
                output += "---\n\n"

            return [TextContent(type="text", text=output)]

        elif name == "index_codebase":
            result = await memory_rag_server.index_codebase(
                directory_path=arguments["directory_path"],
                project_name=arguments.get("project_name"),
                recursive=arguments.get("recursive", True)
            )

            output = f"✅ Codebase Indexing Complete\n\n"
            output += f"Project: {result['project_name']}\n"
            output += f"Directory: {result['directory']}\n"
            output += f"Files indexed: {result['files_indexed']}\n"
            output += f"Semantic units: {result['units_indexed']}\n"
            output += f"Total time: {result['total_time_s']:.2f}s\n"

            if result.get('languages'):
                output += f"\nLanguages:\n"
                for lang, count in result['languages'].items():
                    output += f"  - {lang}: {count} files\n"

            return [TextContent(type="text", text=output)]

        elif name == "find_similar_code":
            result = await memory_rag_server.find_similar_code(
                code_snippet=arguments["code_snippet"],
                project_name=arguments.get("project_name"),
                limit=arguments.get("limit", 10),
                file_pattern=arguments.get("file_pattern"),
                language=arguments.get("language")
            )

            if not result["results"]:
                output = f"No similar code found.\n\n"
                output += f"{result['interpretation']}\n\n"
                output += "Suggestions:\n"
                for suggestion in result["suggestions"]:
                    output += f"  - {suggestion}\n"
                return [TextContent(type="text", text=output)]

            output = f"✅ Similar Code Found ({result['total_found']} results)\n\n"
            output += f"Project: {result['project_name']}\n"
            output += f"Code snippet length: {result['code_snippet_length']} chars\n"
            output += f"Search time: {result['query_time_ms']:.2f}ms\n\n"
            output += f"{result['interpretation']}\n\n"

            for i, code in enumerate(result["results"], 1):
                output += f"## {i}. {code['unit_name']} ({code['unit_type']})\n\n"
                output += f"**File:** `{code['file_path']}`:{code['start_line']}-{code['end_line']}\n"
                output += f"**Language:** {code['language']}\n"
                output += f"**Similarity:** {code['similarity_score']:.2%}\n\n"
                if code['signature']:
                    output += f"**Signature:**\n```{code['language']}\n{code['signature']}\n```\n\n"
                output += f"**Code:**\n```{code['language']}\n{code['code']}\n```\n\n"
                output += "---\n\n"

            if result["suggestions"]:
                output += "\nSuggestions:\n"
                for suggestion in result["suggestions"]:
                    output += f"  - {suggestion}\n"

            return [TextContent(type="text", text=output)]

        elif name == "search_all_projects":
            result = await memory_rag_server.search_all_projects(
                query=arguments["query"],
                limit=arguments.get("limit", 10),
                file_pattern=arguments.get("file_pattern"),
                language=arguments.get("language"),
                search_mode=arguments.get("search_mode", "semantic")
            )

            if not result["results"]:
                output = f"No results found.\n\n"
                output += f"{result['interpretation']}\n\n"
                output += "Suggestions:\n"
                for suggestion in result["suggestions"]:
                    output += f"  - {suggestion}\n"
                return [TextContent(type="text", text=output)]

            output = f"✅ Cross-Project Search Results ({result['total_found']} found)\n\n"
            output += f"Query: '{result['query']}'\n"
            output += f"Projects searched: {', '.join(result['projects_searched'])}\n"
            output += f"Search time: {result['query_time_ms']:.2f}ms\n\n"
            output += f"{result['interpretation']}\n\n"

            for i, code in enumerate(result["results"], 1):
                output += f"## {i}. {code['unit_name']} ({code['unit_type']})\n\n"
                output += f"**Project:** {code['source_project']}\n"
                output += f"**File:** `{code['file_path']}`:{code['start_line']}-{code['end_line']}\n"
                output += f"**Language:** {code['language']}\n"
                output += f"**Relevance:** {code['relevance_score']:.2%}\n\n"
                if code['signature']:
                    output += f"**Signature:**\n```{code['language']}\n{code['signature']}\n```\n\n"
                output += f"**Code:**\n```{code['language']}\n{code['code']}\n```\n\n"
                output += "---\n\n"

            if result["suggestions"]:
                output += "\nSuggestions:\n"
                for suggestion in result["suggestions"]:
                    output += f"  - {suggestion}\n"

            return [TextContent(type="text", text=output)]

        elif name == "opt_in_cross_project":
            result = await memory_rag_server.opt_in_cross_project(
                project_name=arguments["project_name"]
            )

            if result["status"] == "success":
                output = f"✅ {result['message']}\n\n"
                output += f"Opted-in projects ({len(result['opted_in_projects'])}):\n"
                for project in sorted(result['opted_in_projects']):
                    output += f"  - {project}\n"
            else:
                output = f"⚠️ {result['message']}"

            return [TextContent(type="text", text=output)]

        elif name == "opt_out_cross_project":
            result = await memory_rag_server.opt_out_cross_project(
                project_name=arguments["project_name"]
            )

            if result["status"] == "success":
                output = f"✅ {result['message']}\n\n"
                output += f"Opted-in projects ({len(result['opted_in_projects'])}):\n"
                for project in sorted(result['opted_in_projects']):
                    output += f"  - {project}\n"
            else:
                output = f"⚠️ {result['message']}"

            return [TextContent(type="text", text=output)]

        elif name == "list_opted_in_projects":
            result = await memory_rag_server.list_opted_in_projects()

            if result["status"] == "success":
                output = f"✅ Opted-in Projects ({result['count']})\n\n"
                if result["opted_in_projects"]:
                    for project in sorted(result["opted_in_projects"]):
                        output += f"  - {project}\n"
                else:
                    output += "No projects are currently opted in for cross-project search.\n"
                    output += "Use opt_in_cross_project to enable cross-project search for your projects."
            else:
                output = f"⚠️ {result['message']}"

            return [TextContent(type="text", text=output)]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        return [TextContent(type="text", text=f"Error: {str(e)}\n\n{error_details}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
