"""Smart dependency checking with helpful error messages."""

from typing import Optional, Any
from src.core.exceptions import DependencyError


def safe_import(
    module_name: str, package_name: Optional[str] = None, context: str = ""
) -> Any:
    """
    Safely import a module with helpful error message if missing.

    Args:
        module_name: Module to import (e.g., "sentence_transformers")
        package_name: PyPI package name if different from module (e.g., "sentence-transformers")
        context: What the module is used for

    Returns:
        Imported module

    Raises:
        DependencyError: If module cannot be imported with installation instructions
    """
    try:
        return __import__(module_name)
    except ImportError as e:
        pkg = package_name or module_name
        raise DependencyError(pkg, context) from e


def check_sentence_transformers() -> Any:
    """
    Check sentence-transformers is available.

    Returns:
        sentence_transformers module

    Raises:
        DependencyError: If not installed
    """
    return safe_import(
        "sentence_transformers",
        package_name="sentence-transformers",
        context="required for embedding generation",
    )


def check_qdrant_client() -> Any:
    """
    Check qdrant-client is available.

    Returns:
        qdrant_client module

    Raises:
        DependencyError: If not installed
    """
    return safe_import(
        "qdrant_client",
        package_name="qdrant-client",
        context="required for vector storage with Qdrant",
    )


def check_tree_sitter() -> Any:
    """
    Check tree-sitter is available.

    Returns:
        tree_sitter module

    Raises:
        DependencyError: If not installed
    """
    return safe_import(
        "tree_sitter",
        package_name="tree-sitter",
        context="required for code parsing",
    )


def check_watchdog() -> Any:
    """
    Check watchdog is available.

    Returns:
        watchdog module

    Raises:
        DependencyError: If not installed
    """
    return safe_import(
        "watchdog",
        package_name="watchdog",
        context="required for file watching",
    )


def check_rich() -> Any:
    """
    Check rich is available.

    Returns:
        rich module

    Raises:
        DependencyError: If not installed
    """
    return safe_import(
        "rich",
        package_name="rich",
        context="required for terminal UI",
    )


def check_textual() -> Any:
    """
    Check textual is available.

    Returns:
        textual module

    Raises:
        DependencyError: If not installed
    """
    return safe_import(
        "textual",
        package_name="textual",
        context="required for interactive TUI applications",
    )


def check_anthropic() -> Any:
    """
    Check anthropic is available.

    Returns:
        anthropic module

    Raises:
        DependencyError: If not installed
    """
    return safe_import(
        "anthropic",
        package_name="anthropic",
        context="required for Claude API integration",
    )


def check_mcp() -> Any:
    """
    Check mcp is available.

    Returns:
        mcp module

    Raises:
        DependencyError: If not installed
    """
    return safe_import(
        "mcp",
        package_name="mcp",
        context="required for Model Context Protocol server",
    )


def check_gitpython() -> Any:
    """
    Check GitPython is available.

    Returns:
        git module

    Raises:
        DependencyError: If not installed
    """
    return safe_import(
        "git",
        package_name="GitPython",
        context="required for Git history indexing",
    )


def check_apscheduler() -> Any:
    """
    Check APScheduler is available.

    Returns:
        apscheduler module

    Raises:
        DependencyError: If not installed
    """
    return safe_import(
        "apscheduler",
        package_name="apscheduler",
        context="required for background job scheduling",
    )


def check_numpy() -> Any:
    """
    Check numpy is available.

    Returns:
        numpy module

    Raises:
        DependencyError: If not installed
    """
    return safe_import(
        "numpy",
        package_name="numpy",
        context="required for numerical operations",
    )


def check_pydantic() -> Any:
    """
    Check pydantic is available.

    Returns:
        pydantic module

    Raises:
        DependencyError: If not installed
    """
    return safe_import(
        "pydantic",
        package_name="pydantic",
        context="required for data validation",
    )


def check_all_dependencies() -> dict[str, bool]:
    """
    Check all dependencies and return status.

    Returns:
        Dictionary mapping package name to availability (True/False)
    """
    dependencies = {
        "sentence-transformers": check_sentence_transformers,
        "qdrant-client": check_qdrant_client,
        "tree-sitter": check_tree_sitter,
        "watchdog": check_watchdog,
        "rich": check_rich,
        "textual": check_textual,
        "anthropic": check_anthropic,
        "mcp": check_mcp,
        "GitPython": check_gitpython,
        "apscheduler": check_apscheduler,
        "numpy": check_numpy,
        "pydantic": check_pydantic,
    }

    results = {}
    for name, check_func in dependencies.items():
        try:
            check_func()
            results[name] = True
        except DependencyError:
            results[name] = False

    return results
