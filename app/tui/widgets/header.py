from __future__ import annotations

"""Gradient logo header with session summary."""

from rich.text import Text as RichText
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from ..logo import render_logo, render_compact_logo, SUBTITLE
from .. import theme as T


class HeaderLogo(Widget):
    """Top header: gradient ASCII logo, subtitle, and session summary."""

    DEFAULT_CSS = """
    HeaderLogo {
        height: auto;
        padding: 1 1 0 1;
        background: $surface;
        border-bottom: solid $primary-darken-2;
    }
    HeaderLogo #logo-area {
        height: auto;
    }
    HeaderLogo #subtitle-area {
        height: auto;
        padding: 1 0 0 0;
    }
    HeaderLogo #summary-area {
        height: 1;
        color: $text-muted;
        padding: 1 0 0 0;
    }
    """

    def __init__(
        self,
        session_id: str = "",
        backend: str = "conda",
        mode: str = "ACT",
        status: str = "draft",
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.session_id = session_id
        self.backend = backend
        self.mode = mode
        self.status = status

    def update_summary(
        self,
        session_id: str = "",
        backend: str = "",
        mode: str = "",
        status: str = "",
    ) -> None:
        if session_id:
            self.session_id = session_id
        if backend:
            self.backend = backend
        if mode:
            self.mode = mode
        if status:
            self.status = status
        self._refresh_summary()

    def _render_logo(self, max_width: int | None = None) -> list[RichText]:
        texts = render_logo(max_width)
        return texts

    def compose(self) -> ComposeResult:
        yield Static("", id="logo-area")
        yield Static("", id="subtitle-area")
        yield Static("", id="summary-area")

    def on_mount(self) -> None:
        self._render_and_display()

    def _render_and_display(self) -> None:
        """Render logo based on available width."""
        try:
            logo_texts = render_logo(max_width=self.size.width if self.size else None)
        except Exception:
            logo_texts = [render_compact_logo()]

        logo_md = "\n".join(str(t) for t in logo_texts)
        try:
            self.query_one("#logo-area", Static).update(logo_md)
        except Exception:
            pass

        subtitle = f"[dim italic]{SUBTITLE}[/]"
        try:
            self.query_one("#subtitle-area", Static).update(subtitle)
        except Exception:
            pass

        self._refresh_summary()

    def _refresh_summary(self) -> None:
        mode_color = T.PURPLE if self.mode.upper() == "PLAN" else T.GREEN
        status_c = T.status_color(self.status)
        text = (
            f"[{T.FG_DIM}]session:[/] [{T.INFO_BORDER}]{self.session_id[:8]}[/]  "
            f"[{T.FG_DIM}]mode:[/] [bold {mode_color}]{self.mode.upper()}[/]  "
            f"[{T.FG_DIM}]backend:[/] [{T.INFO_BORDER}]{self.backend}[/]  "
            f"[{T.FG_DIM}]status:[/] [{status_c}]{self.status}[/]"
        )
        try:
            self.query_one("#summary-area", Static).update(text)
        except Exception:
            pass

    def on_resize(self) -> None:
        self._render_and_display()
