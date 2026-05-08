from __future__ import annotations

"""Enhanced composer with mode-aware placeholder."""

from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input

from .. import theme as T


class Composer(Widget):
    """Fixed-bottom input area with mode-aware placeholder."""

    DEFAULT_CSS = """
    Composer {
        height: 3;
        dock: bottom;
        padding: 0 1;
        background: $surface;
        border-top: solid $primary-darken-2;
    }
    Composer Input {
        width: 100%;
    }
    """

    class Submitted(Message):
        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()

    def __init__(
        self,
        placeholder: str | None = None,
        mode: str = "act",
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._mode = mode
        self._running = False
        self._default = placeholder or "输入 PDF 路径，或 /help 查看命令"
        self._placeholder = self._default

    def compose(self):
        yield Input(
            placeholder=self._placeholder,
            id="composer-input",
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return
        event.input.value = ""
        self.post_message(self.Submitted(value))

    def focus_input(self) -> None:
        try:
            input_widget = self.query_one("#composer-input", Input)
            input_widget.focus()
        except Exception:
            pass

    def set_placeholder_text(self, text: str) -> None:
        self._default = text
        if not self._running:
            self._placeholder = text
            self._update_placeholder()

    def set_running(self, running: bool) -> None:
        self._running = running
        if running:
            self._placeholder = "Agent 运行中 · 可用 /status /logs /cancel"
        else:
            self._placeholder = self._default
        self._update_placeholder()

    def set_mode(self, mode: str) -> None:
        self._mode = mode.lower()
        if not self._running:
            if self._mode == "plan":
                self._placeholder = "PLAN 模式：输入 /act 切换执行，或 /run 查看计划"
            else:
                self._placeholder = self._default
        self._update_placeholder()

    def _update_placeholder(self) -> None:
        try:
            input_widget = self.query_one("#composer-input", Input)
            input_widget.placeholder = self._placeholder
        except Exception:
            pass

    def set_disabled(self, disabled: bool) -> None:
        self.set_running(disabled)
