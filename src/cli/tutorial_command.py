"""Interactive tutorial command for new users (UX-008 Phase 2)."""

import asyncio
import logging
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
from rich import box

from src.config import get_config

logger = logging.getLogger(__name__)
console = Console()


async def tutorial_command():
    """Run interactive tutorial for new users."""

    # Welcome screen
    console.clear()
    welcome = Panel(
        "[bold cyan]Welcome to Claude Memory RAG Server![/bold cyan]\n\n"
        "This interactive tutorial will guide you through:\n"
        "• Understanding what this tool does\n"
        "• Indexing your first codebase\n"
        "• Searching code semantically\n"
        "• Managing memories\n"
        "• Configuring the system\n\n"
        "[dim]Estimated time: 5-10 minutes[/dim]",
        title="🎓 Tutorial",
        border_style="cyan",
        box=box.DOUBLE,
    )
    console.print(welcome)

    if not Confirm.ask("\n[bold]Ready to start?[/bold]", default=True):
        console.print(
            "[yellow]Tutorial cancelled. Run 'claude-rag tutorial' anytime![/yellow]"
        )
        return

    # Step 1: What is Claude Memory RAG?
    console.clear()
    console.print(
        Panel("[bold]Step 1/6: What is Claude Memory RAG?[/bold]", border_style="cyan")
    )
    console.print()

    explanation = """
## What This Tool Does

Claude Memory RAG Server gives Claude **persistent memory** and **semantic code understanding**.

**Three Core Capabilities:**

1. **📚 Semantic Code Search** - Find code by *meaning*, not keywords
   - "Find authentication logic" → Returns relevant functions
   - Works across 15 file formats (Python, JS, TS, Java, Go, Rust, etc.)

2. **🧠 Persistent Memory** - Claude remembers across sessions
   - Preferences: "I prefer TypeScript"
   - Facts: "This project uses PostgreSQL"
   - Events: "Fixed auth bug on Nov 15"

3. **🔍 Git History Search** - Semantic search over commit history
   - "When did we add caching?" → Finds relevant commits

**How It Works:**
- Indexes your code into semantic units (functions, classes)
- Stores memories with embeddings for semantic search
- Serves Claude via MCP (Model Context Protocol)
    """

    console.print(Markdown(explanation))
    Prompt.ask("\n[dim]Press Enter to continue[/dim]", default="")

    # Step 2: Check System Status
    console.clear()
    console.print(
        Panel("[bold]Step 2/6: Check Your System Status[/bold]", border_style="cyan")
    )
    console.print()

    console.print("Let's verify your installation is working correctly...\n")

    config = get_config()

    # Show configuration
    console.print(f"✓ Storage backend: [green]{config.storage_backend}[/green]")
    console.print(f"✓ Embedding model: [green]{config.embedding_model}[/green]")
    console.print(
        f"✓ Parallel embeddings: [green]{'enabled' if config.performance.parallel_embeddings else 'disabled'}[/green]"
    )

    if config.storage_backend == "qdrant":
        console.print(f"✓ Qdrant URL: [green]{config.qdrant_url}[/green]")
    else:
        console.print(f"✓ SQLite path: [green]{config.sqlite_path}[/green]")

    console.print(
        "\n[dim]You can run 'claude-rag health' anytime for detailed diagnostics[/dim]"
    )
    Prompt.ask("\n[dim]Press Enter to continue[/dim]", default="")

    # Step 3: Index Your First Codebase
    console.clear()
    console.print(
        Panel("[bold]Step 3/6: Index Your First Codebase[/bold]", border_style="cyan")
    )
    console.print()

    console.print("To enable semantic code search, you need to index a codebase.\n")
    console.print(
        "[bold]Command:[/bold] claude-rag index <path> --project-name <name>\n"
    )
    console.print("[bold]Example:[/bold]")
    console.print("  claude-rag index ~/my-project --project-name myapp\n")
    console.print("This will:")
    console.print("  1. Parse all code files (Python, JS, TS, etc.)")
    console.print("  2. Extract semantic units (functions, classes)")
    console.print("  3. Generate embeddings for semantic search")
    console.print("  4. Store in vector database\n")

    if Confirm.ask(
        "[bold]Would you like to try indexing a directory now?[/bold]", default=False
    ):
        path = Prompt.ask("Enter directory path", default=".")
        project_name = Prompt.ask("Enter project name", default=Path(path).name)

        console.print("\n[green]Great! Run this command:[/green]")
        console.print(
            f"[bold cyan]  claude-rag index {path} --project-name {project_name}[/bold cyan]\n"
        )
        console.print(
            "[dim]After this tutorial, you can run the command to index.[/dim]"
        )
    else:
        console.print("[yellow]No problem! You can index later with:[/yellow]")
        console.print("[bold]  claude-rag index <path> --project-name <name>[/bold]")

    Prompt.ask("\n[dim]Press Enter to continue[/dim]", default="")

    # Step 4: Search Code
    console.clear()
    console.print(
        Panel("[bold]Step 4/6: Search Code Semantically[/bold]", border_style="cyan")
    )
    console.print()

    console.print("Once indexed, Claude can search your code by meaning!\n")
    console.print("[bold]Example Searches:[/bold]\n")
    console.print("  🔍 'Find authentication logic'")
    console.print("     → Returns login(), verify_token(), etc.\n")
    console.print("  🔍 'Where do we handle database errors?'")
    console.print("     → Returns error handlers and retry logic\n")
    console.print("  🔍 'Show me all API endpoints'")
    console.print("     → Returns route definitions\n")

    console.print("[bold cyan]How to use:[/bold cyan]")
    console.print("  • In Claude: Just ask! Claude uses MCP to search automatically")
    console.print("  • CLI: Use 'search_code' MCP tool (via Claude)\n")

    Prompt.ask("\n[dim]Press Enter to continue[/dim]", default="")

    # Step 5: Manage Memories
    console.clear()
    console.print(Panel("[bold]Step 5/6: Manage Memories[/bold]", border_style="cyan"))
    console.print()

    console.print("Claude can store and retrieve memories across sessions!\n")
    console.print("[bold]Memory Categories:[/bold]")
    console.print("  • preference - Your preferences (e.g., 'I prefer Python')")
    console.print("  • fact - Project facts (e.g., 'Uses PostgreSQL')")
    console.print("  • event - Significant events (e.g., 'Fixed auth bug')")
    console.print("  • workflow - Common workflows (e.g., 'Always run tests')")
    console.print("  • context - Session context\n")

    console.print("[bold]CLI Commands:[/bold]")
    console.print("  • claude-rag browse     - Interactive memory browser (TUI)")
    console.print("  • claude-rag prune      - Clean up expired memories")
    console.print("  • claude-rag consolidate - Merge duplicate memories\n")

    if Confirm.ask("[bold]Want to try the memory browser?[/bold]", default=False):
        console.print(
            "\n[green]Great! Run:[/green] [bold cyan]claude-rag browse[/bold cyan]"
        )
        console.print(
            "[dim]You can explore, search, and filter memories interactively.[/dim]\n"
        )

    Prompt.ask("\n[dim]Press Enter to continue[/dim]", default="")

    # Step 6: Next Steps
    console.clear()
    console.print(
        Panel("[bold]Step 6/6: Next Steps & Resources[/bold]", border_style="cyan")
    )
    console.print()

    console.print("[bold green]🎉 Tutorial Complete![/bold green]\n")
    console.print("[bold]Quick Reference:[/bold]\n")
    console.print("  📖 Full docs: README.md")
    console.print("  ⚙️  Configuration: config.json.example or .env.example")
    console.print("  🔧 Troubleshooting: docs/TROUBLESHOOTING.md")
    console.print("  💻 All commands: claude-rag --help\n")

    console.print("[bold]Common Commands:[/bold]\n")
    console.print("  claude-rag index <path>      # Index codebase")
    console.print("  claude-rag watch <path>      # Auto-reindex on changes")
    console.print("  claude-rag health           # System diagnostics")
    console.print("  claude-rag status           # View indexed projects")
    console.print("  claude-rag browse           # Memory browser (TUI)")
    console.print("  claude-rag git-index <repo>  # Index git history\n")

    console.print("[bold]Configuration Files:[/bold]\n")
    console.print("  ~/.claude-rag/config.json   # JSON config (recommended)")
    console.print("  .env                        # Environment variables")
    console.print("  See config.json.example for all options\n")

    console.print("[bold cyan]Pro Tips:[/bold cyan]\n")
    console.print("  💡 Use 'claude-rag validate-install' to check setup")
    console.print("  💡 Run 'claude-rag tutorial' anytime to review")
    console.print("  💡 Most commands have --help for detailed options")
    console.print("  💡 Use --dry-run to preview before destructive operations\n")

    if Confirm.ask(
        "[bold]Would you like to see your current system status?[/bold]", default=True
    ):
        console.print("\n[dim]Run: claude-rag status[/dim]")
        console.print("[dim]Or: claude-rag health (for detailed diagnostics)[/dim]\n")

    console.print(
        Panel(
            "[bold green]Thank you for using Claude Memory RAG Server![/bold green]\n\n"
            "Happy coding! 🚀",
            border_style="green",
        )
    )


def main():
    """Entry point for tutorial command."""
    asyncio.run(tutorial_command())


if __name__ == "__main__":
    main()
