"""Incremental code indexing using Rust parsing and vector storage."""

import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, UTC

try:
    from mcp_performance_core import parse_source_file, batch_parse_files, ParseResult, SemanticUnit
    RUST_AVAILABLE = True
    PARSER_MODE = "rust"
    logging.info("Using Rust parser (optimal performance)")
except ImportError:
    RUST_AVAILABLE = False
    PARSER_MODE = "python"
    logging.warning("Rust parsing module not available. Using Python fallback parser (10-20x slower).")
    logging.info("For better performance, install Rust and build: cd rust_core && maturin develop")

    # Import Python fallback parser
    try:
        from src.memory.python_parser import parse_code_file as python_parse_file
        PYTHON_PARSER_AVAILABLE = True
    except ImportError:
        PYTHON_PARSER_AVAILABLE = False
        logging.error("Python fallback parser also not available. Install: pip install tree-sitter tree-sitter-languages")

    # Create ParseResult-like classes for compatibility
    from dataclasses import dataclass
    from typing import List

    @dataclass
    class SemanticUnit:
        """Semantic unit (function, class, method)."""
        unit_type: str
        name: str
        signature: str
        start_line: int
        end_line: int
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
        """Python fallback for parse_source_file."""
        import time
        if not PYTHON_PARSER_AVAILABLE:
            raise ImportError("Neither Rust nor Python parser available")

        # Detect language from file extension
        from pathlib import Path
        ext = Path(file_path).suffix.lower()
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
        }
        language = language_map.get(ext, "unknown")

        # Parse using Python parser
        start_time = time.time()
        units_data = python_parse_file(file_path, language)
        parse_time_ms = (time.time() - start_time) * 1000

        # Convert to SemanticUnit objects
        units = [
            SemanticUnit(
                unit_type=u["unit_type"],
                name=u["name"],
                signature=u["signature"],
                start_line=u["start_line"],
                end_line=u["end_line"],
                content=u["content"],
                language=u["language"],
                file_path=u["file_path"],
            )
            for u in units_data
        ]

        return ParseResult(
            units=units,
            parse_time_ms=parse_time_ms,
            language=language,
            file_path=file_path,
        )

from src.config import ServerConfig, get_config
from src.embeddings.generator import EmbeddingGenerator
from src.embeddings.parallel_generator import ParallelEmbeddingGenerator
from src.store.qdrant_store import QdrantMemoryStore
from src.core.models import MemoryCategory, ContextLevel, MemoryScope
from src.core.exceptions import StorageError
from src.memory.import_extractor import ImportExtractor, build_dependency_metadata

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
        progress_callback: Optional[callable] = None,
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
    SUPPORTED_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs"}

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
        self.store = store or QdrantMemoryStore(config)

        # Use parallel embedding generator if enabled, otherwise use standard generator
        if embedding_generator is not None:
            self.embedding_generator = embedding_generator
        elif config.enable_parallel_embeddings:
            logger.info("Using parallel embedding generator for improved throughput")
            self.embedding_generator = ParallelEmbeddingGenerator(config)
        else:
            logger.info("Using standard embedding generator (single-threaded)")
            self.embedding_generator = EmbeddingGenerator(config)

        # Project name for scoping
        self.project_name = project_name or Path.cwd().name

        # Import extractor for dependency tracking
        self.import_extractor = ImportExtractor()

        logger.info(f"Incremental indexer initialized for project: {self.project_name}")

    async def initialize(self) -> None:
        """Initialize the indexer (connect to storage, etc.)."""
        await self.store.initialize()

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

            logger.info(
                f"Indexed {len(stored_ids)} units from {file_path.name} "
                f"({parse_result.parse_time_ms:.2f}ms parse)"
            )

            return {
                "units_indexed": len(stored_ids),
                "parse_time_ms": parse_result.parse_time_ms,
                "file_path": str(file_path),
                "language": parse_result.language,
                "unit_ids": stored_ids,
                "imports_extracted": len(imports),
                "dependencies": import_metadata.get("dependencies", []),
            }

        except Exception as e:
            logger.error(f"Failed to index {file_path}: {e}")
            raise StorageError(f"Failed to index file: {e}")

    async def index_directory(
        self,
        dir_path: Path,
        recursive: bool = True,
        show_progress: bool = True,
        max_concurrent: int = 4,
        progress_callback: Optional[callable] = None,
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

        # Filter out hidden directories and files
        files_to_index = [
            f for f in all_files
            if not any(part.startswith(".") for part in f.parts)
        ]

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

        return {
            "total_files": len(files_to_index),
            "indexed_files": indexed_files,
            "total_units": total_units,
            "skipped_files": skipped_files,
            "failed_files": failed_files,
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

        # Qdrant doesn't have a direct "delete by filter" API,
        # so we need to:
        # 1. Search for all points with this file_path
        # 2. Delete them by ID

        try:
            # Initialize store if needed
            if self.store.client is None:
                await self.store.initialize()
            
            # Check again after initialization
            if self.store.client is None:
                logger.warning(f"Store not initialized, skipping cleanup for {file_path}")
                return 0
            
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
            points, _ = self.store.client.scroll(
                collection_name=self.store.collection_name,
                scroll_filter=file_filter,
                limit=10000,  # Max units per file
                with_payload=False,
                with_vectors=False,
            )

            point_ids = [point.id for point in points]

            if point_ids:
                # Delete all points
                self.store.client.delete(
                    collection_name=self.store.collection_name,
                    points_selector=point_ids,
                )
                logger.debug(f"Deleted {len(point_ids)} units for {file_path.name}")

            return len(point_ids)

        except Exception as e:
            logger.warning(f"Failed to delete units for {file_path}: {e}")
            return 0

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

        # Build batch store items
        items = []
        for unit, embedding in zip(units, embeddings):
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

            metadata = {
                "category": MemoryCategory.CONTEXT.value,
                "context_level": ContextLevel.PROJECT_CONTEXT.value,
                "scope": MemoryScope.PROJECT.value,
                "project_name": self.project_name,
                "importance": 0.7,  # Code units have moderate importance
                "tags": ["code", unit.unit_type, language.lower()],
                "metadata": unit_metadata,
            }

            items.append((content, embedding, metadata))

        # Batch store
        stored_ids = await self.store.batch_store(items)
        return stored_ids

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
