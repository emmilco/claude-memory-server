"""Archive export functionality for portable project archives."""

import json
import logging
import tarfile
import tempfile
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Optional

from src.memory.archive_compressor import ArchiveCompressor

logger = logging.getLogger(__name__)


class ArchiveExporter:
    """
    Export project archives to portable .tar.gz files.

    Creates self-contained archive files with manifest, index data, and
    human-readable README for backup, migration, and sharing.
    """

    def __init__(
        self,
        archive_compressor: ArchiveCompressor,
        compression_level: int = 6,
    ):
        """
        Initialize archive exporter.

        Args:
            archive_compressor: ArchiveCompressor for accessing archives
            compression_level: gzip compression level (1-9, default 6)
        """
        self.compressor = archive_compressor
        self.compression_level = compression_level

    async def export_project_archive(
        self,
        project_name: str,
        output_path: Optional[Path] = None,
        include_readme: bool = True,
    ) -> Dict:
        """
        Export a project archive to a portable .tar.gz file.

        Args:
            project_name: Name of the project to export
            output_path: Optional custom output path (default: current directory)
            include_readme: Include human-readable README (default: True)

        Returns:
            Dict with export results
        """
        try:
            # Get archive info
            archive_info = self.compressor.get_archive_info(project_name)
            if not archive_info:
                return {
                    "success": False,
                    "error": f"Archive not found for project: {project_name}",
                }

            # Determine output path
            if output_path is None:
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                output_path = Path.cwd() / f"{project_name}_archive_{timestamp}.tar.gz"
            else:
                output_path = Path(output_path)

            # Get source archive file
            archive_dir = self.compressor._get_project_archive_dir(project_name)
            source_archive = archive_dir / f"{project_name}_index.tar.gz"
            manifest_file = archive_dir / "manifest.json"

            if not source_archive.exists():
                return {
                    "success": False,
                    "error": f"Source archive file not found: {source_archive}",
                }

            # Create portable export archive
            with tarfile.open(output_path, "w:gz", compresslevel=self.compression_level) as tar:
                # Add the compressed index archive
                tar.add(source_archive, arcname=f"{project_name}/archive.tar.gz")

                # Add manifest
                if manifest_file.exists():
                    tar.add(manifest_file, arcname=f"{project_name}/manifest.json")

                # Add README if requested
                if include_readme:
                    readme_content = self._generate_readme(project_name, archive_info)
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as tmp:
                        tmp.write(readme_content)
                        tmp_path = tmp.name

                    try:
                        tar.add(tmp_path, arcname=f"{project_name}/README.txt")
                    finally:
                        Path(tmp_path).unlink()

            # Get export file size
            export_size_mb = output_path.stat().st_size / (1024 * 1024)

            logger.info(f"Exported archive for {project_name} to {output_path} ({export_size_mb:.2f} MB)")

            return {
                "success": True,
                "project_name": project_name,
                "export_file": str(output_path),
                "export_size_mb": round(export_size_mb, 2),
                "manifest": archive_info,
            }

        except Exception as e:
            logger.error(f"Failed to export archive for {project_name}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _generate_readme(self, project_name: str, archive_info: Dict) -> str:
        """
        Generate human-readable README for exported archive.

        Args:
            project_name: Name of the project
            archive_info: Archive manifest information

        Returns:
            README content as string
        """
        lines = [
            f"# {project_name} - Claude Memory RAG Archive",
            "",
            "## Archive Information",
            "",
            f"**Project Name:** {project_name}",
            f"**Archive Version:** {archive_info.get('archive_version', 'unknown')}",
            f"**Archived At:** {archive_info.get('archived_at', 'unknown')}",
            f"**Archived By:** {archive_info.get('archived_by', 'unknown')}",
            "",
        ]

        # Statistics
        stats = archive_info.get("statistics", {})
        if stats:
            lines.extend([
                "## Statistics",
                "",
                f"- Total Files: {stats.get('total_files', 'N/A')}",
                f"- Total Semantic Units: {stats.get('total_semantic_units', 'N/A')}",
                f"- Total Memories: {stats.get('total_memories', 'N/A')}",
                "",
            ])

        # Compression info
        comp_info = archive_info.get("compression_info", {})
        if comp_info:
            lines.extend([
                "## Compression",
                "",
                f"- Original Size: {comp_info.get('original_size_mb', 'N/A')} MB",
                f"- Compressed Size: {comp_info.get('compressed_size_mb', 'N/A')} MB",
                f"- Compression Ratio: {comp_info.get('compression_ratio', 'N/A')}",
                f"- Savings: {comp_info.get('savings_percent', 'N/A')}%",
                "",
            ])

        # Last activity
        last_activity = archive_info.get("last_activity", {})
        if last_activity:
            lines.extend([
                "## Last Activity",
                "",
                f"- Date: {last_activity.get('date', 'N/A')}",
                f"- Days Inactive: {last_activity.get('days_inactive', 'N/A')}",
                f"- Searches: {last_activity.get('searches_count', 'N/A')}",
                f"- Index Updates: {last_activity.get('index_updates_count', 'N/A')}",
                "",
            ])

        # Restore info
        restore_info = archive_info.get("restore_info", {})
        if restore_info:
            lines.extend([
                "## Restore Information",
                "",
                f"- Estimated Restore Time: {restore_info.get('estimated_restore_time_seconds', 'N/A')} seconds",
            ])

            warnings = restore_info.get("warnings", [])
            if warnings:
                lines.append("- Warnings:")
                for warning in warnings:
                    lines.append(f"  - {warning}")

            lines.append("")

        # Import instructions
        lines.extend([
            "## How to Import",
            "",
            "To import this archive into Claude Memory RAG:",
            "",
            "```bash",
            "# Using CLI",
            f"python -m src.cli archival import {project_name}_archive_*.tar.gz",
            "",
            "# Or specify custom project name",
            f"python -m src.cli archival import {project_name}_archive_*.tar.gz --name my-project",
            "```",
            "",
            "## Contents",
            "",
            "- `archive.tar.gz` - Compressed project index and embedding cache",
            "- `manifest.json` - Archive metadata and statistics",
            "- `README.txt` - This file",
            "",
            "---",
            "",
            "Generated by Claude Memory RAG Server",
            f"Export Date: {datetime.now(UTC).isoformat()}",
        ])

        return "\n".join(lines)

    def list_exportable_projects(self) -> Dict:
        """
        List all projects available for export.

        Returns:
            Dict with list of exportable projects and summary
        """
        try:
            archives = self.compressor.list_archives()

            exportable = []
            total_size_mb = 0.0

            for project_name in archives:
                archive_info = self.compressor.get_archive_info(project_name)
                if archive_info:
                    size_mb = archive_info.get("archive_file_size_mb", 0)
                    exportable.append({
                        "project_name": project_name,
                        "archived_at": archive_info.get("archived_at"),
                        "size_mb": size_mb,
                        "compression_ratio": archive_info.get("compression_info", {}).get("compression_ratio", 0),
                    })
                    total_size_mb += size_mb

            return {
                "success": True,
                "exportable_projects": exportable,
                "total_projects": len(exportable),
                "total_size_mb": round(total_size_mb, 2),
            }

        except Exception as e:
            logger.error(f"Failed to list exportable projects: {e}")
            return {
                "success": False,
                "error": str(e),
            }
