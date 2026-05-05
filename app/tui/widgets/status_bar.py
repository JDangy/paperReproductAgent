from __future__ import annotations

"""Status bar widget showing session info."""

from textual.widget import Widget
from textual.widgets import Static

from .. import theme as T


class StatusBar(Widget):
    """Bottom status bar with session info."""

    DEFAULT_CSS = """
    StatusBar {
        dock: bottom;
        height: 1;
        width: 100%;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._mode = "ACT"
        self._session = "session-1"
        self._backend = "venv"
        self._status = "draft"
        self._paper = "-"

    def update_info(
        self,
        mode: str | None = None,
        session: str | None = None,
        backend: str | None = None,
        status: str | None = None,
        paper: str | None = None,
    ) -> None:
        if mode is not None:
            self._mode = mode
        if session is not None:
            self._session = session
        if backend is not None:
            self._backend = backend
        if status is not None:
            self._status = status
        if paper is not None:
            self._paper = paper
        self._refresh()

    def _refresh(self) -> None:
        mode_color = T.PURPLE if self._mode == "PLAN" else T.GREEN
        status_color = T.GREEN if self._status in ("success", "running") else T.ORANGE
        text = (
            f"  [bold {mode_color}]{self._mode} MODE[/] │ "
            f"[{T.FG_DIM}]{self._session}[/] │ "
            f"[bold {T.BLUE}]{self._backend}[/] │ "
            f"[bold {status_color}]{self._status}[/] │ "
            f"[{T.FG_DIM}]论文: {self._paper}[/]"
        )
        try:
            static = self.query_one(Static)
            static.update(text)
        except Exception:
            pass

    def compose(self):
        yield Static("")
        self._refresh()
