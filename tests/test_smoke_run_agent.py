import subprocess

from app.agents.smoke_run_agent import (
    SmokeRunAgent,
    _argparse_script_sort_key,
    classify_smoke_failure,
)
from app.core.state import EnvironmentBuildResult, RepoEvaluation, SmokeCommand, TaskState


def test_classify_static_tls_as_runtime_linker_error():
    stderr = "ImportError: libgomp.so.1.0.0: cannot allocate memory in static TLS block"

    failure_type, evidence = classify_smoke_failure(stderr, "")

    assert failure_type == "runtime_linker_error"
    assert "static TLS" in evidence


def test_home_path_with_nvidia_does_not_imply_cuda_error():
    stderr = "ImportError: cannot import name 'rcParams' from '/home/nvidia/project/pkg.py'"

    failure_type, evidence = classify_smoke_failure(stderr, "")

    assert failure_type == "unknown"


def test_pt_file_not_found_is_missing_checkpoint():
    stderr = "FileNotFoundError: [Errno 2] No such file or directory: '../weights/mobile_sam.pt'"

    failure_type, evidence = classify_smoke_failure(stderr, "")

    assert failure_type == "missing_checkpoint"
    assert "mobile_sam.pt" in evidence


def test_camera_failure_is_not_cuda_error_even_when_stdout_mentions_cuda():
    stdout = 'Running inference on device "cuda"\nLoaded model\n'
    stderr = "OSError: Could not read camera\n"

    failure_type, evidence = classify_smoke_failure(stderr, stdout)

    assert failure_type == "missing_input_device"
    assert "camera" in evidence.lower()


def test_argparse_sort_prefers_scripts_over_app_ui():
    scripts = ["app/app.py", "scripts/amg.py", "scripts/export_onnx_model.py"]

    assert sorted(scripts, key=_argparse_script_sort_key)[0] == "scripts/amg.py"


def test_venv_argv_rewrites_python_to_venv_python(tmp_path):
    state = TaskState(
        task_id="task_test",
        input_value="paper.pdf",
        workspace_dir=str(tmp_path),
        task_dir=str(tmp_path / "task_test"),
        backend="venv",
        env_build=EnvironmentBuildResult(environment_path=str(tmp_path / "env" / "venv")),
    )

    argv = SmokeRunAgent()._venv_argv(["python", "demo.py", "--help"], state)

    assert argv == [str(tmp_path / "env" / "venv" / "bin" / "python"), "demo.py", "--help"]


def test_conda_smoke_uses_conda_python(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    task_dir = tmp_path / "task_test"
    conda_python = tmp_path / "env" / "conda_env" / "bin" / "python"
    state = TaskState(
        task_id="task_test",
        input_value="paper.pdf",
        workspace_dir=str(tmp_path),
        task_dir=str(task_dir),
        backend="conda",
        env_build=EnvironmentBuildResult(
            build_success=True,
            environment_path=str(tmp_path / "env" / "conda_env"),
            python_executable=str(conda_python),
        ),
        repo_evaluation=RepoEvaluation(
            repo_dir=str(repo_dir),
            candidate_scripts=["demo.py"],
        ),
    )
    agent = SmokeRunAgent()
    command = SmokeCommand(argv=["python", "demo.py", "--help"], display="python demo.py --help")
    seen = {}
    monkeypatch.setattr(agent, "_select_smoke_command", lambda _: command)

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, "ok\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = agent.run(state)

    assert result.smoke_run.success
    assert seen["argv"] == [str(conda_python), "demo.py", "--help"]


def test_venv_smoke_repairs_missing_dependency_and_retries(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    task_dir = tmp_path / "task_test"
    state = TaskState(
        task_id="task_test",
        input_value="paper.pdf",
        workspace_dir=str(tmp_path),
        task_dir=str(task_dir),
        backend="venv",
        env_build=EnvironmentBuildResult(
            build_success=True,
            environment_path=str(tmp_path / "env" / "venv"),
        ),
        repo_evaluation=RepoEvaluation(
            repo_dir=str(repo_dir),
            candidate_scripts=["demo.py"],
        ),
    )
    agent = SmokeRunAgent(max_repair_attempts=2)
    command = SmokeCommand(argv=["python", "demo.py", "--help"], display="python demo.py --help")
    monkeypatch.setattr(agent, "_select_smoke_command", lambda _: command)

    runs = [
        subprocess.CompletedProcess(command.argv, 1, "", "ModuleNotFoundError: No module named 'gradio'\n"),
        subprocess.CompletedProcess(command.argv, 0, "ok\n", ""),
    ]

    def fake_run_command(*args, **kwargs):
        return runs.pop(0)

    def fake_repair(package, *args, **kwargs):
        return {
            "package": package,
            "success": True,
            "summary": f"Installed missing dependency {package}",
            "log_path": str(tmp_path / "repair.log"),
        }

    monkeypatch.setattr(agent, "_run_command", fake_run_command)
    monkeypatch.setattr(agent, "_repair_venv_dependency", fake_repair)

    state = agent.run(state)

    assert state.smoke_run.success
    assert len(state.smoke_run.attempts) == 2
    assert state.smoke_run.repair_actions[0]["package"] == "gradio"


def test_smoke_run_clears_previous_run_dir_before_execution(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    task_dir = tmp_path / "task_test"
    stale_run_dir = task_dir / "runs" / "smoke_001"
    stale_run_dir.mkdir(parents=True)
    stale_file = stale_run_dir / "old_output.txt"
    stale_file.write_text("stale", encoding="utf-8")

    state = TaskState(
        task_id="task_test",
        input_value="paper.pdf",
        workspace_dir=str(tmp_path),
        task_dir=str(task_dir),
        backend="local",
        repo_evaluation=RepoEvaluation(
            repo_dir=str(repo_dir),
            candidate_scripts=["demo.py"],
        ),
    )
    agent = SmokeRunAgent()
    command = SmokeCommand(argv=["python", "demo.py", "--help"], display="python demo.py --help")
    monkeypatch.setattr(agent, "_select_smoke_command", lambda _: command)
    monkeypatch.setattr(
        agent,
        "_run_command",
        lambda *args, **kwargs: subprocess.CompletedProcess(command.argv, 0, "fresh\n", ""),
    )

    state = agent.run(state)

    assert state.smoke_run.success
    assert not stale_file.exists()
    assert (stale_run_dir / "stdout.log").read_text(encoding="utf-8") == "fresh\n"
