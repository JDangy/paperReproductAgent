from app.core.state import ReportResult, TaskState
from app.agents.input_resolver_agent import PaperInputResolution
from app.tui_old import PaperSmokeTUI, parse_command


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
