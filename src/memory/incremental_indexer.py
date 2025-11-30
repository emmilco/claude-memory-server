"""Incremental code indexing using Rust parsing and vector storage."""

import asyncio
import logging
import hashlib
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
from datetime import datetime, UTC

# Rust parser is REQUIRED - no Python fallback (it was broken and returned 0 units)
try:
    from mcp_performance_core import parse_source_file, batch_parse_files, ParseResult, SemanticUnit
    RUST_AVAILABLE = True
except ImportError as e:
    RUST_AVAILABLE = False
    logging.error(
        "Rust parser (mcp_performance_core) is required but not installed.\n"
        "Install with: cd rust_core && maturin build --release && pip install target/wheels/*.whl\n"
        "Code indexing will not work without it."
    )

    # Create stub classes so imports don't fail, but parsing will raise clear errors
    from dataclasses import dataclass

    @dataclass
    class SemanticUnit:
        """Semantic unit (function, class, method)."""
        unit_type: str
        name: str
        signature: str
        start_line: int
        end_line: int
        start_byte: int
        end_byte: int
        content: str
        language: str
        file_path: str

    @dataclass
    class ParseResult:
        """Result of parsing a file."""
        units: List[SemanticUnit]
        parse_time_ms: float
        language: str
        file_path: str

    def parse_source_file(file_path: str, source_code: str) -> ParseResult:
        """Stub that raises clear error when Rust parser is missing."""
        raise ImportError(
            "Rust parser (mcp_performance_core) is required for code indexing.\n"
            "Install with: cd rust_core && maturin build --release && pip install target/wheels/*.whl"
        )

    def batch_parse_files(files: List[Tuple[str, str]]) -> List[ParseResult]:
        """Stub that raises clear error when Rust parser is missing."""
        raise ImportError(
            "Rust parser (mcp_performance_core) is required for code indexing.\n"
            "Install with: cd rust_core && maturin build --release && pip install target/wheels/*.whl"
        )

from src.config import ServerConfig, get_config, DEFAULT_EMBEDDING_DIM
from src.embeddings.generator import EmbeddingGenerator
from src.embeddings.parallel_generator import ParallelEmbeddingGenerator
from src.store.qdrant_store import QdrantMemoryStore
from src.core.models import MemoryCategory, ContextLevel, MemoryScope
from src.core.exceptions import StorageError
from src.memory.import_extractor import ImportExtractor, build_dependency_metadata
from src.store.call_graph_store import QdrantCallGraphStore
from src.analysis.call_extractors import get_call_extractor

logger = logging.getLogger(__name__)


class BaseCodeIndexer(ABC):
    """
    Abstract base class for code indexers.

    This provides a common interface for different code parsing and indexing strategies,
    enabling future support for different languages, parsers, or analysis tools.

    Implementations can use:
    - Different parsers (tree-sitter, AST, LSP)
    - Different languages (Python, JavaScript, Java, Go, Rust, etc.)
    - Different analysis strategies (semantic, AST-based, etc.)
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the indexer (connect to storage, etc.)."""
        pass

    @abstractmethod
    async def index_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Index a single source file.

        Args:
            file_path: Path to source file

        Returns:
            Dict with indexing stats (units_indexed, parse_time_ms, etc.)
        """
        pass

    @abstractmethod
    async def index_directory(
        self,
        dir_path: Path,
        recursive: bool = True,
        show_progress: bool = True,
        max_concurrent: int = 4,
        progress_callback: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        """
        Index all supported files in a directory.

        Args:
            dir_path: Directory to index
            recursive: Recursively index subdirectories
            show_progress: Show progress logging
            max_concurrent: Maximum concurrent indexing tasks
            progress_callback: Optional callback for progress updates

        Returns:
            Dict with indexing stats (total_files, total_units, etc.)
        """
        pass

    @abstractmethod
    async def delete_file_index(self, file_path: Path) -> int:
        """
        Remove all index entries for a deleted file.

        Args:
            file_path: Path to deleted file

        Returns:
            Number of units deleted
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Clean up resources."""
        pass


class IncrementalIndexer(BaseCodeIndexer):
    """
    Incremental code indexer that extracts semantic units and stores them in vector DB.

    Features:
    - Uses Rust tree-sitter parser for fast, accurate parsing
    - Extracts functions and classes as semantic units
    - Generates embeddings for rich semantic search
    - Supports incremental updates (only re-index changed files)
    - Handles deletions (removes stale index entries)
    - Batch processing for efficiency
    """

    # Supported file extensions
    SUPPORTED_EXTENSIONS = {
        ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs",
        ".rb", ".swift", ".kt", ".kts", ".php",
        ".json", ".yaml", ".yml", ".toml",
        ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".hh",
        ".cs", ".sql"
    }

    def __init__(
        self,
        store: Optional[QdrantMemoryStore] = None,
        embedding_generator: Optional[EmbeddingGenerator] = None,
        config: Optional[ServerConfig] = None,
        project_name: Optional[str] = None,
    ):
        """
        Initialize incremental indexer.

        Args:
            store: Vector store for semantic units (defaults to Qdrant)
            embedding_generator: Embedding generator (defaults to configured model)
            config: Server configuration
            project_name: Project name for scoping (defaults to current directory name)
        """
        if not RUST_AVAILABLE and not PYTHON_PARSER_AVAILABLE:
            raise RuntimeError(
                "Neither Rust nor Python parser available. "
                "Install Rust parser: cd rust_core && maturin develop OR "
                "Install Python parser: pip install tree-sitter tree-sitter-languages"
            )

        if config is None:
            config = get_config()

        self.config = config

        # Use factory function to respect config.storage_backend
        if store is None:
            from src.store import create_memory_store
            store = create_memory_store(config=config)

        self.store = store

        # Use parallel embedding generator if enabled, otherwise use standard generator
        if embedding_generator is not None:
            self.embedding_generator = embedding_generator
        elif config.performance.parallel_embeddings:
            logger.info("Using parallel embedding generator for improved throughput")
            self.embedding_generator = ParallelEmbeddingGenerator(config)
        else:
            logger.info("Using standard embedding generator (single-threaded)")
            self.embedding_generator = EmbeddingGenerator(config)

        # Project name for scoping
        self.project_name = project_name or Path.cwd().name

        # Import extractor for dependency tracking
        self.import_extractor = ImportExtractor()

        # Call graph store for call extraction (FEAT-059)
        self.call_graph_store = QdrantCallGraphStore(config)
        logger.info("Call graph store initialized for call extraction")

        # Importance scorer for intelligent code importance (FEAT-049)
        if config.performance.importance_scoring:
            from src.analysis.importance_scorer import ImportanceScorer
            self.importance_scorer = ImportanceScorer(
                complexity_weight=config.importance_complexity_weight,
                usage_weight=config.importance_usage_weight,
                criticality_weight=config.importance_criticality_weight,
            )
            logger.info("Importance scoring enabled for code units")
        else:
            self.importance_scorer = None
            logger.info("Importance scoring disabled (using fixed 0.7)")

        logger.info(f"Incremental indexer initialized for project: {self.project_name}")

    async def initialize(self) -> None:
        """Initialize the indexer (connect to storage, etc.)."""
        await self.store.initialize()

        # Initialize call graph store (FEAT-059)
        await self.call_graph_store.initialize()

        # Initialize embedding generator (especially important for parallel generator)
        if hasattr(self.embedding_generator, 'initialize'):
            await self.embedding_generator.initialize()

        logger.info("Incremental indexer ready")

    async def index_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Index a single source file.

        This will:
        1. Parse the file to extract semantic units (functions, classes)
        2. Generate embeddings for each unit
        3. Delete old units for this file (if any)
        4. Store new units in vector DB

        Args:
            file_path: Path to source file

        Returns:
            Dict with indexing stats (units_indexed, parse_time_ms, etc.)
        """
        file_path = Path(file_path).resolve()

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if file_path.suffix not in self.SUPPORTED_EXTENSIONS:
            logger.debug(f"Skipping unsupported file: {file_path}")
            return {"units_indexed": 0, "skipped": True}

        try:
            # Step 1: Parse file with Rust
            logger.debug(f"Parsing file: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()

            parse_result = parse_source_file(str(file_path), source_code)
            logger.debug(f"Parsed {len(parse_result.units)} units in {parse_result.parse_time_ms:.2f}ms")

            # Extract imports for dependency tracking
            imports = self.import_extractor.extract_imports(
                str(file_path),
                source_code,
                parse_result.language
            )
            import_metadata = build_dependency_metadata(imports)
            logger.debug(f"Extracted {len(imports)} imports from {file_path.name}")

            # Extract function calls for call graph (FEAT-059)
            call_extractor = get_call_extractor(parse_result.language)
            if call_extractor:
                try:
                    call_sites = call_extractor.extract_calls(
                        str(file_path),
                        source_code,
                        parse_result
                    )
                    implementations = call_extractor.extract_implementations(
                        str(file_path),
                        source_code
                    )
                    logger.debug(f"Extracted {len(call_sites)} call sites and {len(implementations)} implementations from {file_path.name}")
                except Exception as e:
                    logger.warning(f"Failed to extract calls from {file_path.name}: {e}")
                    call_sites = []
                    implementations = []
            else:
                logger.debug(f"No call extractor available for {parse_result.language}")
                call_sites = []
                implementations = []

            if not parse_result.units:
                logger.debug(f"No semantic units found in {file_path}")
                return {
                    "units_indexed": 0,
                    "parse_time_ms": parse_result.parse_time_ms,
                    "file_path": str(file_path),
                    "imports_extracted": len(imports),
                }

            # Step 2: Build indexable content for each unit
            indexable_contents = []
            for unit in parse_result.units:
                content = self._build_indexable_content(file_path, unit)
                indexable_contents.append(content)

            # Step 3: Generate embeddings in batch
            logger.debug(f"Generating embeddings for {len(indexable_contents)} units")
            embeddings = await self.embedding_generator.batch_generate(
                indexable_contents,
                show_progress=False,
            )

            # Step 4: Delete old units for this file
            logger.debug(f"Removing old index entries for {file_path}")
            await self._delete_file_units(file_path)

            # Step 5: Store new units with import metadata
            logger.debug(f"Storing {len(parse_result.units)} semantic units")
            stored_ids = await self._store_units(
                file_path,
                parse_result.units,
                embeddings,
                parse_result.language,
                import_metadata,
            )

            # Step 6: Store call graph data (FEAT-059)
            if call_sites or implementations:
                await self._store_call_graph(
                    file_path,
                    parse_result.units,
                    call_sites,
                    implementations,
                    parse_result.language,
                )
                logger.debug(f"Stored call graph: {len(call_sites)} calls, {len(implementations)} implementations")

            logger.info(
                f"Indexed {len(stored_ids)} units from {file_path.name} "
                f"({parse_result.parse_time_ms:.2f}ms parse, "
                f"{len(call_sites)} calls extracted)"
            )

            return {
                "units_indexed": len(stored_ids),
                "parse_time_ms": parse_result.parse_time_ms,
                "file_path": str(file_path),
                "language": parse_result.language,
                "unit_ids": stored_ids,
                "imports_extracted": len(imports),
                "dependencies": import_metadata.get("dependencies", []),
                "call_sites_extracted": len(call_sites),
                "implementations_extracted": len(implementations),
            }

        except Exception as e:
            logger.error(f"Failed to index {file_path}: {e}")
            raise StorageError(f"Failed to index file: {e}") from e

    async def index_directory(
        self,
        dir_path: Path,
        recursive: bool = True,
        show_progress: bool = True,
        max_concurrent: int = 4,
        progress_callback: Optional[Callable[..., Any]] = None,
    ) -> Dict[str, Any]:
        """
        Index all supported files in a directory with concurrent processing.

        Args:
            dir_path: Directory to index
            recursive: Recursively index subdirectories
            show_progress: Show progress logging
            max_concurrent: Maximum concurrent indexing tasks (default 4)
            progress_callback: Optional callback for progress updates.
                Called with (current, total, current_file, error_info)

        Returns:
            Dict with indexing stats (total_files, total_units, etc.)
        """
        dir_path = Path(dir_path).resolve()

        if not dir_path.is_dir():
            raise ValueError(f"Not a directory: {dir_path}")

        # Find all supported files
        pattern = "**/*" if recursive else "*"
        all_files = []
        for ext in self.SUPPORTED_EXTENSIONS:
            all_files.extend(dir_path.glob(f"{pattern}{ext}"))

        # Filter out common unwanted directories (but allow other dot-prefixed paths)
        # BUG-022: Previous logic filtered ALL paths with dots (broke git worktrees, .config dirs, etc)
        EXCLUDED_DIRS = {
            ".git", ".venv", "venv", ".virtualenv", "__pycache__",
            "node_modules", ".pytest_cache", ".mypy_cache", ".tox",
            ".worktrees",  # Git worktrees for parallel development
        }

        def should_include_file(file_path: Path) -> bool:
            """Check if file should be indexed (not in excluded directories or hidden)."""
            # Skip hidden files (files starting with .)
            if file_path.name.startswith('.'):
                return False

            # Get relative path from dir_path to check only subdirectories being indexed
            try:
                rel_path = file_path.relative_to(dir_path)
                # Only filter based on parts within the directory being indexed
                return not any(part in EXCLUDED_DIRS for part in rel_path.parts)
            except ValueError:
                # File is not relative to dir_path (shouldn't happen, but be safe)
                return not any(part in EXCLUDED_DIRS for part in file_path.parts)

        files_to_index = [f for f in all_files if should_include_file(f)]

        logger.info(f"Found {len(files_to_index)} files to index in {dir_path}")

        # Notify callback of total file count
        if progress_callback:
            progress_callback(0, len(files_to_index), None, None)

        if not files_to_index:
            return {
                "total_files": 0,
                "total_units": 0,
                "skipped_files": 0,
                "indexed_files": 0,
                "failed_files": [],
            }

        # Use semaphore to limit concurrent indexing and prevent resource exhaustion
        semaphore = asyncio.Semaphore(max_concurrent)
        completed_count = 0

        async def index_with_semaphore(i: int, file_path: Path) -> Tuple[str, Dict[str, Any]]:
            """Index a file with semaphore-controlled concurrency."""
            nonlocal completed_count

            async with semaphore:
                # Notify callback of current file
                if progress_callback:
                    progress_callback(completed_count, len(files_to_index), file_path.name, None)

                if show_progress:
                    logger.info(f"Indexing [{i}/{len(files_to_index)}]: {file_path.name}")

                try:
                    result = await self.index_file(file_path)
                    completed_count += 1

                    # Update progress on success
                    if progress_callback:
                        progress_callback(completed_count, len(files_to_index), file_path.name, None)

                    return "success", result
                except Exception as e:
                    logger.error(f"Failed to index {file_path}: {e}")
                    completed_count += 1

                    # Update progress with error
                    error_info = {"file": file_path.name, "error": str(e)}
                    if progress_callback:
                        progress_callback(completed_count, len(files_to_index), file_path.name, error_info)

                    return "error", {"path": str(file_path), "error": str(e)}

        # Index all files concurrently
        tasks = [
            index_with_semaphore(i, file_path)
            for i, file_path in enumerate(files_to_index, 1)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        total_units = 0
        skipped_files = 0
        indexed_files = 0
        failed_files = []

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Unexpected error during indexing: {result}")
                failed_files.append(str(result))
                continue

            status, data = result

            if status == "error":
                failed_files.append(data.get("path", "unknown"))
            elif data.get("skipped"):
                skipped_files += 1
            else:
                total_units += data.get("units_indexed", 0)
                indexed_files += 1

        logger.info(
            f"Directory indexing complete: {indexed_files} files, {total_units} units indexed "
            f"({skipped_files} skipped, {len(failed_files)} failed)"
        )

        # Clean up stale entries for files that no longer exist
        cleaned_count = await self._cleanup_stale_entries(dir_path, files_to_index)
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} stale index entries")

        return {
            "total_files": len(files_to_index),
            "indexed_files": indexed_files,
            "total_units": total_units,
            "skipped_files": skipped_files,
            "failed_files": failed_files,
            "cleaned_entries": cleaned_count,
        }

    async def delete_file_index(self, file_path: Path) -> int:
        """
        Remove all index entries for a deleted file.

        Args:
            file_path: Path to deleted file

        Returns:
            Number of units deleted
        """
        file_path = Path(file_path).resolve()
        return await self._delete_file_units(file_path)

    async def _delete_file_units(self, file_path: Path) -> int:
        """
        Delete all semantic units for a specific file.

        Args:
            file_path: File path to delete units for

        Returns:
            Number of units deleted
        """
        file_path_str = str(file_path.resolve())

        try:
            # Check if store has client attribute (Qdrant) or conn attribute (SQLite)
            has_client = hasattr(self.store, 'client')
            has_conn = hasattr(self.store, 'conn')

            if not has_client and not has_conn:
                logger.warning(f"Store type not supported for deletion, skipping cleanup for {file_path}")
                return 0

            # Handle Qdrant store
            if has_client:
                # Get client - either directly or from pool
                client = None
                # Check if store uses connection pool (must be explicit bool True)
                use_pool = getattr(self.store, 'use_pool', None)
                use_pool = use_pool is True  # Ensure it's explicitly True, not just truthy

                if use_pool:
                    # Acquire client from pool
                    client = await self.store._get_client()
                    if client is None:
                        logger.warning(f"Could not acquire client from pool, skipping cleanup for {file_path}")
                        return 0
                else:
                    # Initialize store if needed
                    if self.store.client is None:
                        await self.store.initialize()

                    # Check again after initialization
                    if self.store.client is None:
                        logger.warning(f"Store not initialized, skipping cleanup for {file_path}")
                        return 0
                    client = self.store.client

                try:
                    # Build proper Qdrant filter
                    from qdrant_client.models import Filter, FieldCondition, MatchValue

                    file_filter = Filter(
                        must=[
                            FieldCondition(
                                key="file_path",
                                match=MatchValue(value=file_path_str),
                            )
                        ]
                    )

                    # Get all points for this file using scroll
                    points, _ = client.scroll(
                        collection_name=self.store.collection_name,
                        scroll_filter=file_filter,
                        limit=self.config.quality.incremental_indexer_limit,  # Max units per file (REF-021)
                        with_payload=False,
                        with_vectors=False,
                    )

                    point_ids = [point.id for point in points]

                    if point_ids:
                        # Delete all points
                        client.delete(
                            collection_name=self.store.collection_name,
                            points_selector=point_ids,
                        )
                    logger.debug(f"Deleted {len(point_ids)} units for {file_path.name}")

                    return len(point_ids)
                finally:
                    # Release client back to pool if we acquired it
                    if use_pool:
                        await self.store._release_client(client)

            # Handle SQLite store
            else:
                # Query for all memory units with this file_path
                from src.core.models import SearchFilters, MemoryCategory

                filters = SearchFilters(
                    category=MemoryCategory.CONTEXT,
                    tags=["code"],
                )

                # Retrieve all memories with dummy embedding (not used for filtering)
                dummy_embedding = [0.0] * DEFAULT_EMBEDDING_DIM
                results = await self.store.retrieve(
                    query_embedding=dummy_embedding,
                    filters=filters,
                    limit=self.config.quality.incremental_indexer_limit,  # REF-021
                )

                # Filter by file_path in metadata
                deleted_count = 0
                for memory, _ in results:
                    metadata = memory.metadata or {}
                    if isinstance(metadata, dict):
                        mem_file_path = metadata.get("file_path", "")
                        if mem_file_path == file_path_str:
                            await self.store.delete(memory.id)
                            deleted_count += 1

                if deleted_count > 0:
                    logger.debug(f"Deleted {deleted_count} units for {file_path.name}")

                return deleted_count

        except Exception as e:
            logger.warning(f"Failed to delete units for {file_path}: {e}")
            return 0

    async def _cleanup_stale_entries(self, dir_path: Path, current_files: List[Path]) -> int:
        """
        Remove index entries for files that no longer exist on disk.

        Args:
            dir_path: Base directory that was indexed
            current_files: List of files that currently exist in the directory

        Returns:
            Number of stale entries cleaned up
        """
        try:
            # Get set of current file paths (as strings) for fast lookup
            current_file_paths = {str(f.resolve()) for f in current_files}

            # Get all indexed files for this project from the store
            indexed_files = await self._get_indexed_files()

            # Filter to files within the dir_path and check if they still exist
            stale_files = []
            for file_path_str in indexed_files:
                file_path = Path(file_path_str)

                # Check if file is within the indexed directory
                try:
                    file_path.relative_to(dir_path)
                except ValueError:
                    # File is outside the indexed directory, skip
                    continue

                # Check if file still exists on disk
                if file_path_str not in current_file_paths:
                    stale_files.append(file_path)

            # Delete stale entries
            total_cleaned = 0
            for stale_file in stale_files:
                logger.debug(f"Cleaning up stale index for deleted file: {stale_file.name}")
                count = await self._delete_file_units(stale_file)
                total_cleaned += count

            return total_cleaned

        except Exception as e:
            logger.warning(f"Failed to cleanup stale entries: {e}")
            return 0

    async def _get_indexed_files(self) -> set:
        """
        Get all unique file paths currently in the index for this project.

        Returns:
            Set of file path strings
        """
        try:
            # Check if store has client attribute (Qdrant) or conn attribute (SQLite)
            has_client = hasattr(self.store, 'client')
            has_conn = hasattr(self.store, 'conn')

            if not has_client and not has_conn:
                logger.warning("Store type not supported for listing files")
                return set()

            # Handle Qdrant store
            if has_client:
                # Initialize store if needed
                if self.store.client is None:
                    await self.store.initialize()

                if self.store.client is None:
                    return set()

                # Build filter for this project
                from qdrant_client.models import Filter, FieldCondition, MatchValue

                project_filter = Filter(
                    must=[
                        FieldCondition(
                            key="project_name",
                            match=MatchValue(value=self.project_name),
                        )
                    ]
                )

                # Scroll through all points and collect unique file paths
                file_paths = set()
                offset = None

                while True:
                    points, offset = self.store.client.scroll(
                        collection_name=self.store.collection_name,
                        scroll_filter=project_filter,
                        limit=100,
                        offset=offset,
                        with_payload=True,
                        with_vectors=False,
                    )

                    for point in points:
                        if point.payload and "file_path" in point.payload:
                            file_paths.add(point.payload["file_path"])

                    if offset is None:
                        break

                return file_paths

            # Handle SQLite store
            else:
                from src.core.models import SearchFilters, MemoryCategory

                filters = SearchFilters(
                    category=MemoryCategory.CONTEXT,
                    tags=["code"],
                    scope_filters={"project_name": self.project_name},
                )

                # Retrieve all memories with dummy embedding
                dummy_embedding = [0.0] * DEFAULT_EMBEDDING_DIM
                results = await self.store.retrieve(
                    query_embedding=dummy_embedding,
                    filters=filters,
                    limit=self.config.quality.incremental_indexer_limit,  # REF-021
                )

                # Extract unique file paths
                file_paths = set()
                for memory, _ in results:
                    metadata = memory.metadata or {}
                    if isinstance(metadata, dict) and "file_path" in metadata:
                        file_paths.add(metadata["file_path"])

                return file_paths

        except Exception as e:
            logger.warning(f"Failed to get indexed files: {e}")
            return set()

    def _build_indexable_content(self, file_path: Path, unit: "SemanticUnit") -> str:
        """
        Build rich indexable content for a semantic unit.

        Format:
        File: path/to/file.py:45-67
        Function: function_name
        Signature: def function_name(param: Type) -> ReturnType

        Content:
        <full function/class code>

        Args:
            file_path: Source file path
            unit: Semantic unit from parser

        Returns:
            Formatted content string for embedding
        """
        # Make file path relative to current working directory if possible
        try:
            rel_path = file_path.relative_to(Path.cwd())
        except ValueError:
            rel_path = file_path

        # Build header
        header = f"File: {rel_path}:{unit.start_line}-{unit.end_line}\n"
        header += f"{unit.unit_type.title()}: {unit.name}\n"
        header += f"Signature: {unit.signature}\n"
        header += "\nContent:\n"

        # Combine with content
        return header + unit.content

    async def _store_units(
        self,
        file_path: Path,
        units: List["SemanticUnit"],
        embeddings: List[List[float]],
        language: str,
        import_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Store semantic units in vector DB.

        Args:
            file_path: Source file path
            units: List of semantic units
            embeddings: List of embedding vectors
            language: Programming language
            import_metadata: Optional import/dependency metadata for the file

        Returns:
            List of stored unit IDs
        """
        if len(units) != len(embeddings):
            raise ValueError("Units and embeddings must have same length")

        if import_metadata is None:
            import_metadata = {"imports": [], "dependencies": [], "import_count": 0}

        # Read file content for export detection (used by importance scorer)
        try:
            file_content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            logger.warning(f"Failed to read file content for importance scoring: {e}")
            file_content = None

        # Calculate importance scores for all units (batch mode for efficiency)
        if self.importance_scorer:
            try:
                # Convert SemanticUnit objects to dicts for scorer
                unit_dicts = [
                    {
                        "name": u.name,
                        "content": u.content,
                        "signature": u.signature,
                        "unit_type": u.unit_type,
                        "language": language,
                    }
                    for u in units
                ]
                importance_scores = self.importance_scorer.calculate_batch(
                    unit_dicts, file_path, file_content
                )
            except Exception as e:
                logger.warning(f"Failed to calculate importance scores: {e}, using default 0.5")
                importance_scores = [None] * len(units)
        else:
            importance_scores = [None] * len(units)

        # Build batch store items
        items = []
        for unit, embedding, importance_score in zip(units, embeddings, importance_scores):
            # Build content for storage
            content = self._build_indexable_content(file_path, unit)

            # Build metadata with import information
            unit_metadata = {
                "file_path": str(file_path.resolve()),
                "unit_type": unit.unit_type,
                "unit_name": unit.name,
                "start_line": unit.start_line,
                "end_line": unit.end_line,
                "start_byte": unit.start_byte,
                "end_byte": unit.end_byte,
                "signature": unit.signature,
                "language": language,
                # Add import/dependency information
                "imports": import_metadata.get("imports", []),
                "dependencies": import_metadata.get("dependencies", []),
                "import_count": import_metadata.get("import_count", 0),
            }

            # FEAT-056: Add complexity metrics and file metadata
            try:
                # Complexity metrics (from ImportanceScore if available)
                if importance_score:
                    unit_metadata["cyclomatic_complexity"] = importance_score.cyclomatic_complexity
                    unit_metadata["line_count"] = importance_score.line_count
                    unit_metadata["nesting_depth"] = importance_score.nesting_depth
                    unit_metadata["parameter_count"] = importance_score.parameter_count
                else:
                    # Fallback values if importance scorer not available
                    unit_metadata["cyclomatic_complexity"] = 0
                    unit_metadata["line_count"] = len(unit.content.splitlines())
                    unit_metadata["nesting_depth"] = 0
                    unit_metadata["parameter_count"] = 0

                # File metadata (modification time, size, indexed timestamp)
                file_stats = file_path.stat()
                unit_metadata["file_modified_at"] = file_stats.st_mtime  # Unix timestamp
                unit_metadata["file_size_bytes"] = file_stats.st_size

                # Add indexed timestamp
                from datetime import datetime, UTC
                unit_metadata["indexed_at"] = datetime.now(UTC).isoformat()
            except (OSError, IOError) as e:
                # If file stats fail, use fallback values
                logger.warning(f"Failed to get file stats for {file_path}: {e}, using defaults")
                if not importance_score:
                    unit_metadata["cyclomatic_complexity"] = 0
                    unit_metadata["line_count"] = len(unit.content.splitlines())
                    unit_metadata["nesting_depth"] = 0
                    unit_metadata["parameter_count"] = 0
                unit_metadata["file_modified_at"] = 0
                unit_metadata["file_size_bytes"] = 0
                from datetime import datetime, UTC
                unit_metadata["indexed_at"] = datetime.now(UTC).isoformat()

            # Generate deterministic ID for this code unit
            # Format: hash(project_name + file_path + start_line + unit_name)
            id_string = f"{self.project_name}:{str(file_path.resolve())}:{unit.start_line}:{unit.name}"
            deterministic_id = hashlib.sha256(id_string.encode()).hexdigest()[:32]

            # Determine importance (FEAT-049: intelligent scoring or fallback to default)
            if importance_score:
                importance = importance_score.importance
            else:
                importance = 0.7  # Fallback to moderate importance

            metadata = {
                "id": deterministic_id,  # Deterministic ID prevents duplicates
                "category": MemoryCategory.CODE.value,
                "context_level": ContextLevel.PROJECT_CONTEXT.value,
                "scope": MemoryScope.PROJECT.value,
                "project_name": self.project_name,
                "importance": importance,  # Dynamic importance (FEAT-049)
                "tags": ["code", unit.unit_type, language.lower()],
                "metadata": unit_metadata,
            }

            items.append((content, embedding, metadata))

        # Batch store
        stored_ids = await self.store.batch_store(items)
        return stored_ids

    async def _store_call_graph(
        self,
        file_path: Path,
        units: List["SemanticUnit"],
        call_sites: List["CallSite"],
        implementations: List["InterfaceImplementation"],
        language: str,
    ) -> None:
        """
        Store call graph data for indexed file.

        Args:
            file_path: Source file path
            units: List of semantic units (functions/classes)
            call_sites: List of function calls
            implementations: List of interface implementations
            language: Programming language
        """
        from src.graph.call_graph import FunctionNode

        try:
            # Build unit hierarchy to determine qualified names
            # Two-pass approach: first find all classes, then assign qualified names

            # Pass 1: Find all class definitions and their line ranges
            class_ranges = []  # List of (class_name, start_line, end_line)
            for unit in units:
                if unit.unit_type == "class":
                    class_name = self._extract_function_name(unit.name)
                    class_ranges.append((class_name, unit.start_line, unit.end_line))

            # Pass 2: Build qualified names for all units
            unit_qualified_names = {}
            for unit in units:
                if unit.unit_type == "class":
                    class_name = self._extract_function_name(unit.name)
                    unit_qualified_names[unit] = class_name
                elif unit.unit_type in ("function", "method"):
                    func_name = self._extract_function_name(unit.name)

                    # Check if this function is within a class
                    parent_class = None
                    for class_name, class_start, class_end in class_ranges:
                        if class_start < unit.start_line < class_end:
                            parent_class = class_name
                            break

                    # Build qualified name
                    if parent_class:
                        qualified_name = f"{parent_class}.{func_name}"
                    else:
                        qualified_name = func_name

                    unit_qualified_names[unit] = qualified_name

            # Step 1: Store function nodes for all units FIRST
            # (must exist before we can attach call sites to them)
            for unit in units:
                qualified_name = unit_qualified_names.get(unit, self._extract_function_name(unit.name))
                func_name = self._extract_function_name(unit.name)

                # Determine if function is exported (heuristic: not starting with _)
                is_exported = not func_name.startswith("_")

                # Determine if async
                is_async = "async" in unit.signature

                # Extract parameters from signature (basic parsing)
                parameters = self._extract_parameters(unit.signature)

                # Create function node
                node = FunctionNode(
                    name=func_name,
                    qualified_name=qualified_name,  # Use qualified name (Class.method or just function)
                    file_path=str(file_path.resolve()),
                    language=language,
                    start_line=unit.start_line,
                    end_line=unit.end_line,
                    is_exported=is_exported,
                    is_async=is_async,
                    parameters=parameters,
                    return_type=None,  # TODO: Extract from signature if available
                )

                # Store function node WITHOUT call sites (those come later)
                await self.call_graph_store.store_function_node(
                    node=node,
                    project_name=self.project_name,
                    calls_to=[],  # Empty for now
                    called_by=[],  # Empty for now
                )

            # Step 2: Store call sites for each caller function
            # (now that all function nodes exist in the database)
            caller_groups = {}
            for call_site in call_sites:
                if call_site.caller_function not in caller_groups:
                    caller_groups[call_site.caller_function] = []
                caller_groups[call_site.caller_function].append(call_site)

            for caller_function, sites in caller_groups.items():
                try:
                    await self.call_graph_store.store_call_sites(
                        function_name=caller_function,
                        call_sites=sites,
                        project_name=self.project_name,
                    )
                except Exception as e:
                    logger.warning(f"Failed to store call sites for {caller_function}: {e}")

            # Store implementations grouped by interface
            impl_groups = {}
            for impl in implementations:
                if impl.interface_name not in impl_groups:
                    impl_groups[impl.interface_name] = []
                impl_groups[impl.interface_name].append(impl)

            for interface_name, impls in impl_groups.items():
                try:
                    await self.call_graph_store.store_implementations(
                        interface_name=interface_name,
                        implementations=impls,
                        project_name=self.project_name,
                    )
                except Exception as e:
                    logger.warning(f"Failed to store implementations for {interface_name}: {e}")

            logger.debug(
                f"Stored call graph for {file_path.name}: "
                f"{len(units)} functions, {len(call_sites)} calls, {len(implementations)} implementations"
            )

        except Exception as e:
            logger.error(f"Failed to store call graph for {file_path}: {e}")
            # Don't raise - call graph is optional, continue with indexing

    def _extract_function_name(self, signature: str) -> str:
        """
        Extract clean function name from signature.

        Args:
            signature: Function signature (e.g., "def add(a, b):" or "async def foo():" or "class MyClass:")

        Returns:
            Clean function name (e.g., "add", "foo", "MyClass")
        """
        # Handle class definitions
        if signature.startswith('class '):
            signature = signature.replace('class ', '').strip(':')
            match = re.match(r'([a-zA-Z_][a-zA-Z0-9_]*)', signature)
            if match:
                return match.group(1)

        # Remove 'def' or 'async def' prefix
        signature = re.sub(r'^(async\s+)?def\s+', '', signature)

        # Extract function name (everything before the opening parenthesis)
        match = re.match(r'([a-zA-Z_][a-zA-Z0-9_\.]*)', signature)
        if match:
            # Handle qualified names (e.g., "Calculator.add_numbers")
            # Use the last component (method name)
            full_name = match.group(1)
            return full_name.split('.')[-1] if '.' in full_name else full_name

        # Fallback: return the signature as-is
        return signature

    def _extract_parameters(self, signature: str) -> List[str]:
        """
        Extract parameter names from function signature.

        Args:
            signature: Function signature string

        Returns:
            List of parameter names
        """
        # Simple regex to extract parameters from signature
        # Handles: def func(a, b, c=1, *args, **kwargs)
        match = re.search(r'\((.*?)\)', signature)
        if not match:
            return []

        params_str = match.group(1)
        if not params_str.strip():
            return []

        # Split by comma and extract parameter names
        params = []
        for param in params_str.split(','):
            param = param.strip()
            if not param:
                continue

            # Remove default values, type hints, *args, **kwargs
            param = re.sub(r':\s*[^=]+', '', param)  # Remove type hints
            param = re.sub(r'=.*$', '', param)  # Remove default values
            param = param.strip('*').strip()  # Remove *, **

            if param:
                params.append(param)

        return params

    async def close(self) -> None:
        """Clean up resources."""
        await self.store.close()
        await self.embedding_generator.close()
        logger.info("Incremental indexer closed")


# Convenience function for file watcher callback
async def file_change_callback(file_path: Path, indexer: IncrementalIndexer):
    """
    Callback for file watcher to re-index changed files.

    Args:
        file_path: Changed file path
        indexer: Indexer instance
    """
    try:
        if file_path.exists():
            await indexer.index_file(file_path)
        else:
            # File was deleted
            await indexer.delete_file_index(file_path)
    except Exception as e:
        logger.error(f"Error in file change callback for {file_path}: {e}")
