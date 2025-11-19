"""Installation validation command."""

import asyncio
import sys
from typing import List
from src.core.system_check import SystemChecker, SystemRequirement
from src.core.dependency_checker import check_all_dependencies

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


async def validate_installation():
    """
    Validate that the installation is complete and functional.

    Checks:
    - System prerequisites (Python, Docker, Rust, Git)
    - Python package dependencies
    - Qdrant connectivity (optional)
    - Embedding model availability
    - Rust parser availability

    Returns:
        bool: True if all required components are available
    """
    console = Console() if RICH_AVAILABLE else None

    if console:
        console.print()
        console.print(
            Panel.fit(
                "[bold blue]Claude Memory RAG Server - Installation Validation[/bold blue]",
                border_style="blue",
            )
        )
        console.print()
    else:
        print("\n" + "=" * 60)
        print("Claude Memory RAG Server - Installation Validation")
        print("=" * 60 + "\n")

    all_ok = True

    # 1. System prerequisites
    if console:
        console.print("[bold cyan]1. System Prerequisites[/bold cyan]\n")
    else:
        print("1. System Prerequisites\n")

    checker = SystemChecker()
    requirements = checker.check_all()

    # Print system info
    if console:
        console.print(f"OS: [yellow]{checker.os_type} {checker.os_version}[/yellow]")
        console.print(f"Platform: [dim]{checker.os_platform}[/dim]\n")
    else:
        print(f"OS: {checker.os_type} {checker.os_version}")
        print(f"Platform: {checker.os_platform}\n")

    # Group by priority
    required = [r for r in requirements if r.priority == "required"]
    recommended = [r for r in requirements if r.priority == "recommended"]
    optional = [r for r in requirements if r.priority == "optional"]

    def print_requirement(req: SystemRequirement, show_commands: bool = False):
        nonlocal all_ok

        if console:
            status = "✅" if req.installed else "❌"
            version_str = f" ({req.version})" if req.version else ""
            console.print(f"{status} {req.name}{version_str} [{req.priority.upper()}]")

            if not req.installed and show_commands:
                console.print(f"\n   [dim]Install:[/dim]")
                for line in req.install_command.split("\n"):
                    console.print(f"   [dim]{line}[/dim]")
                console.print()
        else:
            status = "✅" if req.installed else "❌"
            version_str = f" ({req.version})" if req.version else ""
            print(f"{status} {req.name}{version_str} [{req.priority.upper()}]")

            if not req.installed and show_commands:
                print("\n   Install:")
                for line in req.install_command.split("\n"):
                    print(f"   {line}")
                print()

        if req.priority == "required" and not req.installed:
            all_ok = False

    # Required
    if console:
        console.print("[yellow]Required:[/yellow]")
    else:
        print("Required:")

    for req in required:
        print_requirement(req, show_commands=True)

    if console:
        console.print()

    # Recommended
    if console:
        console.print("[yellow]Recommended:[/yellow]")
    else:
        print("\nRecommended:")

    for req in recommended:
        print_requirement(req, show_commands=not req.installed)

    if console:
        console.print()

    # Optional
    if console:
        console.print("[yellow]Optional (for performance):[/yellow]")
    else:
        print("\nOptional (for performance):")

    for req in optional:
        print_requirement(req, show_commands=not req.installed)

    if console:
        console.print()

    # 2. Python packages
    if console:
        console.print("[bold cyan]2. Python Dependencies[/bold cyan]\n")
    else:
        print("\n2. Python Dependencies\n")

    dependencies_status = check_all_dependencies()

    # Categorize dependencies
    required_deps = [
        "sentence-transformers",
        "tree-sitter",
        "numpy",
        "pydantic",
        "mcp",
    ]
    recommended_deps = ["qdrant-client", "anthropic", "rich", "GitPython"]
    optional_deps = ["textual", "watchdog", "apscheduler"]

    def print_dependency_group(deps: List[str], group_name: str):
        nonlocal all_ok

        if console:
            console.print(f"[yellow]{group_name}:[/yellow]")
        else:
            print(f"{group_name}:")

        for dep in deps:
            installed = dependencies_status.get(dep, False)
            status = "✅" if installed else "❌"

            if console:
                console.print(f"{status} {dep}")
            else:
                print(f"{status} {dep}")

            if not installed:
                if console:
                    console.print(f"   [dim]Install: pip install {dep}[/dim]")
                else:
                    print(f"   Install: pip install {dep}")

                if dep in required_deps:
                    all_ok = False

        if console:
            console.print()

    print_dependency_group(required_deps, "Required")
    print_dependency_group(recommended_deps, "Recommended")
    print_dependency_group(optional_deps, "Optional")

    # 3. Qdrant connectivity
    if console:
        console.print("[bold cyan]3. Qdrant Vector Store[/bold cyan]\n")
    else:
        print("\n3. Qdrant Vector Store\n")

    try:
        from src.store.qdrant_store import QdrantMemoryStore
        from src.config import ServerConfig

        config = ServerConfig()
        store = QdrantMemoryStore(config)

        if console:
            console.print(f"✅ Qdrant reachable at [cyan]{config.qdrant_url}[/cyan]")
            console.print(
                "   [dim]Performance: Optimal (vector search, semantic similarity)[/dim]"
            )
        else:
            print(f"✅ Qdrant reachable at {config.qdrant_url}")
            print("   Performance: Optimal (vector search, semantic similarity)")

    except Exception as e:
        if console:
            console.print(f"⚠️  Qdrant not available: [yellow]{e}[/yellow]")
            console.print(
                "   [dim]System will use SQLite fallback (keyword search only)[/dim]"
            )
            console.print("   [dim]Performance impact: 3-5x slower search[/dim]")
            console.print()
            console.print("   [dim]To enable Qdrant:[/dim]")
            console.print("   [dim]docker-compose up -d[/dim]")
        else:
            print(f"⚠️  Qdrant not available: {e}")
            print("   System will use SQLite fallback (keyword search only)")
            print("   Performance impact: 3-5x slower search")
            print()
            print("   To enable Qdrant:")
            print("   docker-compose up -d")

    if console:
        console.print()

    # 4. Rust parser
    if console:
        console.print("[bold cyan]4. Code Parser[/bold cyan]\n")
    else:
        print("\n4. Code Parser\n")

    try:
        import rust_core

        if console:
            console.print("✅ Rust parser available")
            console.print("   [dim]Performance: Optimal (1-6ms per file)[/dim]")
        else:
            print("✅ Rust parser available")
            print("   Performance: Optimal (1-6ms per file)")

    except ImportError:
        if console:
            console.print("⚠️  Rust parser not built")
            console.print(
                "   [dim]System will use Python fallback (tree-sitter)[/dim]"
            )
            console.print("   [dim]Performance impact: 10-20x slower parsing[/dim]")
            console.print()
            console.print("   [dim]To enable Rust parser:[/dim]")
            console.print("   [dim]cd rust_core && maturin develop[/dim]")
        else:
            print("⚠️  Rust parser not built")
            print("   System will use Python fallback (tree-sitter)")
            print("   Performance impact: 10-20x slower parsing")
            print()
            print("   To enable Rust parser:")
            print("   cd rust_core && maturin develop")

    if console:
        console.print()

    # 5. Embedding model
    if console:
        console.print("[bold cyan]5. Embedding Model[/bold cyan]\n")
    else:
        print("\n5. Embedding Model\n")

    try:
        from src.embeddings.generator import EmbeddingGenerator
        from src.config import ServerConfig

        config = ServerConfig()
        generator = EmbeddingGenerator(config)

        # Try to load the model
        _ = generator.model

        if console:
            console.print(
                f"✅ Embedding model loaded: [cyan]{config.embedding_model}[/cyan]"
            )
            console.print("   [dim]Dimensions: 384[/dim]")
        else:
            print(f"✅ Embedding model loaded: {config.embedding_model}")
            print("   Dimensions: 384")

    except Exception as e:
        if console:
            console.print(f"❌ Embedding model failed to load: [red]{e}[/red]")
            console.print()
            console.print("   [dim]The model will download on first use[/dim]")
            console.print("   [dim]Requires: ~100MB disk space, internet connection[/dim]")
        else:
            print(f"❌ Embedding model failed to load: {e}")
            print()
            print("   The model will download on first use")
            print("   Requires: ~100MB disk space, internet connection")

        all_ok = False

    if console:
        console.print()

    # Summary
    if console:
        console.print("=" * 60)
        console.print()
    else:
        print("\n" + "=" * 60 + "\n")

    if all_ok:
        if console:
            console.print("✅ [bold green]Installation valid! Ready to use.[/bold green]\n")
            console.print("[cyan]Quick start:[/cyan]")
            console.print("  [dim]python -m src.cli index ./your-code[/dim]")
            console.print("  [dim]python -m src.cli status[/dim]")
            console.print()
        else:
            print("✅ Installation valid! Ready to use.\n")
            print("Quick start:")
            print("  python -m src.cli index ./your-code")
            print("  python -m src.cli status\n")
        return True
    else:
        if console:
            console.print(
                "❌ [bold red]Installation incomplete. Fix required errors above.[/bold red]\n"
            )
            console.print("[cyan]For help:[/cyan]")
            console.print(
                "  [dim]docs/troubleshooting.md[/dim] - Common installation issues"
            )
            console.print(
                "  [dim]docs/setup.md[/dim] - Complete setup instructions"
            )
            console.print()
        else:
            print("❌ Installation incomplete. Fix required errors above.\n")
            print("For help:")
            print("  docs/troubleshooting.md - Common installation issues")
            print("  docs/setup.md - Complete setup instructions\n")
        return False


def main():
    """Entry point for validation command."""
    try:
        result = asyncio.run(validate_installation())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nValidation interrupted.")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
