from __future__ import annotations

"""Composer with slash-command completion popup."""

from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Static

from ..completion import complete_command, CompletionItem
from .. import theme as T


class Composer(Widget):
    """Bottom input area with mode-aware placeholder and slash-command completion."""

    DEFAULT_CSS = """
    Composer {
        height: 4;
        min-height: 4;
        padding: 0 1 1 1;
        background: $surface;
        border-top: solid $primary-darken-2;
    }
    Composer.has-completion {
        height: 8;
    }
    Composer Input {
        height: 3;
        min-height: 3;
        width: 100%;
        content-align: left middle;
    }
    #completion-popup {
        height: 4;
        max-height: 4;
        display: none;
        color: $text-muted;
        padding: 0 0 0 2;
    }
    #completion-popup.visible {
        display: block;
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

        # Completion state
        self._completion_items: list[CompletionItem] = []
        self._completion_index: int = 0
        self._completion_visible: bool = False

    def compose(self):
        yield Static("", id="completion-popup")
        yield Input(
            placeholder=self._placeholder,
            id="composer-input",
        )

    # ── Input handling ──────────────────────────────────────

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return
        # Don't auto-accept completion on Enter
        event.input.value = ""
        self._hide_completion()
        self.post_message(self.Submitted(value))

    def on_input_changed(self, event: Input.Changed) -> None:
        value = event.value
        if value.startswith("/") and " " not in value:
            items = complete_command(value)
            if items:
                self._show_completion(items)
            else:
                self._hide_completion()
        else:
            self._hide_completion()

    # ── Completion display ──────────────────────────────────

    def _show_completion(self, items: list[CompletionItem]) -> None:
        self._completion_items = items
        self._completion_index = 0
        self._completion_visible = True
        self._refresh_completion_display()
        self.add_class("has-completion")

    def _hide_completion(self) -> None:
        self._completion_items.clear()
        self._completion_index = 0
        self._completion_visible = False
        self.remove_class("has-completion")
        try:
            popup = self.query_one("#completion-popup", Static)
            popup.remove_class("visible")
            popup.update("")
        except Exception:
            pass

    def hide_completion(self) -> None:
        self._hide_completion()

    def _refresh_completion_display(self) -> None:
        try:
            popup = self.query_one("#completion-popup", Static)
        except Exception:
            return

        if not self._completion_items:
            popup.remove_class("visible")
            popup.update("")
            return

        popup.add_class("visible")
        lines: list[str] = []
        for i, item in enumerate(self._completion_items):
            prefix = ">" if i == self._completion_index else " "
            color = T.GREEN if i == self._completion_index else T.FG_DIM
            arg_part = f" {item.args}" if item.args else ""
            lines.append(
                f"[{color}]{prefix} /{item.command}{arg_part}[/]  "
                f"[{T.FG_DIM}]({item.category}) {item.description}[/]"
            )
        popup.update("\n".join(lines))

    # ── Completion navigation ───────────────────────────────

    def has_completion(self) -> bool:
        return self._completion_visible and len(self._completion_items) > 0

    def accept_completion(self) -> bool:
        """Accept the currently highlighted completion.  Returns True if accepted."""
        if not self.has_completion():
            return False
        if 0 <= self._completion_index < len(self._completion_items):
            item = self._completion_items[self._completion_index]
            text = item.insert_text
            try:
                inp = self.query_one("#composer-input", Input)
                inp.value = text
                inp.action_end()
                inp.focus()
            except Exception:
                pass
        self._hide_completion()
        return True

    def move_completion(self, delta: int) -> bool:
        """Move highlight up (-1) or down (+1).  Returns True if moved."""
        if not self.has_completion():
            return False
        self._completion_index += delta
        self._completion_index %= len(self._completion_items)
        self._refresh_completion_display()
        return True

    # ── Focus / placeholder ─────────────────────────────────

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
