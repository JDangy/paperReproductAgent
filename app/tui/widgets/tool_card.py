from __future__ import annotations

"""Collapsible stage card — self-managed collapse, log buffer, no Collapsible widget."""

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static

from .. import theme as T

# Chinese labels
_STAGE_CN: dict[str, str] = {
    "Ingest paper": "解析论文",
    "Understand paper": "理解论文",
    "Search GitHub": "搜索 GitHub",
    "Evaluate repo": "评估仓库",
    "Build conda env": "构建 conda 环境",
    "Build virtualenv": "构建虚拟环境",
    "Build Docker image": "构建 Docker 镜像",
    "Run smoke command": "运行冒烟测试",
    "Run benchmark reproduction": "运行 benchmark 复现",
    "Run simple reproduction": "运行轻量复现",
    "Write report": "生成报告",
}

_STATUS_CN: dict[str, str] = {
    "queued": "等待",
    "running": "运行中",
    "success": "完成",
    "failed": "失败",
    "skipped": "跳过",
    "cancelled": "取消",
    "disabled": "禁用",
}

_ICON_MAP: dict[str, str] = {
    "queued": "○", "running": "●", "success": "✓",
    "failed": "✗", "skipped": "–", "cancelled": "–", "disabled": "–",
}


def _clean(text: str) -> str:
    """Remove Markdown bold markers from display text."""
    return text.replace("**", "").replace("__", "").strip()


class ToolCard(Widget):
    """A single pipeline stage card: click to expand/collapse."""

    DEFAULT_CSS = """
    ToolCard {
        margin: 0 0 1 1;
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

        # Collapse state
        self._collapsed = True
        self._log_lines: list[str] = []
        self._max_expanded = 5

    # ── Properties ──────────────────────────────────────────

    @property
    def status(self) -> str: return self._status

    @property
    def stage_label(self) -> str:
        return _STAGE_CN.get(self.tool_name, self.tool_name)

    @property
    def status_label(self) -> str:
        return _STATUS_CN.get(self._status, self._status)

    @property
    def icon(self) -> str:
        return _ICON_MAP.get(self._status, "●")

    @property
    def color(self) -> str:
        return T.stage_color(self._status)

    def latest_log(self) -> str:
        return self._log_lines[-1] if self._log_lines else self._message or ""

    # ── Log buffer ──────────────────────────────────────────

    def append_log(self, line: str) -> None:
        clean = _clean(line)
        if not clean:
            return
        if self._log_lines and clean == self._log_lines[-1]:
            return  # dedup consecutive identical lines
        self._log_lines.append(clean)
        if len(self._log_lines) > 200:
            self._log_lines = self._log_lines[-200:]

    def get_visible_logs(self) -> list[str]:
        return self._log_lines[-self._max_expanded:] if self._log_lines else []

    # ── Collapse ────────────────────────────────────────────

    def toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self._refresh_display()

    # ── Update ──────────────────────────────────────────────

    def update(
        self,
        status: str | None = None,
        message: str | None = None,
        detail: str | None = None,
        duration: float | None = None,
        attempts: int | None = None,
        append_log: str | None = None,
    ) -> None:
        if status is not None:
            self._status = status
        if message is not None:
            self._message = _clean(message)
        if detail is not None:
            self._detail = _clean(detail)
            if detail.strip():
                for line in detail.splitlines():
                    self.append_log(line)
        if duration is not None:
            self._duration = duration
        if attempts is not None:
            self._attempts = attempts
        if append_log is not None:
            self.append_log(append_log)

        self._refresh_display()

    # ── Display ─────────────────────────────────────────────

    def _format_duration(self) -> str:
        if self._duration is None:
            return ""
        d = self._duration
        if d >= 60:
            return f"{int(d // 60)}m{d % 60:.0f}s"
        return f"{d:.1f}s"

    def _refresh_display(self) -> None:
        icon = self.icon
        color = self.color
        dur = self._format_duration()
        dur_str = f" {dur}" if dur else ""
        latest = self.latest_log()[:60]
        latest_str = f" · {latest}" if latest else ""
        collapse_icon = "▾" if not self._collapsed else "▸"

        header_text = (
            f"[bold {color}]{collapse_icon} {icon} {self.stage_label}[/] "
            f"[dim {color}]{self.status_label}{dur_str}{latest_str}[/]"
        )
        try:
            self.query_one(".tool-header", Static).update(header_text)
        except Exception:
            pass

        # Body: visible only when expanded
        try:
            body = self.query_one(".tool-body", Static)
            if self._collapsed:
                body.display = False
            else:
                visible = self.get_visible_logs()
                if visible:
                    body.update("\n".join(f"  {l}" for l in visible))
                    body.display = True
                else:
                    body.display = False
        except Exception:
            pass

    # ── Compose ─────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Static("", classes="tool-header")
        body = Static("", classes="tool-body")
        body.display = False
        yield body

    def on_mount(self) -> None:
        self._refresh_display()
