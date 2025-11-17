"""System degradation warning and tracking."""

import logging
from typing import List, Dict, Optional
from datetime import datetime, UTC
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DegradationWarning:
    """A single system degradation warning."""

    component: str
    message: str
    upgrade_path: str
    performance_impact: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "component": self.component,
            "message": self.message,
            "upgrade_path": self.upgrade_path,
            "performance_impact": self.performance_impact,
            "timestamp": self.timestamp.isoformat(),
        }


class DegradationTracker:
    """
    Tracks system degradations and provides summary.

    Used to alert users when system is running in degraded mode due to
    missing optional dependencies.
    """

    def __init__(self):
        self.warnings: List[DegradationWarning] = []
        self._warning_keys = set()  # Prevent duplicate warnings

    def add_warning(
        self,
        component: str,
        message: str,
        upgrade_path: str,
        performance_impact: str,
    ) -> None:
        """
        Add a degradation warning.

        Args:
            component: Component name (e.g., "Qdrant", "Rust Parser")
            message: Human-readable message
            upgrade_path: Instructions to upgrade
            performance_impact: Performance impact description
        """
        # Prevent duplicates
        warning_key = f"{component}:{message}"
        if warning_key in self._warning_keys:
            return

        self._warning_keys.add(warning_key)

        warning = DegradationWarning(
            component=component,
            message=message,
            upgrade_path=upgrade_path,
            performance_impact=performance_impact,
        )

        self.warnings.append(warning)
        logger.warning(f"Degradation: {component} - {message}")

    def has_degradations(self) -> bool:
        """Check if any degradations exist."""
        return len(self.warnings) > 0

    def get_summary(self) -> str:
        """
        Get human-readable summary of all degradations.

        Returns:
            Formatted string with all warnings
        """
        if not self.warnings:
            return "✓ All components running at full performance"

        lines = ["⚠️  System running in degraded mode:", ""]

        for warning in self.warnings:
            lines.append(f"  • {warning.component}: {warning.message}")
            lines.append(f"    Impact: {warning.performance_impact}")
            lines.append(f"    Upgrade: {warning.upgrade_path}")
            lines.append("")

        lines.append("Run 'status' command for full system health check.")

        return "\n".join(lines)

    def get_warnings_list(self) -> List[Dict]:
        """Get list of warnings as dictionaries."""
        return [w.to_dict() for w in self.warnings]

    def clear(self) -> None:
        """Clear all warnings."""
        self.warnings.clear()
        self._warning_keys.clear()


# Global singleton instance
_degradation_tracker: Optional[DegradationTracker] = None


def get_degradation_tracker() -> DegradationTracker:
    """Get global degradation tracker instance."""
    global _degradation_tracker
    if _degradation_tracker is None:
        _degradation_tracker = DegradationTracker()
    return _degradation_tracker


def add_degradation_warning(
    component: str,
    message: str,
    upgrade_path: str,
    performance_impact: str,
) -> None:
    """
    Add a degradation warning to the global tracker.

    Args:
        component: Component name (e.g., "Qdrant", "Rust Parser")
        message: Human-readable message
        upgrade_path: Instructions to upgrade
        performance_impact: Performance impact description
    """
    tracker = get_degradation_tracker()
    tracker.add_warning(component, message, upgrade_path, performance_impact)


def has_degradations() -> bool:
    """Check if system has any degradations."""
    tracker = get_degradation_tracker()
    return tracker.has_degradations()


def get_degradation_summary() -> str:
    """Get summary of all system degradations."""
    tracker = get_degradation_tracker()
    return tracker.get_summary()
