from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

EventType = Literal[
    "user_message",
    "assistant_message",
    "tool_started",
    "tool_finished",
    "tool_failed",
    "status_changed",
    "error",
    "report_ready",
    "mode_changed",
    "session_resumed",
]


@dataclass
class AgentEvent:
    """Structured event emitted by the agent pipeline."""

    type: EventType
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()
