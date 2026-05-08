from __future__ import annotations

"""Help panel showing available slash commands."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from .. import theme as T

_COMMAND_HELP: dict[str, list[tuple[str, str]]] = {
    "Input": [
        ("/input <path>", "Set local PDF path (use @ for local files)"),
        ("/repo <url>", "Set GitHub repository URL directly"),
        ("/repo-dir <path>", "Set local repository directory"),
    ],
    "Run": [
        ("/run", "Execute the full reproduction pipeline"),
        ("/cancel", "Cancel current pipeline run"),
        ("/backend <type>", "Set backend: none|local|venv|conda|docker"),
        ("/workspace <path>", "Set output workspace directory"),
        ("/timeout <minutes>", "Set timeout for pipeline steps"),
        ("/repairs <n>", "Set max dependency repair attempts"),
    ],
    "View": [
        ("/status", "Show current session and pipeline status"),
        ("/report", "Show reproduction report path and summary"),
        ("/logs <type>", "View logs: env|conda|venv|build|smoke|benchmark|reproduction|stdout|stderr"),
        ("/artifact", "Show current task directory and output paths"),
        ("/open-report", "Print report file path"),
    ],
    "Mode": [
        ("/plan", "Switch to PLAN mode (no execution)"),
        ("/act", "Switch to ACT mode (execute pipeline)"),
        ("/panel <name>", "Show panel: session|pipeline|help|artifacts|none"),
        ("/mode", "Display current PLAN/ACT mode"),
    ],
    "Session": [
        ("/sessions", "List saved sessions"),
        ("/resume <id>", "Resume a previous session"),
        ("/reset", "Clear current session input (no disk deletion)"),
        ("/clear", "Clear message timeline"),
    ],
    "System": [
        ("/help", "Show this help"),
        ("!shell <command>", "Run shell command (confirmation required)"),
        ("/quit | /exit", "Exit the TUI"),
        ("ctrl+c", "Quit immediately"),
        ("ctrl+p", "Toggle PLAN/ACT mode"),
        ("ctrl+l", "Clear message timeline"),
    ],
}


class HelpPanel(Widget):
    """Scrollable slash-command reference."""

    DEFAULT_CSS = """
    HelpPanel {
        width: 34;
        height: 1fr;
        background: $surface;
        border-left: solid $primary-darken-2;
        padding: 0 1;
    }
    HelpPanel #help-title {
        height: 1;
        color: $text;
        padding: 1 0 0 0;
    }
    HelpPanel #help-body {
        height: 1fr;
        padding: 1 0 0 0;
    }
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static("[bold]Commands[/]", id="help-title")
            yield Static("", id="help-body")

    def on_mount(self) -> None:
        self._build()

    def _build(self) -> None:
        lines: list[str] = []
        for category, cmds in _COMMAND_HELP.items():
            lines.append(f"\n[bold {T.INFO_BORDER}]{category}[/]")
            for cmd, desc in cmds:
                lines.append(f"  [{T.GREEN}]{cmd}[/]")
                lines.append(f"    [{T.FG_DIM}]{desc}[/]")
        content = "\n".join(lines)
        try:
            self.query_one("#help-body", Static).update(content)
        except Exception:
            pass
