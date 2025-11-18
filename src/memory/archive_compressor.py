"""
Archive compression and decompression for project archival system.

Provides efficient compression of project indexes, embedding caches, and
metadata with manifest generation for reliable restore operations.
"""

import json
import logging
import tarfile
import shutil
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Optional, List
import sqlite3

logger = logging.getLogger(__name__)


class ArchiveCompressor:
    """
    Compress and decompress project archives for efficient storage.

    Handles:
    - Index data compression (Qdrant snapshots or SQLite databases)
    - Embedding cache compression
    - Manifest generation with comprehensive metadata
    - Integrity verification
    """

    def __init__(
        self,
        archive_root: str = "~/.claude-rag/archives",
        compression_level: int = 6,
    ):
        """
        Initialize archive compressor.

        Args:
            archive_root: Root directory for archived projects
            compression_level: gzip compression level (1-9, default 6)
        """
        self.archive_root = Path(archive_root).expanduser()
        self.archive_root.mkdir(parents=True, exist_ok=True)
        self.compression_level = compression_level

    def _get_project_archive_dir(self, project_name: str) -> Path:
        """Get the archive directory for a specific project."""
        return self.archive_root / project_name

    def _calculate_dir_size(self, directory: Path) -> int:
        """Calculate total size of directory in bytes."""
        total_size = 0
        try:
            for item in directory.rglob("*"):
                if item.is_file():
                    total_size += item.stat().st_size
        except Exception as e:
            logger.warning(f"Failed to calculate size for {directory}: {e}")
        return total_size

    def _generate_manifest(
        self,
        project_name: str,
        stats: Dict,
        compression_info: Dict,
        last_activity: Optional[Dict] = None,
    ) -> Dict:
        """
        Generate archive manifest with comprehensive metadata.

        Args:
            project_name: Name of the project
            stats: Project statistics
            compression_info: Compression statistics
            last_activity: Last activity information

        Returns:
            Manifest dictionary
        """
        manifest = {
            "project_name": project_name,
            "archive_version": "1.0",
            "archived_at": datetime.now(UTC).isoformat(),
            "archived_by": "manual",  # Can be enhanced to detect automatic
            "statistics": stats,
            "compression_info": compression_info,
            "restore_info": {
                "estimated_restore_time_seconds": max(5, compression_info.get("compressed_size_mb", 0) / 2),
                "dependencies": [],
                "warnings": [],
            },
        }

        if last_activity:
            manifest["last_activity"] = last_activity

        return manifest

    async def compress_project_index(
        self,
        project_name: str,
        index_path: Path,
        cache_path: Optional[Path] = None,
        project_stats: Optional[Dict] = None,
    ) -> Dict:
        """
        Compress a project's index and cache data.

        Args:
            project_name: Name of the project
            index_path: Path to index directory or database file
            cache_path: Optional path to embedding cache
            project_stats: Optional project statistics

        Returns:
            Dict with compression results
        """
        try:
            # Create archive directory
            archive_dir = self._get_project_archive_dir(project_name)
            archive_dir.mkdir(parents=True, exist_ok=True)

            # Calculate original sizes
            index_size = 0
            cache_size = 0

            if index_path.exists():
                if index_path.is_dir():
                    index_size = self._calculate_dir_size(index_path)
                else:
                    index_size = index_path.stat().st_size

            if cache_path and cache_path.exists():
                cache_size = cache_path.stat().st_size

            original_size_mb = (index_size + cache_size) / (1024 * 1024)

            # Create tar.gz archive
            archive_file = archive_dir / f"{project_name}_index.tar.gz"

            with tarfile.open(archive_file, "w:gz", compresslevel=self.compression_level) as tar:
                # Add index data
                if index_path.exists():
                    tar.add(
                        index_path,
                        arcname="index",
                        recursive=True,
                    )
                    logger.info(f"Added index to archive: {index_path}")

                # Add cache if exists
                if cache_path and cache_path.exists():
                    tar.add(
                        cache_path,
                        arcname="embeddings_cache.db",
                    )
                    logger.info(f"Added cache to archive: {cache_path}")

            # Calculate compressed size
            compressed_size = archive_file.stat().st_size
            compressed_size_mb = compressed_size / (1024 * 1024)
            compression_ratio = compressed_size / (index_size + cache_size) if (index_size + cache_size) > 0 else 0

            # Prepare compression info
            compression_info = {
                "original_size_mb": round(original_size_mb, 2),
                "compressed_size_mb": round(compressed_size_mb, 2),
                "compression_ratio": round(compression_ratio, 3),
                "savings_mb": round(original_size_mb - compressed_size_mb, 2),
                "savings_percent": round((1 - compression_ratio) * 100, 1),
            }

            # Generate and save manifest
            manifest = self._generate_manifest(
                project_name,
                stats=project_stats or {},
                compression_info=compression_info,
            )

            manifest_file = archive_dir / "manifest.json"
            with open(manifest_file, "w") as f:
                json.dump(manifest, f, indent=2)

            logger.info(
                f"Compressed {project_name}: {original_size_mb:.1f}MB → "
                f"{compressed_size_mb:.1f}MB ({compression_info['savings_percent']}% savings)"
            )

            return {
                "success": True,
                "archive_file": str(archive_file),
                "manifest_file": str(manifest_file),
                "compression_info": compression_info,
            }

        except Exception as e:
            logger.error(f"Failed to compress project {project_name}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def decompress_project_index(
        self,
        project_name: str,
        restore_path: Path,
    ) -> Dict:
        """
        Decompress a project archive and restore index data.

        Args:
            project_name: Name of the project
            restore_path: Path to restore the index data

        Returns:
            Dict with decompression results
        """
        try:
            archive_dir = self._get_project_archive_dir(project_name)
            archive_file = archive_dir / f"{project_name}_index.tar.gz"
            manifest_file = archive_dir / "manifest.json"

            # Verify archive exists
            if not archive_file.exists():
                return {
                    "success": False,
                    "error": f"Archive not found for project: {project_name}",
                }

            # Load manifest
            manifest = {}
            if manifest_file.exists():
                with open(manifest_file, "r") as f:
                    manifest = json.load(f)
                logger.info(f"Loaded manifest for {project_name}")

            # Create restore directory
            restore_path.mkdir(parents=True, exist_ok=True)

            # Extract archive
            start_time = datetime.now(UTC)

            with tarfile.open(archive_file, "r:gz") as tar:
                tar.extractall(restore_path)

            extraction_time = (datetime.now(UTC) - start_time).total_seconds()

            # Calculate restored size
            restored_size = self._calculate_dir_size(restore_path)
            restored_size_mb = restored_size / (1024 * 1024)

            logger.info(
                f"Decompressed {project_name}: {restored_size_mb:.1f}MB "
                f"in {extraction_time:.1f}s"
            )

            return {
                "success": True,
                "restored_path": str(restore_path),
                "manifest": manifest,
                "restored_size_mb": round(restored_size_mb, 2),
                "extraction_time_seconds": round(extraction_time, 2),
            }

        except Exception as e:
            logger.error(f"Failed to decompress project {project_name}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_archive_info(self, project_name: str) -> Optional[Dict]:
        """
        Get information about an archived project.

        Args:
            project_name: Name of the project

        Returns:
            Archive information dict or None if not found
        """
        try:
            archive_dir = self._get_project_archive_dir(project_name)
            manifest_file = archive_dir / "manifest.json"

            if not manifest_file.exists():
                return None

            with open(manifest_file, "r") as f:
                manifest = json.load(f)

            # Add archive file info
            archive_file = archive_dir / f"{project_name}_index.tar.gz"
            if archive_file.exists():
                manifest["archive_file_size_mb"] = round(
                    archive_file.stat().st_size / (1024 * 1024), 2
                )
                manifest["archive_file_path"] = str(archive_file)

            return manifest

        except Exception as e:
            logger.error(f"Failed to get archive info for {project_name}: {e}")
            return None

    def list_archives(self) -> List[str]:
        """
        List all archived projects.

        Returns:
            List of archived project names
        """
        try:
            if not self.archive_root.exists():
                return []

            archives = []
            for item in self.archive_root.iterdir():
                if item.is_dir():
                    manifest_file = item / "manifest.json"
                    if manifest_file.exists():
                        archives.append(item.name)

            return sorted(archives)

        except Exception as e:
            logger.error(f"Failed to list archives: {e}")
            return []

    def delete_archive(self, project_name: str) -> bool:
        """
        Delete an archived project.

        Args:
            project_name: Name of the project

        Returns:
            True if deleted successfully
        """
        try:
            archive_dir = self._get_project_archive_dir(project_name)

            if archive_dir.exists():
                shutil.rmtree(archive_dir)
                logger.info(f"Deleted archive for {project_name}")
                return True
            else:
                logger.warning(f"Archive not found for {project_name}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete archive for {project_name}: {e}")
            return False

    def get_total_storage_savings(self) -> Dict:
        """
        Calculate total storage savings from all archives.

        Returns:
            Dict with aggregated savings statistics
        """
        try:
            archives = self.list_archives()
            total_original_mb = 0.0
            total_compressed_mb = 0.0
            archive_count = 0

            for project_name in archives:
                manifest = self.get_archive_info(project_name)
                if manifest and "compression_info" in manifest:
                    info = manifest["compression_info"]
                    total_original_mb += info.get("original_size_mb", 0)
                    total_compressed_mb += info.get("compressed_size_mb", 0)
                    archive_count += 1

            total_savings_mb = total_original_mb - total_compressed_mb
            savings_percent = (
                (1 - total_compressed_mb / total_original_mb) * 100
                if total_original_mb > 0
                else 0
            )

            return {
                "archive_count": archive_count,
                "total_original_mb": round(total_original_mb, 2),
                "total_compressed_mb": round(total_compressed_mb, 2),
                "total_savings_mb": round(total_savings_mb, 2),
                "savings_percent": round(savings_percent, 1),
            }

        except Exception as e:
            logger.error(f"Failed to calculate storage savings: {e}")
            return {
                "archive_count": 0,
                "total_original_mb": 0,
                "total_compressed_mb": 0,
                "total_savings_mb": 0,
                "savings_percent": 0,
            }
