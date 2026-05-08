import subprocess

from app.agents.conda_build_agent import CondaBuildAgent
from app.core.naming import stable_paper_slug
from app.core.state import PaperMetadata, RepoEvaluation, TaskState


def test_find_conda_executable_prefers_explicit_path(tmp_path):
    conda = tmp_path / "conda"
    conda.write_text("#!/bin/sh\n", encoding="utf-8")

    agent = CondaBuildAgent(conda_executable=str(conda))

    assert agent._find_conda_executable() == str(conda)


def test_conda_build_creates_expected_environment_summary(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    task_dir = tmp_path / "task"
    fake_conda = tmp_path / "conda"
    fake_conda.write_text("#!/bin/sh\n", encoding="utf-8")

    state = TaskState(
        task_id="task_test",
        input_value="paper.pdf",
        workspace_dir=str(tmp_path),
        task_dir=str(task_dir),
        backend="conda",
        repo_evaluation=RepoEvaluation(repo_dir=str(repo_dir)),
    )
    agent = CondaBuildAgent(conda_executable=str(fake_conda))

    def fake_run_process(argv, cwd, deadline, log_parts, step_name):
        log_parts.append(f"$ {' '.join(argv)}")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(agent, "_run_process", fake_run_process)

    result = agent.run(state)

    assert result.env_build.build_success
    assert result.env_build.environment_path == str(tmp_path / "envs" / "task-test")
    assert result.env_build.python_executable == str(tmp_path / "envs" / "task-test" / "bin" / "python")
    assert (task_dir / "env" / "environment_summary.json").exists()


def test_conda_build_reuses_paper_named_environment(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    task_dir = tmp_path / "task"
    existing_python = tmp_path / "envs" / "demo-paper" / "bin" / "python"
    existing_python.parent.mkdir(parents=True)
    existing_python.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_conda = tmp_path / "conda"
    fake_conda.write_text("#!/bin/sh\n", encoding="utf-8")

    state = TaskState(
        task_id="task_test",
        input_value="paper.pdf",
        workspace_dir=str(tmp_path),
        task_dir=str(task_dir),
        backend="conda",
        paper_metadata=PaperMetadata(title="Demo Paper"),
        repo_evaluation=RepoEvaluation(repo_dir=str(repo_dir)),
    )
    agent = CondaBuildAgent(conda_executable=str(fake_conda))

    def fail_run_process(*args, **kwargs):
        raise AssertionError("existing paper-named conda env should be reused")

    monkeypatch.setattr(agent, "_run_process", fail_run_process)

    result = agent.run(state)

    assert result.env_build.build_success
    assert result.env_build.environment_path == str(tmp_path / "envs" / "demo-paper")
    assert result.env_build.install_actions[0]["action"] == "reuse_conda_env"


def test_stable_paper_slug_prefers_specific_input_stem_over_noisy_title(tmp_path):
    state = TaskState(
        task_id="task_test",
        input_value=str(tmp_path / "clip.pdf"),
        workspace_dir=str(tmp_path),
        task_dir=str(tmp_path / "task"),
        paper_metadata=PaperMetadata(title="Alec Radford 1 Jong Wook Kim 1"),
    )

    assert stable_paper_slug(state) == "clip"
