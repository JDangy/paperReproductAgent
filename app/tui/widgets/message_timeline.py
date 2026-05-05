from __future__ import annotations

"""Scrollable message timeline widget."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static, Markdown

from .. import theme as T


class MessageBubble(Widget):
    """A single message in the timeline."""

    DEFAULT_CSS = """
    MessageBubble {
        margin: 0 0 0 0;
        padding: 0 1;
        height: auto;
    }
    MessageBubble.user {
        border-left: thick $success;
    }
    MessageBubble.assistant {
        border-left: thick $primary;
    }
    MessageBubble.tool {
        border-left: thick #585b70;
    }
    MessageBubble.error {
        border-left: thick $error;
    }
    """

    def __init__(
        self,
        text: str,
        kind: str = "assistant",
        label: str = "",
        **kwargs: object,
    ) -> None:
        super().__init__(classes=kind, **kwargs)
        self._text = text
        self._kind = kind
        self._label = label

    def compose(self) -> ComposeResult:
        color_map = {
            "user": T.USER_BORDER,
            "assistant": T.AGENT_BORDER,
            "tool": T.TOOL_BORDER,
            "error": T.ERROR_BORDER,
        }
        color = color_map.get(self._kind, T.FG)
        label_str = f"[bold {color}]{self._label:<12}[/]" if self._label else ""
        content = f"{label_str} {self._text}" if label_str else self._text

        # Use Markdown for assistant messages so reports render properly
        if self._kind == "assistant" and _has_markdown(content):
            # Prepend label as a styled paragraph if present
            if label_str:
                yield Static(label_str)
                yield Markdown(self._text)
            else:
                yield Markdown(content)
        else:
            yield Static(content)


def _has_markdown(text: str) -> bool:
    """Heuristic: does this text likely contain Markdown syntax?"""
    if any(line.startswith("#") for line in text.splitlines()):
        return True
    if "**" in text or "`" in text:
        return True
    if "```" in text:
        return True
    if "- " in text or "* " in text:
        return True
    if "|" in text and "---" in text:
        return True
    return False


class MessageTimeline(VerticalScroll):
    """Scrollable list of message bubbles."""

    DEFAULT_CSS = """
    MessageTimeline {
        height: 1fr;
        scrollbar-size: 1 1;
        padding: 0 1;
    }
    """

    class ComposerFocused(Message):
        pass

    def add_message(
        self,
        text: str,
        kind: str = "assistant",
        label: str = "",
    ) -> MessageBubble:
        bubble = MessageBubble(text=text, kind=kind, label=label)
        self.mount(bubble)
        self.scroll_end(animate=False)
        return bubble

    def add_user(self, text: str) -> MessageBubble:
        return self.add_message(text, kind="user", label="用户")

    def add_assistant(self, text: str) -> MessageBubble:
        return self.add_message(text, kind="assistant", label="Agent")

    def add_tool(
        self,
        text: str,
        label: str = "工具",
    ) -> MessageBubble:
        return self.add_message(text, kind="tool", label=label)

    def add_error(self, text: str) -> MessageBubble:
        return self.add_message(text, kind="error", label="错误")

    def clear_messages(self) -> None:
        for child in list(self.children):
            child.remove()
