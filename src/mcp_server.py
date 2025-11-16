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
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
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
