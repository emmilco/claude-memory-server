"""Optimization analysis for indexing performance."""

import mimetypes
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class FileStats:
    """Statistics for a single file."""
    path: Path
    size_bytes: int
    is_binary: bool
    mime_type: Optional[str]
    category: str  # 'source', 'binary', 'log', 'cache', 'build', etc.


@dataclass
class DirectoryInfo:
    """Information about a directory."""
    path: Path
    file_count: int
    total_size_bytes: int
    category: str  # 'node_modules', 'build', 'cache', 'venv', etc.


@dataclass
class OptimizationSuggestion:
    """A single optimization suggestion."""
    type: str  # 'exclude_binary', 'exclude_directory', 'exclude_pattern'
    description: str
    pattern: str  # .ragignore pattern
    affected_files: int
    size_savings_mb: float
    time_savings_seconds: float
    priority: int = 5  # 1-5, higher is more important

    def __lt__(self, other):
        """Sort by priority (descending) then time savings."""
        if self.priority != other.priority:
            return self.priority > other.priority
        return self.time_savings_seconds > other.time_savings_seconds


@dataclass
class AnalysisResult:
    """Result of optimization analysis."""
    total_files: int
    total_size_mb: float
    indexable_files: int  # Files that would be indexed
    suggestions: List[OptimizationSuggestion] = field(default_factory=list)
    estimated_speedup: float = 1.0  # e.g., 2.5x faster
    estimated_storage_savings_mb: float = 0.0


class OptimizationAnalyzer:
    """
    Analyze directory structure and suggest indexing optimizations.

    Detects:
    - Large binary files
    - Build directories (dist, build, target, .next, etc.)
    - Dependency directories (node_modules, vendor, venv)
    - Cache directories (__pycache__, .cache, etc.)
    - Version control (.git, .svn)
    - Log files
    """

    # Supported source code extensions (what we want to index)
    SOURCE_EXTENSIONS = {
        ".py", ".js", ".jsx", ".ts", ".tsx",
        ".java", ".go", ".rs", ".cpp", ".c", ".h",
        ".rb", ".php", ".swift", ".kt", ".scala",
        ".css", ".scss", ".sass", ".less",
        ".html", ".vue", ".svelte",
        ".json", ".yaml", ".yml", ".toml",
        ".md", ".rst", ".txt",
    }

    # Binary file extensions to exclude
    BINARY_EXTENSIONS = {
        # Images
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".ico", ".svg", ".webp",
        # Videos
        ".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm",
        # Audio
        ".mp3", ".wav", ".flac", ".aac", ".ogg",
        # Archives
        ".zip", ".tar", ".gz", ".bz2", ".7z", ".rar",
        # Executables
        ".exe", ".dll", ".so", ".dylib", ".bin",
        # Documents
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        # Databases
        ".db", ".sqlite", ".sqlite3",
        # Fonts
        ".ttf", ".otf", ".woff", ".woff2", ".eot",
    }

    # Directories to always exclude
    EXCLUDE_DIRECTORIES = {
        # Dependencies
        "node_modules", "bower_components",
        "vendor", "third_party", "external",
        # Python virtual environments
        "venv", "env", ".venv", ".env", "virtualenv", ".virtualenv",
        "site-packages",
        # Build outputs
        "dist", "build", "out", "target", "bin", "obj",
        ".next", ".nuxt", ".vuepress", ".docusaurus",
        "cmake-build-debug", "cmake-build-release",
        # Caches
        ".cache", "__pycache__", ".pytest_cache", ".mypy_cache",
        ".ruff_cache", ".turbo", ".parcel-cache", ".webpack",
        # Version control
        ".git", ".svn", ".hg",
        # IDE
        ".idea", ".vscode", ".vs", ".eclipse",
        # OS
        ".DS_Store", "Thumbs.db",
        # Coverage
        ".coverage", "htmlcov", "coverage",
    }

    # Default time per file (100ms)
    DEFAULT_TIME_PER_FILE = 0.1

    def __init__(
        self,
        directory: Path,
        large_file_threshold_mb: float = 1.0,
        large_dir_threshold: int = 100,
    ):
        """
        Initialize optimization analyzer.

        Args:
            directory: Directory to analyze
            large_file_threshold_mb: Files larger than this are flagged
            large_dir_threshold: Directories with more files than this are flagged
        """
        self.directory = Path(directory).resolve()
        self.large_file_threshold_mb = large_file_threshold_mb
        self.large_dir_threshold = large_dir_threshold

        self.file_stats: Dict[Path, FileStats] = {}
        self.directory_info: Dict[Path, DirectoryInfo] = {}

    def analyze(self) -> AnalysisResult:
        """
        Analyze directory and generate optimization suggestions.

        Returns:
            AnalysisResult with suggestions and impact estimates
        """
        logger.info(f"Analyzing directory: {self.directory}")

        # Scan directory
        self._scan_directory()

        # Generate suggestions
        suggestions = []

        # Detect redundant directories
        dir_suggestions = self._suggest_directory_exclusions()
        suggestions.extend(dir_suggestions)

        # Detect large binary files
        binary_suggestions = self._suggest_binary_exclusions()
        suggestions.extend(binary_suggestions)

        # Detect log files
        log_suggestions = self._suggest_log_exclusions()
        suggestions.extend(log_suggestions)

        # Sort by priority
        suggestions.sort()

        # Calculate totals
        total_files = len(self.file_stats)
        total_size_mb = sum(f.size_bytes for f in self.file_stats.values()) / (1024 * 1024)

        # Calculate indexable files (source code files not in excluded dirs)
        indexable_files = sum(
            1 for f in self.file_stats.values()
            if f.path.suffix in self.SOURCE_EXTENSIONS
            and not self._in_excluded_directory(f.path)
        )

        # Calculate impact
        total_time_savings = sum(s.time_savings_seconds for s in suggestions)
        total_storage_savings = sum(s.size_savings_mb for s in suggestions)

        # Estimate speedup
        baseline_time = total_files * self.DEFAULT_TIME_PER_FILE
        optimized_time = max(1.0, baseline_time - total_time_savings)
        speedup = baseline_time / optimized_time if baseline_time > 0 and optimized_time > 0 else 1.0

        result = AnalysisResult(
            total_files=total_files,
            total_size_mb=total_size_mb,
            indexable_files=indexable_files,
            suggestions=suggestions,
            estimated_speedup=speedup,
            estimated_storage_savings_mb=total_storage_savings,
        )

        logger.info(
            f"Analysis complete: {total_files} files, {len(suggestions)} suggestions, "
            f"{speedup:.1f}x speedup possible"
        )

        return result

    def _scan_directory(self) -> None:
        """Scan directory and collect file statistics."""
        for file_path in self.directory.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip hidden files (but allow .git, .cache, etc. directories)
            skip = False
            for part in file_path.relative_to(self.directory).parts[:-1]:  # Check dirs, not file itself
                if part.startswith(".") and part not in {".git", ".cache", ".vscode", ".idea"}:
                    skip = True
                    break
            if skip:
                continue

            # Skip hidden files (not directories)
            if file_path.name.startswith(".") and file_path.name not in {".gitignore", ".ragignore", ".env.example"}:
                continue

            try:
                size_bytes = file_path.stat().st_size
                is_binary = self._is_binary(file_path)
                mime_type = mimetypes.guess_type(str(file_path))[0]
                category = self._categorize_file(file_path, is_binary)

                self.file_stats[file_path] = FileStats(
                    path=file_path,
                    size_bytes=size_bytes,
                    is_binary=is_binary,
                    mime_type=mime_type,
                    category=category,
                )

                # Track directory info
                parent = file_path.parent
                if parent not in self.directory_info:
                    self.directory_info[parent] = DirectoryInfo(
                        path=parent,
                        file_count=0,
                        total_size_bytes=0,
                        category=self._categorize_directory(parent),
                    )

                dir_info = self.directory_info[parent]
                dir_info.file_count += 1
                dir_info.total_size_bytes += size_bytes

            except Exception as e:
                logger.debug(f"Error analyzing {file_path}: {e}")
                continue

    def _is_binary(self, file_path: Path) -> bool:
        """Check if file is binary."""
        # Check extension first
        if file_path.suffix.lower() in self.BINARY_EXTENSIONS:
            return True

        # Check if it's a known text extension
        if file_path.suffix.lower() in self.SOURCE_EXTENSIONS:
            return False

        # Try to read first chunk
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                # Check for null bytes (binary indicator)
                if b"\x00" in chunk:
                    return True
                # Check if mostly text
                text_chars = sum(1 for b in chunk if 32 <= b < 127 or b in (9, 10, 13))
                return text_chars / len(chunk) < 0.7 if chunk else False
        except Exception:
            return True

    def _categorize_file(self, file_path: Path, is_binary: bool) -> str:
        """Categorize file by type."""
        if is_binary:
            return "binary"

        if file_path.suffix == ".log":
            return "log"

        if file_path.suffix in self.SOURCE_EXTENSIONS:
            return "source"

        # Check parent directory
        for parent in file_path.parents:
            dir_name = parent.name
            if dir_name in {"__pycache__", ".cache", ".pytest_cache"}:
                return "cache"
            if dir_name in {"dist", "build", "out", "target"}:
                return "build"

        return "other"

    def _categorize_directory(self, dir_path: Path) -> str:
        """Categorize directory by name."""
        dir_name = dir_path.name

        if dir_name == "node_modules":
            return "node_modules"
        if dir_name in {"venv", ".venv", "env", ".env", "virtualenv"}:
            return "venv"
        if dir_name in {"dist", "build", "out", "target", ".next", ".nuxt"}:
            return "build"
        if dir_name in {"__pycache__", ".cache", ".pytest_cache", ".mypy_cache"}:
            return "cache"
        if dir_name == ".git":
            return "git"
        if dir_name in {"vendor", "third_party", "external"}:
            return "vendor"

        return "other"

    def _in_excluded_directory(self, file_path: Path) -> bool:
        """Check if file is in an excluded directory."""
        for parent in file_path.parents:
            if parent.name in self.EXCLUDE_DIRECTORIES:
                return True
        return False

    def _suggest_directory_exclusions(self) -> List[OptimizationSuggestion]:
        """Suggest excluding redundant directories."""
        suggestions = []

        # Group by category
        category_dirs: Dict[str, List[DirectoryInfo]] = defaultdict(list)
        for dir_info in self.directory_info.values():
            if dir_info.category != "other":
                category_dirs[dir_info.category].append(dir_info)

        # Suggest exclusions for each category
        category_patterns = {
            "node_modules": ("node_modules/", "Node.js dependencies"),
            "venv": ("venv/", "Python virtual environments (also exclude .venv/, env/)"),
            "build": ("dist/", "Build output directories (also exclude build/, out/, target/)"),
            "cache": ("__pycache__/", "Python cache directories"),
            "git": (".git/", "Git repository metadata"),
            "vendor": ("vendor/", "Third-party dependencies"),
        }

        for category, dirs in category_dirs.items():
            if not dirs or category not in category_patterns:
                continue

            pattern, description = category_patterns[category]

            total_files = sum(d.file_count for d in dirs)
            total_size = sum(d.total_size_bytes for d in dirs)

            # Skip if minimal impact
            if total_files < 5:
                continue

            time_savings = total_files * self.DEFAULT_TIME_PER_FILE
            size_savings_mb = total_size / (1024 * 1024)

            # Priority based on impact
            if category == "node_modules":
                priority = 5  # Highest
            elif category in {"build", "cache", "git"}:
                priority = 4
            else:
                priority = 3

            suggestions.append(
                OptimizationSuggestion(
                    type="exclude_directory",
                    description=f"Exclude {description}",
                    pattern=pattern,
                    affected_files=total_files,
                    size_savings_mb=size_savings_mb,
                    time_savings_seconds=time_savings,
                    priority=priority,
                )
            )

        return suggestions

    def _suggest_binary_exclusions(self) -> List[OptimizationSuggestion]:
        """Suggest excluding large binary files."""
        suggestions = []

        # Find large binaries
        large_binaries = [
            f for f in self.file_stats.values()
            if f.is_binary
            and f.size_bytes > self.large_file_threshold_mb * 1024 * 1024
        ]

        if not large_binaries:
            return suggestions

        # Group by extension
        by_extension: Dict[str, List[FileStats]] = defaultdict(list)
        for file_stat in large_binaries:
            by_extension[file_stat.path.suffix].append(file_stat)

        for ext, files in by_extension.items():
            if len(files) < 3:  # Need at least 3 files to suggest pattern
                continue

            total_size = sum(f.size_bytes for f in files)
            size_savings_mb = total_size / (1024 * 1024)
            time_savings = len(files) * self.DEFAULT_TIME_PER_FILE

            suggestions.append(
                OptimizationSuggestion(
                    type="exclude_pattern",
                    description=f"Exclude large {ext} files",
                    pattern=f"*{ext}",
                    affected_files=len(files),
                    size_savings_mb=size_savings_mb,
                    time_savings_seconds=time_savings,
                    priority=2,
                )
            )

        return suggestions

    def _suggest_log_exclusions(self) -> List[OptimizationSuggestion]:
        """Suggest excluding log files."""
        log_files = [
            f for f in self.file_stats.values()
            if f.category == "log" or f.path.suffix == ".log"
        ]

        if len(log_files) < 10:  # Only suggest if many logs
            return []

        total_size = sum(f.size_bytes for f in log_files)
        size_savings_mb = total_size / (1024 * 1024)
        time_savings = len(log_files) * self.DEFAULT_TIME_PER_FILE

        return [
            OptimizationSuggestion(
                type="exclude_pattern",
                description="Exclude log files",
                pattern="*.log",
                affected_files=len(log_files),
                size_savings_mb=size_savings_mb,
                time_savings_seconds=time_savings,
                priority=2,
            )
        ]

    def generate_ragignore(self, suggestions: List[OptimizationSuggestion]) -> str:
        """
        Generate .ragignore content from suggestions.

        Args:
            suggestions: List of optimization suggestions

        Returns:
            .ragignore file content
        """
        lines = [
            "# .ragignore - Generated by Claude Memory RAG Server",
            "# Patterns to exclude from indexing (gitignore syntax)",
            "",
        ]

        # Group by type
        dir_patterns = [s for s in suggestions if s.type == "exclude_directory"]
        pattern_patterns = [s for s in suggestions if s.type == "exclude_pattern"]

        if dir_patterns:
            lines.append("# Directories")
            for suggestion in dir_patterns:
                lines.append(f"# {suggestion.description}")
                lines.append(suggestion.pattern)
                lines.append("")

        if pattern_patterns:
            lines.append("# File patterns")
            for suggestion in pattern_patterns:
                lines.append(f"# {suggestion.description}")
                lines.append(suggestion.pattern)
                lines.append("")

        return "\n".join(lines)
