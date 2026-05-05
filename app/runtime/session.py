from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from app.core.progress import ProgressEvent, progress_events
from .events import AgentEvent, EventType

SESSIONS_DIR = Path(".paper-agent/sessions")


@dataclass
class Session:
    """Represents a single paper reproduction session."""

    id: str = ""
    paper_path: str | None = None
    repo: str | None = None
    repo_dir: str | None = None
    backend: str = "venv"
    workspace: str = "./workspace"
    timeout_minutes: int = 30
    max_repair_attempts: int = 5
    status: str = "draft"
    mode: str = "act"  # "plan" or "act"
    task_dir: str | None = None
    report_path: str | None = None
    input_resolved: bool = False
    created_at: float = 0.0

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:8]
        if self.created_at == 0.0:
            self.created_at = time.time()


class SessionStore:
    """JSONL-backed session event persistence."""

    def __init__(self, session_id: str, base_dir: Path | None = None) -> None:
        self.session_id = session_id
        self._dir = base_dir or SESSIONS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / f"{session_id}.jsonl"

    def append(self, event: AgentEvent) -> None:
        record = {
            "type": event.type,
            "payload": event.payload,
            "timestamp": event.timestamp,
        }
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def load_events(self) -> list[AgentEvent]:
        if not self._path.exists():
            return []
        events: list[AgentEvent] = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                events.append(
                    AgentEvent(
                        type=record["type"],
                        payload=record["payload"],
                        timestamp=record.get("timestamp", 0.0),
                    )
                )
        return events


def make_progress_bridge(
    emit: Callable[[AgentEvent], None],
    store: SessionStore | None = None,
) -> Callable[[ProgressEvent], None]:
    """Create a progress handler that bridges ProgressEvent -> AgentEvent."""

    def on_progress(event: ProgressEvent) -> None:
        level = event.level
        if level in ("success", "warning", "error"):
            etype: EventType = "tool_finished" if level == "success" else "error"
        else:
            etype = "tool_started"

        agent_event = AgentEvent(
            type=etype,
            payload={
                "stage": event.stage,
                "message": event.message,
                "level": event.level,
                "detail": event.detail,
            },
        )
        emit(agent_event)
        if store is not None:
            store.append(agent_event)

    return on_progress
