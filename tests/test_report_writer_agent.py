from app.agents.report_writer_agent import ReportWriterAgent
from app.core.state import (
    EnvironmentBuildResult,
    PaperMetadata,
    RepoCandidate,
    RepoEvaluation,
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
