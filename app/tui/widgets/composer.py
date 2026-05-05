from __future__ import annotations

"""Bottom composer / input widget."""

from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input

from .. import theme as T


class Composer(Widget):
    """Fixed-bottom input area with prompt."""

    DEFAULT_CSS = """
    Composer {
        height: 3;
        dock: bottom;
        padding: 0 1;
        background: $surface;
    }
    Composer Input {
        width: 100%;
    }
    """

    class Submitted(Message):
        """Posted when user submits text."""

        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()

    def __init__(self, placeholder: str = "输入 PDF 路径或 /help 查看帮助", **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._placeholder = placeholder

    def compose(self):
        yield Input(
            placeholder=self._placeholder,
            id="composer-input",
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return
        # Clear the input
        event.input.value = ""
        self.post_message(self.Submitted(value))

    def focus_input(self) -> None:
        try:
            input_widget = self.query_one("#composer-input", Input)
            input_widget.focus()
        except Exception:
            pass

    def set_disabled(self, disabled: bool) -> None:
        try:
            input_widget = self.query_one("#composer-input", Input)
            input_widget.disabled = disabled
            if disabled:
                input_widget.placeholder = "Agent 运行中，输入已禁用"
            else:
                input_widget.placeholder = self._placeholder
        except Exception:
            pass
