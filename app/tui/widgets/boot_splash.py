from __future__ import annotations

"""Boot splash screen with logo and preflight checks."""

import asyncio
import time

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import Static

from .. import theme as T
from ..logo_loader import load_logo_text
from ..preflight import CheckItem, run_preflight


class BootSplash(Screen):
    """Full-screen preflight check display before main TUI."""

    DEFAULT_CSS = """
    BootSplash {
        align: center middle;
        background: $surface;
    }
    BootSplash #splash-logo {
        height: auto;
        content-align: center middle;
        margin-bottom: 1;
    }
    BootSplash #splash-checks {
        height: auto;
        width: 54;
        padding: 1 2;
        color: $text-muted;
    }
    BootSplash #splash-status {
        height: 1;
        content-align: center middle;
        color: $text-muted;
        margin-top: 1;
    }
    """

    def __init__(self, on_done=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._on_done = on_done
        self._checks: list[CheckItem] = []
        self._done = False

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("", id="splash-logo")
            yield Static("", id="splash-checks")
            yield Static("", id="splash-status")

    def on_mount(self) -> None:
        try:
            logo = load_logo_text()
        except Exception:
            from rich.text import Text
            logo = Text("Paper Reproduct Agent", style="bold #bd93f9")
        self.query_one("#splash-logo", Static).update(logo)
        self.run_worker(self._run_checks(), exclusive=True)

    async def _run_checks(self) -> None:
        status = self.query_one("#splash-status", Static)
        checks = self.query_one("#splash-checks", Static)

        status.update("正在检查系统环境……")

        results = await asyncio.to_thread(run_preflight)
        self._checks = results

        for i, item in enumerate(results):
            item.status = "running"
            self._refresh_checks(checks)
            await asyncio.sleep(0.15)

            # Actually run was already done; we just animate
            item.status = item.status  # preserve
            self._refresh_checks(checks)

        await asyncio.sleep(0.5)

        # Show completion
        passes = sum(1 for c in results if c.status == "pass")
        fails = sum(1 for c in results if c.status == "fail")
        blocking = sum(1 for c in results if c.status == "fail" and c.blocking)

        if blocking > 0:
            status.update(f"[{T.ERROR_BORDER}]检查完成：{passes} 通过，{fails} 失败（{blocking} 项阻塞）[/]")
        elif fails > 0:
            status.update(f"[{T.WARNING_BORDER}]检查完成：{passes} 通过，{fails} 项非阻塞警告[/]")
        else:
            status.update(f"[{T.GREEN}]全部检查通过 ✓[/]")

        await asyncio.sleep(1.0)

        if self._on_done:
            self._on_done(results)
        self._done = True

    def _refresh_checks(self, widget: Static) -> None:
        lines: list[str] = []
        for item in self._checks:
            icon = _icon_for(item.status)
            color = _color_for(item.status)
            msg = item.message[:50] if item.message else ""
            lines.append(f"[{color}]{icon} {item.name:<14}[/] [{T.FG_DIM}]{msg}[/]")
        widget.update("\n".join(lines))


def _icon_for(status: str) -> str:
    return {"pending": "○", "running": "⟳", "pass": "✓", "fail": "✗"}.get(status, "?")


def _color_for(status: str) -> str:
    return {"pending": T.FG_DIM, "running": T.INFO_BORDER, "pass": T.GREEN, "fail": T.ERROR_BORDER}.get(status, T.FG)
