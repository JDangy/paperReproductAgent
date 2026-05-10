from __future__ import annotations

"""Boot splash screen with logo and preflight checks."""

import asyncio

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import Screen
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

    BINDINGS = [
        Binding("ctrl+c", "quit_app", "退出", show=False),
        Binding("q", "quit_app", "退出", show=False),
        Binding("escape", "skip_splash", "跳过", show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._checks: list[CheckItem] = []
        self._done = False
        self._cancelled = False

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
            logo = Text("", style="dim")
        self.query_one("#splash-logo", Static).update(logo)
        self.run_worker(self._run_checks(), exclusive=True)

    def action_quit_app(self) -> None:
        self.app.exit()

    def action_skip_splash(self) -> None:
        self._cancelled = True
        self.dismiss([])

    async def _run_checks(self) -> None:
        status = self.query_one("#splash-status", Static)
        checks = self.query_one("#splash-checks", Static)

        status.update("正在检查系统环境……")

        results = await asyncio.to_thread(run_preflight)

        if self._cancelled:
            return

        animated: list[CheckItem] = [
            CheckItem(name=item.name, status="pending", message="", blocking=item.blocking)
            for item in results
        ]
        self._checks = animated
        self._refresh_checks(checks)

        for i, final_item in enumerate(results):
            if self._cancelled:
                return

            animated[i].status = "running"
            animated[i].message = "正在检查……"
            self._refresh_checks(checks)
            await asyncio.sleep(0.12)

            animated[i].status = final_item.status
            animated[i].message = final_item.message
            animated[i].blocking = final_item.blocking
            self._refresh_checks(checks)

        if self._cancelled:
            return

        passes = sum(1 for c in results if c.status == "pass")
        fails = sum(1 for c in results if c.status == "fail")
        blocking = sum(1 for c in results if c.status == "fail" and c.blocking)

        if blocking > 0:
            status.update(
                f"[{T.ERROR_BORDER}]检查完成：{passes} 通过，{fails} 失败"
                f"（{blocking} 项阻塞，将进入 TUI 显示警告）[/]"
            )
        elif fails > 0:
            status.update(f"[{T.WARNING_BORDER}]检查完成：{passes} 通过，{fails} 项非阻塞警告[/]")
        else:
            status.update(f"[{T.GREEN}]全部检查通过 ✓[/]")

        await asyncio.sleep(1.0)

        if self._cancelled:
            return

        status.update(f"[{T.FG_DIM}]正在进入 TUI…[/]")
        await asyncio.sleep(0.2)

        self._done = True
        self.dismiss(results)

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