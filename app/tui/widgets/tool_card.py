from __future__ import annotations

"""Enhanced tool call card — simple header + body without Collapsible."""

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from .. import theme as T


class ToolCard(Widget):
    """A collapsible card showing a pipeline stage call.

    Supports: queued, running, success, failed, skipped.
    Auto-collapses success cards; auto-expands failed ones.
    """

    DEFAULT_CSS = """
    ToolCard {
        margin: 0 0 0 1;
        height: auto;
    }
    ToolCard .tool-header {
        color: $text;
        height: 1;
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
        attempts: int = 1,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.tool_name = name
        self._status = status
        self._message = message
        self._detail = detail or ""
        self._duration = duration
        self._attempts = attempts

    @property
    def status(self) -> str:
        return self._status

    def update(
        self,
        status: str | None = None,
        message: str | None = None,
        detail: str | None = None,
        duration: float | None = None,
        attempts: int | None = None,
    ) -> None:
        if status is not None:
            self._status = status
        if message is not None:
            self._message = message
        if detail is not None:
            self._detail = detail
        if duration is not None:
            self._duration = duration
        if attempts is not None:
            self._attempts = attempts
        self._refresh_display()

    def _format_duration(self) -> str:
        if self._duration is None:
            return ""
        if self._duration >= 60:
            mins = int(self._duration // 60)
            secs = self._duration % 60
            return f"{mins}m{secs:.0f}s"
        return f"{self._duration:.1f}s"

    def _status_label(self) -> str:
        labels: dict[str, str] = {
            "queued": "queued",
            "running": "running",
            "success": "success",
            "failed": "failed",
            "skipped": "skipped",
            "cancelled": "cancelled",
        }
        return labels.get(self._status, self._status)

    def _refresh_display(self) -> None:
        icon_map = {
            "queued": "○",
            "running": "●",
            "success": "✓",
            "failed": "✗",
            "skipped": "–",
            "cancelled": "–",
        }
        icon = icon_map.get(self._status, "●")
        color = T.stage_color(self._status)

        dur = self._format_duration()
        dur_str = f" {dur}" if dur else ""
        label = self._status_label()
        attempt = f" [{self._attempts}]" if self._attempts > 1 else ""

        header_text = (
            f"[bold {color}]{icon} {self.tool_name}[/] "
            f"[dim {color}]{label}{dur_str}{attempt}[/]"
        )
        try:
            self.query_one(".tool-header", Static).update(header_text)
        except Exception:
            pass

        body_text = self._detail or self._message or ""
        try:
            body = self.query_one(".tool-body", Static)
            if body_text:
                body.update(body_text)
                body.display = True
            else:
                body.display = False
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        yield Static("", classes="tool-header")
        body = Static("", classes="tool-body")
        body.display = False
        yield body

    def on_mount(self) -> None:
        self._refresh_display()
