from app.agents import report_writer_agent
from app.agents.report_writer_agent import ReportWriterAgent
from app.core.state import (
    BenchmarkRunResult,
    EnvironmentBuildResult,
    PaperMetadata,
    RepoCandidate,
    RepoEvaluation,
    ReproductionRunResult,
    SmokeRunResult,
    TaskState,
)


def _base_state(tmp_path):
    return TaskState(
        task_id="task_test",
        input_value="paper.pdf",
        workspace_dir=str(tmp_path),
        task_dir=str(tmp_path / "task_test"),
        backend="local",
        paper_metadata=PaperMetadata(title="Demo Paper"),
        selected_repo=RepoCandidate(url="https://github.com/example/repo"),
        repo_evaluation=RepoEvaluation(repo_dir=str(tmp_path / "repo")),
    )


def test_report_status_treats_missing_dependency_as_env_failed(tmp_path):
    state = _base_state(tmp_path)
    state.smoke_run = SmokeRunResult(success=False, failure_type="missing_dependency")

    status = ReportWriterAgent()._determine_final_status(state)

    assert status == "repo_found_but_env_failed"


def test_report_status_keeps_argument_error_as_smoke_failed(tmp_path):
    state = _base_state(tmp_path)
    state.smoke_run = SmokeRunResult(success=False, failure_type="argument_error")

    status = ReportWriterAgent()._determine_final_status(state)

    assert status == "repo_found_but_smoke_failed"


def test_report_status_prioritizes_failed_isolated_env_build(tmp_path):
    state = _base_state(tmp_path)
    state.backend = "venv"
    state.env_build = EnvironmentBuildResult(build_success=False, failure_type="package_not_found")

    status = ReportWriterAgent()._determine_final_status(state)

    assert status == "repo_found_but_env_failed"


def test_report_status_preserves_reproduction_success_when_benchmark_fails(tmp_path):
    state = _base_state(tmp_path)
    state.benchmark_run = BenchmarkRunResult(
        eligible=True,
        success=False,
        skipped=False,
        failure_type="missing_dependency",
    )
    state.reproduction_run = ReproductionRunResult(success=True, skipped=False)

    status = ReportWriterAgent()._determine_final_status(state)

    assert status == "reproduction_success_benchmark_failed"


def test_report_status_does_not_call_metricless_benchmark_success(tmp_path):
    state = _base_state(tmp_path)
    state.benchmark_run = BenchmarkRunResult(eligible=True, success=True, skipped=False)
    state.reproduction_run = ReproductionRunResult(success=True, skipped=False)

    status = ReportWriterAgent()._determine_final_status(state)

    assert status == "reproduction_success"


def test_report_llm_prompt_requires_chinese(tmp_path, monkeypatch):
    captured = {}

    def fake_call_llm_json(**kwargs):
        captured.update(kwargs)
        return {
            "conclusion": "仓库已经找到，但 Smoke 测试失败，需要继续排查依赖和命令参数。",
            "next_steps": ["查看 stderr.log 中的报错。", "确认依赖版本后重跑。", "补充必要的数据或权重。"],
        }

    monkeypatch.setattr(report_writer_agent, "call_llm_json", fake_call_llm_json)

    state = _base_state(tmp_path)
    state.smoke_run = SmokeRunResult(success=False, failure_type="argument_error", failure_evidence="bad arg")

    result = ReportWriterAgent()._llm_generate_insights(state, "repo_found_but_smoke_failed")

    assert result is not None
    assert "必须使用简体中文" in captured["system_prompt"]
    assert "请只输出中文自然语言" in captured["user_prompt"]
    assert "最终状态" in captured["user_prompt"]
    assert "Final status" not in captured["user_prompt"]


def test_report_rejects_english_llm_result_and_uses_chinese_fallback(tmp_path, monkeypatch):
    def fake_call_llm_json(**kwargs):
        return {
            "conclusion": "Smoke failed and the environment needs debugging.",
            "next_steps": [
                "Open stderr.log and inspect the traceback.",
                "Install missing dependencies.",
                "Run the command again.",
            ],
        }

    monkeypatch.setattr(report_writer_agent, "call_llm_json", fake_call_llm_json)

    state = _base_state(tmp_path)
    state.smoke_run = SmokeRunResult(success=False, failure_type="argument_error", failure_evidence="bad arg")

    state = ReportWriterAgent().run(state)

    assert state.report.short_conclusion == "仓库已找到，但 Smoke 测试命令执行失败。"
    report_text = (tmp_path / "task_test" / "report" / "reproduction_smoke_report.md").read_text(encoding="utf-8")
    assert "Smoke failed and the environment needs debugging." not in report_text
    assert "仓库已找到，但 Smoke 测试命令执行失败。" in report_text
