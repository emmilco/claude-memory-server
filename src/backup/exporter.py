"""Data export functionality for memories and code indexes."""

import json
import tarfile
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, UTC
import numpy as np

from src.core.models import MemoryUnit, ContextLevel, MemoryCategory, MemoryScope
from src.store.base import MemoryStore
from src.core.exceptions import StorageError

logger = logging.getLogger(__name__)


class DataExporter:
    """Export memories and code indexes to various formats."""

    def __init__(self, store: MemoryStore):
        """
        Initialize data exporter.

        Args:
            store: Memory store to export from
        """
        self.store = store

    async def export_to_json(
        self,
        output_path: Path,
        project_name: Optional[str] = None,
        category: Optional[MemoryCategory] = None,
        context_level: Optional[ContextLevel] = None,
        since_date: Optional[datetime] = None,
        until_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Export memories to JSON format.

        Args:
            output_path: Path to write JSON file
            project_name: Filter by project name
            category: Filter by category
            context_level: Filter by context level
            since_date: Filter by creation date (after)
            until_date: Filter by creation date (before)

        Returns:
            Export statistics dictionary

        Raises:
            StorageError: If export fails
        """
        try:
            logger.info(f"Starting JSON export to {output_path}")

            # Retrieve all memories matching filters
            memories = await self._get_filtered_memories(
                project_name=project_name,
                category=category,
                context_level=context_level,
                since_date=since_date,
                until_date=until_date,
            )

            # Convert to JSON-serializable format
            export_data = {
                "version": "1.0.0",
                "schema_version": "3.0.0",
                "export_date": datetime.now(UTC).isoformat(),
                "export_type": "filtered" if any([project_name, category, context_level, since_date, until_date]) else "full",
                "filters": {
                    "project_name": project_name,
                    "category": category.value if category else None,
                    "context_level": context_level.value if context_level else None,
                    "since_date": since_date.isoformat() if since_date else None,
                    "until_date": until_date.isoformat() if until_date else None,
                },
                "memory_count": len(memories),
                "memories": [self._memory_to_dict(m) for m in memories],
            }

            # Write to file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            stats = {
                "format": "json",
                "output_path": str(output_path),
                "memory_count": len(memories),
                "file_size_bytes": output_path.stat().st_size,
            }

            logger.info(f"JSON export complete: {len(memories)} memories exported")
            return stats

        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            raise StorageError(f"Failed to export to JSON: {e}") from e

    async def create_portable_archive(
        self,
        output_path: Path,
        project_name: Optional[str] = None,
        include_embeddings: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a portable .tar.gz archive with all data.

        Args:
            output_path: Path to write archive file
            project_name: Filter by project name
            include_embeddings: Include embedding vectors in archive

        Returns:
            Export statistics dictionary

        Raises:
            StorageError: If archive creation fails
        """
        try:
            logger.info(f"Creating portable archive: {output_path}")

            # Create temporary directory for archive contents
            import tempfile
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Export memories
                memories = await self._get_filtered_memories(project_name=project_name)

                memories_data = {
                    "version": "1.0.0",
                    "schema_version": "3.0.0",
                    "export_date": datetime.now(UTC).isoformat(),
                    "memory_count": len(memories),
                    "memories": [self._memory_to_dict(m) for m in memories],
                }

                memories_file = temp_path / "memories.json"
                with open(memories_file, 'w', encoding='utf-8') as f:
                    json.dump(memories_data, f, indent=2)

                # Export embeddings if requested
                embeddings_file = None
                if include_embeddings and memories:
                    embeddings = np.array([m.embedding for m in memories])
                    embeddings_file = temp_path / "embeddings.npz"
                    np.savez_compressed(embeddings_file, embeddings=embeddings)

                # Create manifest
                manifest = self._create_manifest(memories, include_embeddings)
                manifest_file = temp_path / "manifest.json"
                with open(manifest_file, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, indent=2)

                # Calculate checksums
                checksums = {}
                for file in [memories_file, embeddings_file, manifest_file]:
                    if file and file.exists():
                        checksums[file.name] = self._calculate_checksum(file)

                checksums_file = temp_path / "checksums.sha256"
                with open(checksums_file, 'w') as f:
                    for filename, checksum in checksums.items():
                        f.write(f"{checksum}  {filename}\n")

                # Create tar.gz archive
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with tarfile.open(output_path, 'w:gz') as tar:
                    tar.add(memories_file, arcname="memories.json")
                    if embeddings_file and embeddings_file.exists():
                        tar.add(embeddings_file, arcname="embeddings.npz")
                    tar.add(manifest_file, arcname="manifest.json")
                    tar.add(checksums_file, arcname="checksums.sha256")

            stats = {
                "format": "archive",
                "output_path": str(output_path),
                "memory_count": len(memories),
                "file_size_bytes": output_path.stat().st_size,
                "includes_embeddings": include_embeddings,
            }

            logger.info(f"Archive creation complete: {output_path} ({stats['file_size_bytes']} bytes)")
            return stats

        except Exception as e:
            logger.error(f"Archive creation failed: {e}")
            raise StorageError(f"Failed to create portable archive: {e}") from e

    async def export_to_markdown(
        self,
        output_path: Path,
        project_name: Optional[str] = None,
        include_metadata: bool = True,
    ) -> Dict[str, Any]:
        """
        Export memories to human-readable Markdown format.

        Args:
            output_path: Path to write markdown file
            project_name: Filter by project name
            include_metadata: Include metadata in output

        Returns:
            Export statistics dictionary

        Raises:
            StorageError: If export fails
        """
        try:
            logger.info(f"Starting Markdown export to {output_path}")

            # Retrieve memories
            memories = await self._get_filtered_memories(project_name=project_name)

            # Group by project and category
            grouped = self._group_memories(memories)

            # Generate Markdown content
            lines = []
            lines.append("# Memory Export")
            lines.append("")
            lines.append(f"**Export Date:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            lines.append(f"**Total Memories:** {len(memories)}")
            if project_name:
                lines.append(f"**Project Filter:** {project_name}")
            lines.append("")
            lines.append("---")
            lines.append("")

            # Table of contents
            lines.append("## Table of Contents")
            lines.append("")
            for project, categories in grouped.items():
                lines.append(f"- [{project}](#{self._slugify(project)})")
                for category in categories:
                    lines.append(f"  - [{category}](#{self._slugify(project)}-{self._slugify(category)})")
            lines.append("")
            lines.append("---")
            lines.append("")

            # Content
            for project, categories in grouped.items():
                lines.append(f"## {project}")
                lines.append("")

                for category, category_memories in categories.items():
                    lines.append(f"### {category}")
                    lines.append("")

                    for memory in category_memories:
                        lines.append(f"#### {memory.id[:8]}")
                        lines.append("")
                        lines.append(memory.content)
                        lines.append("")

                        if include_metadata:
                            lines.append("**Metadata:**")
                            lines.append("")
                            lines.append(f"- **Context Level:** {memory.context_level.value}")
                            lines.append(f"- **Importance:** {memory.importance:.2f}")
                            lines.append(f"- **Created:** {memory.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                            lines.append(f"- **Updated:** {memory.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")

                            if memory.tags:
                                lines.append(f"- **Tags:** {', '.join(memory.tags)}")

                            if memory.metadata:
                                lines.append(f"- **Additional Metadata:** {json.dumps(memory.metadata, indent=2)}")

                            lines.append("")

                        lines.append("---")
                        lines.append("")

            # Write to file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            stats = {
                "format": "markdown",
                "output_path": str(output_path),
                "memory_count": len(memories),
                "file_size_bytes": output_path.stat().st_size,
            }

            logger.info(f"Markdown export complete: {len(memories)} memories exported")
            return stats

        except Exception as e:
            logger.error(f"Markdown export failed: {e}")
            raise StorageError(f"Failed to export to Markdown: {e}") from e

    async def _get_filtered_memories(
        self,
        project_name: Optional[str] = None,
        category: Optional[MemoryCategory] = None,
        context_level: Optional[ContextLevel] = None,
        since_date: Optional[datetime] = None,
        until_date: Optional[datetime] = None,
    ) -> List[MemoryUnit]:
        """
        Retrieve memories with filters applied.

        Args:
            project_name: Filter by project name
            category: Filter by category
            context_level: Filter by context level
            since_date: Filter by creation date (after)
            until_date: Filter by creation date (before)

        Returns:
            List of matching memories
        """
        # Get all memories (store-specific implementation)
        # For now, use search with empty query to get all
        from src.core.models import SearchFilters

        filters = SearchFilters(
            category=category,
            context_level=context_level,
            project_name=project_name,
        )

        # Retrieve all memories via search (with high limit)
        results = await self.store.search(
            query_vector=[0.0] * 384,  # Dummy vector
            limit=100000,  # High limit to get all
            filters=filters
        )

        # Extract memories from results
        memories = [r.memory for r in results]

        # Apply date filters
        if since_date:
            memories = [m for m in memories if m.created_at >= since_date]
        if until_date:
            memories = [m for m in memories if m.created_at <= until_date]

        return memories

    def _memory_to_dict(self, memory: MemoryUnit) -> Dict[str, Any]:
        """
        Convert MemoryUnit to JSON-serializable dictionary.

        Args:
            memory: Memory unit to convert

        Returns:
            Dictionary representation
        """
        data = {
            "id": memory.id,
            "content": memory.content,
            "category": memory.category.value,
            "context_level": memory.context_level.value,
            "scope": memory.scope.value,
            "project_name": memory.project_name,
            "importance": memory.importance,
            "embedding_model": memory.embedding_model,
            "embedding": memory.embedding,
            "created_at": memory.created_at.isoformat(),
            "updated_at": memory.updated_at.isoformat(),
            "last_accessed": memory.last_accessed.isoformat(),
            "lifecycle_state": memory.lifecycle_state.value,
            "tags": memory.tags or [],
            "metadata": memory.metadata or {},
        }

        # Add provenance if available
        if memory.provenance:
            data["provenance"] = {
                "source": memory.provenance.source.value,
                "created_by": memory.provenance.created_by,
                "last_confirmed": memory.provenance.last_confirmed.isoformat() if memory.provenance.last_confirmed else None,
                "confidence": memory.provenance.confidence,
                "verified": memory.provenance.verified,
                "conversation_id": memory.provenance.conversation_id,
                "file_context": memory.provenance.file_context,
                "notes": memory.provenance.notes,
            }

        return data

    def _create_manifest(self, memories: List[MemoryUnit], include_embeddings: bool) -> Dict[str, Any]:
        """
        Create manifest file for archive.

        Args:
            memories: List of memories in archive
            include_embeddings: Whether embeddings are included

        Returns:
            Manifest dictionary
        """
        # Group by project
        projects = list(set(m.project_name for m in memories if m.project_name))

        return {
            "version": "1.0.0",
            "schema_version": "3.0.0",
            "export_date": datetime.now(UTC).isoformat(),
            "export_type": "full",
            "memory_count": len(memories),
            "projects": projects,
            "includes_embeddings": include_embeddings,
            "compression": "gzip",
            "encryption": "none",
        }

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

    def _group_memories(self, memories: List[MemoryUnit]) -> Dict[str, Dict[str, List[MemoryUnit]]]:
        """
        Group memories by project and category.

        Args:
            memories: List of memories

        Returns:
            Nested dictionary: project -> category -> memories
        """
        grouped: Dict[str, Dict[str, List[MemoryUnit]]] = {}

        for memory in memories:
            project = memory.project_name or "Global"
            category = memory.category.value

            if project not in grouped:
                grouped[project] = {}
            if category not in grouped[project]:
                grouped[project][category] = []

            grouped[project][category].append(memory)

        return grouped

    def _slugify(self, text: str) -> str:
        """
        Convert text to URL-safe slug for markdown anchors.

        Args:
            text: Text to slugify

        Returns:
            Slugified text
        """
        import re
        text = text.lower()
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[-\s]+', '-', text)
        return text
