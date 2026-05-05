from __future__ import annotations

"""Public API for the Textual TUI."""

from typing import Callable

from app.core.state import TaskState

from .app import PaperAgentApp

PipelineRunner = Callable[..., TaskState]


def run_tui(
    runner: PipelineRunner,
    *,
    workspace: str,
    backend: str,
    timeout_minutes: int,
    max_repair_attempts: int,
) -> None:
    """Launch the Textual TUI application."""
    app = PaperAgentApp(
        runner,
        workspace=workspace,
        backend=backend,
        timeout_minutes=timeout_minutes,
        max_repair_attempts=max_repair_attempts,
    )
    app.run()
