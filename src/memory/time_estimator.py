"""Time estimation for indexing operations."""

from typing import Optional, Tuple, List
from pathlib import Path

from src.memory.indexing_metrics import IndexingMetricsStore


class TimeEstimator:
    """Estimate indexing time based on historical data and heuristics."""

    # Default conservative estimate (100ms per file)
    DEFAULT_TIME_PER_FILE = 0.1

    def __init__(self, metrics_store: IndexingMetricsStore):
        """
        Initialize time estimator.

        Args:
            metrics_store: Metrics store for historical data
        """
        self.metrics = metrics_store

    def estimate_indexing_time(
        self,
        file_count: int,
        project_name: Optional[str] = None,
        total_size_bytes: Optional[int] = None,
    ) -> Tuple[float, float]:
        """
        Estimate indexing time range.

        Args:
            file_count: Number of files to index
            project_name: Optional project name for project-specific estimates
            total_size_bytes: Optional total size for size-based adjustments

        Returns:
            (min_seconds, max_seconds) - Range estimate
        """
        # Get historical average
        avg_time = self.metrics.get_average_time_per_file(project_name)

        # Use default if no history
        if avg_time is None:
            avg_time = self.DEFAULT_TIME_PER_FILE

        # Adjust for file size if available
        if total_size_bytes and file_count > 0:
            avg_size = total_size_bytes / file_count
            # Larger files take longer (rough heuristic: +10ms per 10KB)
            size_factor = 1.0 + (avg_size / 100000)  # 100KB baseline
            avg_time *= size_factor

        # Calculate base estimate
        base_estimate = file_count * avg_time

        # Add variance for estimate range
        # Min: -20% (optimistic), Max: +50% (conservative)
        min_estimate = base_estimate * 0.8
        max_estimate = base_estimate * 1.5

        return (min_estimate, max_estimate)

    def calculate_eta(
        self,
        files_completed: int,
        files_total: int,
        elapsed_seconds: float,
    ) -> float:
        """
        Calculate ETA based on current progress.

        Args:
            files_completed: Number of files completed
            files_total: Total number of files
            elapsed_seconds: Time elapsed so far

        Returns:
            Estimated seconds remaining
        """
        if files_completed == 0:
            return 0.0

        # Calculate current rate
        rate = elapsed_seconds / files_completed

        # Estimate remaining time
        remaining_files = files_total - files_completed
        eta = remaining_files * rate

        return eta

    def suggest_optimizations(
        self,
        file_paths: List[str],
        estimated_seconds: float,
    ) -> List[str]:
        """
        Suggest performance optimizations if estimate is high.

        Args:
            file_paths: List of file paths to be indexed
            estimated_seconds: Estimated indexing time

        Returns:
            List of optimization suggestions
        """
        suggestions = []

        # Only suggest if estimate is > 30 seconds
        if estimated_seconds < 30:
            return suggestions

        # Check for common slow patterns
        node_modules_files = [p for p in file_paths if "node_modules" in p]
        test_files = [p for p in file_paths if any(t in p for t in ["test", "tests", "spec", "__tests__"])]
        git_files = [p for p in file_paths if ".git" in p]
        vendor_files = [p for p in file_paths if any(v in p for v in ["vendor", "third_party", "external"])]

        if node_modules_files:
            time_saved = len(node_modules_files) * self.DEFAULT_TIME_PER_FILE
            suggestions.append(
                f"💡 Exclude node_modules/ ({len(node_modules_files)} files, saves ~{time_saved:.0f}s)"
            )

        if len(test_files) > 50:
            time_saved = len(test_files) * self.DEFAULT_TIME_PER_FILE
            suggestions.append(
                f"💡 Exclude test directories ({len(test_files)} files, saves ~{time_saved:.0f}s)"
            )

        if git_files:
            suggestions.append(
                f"💡 Exclude .git/ directory ({len(git_files)} files)"
            )

        if vendor_files:
            time_saved = len(vendor_files) * self.DEFAULT_TIME_PER_FILE
            suggestions.append(
                f"💡 Exclude vendor/third_party directories ({len(vendor_files)} files, saves ~{time_saved:.0f}s)"
            )

        # Suggest creating .ragignore if many exclusions possible
        if len(suggestions) >= 2:
            suggestions.append(
                "\n📝 Create a .ragignore file to permanently exclude these patterns"
            )

        return suggestions

    def format_time(self, seconds: float) -> str:
        """
        Format seconds into human-readable string.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted string (e.g., "2m 30s", "45s")
        """
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            remaining_seconds = int(seconds % 60)
            if remaining_seconds > 0:
                return f"{minutes}m {remaining_seconds}s"
            return f"{minutes}m"
        else:
            hours = int(seconds / 3600)
            remaining_minutes = int((seconds % 3600) / 60)
            if remaining_minutes > 0:
                return f"{hours}h {remaining_minutes}m"
            return f"{hours}h"

    def format_estimate_range(self, min_seconds: float, max_seconds: float) -> str:
        """
        Format estimate range into human-readable string.

        Args:
            min_seconds: Minimum estimate
            max_seconds: Maximum estimate

        Returns:
            Formatted range string (e.g., "2-3 minutes")
        """
        min_str = self.format_time(min_seconds)
        max_str = self.format_time(max_seconds)

        # If both are in the same unit, simplify
        if min_str.endswith("s") and max_str.endswith("s"):
            return f"{min_str}-{max_str}"
        elif min_str.endswith("m") and max_str.endswith("m"):
            return f"{min_str}-{max_str}"

        # Otherwise show full range
        return f"{min_str} to {max_str}"
