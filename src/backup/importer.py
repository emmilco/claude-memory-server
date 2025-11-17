"""Data import functionality for memories and code indexes."""

import json
import tarfile
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, UTC
from enum import Enum
import numpy as np

from src.core.models import (
    MemoryUnit, ContextLevel, MemoryCategory, MemoryScope,
    LifecycleState, MemoryProvenance, ProvenanceSource
)
from src.store.base import MemoryStore
from src.core.exceptions import StorageError

logger = logging.getLogger(__name__)


class ConflictStrategy(str, Enum):
    """Strategy for handling conflicting memories during import."""

    KEEP_NEWER = "keep_newer"  # Keep memory with more recent timestamp
    KEEP_OLDER = "keep_older"  # Keep existing memory, skip import
    KEEP_BOTH = "keep_both"  # Import as new memory with suffix
    SKIP = "skip"  # Skip conflicting memory entirely
    MERGE_METADATA = "merge_metadata"  # Merge metadata fields


class DataImporter:
    """Import memories and code indexes from backups."""

    def __init__(self, store: MemoryStore):
        """
        Initialize data importer.

        Args:
            store: Memory store to import into
        """
        self.store = store

    async def import_from_json(
        self,
        input_path: Path,
        conflict_strategy: ConflictStrategy = ConflictStrategy.KEEP_NEWER,
        dry_run: bool = False,
        selective_project: Optional[str] = None,
        selective_category: Optional[MemoryCategory] = None,
    ) -> Dict[str, Any]:
        """
        Import memories from JSON file.

        Args:
            input_path: Path to JSON file
            conflict_strategy: How to handle conflicts
            dry_run: If True, don't actually import, just analyze
            selective_project: Only import this project
            selective_category: Only import this category

        Returns:
            Import statistics dictionary

        Raises:
            StorageError: If import fails
        """
        try:
            logger.info(f"Starting JSON import from {input_path} (strategy={conflict_strategy.value}, dry_run={dry_run})")

            # Load and validate JSON
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self._validate_import_data(data)

            # Extract memories with embeddings
            imported_memory_embeddings = []
            for mem_dict in data.get("memories", []):
                # Apply selective filters
                if selective_project and mem_dict.get("project_name") != selective_project:
                    continue
                if selective_category and mem_dict.get("category") != selective_category.value:
                    continue

                memory, embedding = self._dict_to_memory(mem_dict)
                imported_memory_embeddings.append((memory, embedding))

            logger.info(f"Loaded {len(imported_memory_embeddings)} memories from file")

            # Process imports with conflict resolution
            stats = await self._process_imports(
                memory_embeddings=imported_memory_embeddings,
                conflict_strategy=conflict_strategy,
                dry_run=dry_run,
            )

            stats["format"] = "json"
            stats["input_path"] = str(input_path)
            stats["conflict_strategy"] = conflict_strategy.value
            stats["dry_run"] = dry_run

            logger.info(f"JSON import complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"JSON import failed: {e}")
            raise StorageError(f"Failed to import from JSON: {e}") from e

    async def import_from_archive(
        self,
        archive_path: Path,
        conflict_strategy: ConflictStrategy = ConflictStrategy.KEEP_NEWER,
        dry_run: bool = False,
        selective_project: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Import memories from portable .tar.gz archive.

        Args:
            archive_path: Path to archive file
            conflict_strategy: How to handle conflicts
            dry_run: If True, don't actually import, just analyze
            selective_project: Only import this project

        Returns:
            Import statistics dictionary

        Raises:
            StorageError: If import fails
        """
        try:
            logger.info(f"Starting archive import from {archive_path}")

            # Extract archive to temporary directory
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract archive
                with tarfile.open(archive_path, 'r:gz') as tar:
                    tar.extractall(temp_path)

                # Verify checksums
                self._verify_checksums(temp_path)

                # Load manifest
                manifest_path = temp_path / "manifest.json"
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)

                logger.info(f"Archive manifest: {manifest}")

                # Load memories
                memories_path = temp_path / "memories.json"
                with open(memories_path, 'r') as f:
                    memories_data = json.load(f)

                # Load embeddings if available
                embeddings_path = temp_path / "embeddings.npz"
                embeddings_dict = {}
                if embeddings_path.exists():
                    embeddings_array = np.load(embeddings_path)['embeddings']
                    # Map embeddings to memory IDs
                    for i, mem_dict in enumerate(memories_data.get("memories", [])):
                        if i < len(embeddings_array):
                            embeddings_dict[mem_dict["id"]] = embeddings_array[i].tolist()

                # Extract memories with embeddings
                imported_memory_embeddings = []
                for mem_dict in memories_data.get("memories", []):
                    # Apply selective filters
                    if selective_project and mem_dict.get("project_name") != selective_project:
                        continue

                    # Use embedding from archive if available
                    if mem_dict["id"] in embeddings_dict:
                        mem_dict["embedding"] = embeddings_dict[mem_dict["id"]]

                    memory, embedding = self._dict_to_memory(mem_dict)
                    imported_memory_embeddings.append((memory, embedding))

                logger.info(f"Loaded {len(imported_memory_embeddings)} memories from archive")

                # Process imports with conflict resolution
                stats = await self._process_imports(
                    memory_embeddings=imported_memory_embeddings,
                    conflict_strategy=conflict_strategy,
                    dry_run=dry_run,
                )

                stats["format"] = "archive"
                stats["input_path"] = str(archive_path)
                stats["conflict_strategy"] = conflict_strategy.value
                stats["dry_run"] = dry_run
                stats["manifest"] = manifest

                logger.info(f"Archive import complete: {stats}")
                return stats

        except Exception as e:
            logger.error(f"Archive import failed: {e}")
            raise StorageError(f"Failed to import from archive: {e}") from e

    async def _process_imports(
        self,
        memory_embeddings: List[Tuple[MemoryUnit, List[float]]],
        conflict_strategy: ConflictStrategy,
        dry_run: bool,
    ) -> Dict[str, Any]:
        """
        Process memory imports with conflict resolution.

        Args:
            memory_embeddings: List of (MemoryUnit, embedding) tuples to import
            conflict_strategy: How to handle conflicts
            dry_run: If True, don't actually import

        Returns:
            Statistics dictionary
        """
        stats = {
            "total_memories": len(memory_embeddings),
            "imported": 0,
            "skipped": 0,
            "conflicts": 0,
            "errors": 0,
            "conflict_resolutions": {
                "kept_newer": 0,
                "kept_older": 0,
                "kept_both": 0,
                "skipped": 0,
                "merged": 0,
            }
        }

        for memory, embedding in memory_embeddings:
            try:
                # Check if memory already exists
                existing = await self._find_existing_memory(memory)

                if existing:
                    stats["conflicts"] += 1

                    # Resolve conflict
                    resolution = await self._resolve_conflict(
                        imported=memory,
                        imported_embedding=embedding,
                        existing=existing,
                        strategy=conflict_strategy,
                        dry_run=dry_run,
                    )

                    stats["conflict_resolutions"][resolution] += 1

                    if resolution == "skipped":
                        stats["skipped"] += 1
                        continue

                # Import memory
                if not dry_run:
                    await self._store_memory(memory, embedding)

                stats["imported"] += 1

            except Exception as e:
                logger.error(f"Failed to import memory {memory.id}: {e}")
                stats["errors"] += 1

        return stats

    async def _find_existing_memory(self, memory: MemoryUnit) -> Optional[MemoryUnit]:
        """
        Find existing memory by ID.

        Args:
            memory: Memory to check

        Returns:
            Existing memory if found, None otherwise
        """
        try:
            existing = await self.store.retrieve(memory.id)
            return existing
        except:
            return None

    async def _resolve_conflict(
        self,
        imported: MemoryUnit,
        imported_embedding: List[float],
        existing: MemoryUnit,
        strategy: ConflictStrategy,
        dry_run: bool,
    ) -> str:
        """
        Resolve conflict between imported and existing memory.

        Args:
            imported: Memory being imported
            imported_embedding: Embedding vector for imported memory
            existing: Existing memory in database
            strategy: Conflict resolution strategy
            dry_run: If True, don't actually modify data

        Returns:
            Resolution action taken (for statistics)
        """
        if strategy == ConflictStrategy.KEEP_NEWER:
            if imported.updated_at > existing.updated_at:
                # Imported is newer, replace
                if not dry_run:
                    await self._update_memory(imported, imported_embedding)
                logger.debug(f"Conflict resolved: keeping newer (imported) for {imported.id}")
                return "kept_newer"
            else:
                # Existing is newer, skip
                logger.debug(f"Conflict resolved: keeping newer (existing) for {imported.id}")
                return "kept_older"

        elif strategy == ConflictStrategy.KEEP_OLDER:
            # Always keep existing
            logger.debug(f"Conflict resolved: keeping older (existing) for {imported.id}")
            return "kept_older"

        elif strategy == ConflictStrategy.KEEP_BOTH:
            # Import with modified ID and content marker
            if not dry_run:
                imported.id = f"{imported.id}_imported"
                imported.content = f"{imported.content}\n\n(Imported copy)"
                await self._store_memory(imported, imported_embedding)
            logger.debug(f"Conflict resolved: keeping both for {imported.id}")
            return "kept_both"

        elif strategy == ConflictStrategy.SKIP:
            # Skip import
            logger.debug(f"Conflict resolved: skipping import for {imported.id}")
            return "skipped"

        elif strategy == ConflictStrategy.MERGE_METADATA:
            # Merge metadata fields
            if not dry_run:
                # Keep content from existing, merge metadata
                existing.metadata = {**(existing.metadata or {}), **(imported.metadata or {})}
                existing.tags = list(set((existing.tags or []) + (imported.tags or [])))
                existing.updated_at = datetime.now(UTC)
                # Note: We don't update embedding when merging metadata
                await self._update_memory(existing, imported_embedding)
            logger.debug(f"Conflict resolved: merged metadata for {imported.id}")
            return "merged"

        return "skipped"

    def _validate_import_data(self, data: Dict[str, Any]) -> None:
        """
        Validate import data format and version.

        Args:
            data: Import data dictionary

        Raises:
            StorageError: If validation fails
        """
        # Check required fields
        if "version" not in data:
            raise StorageError("Import data missing version field")

        if "memories" not in data:
            raise StorageError("Import data missing memories field")

        # Check version compatibility
        version = data.get("version")
        if not version.startswith("1."):
            raise StorageError(f"Unsupported import format version: {version}")

        logger.info(f"Import data validated: version {version}, {len(data['memories'])} memories")

    def _dict_to_memory(self, data: Dict[str, Any]) -> Tuple[MemoryUnit, List[float]]:
        """
        Convert dictionary to MemoryUnit object and embedding.

        Args:
            data: Dictionary representation

        Returns:
            Tuple of (MemoryUnit object, embedding vector)
        """
        # Extract embedding separately (not part of MemoryUnit model)
        embedding = data.get("embedding", [0.0] * 384)

        # Parse provenance if available
        provenance = None
        if "provenance" in data and data["provenance"]:
            prov_data = data["provenance"]
            provenance = MemoryProvenance(
                source=ProvenanceSource(prov_data.get("source", "imported")),
                created_by=prov_data.get("created_by", "import"),
                last_confirmed=datetime.fromisoformat(prov_data["last_confirmed"]) if prov_data.get("last_confirmed") else None,
                confidence=prov_data.get("confidence", 0.8),
                verified=prov_data.get("verified", False),
                conversation_id=prov_data.get("conversation_id"),
                file_context=prov_data.get("file_context", []),
                notes=prov_data.get("notes"),
            )

        # Create MemoryUnit (without embedding field)
        memory = MemoryUnit(
            id=data["id"],
            content=data["content"],
            category=MemoryCategory(data["category"]),
            context_level=ContextLevel(data["context_level"]),
            scope=MemoryScope(data["scope"]),
            project_name=data.get("project_name"),
            importance=data["importance"],
            embedding_model=data["embedding_model"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            lifecycle_state=LifecycleState(data.get("lifecycle_state", "ACTIVE")),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            provenance=provenance if provenance else MemoryProvenance(),
        )

        return memory, embedding

    def _verify_checksums(self, extract_dir: Path) -> None:
        """
        Verify checksums for extracted archive files.

        Args:
            extract_dir: Directory containing extracted files

        Raises:
            StorageError: If checksums don't match
        """
        checksums_file = extract_dir / "checksums.sha256"
        if not checksums_file.exists():
            logger.warning("No checksums file found, skipping verification")
            return

        # Load expected checksums
        expected = {}
        with open(checksums_file, 'r') as f:
            for line in f:
                if line.strip():
                    checksum, filename = line.strip().split(None, 1)
                    expected[filename] = checksum

        # Verify each file
        for filename, expected_checksum in expected.items():
            if filename == "checksums.sha256":
                continue

            file_path = extract_dir / filename
            if not file_path.exists():
                raise StorageError(f"Expected file not found in archive: {filename}")

            actual_checksum = self._calculate_checksum(file_path)
            if actual_checksum != expected_checksum:
                raise StorageError(f"Checksum mismatch for {filename}: expected {expected_checksum}, got {actual_checksum}")

        logger.info(f"Checksums verified for {len(expected)} files")

    def _calculate_checksum(self, file_path: Path) -> str:
        """
        Calculate SHA256 checksum for a file.

        Args:
            file_path: Path to file

        Returns:
            SHA256 checksum hex string
        """
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def _store_memory(self, memory: MemoryUnit, embedding: List[float]) -> None:
        """Store a memory using the store's API."""
        await self.store.store(
            content=memory.content,
            embedding=embedding,
            metadata={
                "id": memory.id,
                "category": memory.category.value,
                "context_level": memory.context_level.value,
                "scope": memory.scope.value,
                "project_name": memory.project_name,
                "importance": memory.importance,
                "embedding_model": memory.embedding_model,
                "created_at": memory.created_at.isoformat(),
                "updated_at": memory.updated_at.isoformat(),
                "last_accessed": memory.last_accessed.isoformat(),
                "lifecycle_state": memory.lifecycle_state.value,
                "tags": memory.tags,
                "metadata": memory.metadata,
                "provenance": memory.provenance.model_dump() if memory.provenance else None,
            }
        )

    async def _update_memory(self, memory: MemoryUnit, embedding: List[float]) -> None:
        """Update a memory using the store's API."""
        # For update, we need to delete and re-store since embeddings need to be updated
        try:
            await self.store.delete(memory.id)
            await self._store_memory(memory, embedding)
        except Exception as e:
            logger.error(f"Failed to update memory {memory.id}: {e}")
            raise
