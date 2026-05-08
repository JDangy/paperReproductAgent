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
    backend: str = "conda"
    workspace: str = "./workspace"
    timeout_minutes: int = 30
    max_repair_attempts: int = 5
    status: str = "draft"
    mode: str = "act"  # "plan" or "act"
    task_dir: str | None = None
    report_path: str | None = None
    input_resolved: bool = False
    created_at: float = 0.0
    cancel_requested: bool = False

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
        self._state_path = self._dir / f"{session_id}.state.json"

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

    def save_snapshot(self, session: Session) -> None:
        """Save a full snapshot of session state."""
        import dataclasses
        snapshot = dataclasses.asdict(session)
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)

    def load_snapshot(self) -> dict[str, Any] | None:
        """Load session state snapshot."""
        if not self._state_path.exists():
            return None
        with open(self._state_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def list_sessions(cls, base_dir: Path | None = None) -> list[dict[str, Any]]:
        """List all saved sessions with their snapshots."""
        sessions_dir = base_dir or SESSIONS_DIR
        if not sessions_dir.exists():
            return []
        results: list[dict[str, Any]] = []
        for state_file in sorted(sessions_dir.glob("*.state.json")):
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    snapshot = json.load(f)
                results.append(snapshot)
            except Exception:
                # Corrupt file, skip
                pass
        return results


def make_progress_bridge(
    emit: Callable[[AgentEvent], None],
    store: SessionStore | None = None,
) -> Callable[[ProgressEvent], None]:
    """Create a progress handler that bridges ProgressEvent -> AgentEvent."""

    def on_progress(event: ProgressEvent) -> None:
        if event.phase == "start":
            etype: EventType = "tool_started"
        elif event.phase == "finish":
            etype = "tool_finished"
        elif event.phase == "fail" or event.level == "error":
            etype = "tool_failed"
        else:
            etype = "tool_progress"

        agent_event = AgentEvent(
            type=etype,
            payload={
                "stage": event.stage,
                "message": event.message,
                "level": event.level,
                "phase": event.phase,
                "detail": event.detail,
                "data": event.data,
            },
        )
        emit(agent_event)
        if store is not None:
            store.append(agent_event)

    return on_progress
