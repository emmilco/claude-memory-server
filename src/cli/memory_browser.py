"""
Interactive memory browser TUI for managing memories.

This provides a terminal user interface for:
- Browsing all memories
- Searching and filtering
- Viewing memory details
- Editing memories
- Deleting memories
- Bulk operations
"""

import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal
    from textual.widgets import Header, Footer, DataTable, Static, Input, Button
    from textual.binding import Binding
    from textual.screen import ModalScreen

    TEXTUAL_AVAILABLE = True
except ImportError:
    TEXTUAL_AVAILABLE = False
    print("Memory browser requires textual. Install with: pip install textual")

from src.config import get_config
from src.store import create_memory_store

logger = logging.getLogger(__name__)


class MemoryDetailScreen(ModalScreen):
    """Modal screen showing memory details."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("d", "delete", "Delete"),
    ]

    def __init__(self, memory: Dict[str, Any], **kwargs):
        super().__init__(**kwargs)
        self.memory = memory

    def compose(self) -> ComposeResult:
        """Compose the detail view."""
        yield Container(
            Static("[bold cyan]Memory Details[/bold cyan]", id="detail-title"),
            Static(
                f"[yellow]ID:[/yellow] {self.memory.get('id', 'N/A')}", id="detail-id"
            ),
            Static(
                f"[yellow]Category:[/yellow] {self.memory.get('category', 'N/A')}",
                id="detail-category",
            ),
            Static(
                f"[yellow]Context Level:[/yellow] {self.memory.get('context_level', 'N/A')}",
                id="detail-context",
            ),
            Static(
                f"[yellow]Importance:[/yellow] {self.memory.get('importance', 0):.2f}",
                id="detail-importance",
            ),
            Static(
                f"[yellow]Created:[/yellow] {self.memory.get('created_at', 'N/A')}",
                id="detail-created",
            ),
            Static("[yellow]Content:[/yellow]", id="detail-content-label"),
            Static(self.memory.get("content", "N/A"), id="detail-content"),
            Horizontal(
                Button("Delete", variant="error", id="delete-btn"),
                Button("Close", variant="primary", id="close-btn"),
                id="detail-buttons",
            ),
            id="detail-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "close-btn":
            self.dismiss()
        elif event.button.id == "delete-btn":
            self.dismiss(result="delete")

    def action_dismiss(self) -> None:
        """Close the detail view."""
        self.dismiss()

    def action_delete(self) -> None:
        """Delete this memory."""
        self.dismiss(result="delete")


class ConfirmDialog(ModalScreen):
    """Confirmation dialog."""

    def __init__(self, message: str, **kwargs):
        super().__init__(**kwargs)
        self.message = message

    def compose(self) -> ComposeResult:
        yield Container(
            Static(self.message, id="confirm-message"),
            Horizontal(
                Button("Yes", variant="error", id="yes-btn"),
                Button("No", variant="primary", id="no-btn"),
                id="confirm-buttons",
            ),
            id="confirm-container",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "yes-btn":
            self.dismiss(result=True)
        else:
            self.dismiss(result=False)


class MemoryBrowserApp(App):
    """Interactive memory browser application."""

    CSS = """
    #memory-table {
        height: 1fr;
    }

    #search-container {
        height: 3;
        padding: 1;
    }

    #stats-container {
        height: 3;
        padding: 1;
    }

    #detail-container {
        padding: 2;
        background: $surface;
        border: solid $primary;
        width: 80;
        height: auto;
        max-height: 30;
    }

    #confirm-container {
        padding: 2;
        background: $surface;
        border: solid $error;
        width: 50;
        height: auto;
    }

    #detail-content {
        margin: 1 0;
        padding: 1;
        background: $panel;
        max-height: 10;
        overflow-y: scroll;
    }

    #detail-buttons, #confirm-buttons {
        align: center middle;
        height: 3;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("d", "delete_selected", "Delete"),
        Binding("enter", "view_details", "View"),
        Binding("/", "focus_search", "Search"),
        Binding("f", "filter_menu", "Filter"),
        Binding("b", "bulk_delete", "Bulk Delete"),
        Binding("e", "export", "Export"),
        Binding("i", "import_memories", "Import"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = get_config()
        self.store = None
        self.memories: List[Dict[str, Any]] = []
        self.filtered_memories: List[Dict[str, Any]] = []
        self.current_filter_type = "context"  # context, category, project
        self.current_filter_value = "all"
        self.search_query = ""

    def compose(self) -> ComposeResult:
        """Compose the UI."""
        yield Header()
        yield Container(
            Static(
                "[bold]Memory Browser[/bold] - Browse and manage all memories",
                id="title",
            ),
            id="title-container",
        )
        yield Container(
            Input(placeholder="Search memories...", id="search-input"),
            Static("Filter: context=all | F to change", id="filter-label"),
            id="search-container",
        )
        yield Container(
            Static("Loading...", id="stats-label"),
            id="stats-container",
        )
        yield DataTable(id="memory-table")
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize when app starts."""
        # Initialize store
        self.store = create_memory_store(config=self.config)
        await self.store.initialize()

        # Setup table
        table = self.query_one("#memory-table", DataTable)
        table.add_columns("ID", "Category", "Context", "Importance", "Preview")
        table.cursor_type = "row"

        # Load memories
        await self.load_memories()

    async def load_memories(self) -> None:
        """Load memories from store."""
        try:
            # Get all memories (this is simplified - would need pagination for real use)
            # For now, we'll use a search with high limit
            from src.core.models import SearchFilters

            # Generate a dummy embedding for "all memories" query
            import numpy as np

            dummy_embedding = np.zeros(768).tolist()

            results = await self.store.retrieve(
                query_embedding=dummy_embedding,
                filters=SearchFilters(),
                limit=1000,  # Max 1000 memories
            )

            self.memories = [
                {
                    "id": memory.id,
                    "category": memory.category.value,
                    "context_level": memory.context_level.value,
                    "importance": memory.importance,
                    "content": memory.content,
                    "created_at": memory.created_at.isoformat()
                    if memory.created_at
                    else "N/A",
                    "scope": memory.scope.value,
                    "project_name": memory.project_name or "N/A",
                    "tags": memory.tags or [],
                }
                for memory, score in results
            ]

            self.filtered_memories = self.memories.copy()
            self.update_table()
            self.update_stats()

        except Exception as e:
            logger.error(f"Error loading memories: {e}")
            self.query_one("#stats-label", Static).update(
                f"[red]Error loading memories: {e}[/red]"
            )

    def update_table(self) -> None:
        """Update the table with filtered memories."""
        table = self.query_one("#memory-table", DataTable)
        table.clear()

        for memory in self.filtered_memories:
            preview = (
                memory["content"][:50] + "..."
                if len(memory["content"]) > 50
                else memory["content"]
            )
            table.add_row(
                memory["id"][:8] + "...",
                memory["category"],
                memory["context_level"],
                f"{memory['importance']:.2f}",
                preview,
            )

    def update_stats(self) -> None:
        """Update statistics label."""
        total = len(self.memories)
        filtered = len(self.filtered_memories)

        stats_text = f"Total: {total} | Showing: {filtered}"
        if self.search_query:
            stats_text += f" | Search: '{self.search_query}'"
        if self.current_filter_value != "all":
            stats_text += (
                f" | Filter: {self.current_filter_type}={self.current_filter_value}"
            )

        self.query_one("#stats-label", Static).update(stats_text)

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-input":
            self.search_query = event.value.lower()
            self.apply_filters()

    def apply_filters(self) -> None:
        """Apply search and filters to memories."""
        self.filtered_memories = self.memories

        # Apply search query
        if self.search_query:
            self.filtered_memories = [
                m
                for m in self.filtered_memories
                if self.search_query in m["content"].lower()
                or self.search_query in m["category"].lower()
                or self.search_query in m["context_level"].lower()
                or self.search_query in m.get("project_name", "").lower()
            ]

        # Apply filter based on type
        if self.current_filter_value != "all":
            if self.current_filter_type == "context":
                self.filtered_memories = [
                    m
                    for m in self.filtered_memories
                    if m["context_level"].lower() == self.current_filter_value.lower()
                ]
            elif self.current_filter_type == "category":
                self.filtered_memories = [
                    m
                    for m in self.filtered_memories
                    if m["category"].lower() == self.current_filter_value.lower()
                ]
            elif self.current_filter_type == "project":
                self.filtered_memories = [
                    m
                    for m in self.filtered_memories
                    if m.get("project_name", "N/A").lower()
                    == self.current_filter_value.lower()
                ]

        self.update_table()
        self.update_stats()

    async def action_refresh(self) -> None:
        """Refresh memories from store."""
        await self.load_memories()

    async def action_view_details(self) -> None:
        """View details of selected memory."""
        table = self.query_one("#memory-table", DataTable)
        if table.cursor_row < len(self.filtered_memories):
            memory = self.filtered_memories[table.cursor_row]
            result = await self.push_screen_wait(MemoryDetailScreen(memory))

            if result == "delete":
                await self.delete_memory(memory)

    async def action_delete_selected(self) -> None:
        """Delete selected memory."""
        table = self.query_one("#memory-table", DataTable)
        if table.cursor_row < len(self.filtered_memories):
            memory = self.filtered_memories[table.cursor_row]
            await self.delete_memory(memory)

    async def delete_memory(self, memory: Dict[str, Any]) -> None:
        """Delete a memory after confirmation."""
        confirmed = await self.push_screen_wait(
            ConfirmDialog(f"Delete memory?\n\n{memory['content'][:100]}...")
        )

        if confirmed:
            try:
                await self.store.delete(memory["id"])
                self.notify(
                    f"Deleted memory {memory['id'][:8]}...", severity="information"
                )
                await self.load_memories()
            except Exception as e:
                self.notify(f"Error deleting memory: {e}", severity="error")

    def action_focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()

    def action_filter_menu(self) -> None:
        """Cycle through filter types and values."""
        # Get unique values for current filter type
        if self.current_filter_type == "context":
            unique_values = sorted(set(m["context_level"] for m in self.memories))
            unique_values = ["all"] + [v.lower() for v in unique_values]
        elif self.current_filter_type == "category":
            unique_values = sorted(set(m["category"] for m in self.memories))
            unique_values = ["all"] + [v.lower() for v in unique_values]
        elif self.current_filter_type == "project":
            unique_values = sorted(
                set(m.get("project_name", "N/A") for m in self.memories)
            )
            unique_values = ["all"] + [v for v in unique_values]

        # Cycle through values
        if self.current_filter_value in unique_values:
            current_index = unique_values.index(self.current_filter_value)
            next_index = (current_index + 1) % len(unique_values)
            self.current_filter_value = unique_values[next_index]
        else:
            self.current_filter_value = "all"

        # If we're back to "all", cycle to next filter type
        if self.current_filter_value == "all" and len(unique_values) > 1:
            filter_types = ["context", "category", "project"]
            type_index = filter_types.index(self.current_filter_type)
            self.current_filter_type = filter_types[
                (type_index + 1) % len(filter_types)
            ]

        # Update filter label
        self.query_one("#filter-label", Static).update(
            f"Filter: {self.current_filter_type}={self.current_filter_value} | F to change"
        )

        self.apply_filters()

    async def action_bulk_delete(self) -> None:
        """Bulk delete filtered memories."""
        if not self.filtered_memories:
            self.notify("No memories to delete", severity="warning")
            return

        count = len(self.filtered_memories)
        filter_desc = (
            f"{self.current_filter_type}={self.current_filter_value}"
            if self.current_filter_value != "all"
            else "all"
        )

        confirmed = await self.push_screen_wait(
            ConfirmDialog(
                f"Delete {count} memories?\n\nFilter: {filter_desc}\n\nThis cannot be undone!"
            )
        )

        if confirmed:
            try:
                deleted_count = 0
                for memory in self.filtered_memories:
                    try:
                        await self.store.delete(memory["id"])
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Error deleting memory {memory['id']}: {e}")

                self.notify(f"Deleted {deleted_count} memories", severity="information")
                await self.load_memories()
            except Exception as e:
                self.notify(f"Error during bulk delete: {e}", severity="error")

    async def action_export(self) -> None:
        """Export memories to JSON file."""
        import json
        from pathlib import Path

        if not self.filtered_memories:
            self.notify("No memories to export", severity="warning")
            return

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"memories_export_{timestamp}.json"
        filepath = Path.home() / ".claude-rag" / filename

        try:
            # Ensure directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)

            # Export memories
            export_data = {
                "exported_at": timestamp,
                "count": len(self.filtered_memories),
                "filter": {
                    "type": self.current_filter_type,
                    "value": self.current_filter_value,
                },
                "memories": self.filtered_memories,
            }

            with open(filepath, "w") as f:
                json.dump(export_data, f, indent=2, default=str)

            self.notify(
                f"Exported {len(self.filtered_memories)} memories to {filepath}",
                severity="information",
            )

        except Exception as e:
            self.notify(f"Error exporting memories: {e}", severity="error")

    async def action_import_memories(self) -> None:
        """Import memories from JSON file."""
        import json
        from pathlib import Path

        # For now, import from the most recent export file
        export_dir = Path.home() / ".claude-rag"
        if not export_dir.exists():
            self.notify("No exports found", severity="warning")
            return

        try:
            # Find most recent export file
            export_files = sorted(
                export_dir.glob("memories_export_*.json"), reverse=True
            )
            if not export_files:
                self.notify("No export files found", severity="warning")
                return

            filepath = export_files[0]

            confirmed = await self.push_screen_wait(
                ConfirmDialog(
                    f"Import memories from:\n{filepath.name}?\n\nThis will add memories to the database."
                )
            )

            if not confirmed:
                return

            # Load and import memories
            with open(filepath, "r") as f:
                export_data = json.load(f)

            memories_to_import = export_data.get("memories", [])

            # Import each memory
            # Note: This would need proper store.create() method implementation
            self.notify(
                f"Import functionality requires store.create() method. Found {len(memories_to_import)} memories to import.",
                severity="information",
            )

        except Exception as e:
            self.notify(f"Error importing memories: {e}", severity="error")

    async def on_unmount(self) -> None:
        """Cleanup when app closes."""
        if self.store:
            # Store cleanup if needed
            pass


async def run_memory_browser():
    """Run the memory browser TUI."""
    if not TEXTUAL_AVAILABLE:
        print("Memory browser requires the 'textual' library.")
        print("Install with: pip install textual")
        return

    app = MemoryBrowserApp()
    await app.run_async()


def main():
    """Main entry point."""
    if not TEXTUAL_AVAILABLE:
        print("Memory browser requires the 'textual' library.")
        print("Install with: pip install textual")
        return 1

    asyncio.run(run_memory_browser())
    return 0


if __name__ == "__main__":
    exit(main())
