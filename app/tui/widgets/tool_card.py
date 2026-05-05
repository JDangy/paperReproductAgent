from __future__ import annotations

"""Tool call card widget - collapsible display for pipeline stages."""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static, Collapsible

from .. import theme as T


class ToolCard(Widget):
    """A collapsible card showing a tool/pipeline stage call."""

    DEFAULT_CSS = """
    ToolCard {
        margin: 0 0 0 1;
        height: auto;
    }
    ToolCard .tool-header {
        color: $text;
    }
    ToolCard .tool-body {
        color: $text-muted;
        margin-left: 2;
    }
    """

    class StatusChanged(Message):
        def __init__(self, status: str) -> None:
            self.status = status
            super().__init__()

    def __init__(
        self,
        name: str,
        status: str = "running",
        message: str = "",
        detail: str | None = None,
        duration: float | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.tool_name = name
        self._status = status
        self._message = message
        self._detail = detail or ""
        self._duration = duration

    @property
    def status(self) -> str:
        return self._status

    def update(
        self,
        status: str | None = None,
        message: str | None = None,
        detail: str | None = None,
        duration: float | None = None,
    ) -> None:
        if status is not None:
            self._status = status
        if message is not None:
            self._message = message
        if detail is not None:
            self._detail = detail
        if duration is not None:
            self._duration = duration
        self._refresh_display()

    def _refresh_display(self) -> None:
        icon = {"running": "▸", "success": "✓", "failed": "✗"}.get(self._status, "▸")
        color = {
            "running": T.TOOL_BORDER,
            "success": T.SUCCESS_BORDER,
            "failed": T.ERROR_BORDER,
        }.get(self._status, T.TOOL_BORDER)

        duration_str = ""
        if self._duration is not None:
            if self._duration >= 60:
                mins = int(self._duration // 60)
                secs = self._duration % 60
                duration_str = f"  {mins}m{secs:.0f}s"
            else:
                duration_str = f"  {self._duration:.1f}s"

        header_text = f"[bold {color}]{icon}[/] [{color}]{self.tool_name}[/][dim]{duration_str}[/dim]"
        try:
            header = self.query_one(".tool-header", Static)
            header.update(header_text)
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        icon = "▸"
        color = T.TOOL_BORDER
        duration_str = ""

        header_text = f"[bold {color}]{icon}[/] [{color}]{self.tool_name}[/][dim]{duration_str}[/dim]"

        with Collapsible(title="", classes="tool-collapsible"):
            yield Static(header_text, classes="tool-header")
            if self._detail:
                yield Static(self._detail, classes="tool-body")

    def on_mount(self) -> None:
        self._refresh_display()
