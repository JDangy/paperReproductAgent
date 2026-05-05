"""Integration test: run paper reproduction through Textual TUI via Pilot."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from app.core.state import ReportResult, TaskState
from app.tui.app import PaperAgentApp
from app.tui.widgets import Composer

pytest.importorskip("textual")


def _run_async(coro):
    asyncio.get_event_loop().run_until_complete(coro)


def test_tui_paper_input_runs_pipeline_and_shows_report(tmp_path):
    """Submit a PDF path, verify pipeline runs and report appears in timeline."""
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    task_dir = tmp_path / "task_1"
    report_dir = task_dir / "report"
    report_dir.mkdir(parents=True)
    report_path = report_dir / "reproduction_smoke_report.md"
    report_path.write_text("# Reproduction report\n\nSmoke passed.", encoding="utf-8")

    runner_called = {}

    def fake_runner(**kwargs):
        runner_called.update(kwargs)
        state = TaskState(
            task_id="task_1",
            input_value=kwargs["input_value"],
            workspace_dir=kwargs["workspace"],
            task_dir=str(task_dir),
            backend=kwargs["backend"],
            status="report_written",
        )
        state.report = ReportResult(
            final_status="success",
            report_markdown_path=str(report_path),
            short_conclusion="Smoke passed.",
        )
        return state

    # Bypass InputResolverAgent for testing
    from app.agents.input_resolver_agent import PaperInputResolution
    class FakeResolver:
        def resolve(self, raw):
            return PaperInputResolution(
                success=True,
                input_value=str(pdf),
                input_kind="local_pdf",
                exists=True,
                reason="Test resolver.",
            )

    app = PaperAgentApp(
        fake_runner,
        workspace=str(tmp_path / "workspace"),
        backend="venv",
        timeout_minutes=30,
        max_repair_attempts=5,
        resolver=FakeResolver(),
    )

    async def run_test():
        async with app.run_test() as pilot:
            await pilot.pause()

            # Set input value directly and submit
            composer = app.query_one(Composer)
            input_widget = composer.query_one("#composer-input")
            input_widget.value = str(pdf)

            # Post the Submitted message
            composer.post_message(Composer.Submitted(str(pdf)))
            await pilot.pause()

            # Wait for pipeline to complete
            for _ in range(80):
                await pilot.pause(0.1)
                if not app.agent_running:
                    break

            # Verify pipeline was called
            assert runner_called.get("input_value") == str(pdf), f"Expected {str(pdf)}, got {runner_called}"
            assert runner_called.get("backend") == "venv"

            # Verify session state
            assert app.session.status == "success"
            assert app.session.report_path is not None

    _run_async(run_test())


def test_tui_plan_mode_blocks_execution(tmp_path):
    """Plan mode should prevent pipeline from running."""
    runner_called = {}

    def fake_runner(**kwargs):
        runner_called.update(kwargs)
        raise AssertionError("runner should not be called in plan mode")

    app = PaperAgentApp(
        fake_runner,
        workspace=str(tmp_path / "workspace"),
        backend="venv",
        timeout_minutes=30,
        max_repair_attempts=5,
    )

    async def run_test():
        async with app.run_test() as pilot:
            await pilot.pause()

            # Switch to plan mode
            composer = app.query_one(Composer)
            input_widget = composer.query_one("#composer-input")
            input_widget.value = "/plan"
            composer.post_message(Composer.Submitted("/plan"))
            await pilot.pause()

            assert app.session.mode == "plan"

            # Try to submit a paper path — should show plan, not run
            input_widget.value = str(tmp_path / "paper.pdf")
            composer.post_message(Composer.Submitted(str(tmp_path / "paper.pdf")))
            await pilot.pause(0.2)

            # Pipeline should NOT have started
            assert len(runner_called) == 0
            assert app.agent_running is False

    _run_async(run_test())


def test_tui_cancel_during_run(tmp_path):
    """Cancel should stop pipeline via should_cancel callback."""
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    cancel_checked = {"value": False}

    def slow_runner(**kwargs):
        should_cancel = kwargs.get("should_cancel")
        task_dir = tmp_path / "task_cancel"
        task_dir.mkdir(parents=True, exist_ok=True)
        if should_cancel:
            for _ in range(100):
                if should_cancel():
                    cancel_checked["value"] = True
                    return TaskState(
                        task_id="task_cancel",
                        input_value=kwargs["input_value"],
                        workspace_dir=kwargs["workspace"],
                        task_dir=str(task_dir),
                        backend=kwargs["backend"],
                        status="cancelled",
                    )
                time.sleep(0.05)
        return TaskState(
            task_id="task_cancel",
            input_value=kwargs["input_value"],
            workspace_dir=kwargs["workspace"],
            task_dir=str(task_dir),
            backend=kwargs["backend"],
            status="completed",
        )

    from app.agents.input_resolver_agent import PaperInputResolution
    class FakeResolver:
        def resolve(self, raw):
            return PaperInputResolution(
                success=True,
                input_value=str(pdf),
                input_kind="local_pdf",
                exists=True,
            )

    app = PaperAgentApp(
        slow_runner,
        workspace=str(tmp_path / "workspace"),
        backend="venv",
        timeout_minutes=30,
        max_repair_attempts=5,
        resolver=FakeResolver(),
    )

    async def run_test():
        async with app.run_test() as pilot:
            await pilot.pause()

            # Start pipeline by submitting PDF
            composer = app.query_one(Composer)
            input_widget = composer.query_one("#composer-input")
            input_widget.value = str(pdf)
            composer.post_message(Composer.Submitted(str(pdf)))
            await pilot.pause(0.3)

            assert app.agent_running is True

            # Send /cancel
            input_widget.value = "/cancel"
            composer.post_message(Composer.Submitted("/cancel"))
            await pilot.pause(0.2)

            # Wait for pipeline to finish
            for _ in range(60):
                await pilot.pause(0.1)
                if not app.agent_running:
                    break

            assert cancel_checked["value"] is True, "should_cancel was never called with True"
            assert app.session.status == "cancelled"

    _run_async(run_test())


def test_tui_shell_requires_confirmation(tmp_path):
    """Shell commands should require confirmation."""
    app = PaperAgentApp(
        lambda **kw: None,
        workspace=str(tmp_path / "workspace"),
        backend="venv",
        timeout_minutes=30,
        max_repair_attempts=5,
    )

    async def run_test():
        async with app.run_test() as pilot:
            await pilot.pause()

            composer = app.query_one(Composer)
            input_widget = composer.query_one("#composer-input")

            # Submit shell command
            input_widget.value = "!echo hello"
            composer.post_message(Composer.Submitted("!echo hello"))
            await pilot.pause()

            # Should be pending confirmation, not executed
            assert app._pending_shell == "echo hello"

            # Confirm
            input_widget.value = "y"
            composer.post_message(Composer.Submitted("y"))
            await pilot.pause(0.5)

            # Should have executed and cleared pending
            assert app._pending_shell is None

    _run_async(run_test())
