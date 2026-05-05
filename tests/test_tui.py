from app.core.state import ReportResult, TaskState
from app.agents.input_resolver_agent import PaperInputResolution
from app.tui_old import PaperSmokeTUI, parse_command


# -----------------------------------------------------------------------
# Tests for new Textual TUI parse_command
# -----------------------------------------------------------------------

from app.tui.app import parse_command as new_parse_command


def test_new_tui_parse_slash_command():
    assert new_parse_command("/input @paper.pdf") == ("input", "@paper.pdf")


def test_new_tui_parse_shell_command():
    assert new_parse_command("!ls -la") == ("!", "ls -la")


def test_new_tui_parse_plain_message():
    assert new_parse_command("summarize this paper") == ("message", "summarize this paper")


def test_new_tui_parse_absolute_path_as_message():
    assert new_parse_command("/tmp/paper.pdf") == ("message", "/tmp/paper.pdf")


def test_new_tui_parse_empty():
    assert new_parse_command("") == ("", "")
    assert new_parse_command("   ") == ("", "")


def test_new_tui_parse_unknown_slash():
    assert new_parse_command("/unknown blah") == ("message", "/unknown blah")


def test_new_tui_parse_known_commands():
    assert new_parse_command("/help") == ("help", "")
    assert new_parse_command("/clear") == ("clear", "")
    assert new_parse_command("/status") == ("status", "")
    assert new_parse_command("/cancel") == ("cancel", "")
    assert new_parse_command("/sessions") == ("sessions", "")
    assert new_parse_command("/resume abc123") == ("resume", "abc123")


# -----------------------------------------------------------------------
# Tests for old TUI (backward compatibility)
# -----------------------------------------------------------------------


def test_parse_slash_command():
    assert parse_command("/input @paper.pdf") == ("input", "@paper.pdf")


def test_parse_shell_command():
    assert parse_command("!ls -la") == ("!", "ls -la")


def test_parse_plain_message():
    assert parse_command("summarize this paper") == ("message", "summarize this paper")


def test_parse_absolute_path_as_message():
    assert parse_command("/tmp/paper.pdf") == ("message", "/tmp/paper.pdf")


def test_tui_config_commands_update_active_session():
    def runner(**kwargs):
        raise AssertionError("runner should not be called")

    tui = PaperSmokeTUI(
        runner,
        workspace="./workspace",
        backend="venv",
        timeout_minutes=30,
        max_repair_attempts=5,
    )

    tui.handle_line("/input @paper.pdf")
    tui.handle_line("/repo https://github.com/example/repo")
    tui.handle_line("/backend local")
    tui.handle_line("/timeout 12")
    tui.handle_line("/repairs 3")

    assert tui.active.input_value == "paper.pdf"
    assert tui.active.repo == "https://github.com/example/repo"
    assert tui.active.backend == "local"
    assert tui.active.timeout_minutes == 12
    assert tui.active.max_repair_attempts == 3


def test_tui_rejects_input_while_agent_is_running(tmp_path):
    def runner(**kwargs):
        raise AssertionError("runner should not be called")

    tui = PaperSmokeTUI(
        runner,
        workspace=str(tmp_path / "workspace"),
        backend="venv",
        timeout_minutes=30,
        max_repair_attempts=5,
    )
    tui.active.input_value = "old.pdf"
    tui.agent_running = True

    tui.handle_line("/input new.pdf")

    assert tui.active.input_value == "old.pdf"
    assert "暂不接受新的输入" in "\n".join(tui.active.timeline)


def test_plain_paper_input_runs_pipeline_and_prints_report(tmp_path):
    calls = {}
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    class Resolver:
        def resolve(self, raw_input):
            assert raw_input == str(pdf)
            return PaperInputResolution(
                success=True,
                input_value=str(pdf),
                input_kind="local_pdf",
                exists=True,
                reason="Validated by fake resolver.",
            )

    def runner(**kwargs):
        calls.update(kwargs)
        task_dir = tmp_path / "task_1"
        report_dir = task_dir / "report"
        report_dir.mkdir(parents=True)
        report_path = report_dir / "reproduction_smoke_report.md"
        report_path.write_text("# Reproduction report\n\nSmoke passed.", encoding="utf-8")
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

    tui = PaperSmokeTUI(
        runner,
        workspace=str(tmp_path / "workspace"),
        backend="venv",
        timeout_minutes=30,
        max_repair_attempts=5,
        resolver=Resolver(),
    )

    tui.handle_line(str(pdf))

    assert calls["input_value"] == str(pdf)
    assert tui.active.status == "success"
    assert tui.active.report_path
    timeline = "\n".join(tui.active.timeline)
    assert "正在解析输入" in timeline
    assert "本地 PDF 已确认" in timeline
    assert "路径：" in timeline
    assert "Reproduction report" in timeline


def test_plain_paper_input_failure_does_not_call_runner(tmp_path):
    called = False

    class Resolver:
        def resolve(self, raw_input):
            return PaperInputResolution(
                success=False,
                input_kind="local_pdf",
                searched=False,
                failure_reason="本地 PDF 不存在或不可读取。",
            )

    def runner(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("runner should not be called")

    tui = PaperSmokeTUI(
        runner,
        workspace=str(tmp_path / "workspace"),
        backend="venv",
        timeout_minutes=30,
        max_repair_attempts=5,
        resolver=Resolver(),
    )

    tui.handle_line("/missing/paper.pdf")

    assert called is False
    assert tui.active.status == "input_failed"
    timeline = "\n".join(tui.active.timeline)
    assert "不能开始复现" in timeline
    assert "本地 PDF 不存在" in timeline


# -----------------------------------------------------------------------
# Tests for SessionStore snapshot
# -----------------------------------------------------------------------

from app.runtime.session import Session, SessionStore
from app.runtime.events import AgentEvent


def test_session_store_append_and_load(tmp_path):
    store = SessionStore("test-session", base_dir=tmp_path)
    store.append(AgentEvent(type="user_message", payload={"text": "hello"}))
    store.append(AgentEvent(type="assistant_message", payload={"text": "hi"}))

    events = store.load_events()
    assert len(events) == 2
    assert events[0].type == "user_message"
    assert events[1].payload["text"] == "hi"


def test_session_store_snapshot_roundtrip(tmp_path):
    store = SessionStore("snap-test", base_dir=tmp_path)
    session = Session(
        id="snap-test",
        paper_path="/path/to/paper.pdf",
        backend="venv",
        status="success",
    )
    store.save_snapshot(session)

    loaded = store.load_snapshot()
    assert loaded is not None
    assert loaded["id"] == "snap-test"
    assert loaded["paper_path"] == "/path/to/paper.pdf"
    assert loaded["backend"] == "venv"
    assert loaded["status"] == "success"


def test_session_store_list_sessions(tmp_path):
    store1 = SessionStore("sess-1", base_dir=tmp_path)
    store1.save_snapshot(Session(id="sess-1", status="success", paper_path="a.pdf"))
    store2 = SessionStore("sess-2", base_dir=tmp_path)
    store2.save_snapshot(Session(id="sess-2", status="failed", paper_path="b.pdf"))

    sessions = SessionStore.list_sessions(base_dir=tmp_path)
    assert len(sessions) == 2
    ids = {s["id"] for s in sessions}
    assert ids == {"sess-1", "sess-2"}


# -----------------------------------------------------------------------
# Tests for new TUI handle_line with agent_running
# -----------------------------------------------------------------------

from app.tui.app import PaperAgentApp


def test_new_tui_allows_status_while_running_without_crash():
    """handle_line must not crash with UnboundLocalError when agent_running=True."""
    def runner(**kwargs):
        raise AssertionError("should not run")

    app = PaperAgentApp(
        runner,
        workspace="./workspace",
        backend="venv",
        timeout_minutes=30,
        max_repair_attempts=5,
    )
    messages = []
    app._add_assistant = lambda text: messages.append(text)
    app.agent_running = True

    app.handle_line("/status")

    # Should not crash, and should produce a message (either status or "尚未运行")
    assert len(messages) >= 1


def test_new_tui_rejects_run_while_running():
    """Non-allowed commands should be rejected when agent is running."""
    def runner(**kwargs):
        raise AssertionError("should not run")

    app = PaperAgentApp(
        runner,
        workspace="./workspace",
        backend="venv",
        timeout_minutes=30,
        max_repair_attempts=5,
    )
    messages = []
    app._add_assistant = lambda text: messages.append(text)
    app.agent_running = True

    app.handle_line("/run")

    assert any("可用命令" in m for m in messages)


def test_progress_phase_field():
    """ProgressEvent should carry the phase field correctly."""
    from app.core.progress import ProgressEvent

    event_start = ProgressEvent(stage="Build", message="started", phase="start")
    assert event_start.phase == "start"

    event_finish = ProgressEvent(
        stage="Build",
        message="completed",
        level="success",
        phase="finish",
        detail="1.2s",
    )
    assert event_finish.phase == "finish"

    event_fail = ProgressEvent(
        stage="Build",
        message="failed",
        level="error",
        phase="fail",
    )
    assert event_fail.phase == "fail"

    # Default phase should be "progress"
    event_default = ProgressEvent(stage="Build", message="doing stuff")
    assert event_default.phase == "progress"
