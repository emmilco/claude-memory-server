"""Archive import functionality for restoring portable project archives."""

import json
import logging
import tarfile
import shutil
import tempfile
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, Optional, Literal

from src.memory.archive_compressor import ArchiveCompressor

logger = logging.getLogger(__name__)

ConflictResolution = Literal["skip", "overwrite", "merge"]


class ArchiveImporter:
    """
    Import project archives from portable .tar.gz files.

    Restores project archives with validation, conflict resolution, and
    integrity checking for reliable recovery and migration.
    """

    def __init__(
        self,
        archive_compressor: ArchiveCompressor,
    ):
        """
        Initialize archive importer.

        Args:
            archive_compressor: ArchiveCompressor for managing archives
        """
        self.compressor = archive_compressor

    async def import_project_archive(
        self,
        archive_path: Path,
        project_name: Optional[str] = None,
        conflict_resolution: ConflictResolution = "skip",
        validate: bool = True,
    ) -> Dict:
        """
        Import a project archive from a portable .tar.gz file.

        Args:
            archive_path: Path to the exported archive file
            project_name: Optional custom project name (default: use name from archive)
            conflict_resolution: How to handle existing archives (skip, overwrite, merge)
            validate: Validate archive structure and manifest (default: True)

        Returns:
            Dict with import results
        """
        try:
            archive_path = Path(archive_path)

            if not archive_path.exists():
                return {
                    "success": False,
                    "error": f"Archive file not found: {archive_path}",
                }

            # Extract to temporary directory for validation
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract archive
                try:
                    with tarfile.open(archive_path, "r:gz") as tar:
                        tar.extractall(temp_path)
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to extract archive: {e}",
                    }

                # Find project directory (should be single top-level directory)
                project_dirs = [d for d in temp_path.iterdir() if d.is_dir()]
                if len(project_dirs) != 1:
                    return {
                        "success": False,
                        "error": f"Invalid archive structure: expected 1 project directory, found {len(project_dirs)}",
                    }

                extracted_project_dir = project_dirs[0]
                extracted_project_name = extracted_project_dir.name

                # Use custom project name if provided, otherwise use extracted name
                target_project_name = project_name if project_name else extracted_project_name

                # Validate archive structure
                if validate:
                    validation_result = self._validate_archive(extracted_project_dir)
                    if not validation_result["valid"]:
                        return {
                            "success": False,
                            "error": f"Archive validation failed: {validation_result['error']}",
                        }

                # Load manifest
                manifest_file = extracted_project_dir / "manifest.json"
                manifest = {}
                if manifest_file.exists():
                    with open(manifest_file, "r") as f:
                        manifest = json.load(f)
                else:
                    logger.warning(f"No manifest found in archive for {target_project_name}")

                # Check for conflict
                existing_archive = self.compressor.get_archive_info(target_project_name)
                if existing_archive:
                    if conflict_resolution == "skip":
                        return {
                            "success": False,
                            "error": f"Archive already exists for project '{target_project_name}' (use overwrite or merge)",
                            "conflict": True,
                        }
                    elif conflict_resolution == "overwrite":
                        logger.info(f"Overwriting existing archive for {target_project_name}")
                        self.compressor.delete_archive(target_project_name)
                    elif conflict_resolution == "merge":
                        return {
                            "success": False,
                            "error": "Merge conflict resolution not yet implemented",
                        }

                # Copy archive to destination
                dest_archive_dir = self.compressor._get_project_archive_dir(target_project_name)
                dest_archive_dir.mkdir(parents=True, exist_ok=True)

                # Copy the compressed index archive
                source_archive = extracted_project_dir / "archive.tar.gz"
                if source_archive.exists():
                    dest_archive_file = dest_archive_dir / f"{target_project_name}_index.tar.gz"
                    shutil.copy2(source_archive, dest_archive_file)
                else:
                    return {
                        "success": False,
                        "error": "Archive file (archive.tar.gz) not found in extracted archive",
                    }

                # Copy manifest
                if manifest_file.exists():
                    dest_manifest = dest_archive_dir / "manifest.json"

                    # Update project name in manifest if changed
                    if target_project_name != extracted_project_name:
                        manifest["project_name"] = target_project_name
                        manifest["imported_from"] = extracted_project_name
                        manifest["imported_at"] = datetime.now(UTC).isoformat()

                    with open(dest_manifest, "w") as f:
                        json.dump(manifest, f, indent=2)

                # Get import statistics
                import_size_mb = dest_archive_file.stat().st_size / (1024 * 1024)

                logger.info(
                    f"Imported archive for {target_project_name} from {archive_path} ({import_size_mb:.2f} MB)"
                )

                return {
                    "success": True,
                    "project_name": target_project_name,
                    "original_name": extracted_project_name if target_project_name != extracted_project_name else None,
                    "import_size_mb": round(import_size_mb, 2),
                    "manifest": manifest,
                    "conflict_resolution": conflict_resolution if existing_archive else None,
                }

        except Exception as e:
            logger.error(f"Failed to import archive from {archive_path}: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _validate_archive(self, project_dir: Path) -> Dict:
        """
        Validate archive structure and contents.

        Args:
            project_dir: Path to extracted project directory

        Returns:
            Dict with validation results
        """
        try:
            # Check for required files
            archive_file = project_dir / "archive.tar.gz"
            if not archive_file.exists():
                return {
                    "valid": False,
                    "error": "Missing required file: archive.tar.gz",
                }

            manifest_file = project_dir / "manifest.json"
            if not manifest_file.exists():
                logger.warning("Manifest file not found, archive may be incomplete")
                # Not a fatal error, just a warning

            # Validate manifest structure if present
            if manifest_file.exists():
                try:
                    with open(manifest_file, "r") as f:
                        manifest = json.load(f)

                    # Check for required manifest fields
                    required_fields = ["project_name", "archive_version"]
                    missing_fields = [f for f in required_fields if f not in manifest]
                    if missing_fields:
                        return {
                            "valid": False,
                            "error": f"Manifest missing required fields: {', '.join(missing_fields)}",
                        }

                except json.JSONDecodeError as e:
                    return {
                        "valid": False,
                        "error": f"Invalid manifest JSON: {e}",
                    }

            # Validate archive file is a valid tar.gz
            try:
                with tarfile.open(archive_file, "r:gz") as tar:
                    # Just check that it can be opened
                    pass
            except Exception as e:
                return {
                    "valid": False,
                    "error": f"Invalid archive file: {e}",
                }

            return {
                "valid": True,
            }

        except Exception as e:
            return {
                "valid": False,
                "error": f"Validation error: {e}",
            }

    def validate_archive_file(self, archive_path: Path) -> Dict:
        """
        Validate an archive file without importing it.

        Args:
            archive_path: Path to the archive file to validate

        Returns:
            Dict with validation results and summary
        """
        try:
            archive_path = Path(archive_path)

            if not archive_path.exists():
                return {
                    "valid": False,
                    "error": f"Archive file not found: {archive_path}",
                }

            # Extract to temporary directory for validation
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract archive
                try:
                    with tarfile.open(archive_path, "r:gz") as tar:
                        tar.extractall(temp_path)
                except Exception as e:
                    return {
                        "valid": False,
                        "error": f"Failed to extract archive: {e}",
                    }

                # Find project directory
                project_dirs = [d for d in temp_path.iterdir() if d.is_dir()]
                if len(project_dirs) != 1:
                    return {
                        "valid": False,
                        "error": f"Invalid archive structure: expected 1 project directory, found {len(project_dirs)}",
                    }

                extracted_project_dir = project_dirs[0]

                # Validate structure
                validation_result = self._validate_archive(extracted_project_dir)
                if not validation_result["valid"]:
                    return validation_result

                # Load manifest for summary
                manifest_file = extracted_project_dir / "manifest.json"
                manifest = {}
                if manifest_file.exists():
                    with open(manifest_file, "r") as f:
                        manifest = json.load(f)

                return {
                    "valid": True,
                    "project_name": extracted_project_dir.name,
                    "manifest": manifest,
                    "archive_size_mb": round(archive_path.stat().st_size / (1024 * 1024), 2),
                }

        except Exception as e:
            return {
                "valid": False,
                "error": f"Validation error: {e}",
            }
