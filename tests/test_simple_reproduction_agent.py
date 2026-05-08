import subprocess

from app.agents.simple_reproduction_agent import (
    SimpleReproductionAgent,
    _extract_python_code_blocks,
    _is_safe_reproduction_argv,
    _parse_superglue_metrics,
    _sanitize_readme_example_block,
)
from app.core.state import EnvironmentBuildResult, RepoEvaluation, ReproductionCommand, TaskState


def _state(tmp_path, backend="local"):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "demo.py").write_text("print('demo ok')\n", encoding="utf-8")
    return TaskState(
        task_id="task_test",
        input_value="paper.pdf",
        workspace_dir=str(tmp_path),
        task_dir=str(tmp_path / "task_test"),
        backend=backend,
        env_build=EnvironmentBuildResult(build_success=True),
        repo_evaluation=RepoEvaluation(
            repo_dir=str(repo_dir),
            candidate_scripts=["demo.py"],
        ),
    )


def test_reproduction_safety_blocks_help_and_training():
    scripts = ["demo.py", "train.py"]

    assert not _is_safe_reproduction_argv(["python", "demo.py", "--help"], scripts)[0]
    assert not _is_safe_reproduction_argv(["python", "train.py"], scripts)[0]
    assert not _is_safe_reproduction_argv(["python", "demo.py", "--url", "https://example.com/x"], scripts)[0]
    assert not _is_safe_reproduction_argv(["pytest", "-q"], scripts)[0]
    assert _is_safe_reproduction_argv(["python", "demo.py", "--input", "examples/a.png"], scripts)[0]


def test_simple_reproduction_runs_selected_command(tmp_path, monkeypatch):
    state = _state(tmp_path)
    agent = SimpleReproductionAgent(timeout_minutes=1)
    command = ReproductionCommand(
        argv=["python", "demo.py"],
        display="python demo.py",
        kind="demo",
        reason="unit test",
    )
    monkeypatch.setattr(agent, "_select_command", lambda state, run_dir: (command, [], None))

    state = agent.run(state)

    assert state.reproduction_run.success
    assert state.reproduction_run.command.display == "python demo.py"
    assert "demo ok" in (tmp_path / "task_test" / "runs" / "reproduction_001" / "stdout.log").read_text(encoding="utf-8")


def test_simple_reproduction_skips_default_webcam_demo_candidate(tmp_path):
    state = _state(tmp_path)
    repo_dir = tmp_path / "repo"
    (repo_dir / "demo.py").write_text(
        "import argparse\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--input', default='0', help='ID of a USB webcam')\n"
        "print('webcam demo')\n",
        encoding="utf-8",
    )

    candidates = SimpleReproductionAgent(timeout_minutes=1)._heuristic_candidates(state)

    assert candidates == []


def test_simple_reproduction_skips_when_env_failed(tmp_path):
    state = _state(tmp_path, backend="conda")
    state.env_build.build_success = False

    state = SimpleReproductionAgent(timeout_minutes=1).run(state)

    assert state.reproduction_run.skipped
    assert "environment did not build" in state.reproduction_run.skip_reason


def test_simple_reproduction_records_failure(tmp_path, monkeypatch):
    state = _state(tmp_path)
    agent = SimpleReproductionAgent(timeout_minutes=1)
    command = ReproductionCommand(argv=["python", "demo.py"], display="python demo.py", kind="demo")
    monkeypatch.setattr(agent, "_select_command", lambda state, run_dir: (command, [], None))
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 2, "", "FileNotFoundError: missing.txt\n"),
    )

    state = agent.run(state)

    assert not state.reproduction_run.success
    assert state.reproduction_run.failure_type == "file_not_found"


def test_parse_superglue_metrics():
    stdout = """
Evaluation Results (mean over 15 pairs):
AUC@5\t AUC@10\t AUC@20\t Prec\t MScore
23.58\t 42.50\t 61.28\t 73.60\t 19.64
"""

    assert _parse_superglue_metrics(stdout) == {
        "AUC@5": 23.58,
        "AUC@10": 42.50,
        "AUC@20": 61.28,
        "Prec": 73.60,
        "MScore": 19.64,
    }


def test_readme_python_example_harness_uses_bundled_audio_and_small_model(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "jfk.flac").write_bytes(b"fake")
    readme = '''
```python
import whisper

model = whisper.load_model("turbo")
result = model.transcribe("audio.mp3")
print(result["text"])
```
'''
    block = _extract_python_code_blocks(readme)[0]

    script = _sanitize_readme_example_block(block, repo_dir)

    assert script is not None
    assert 'load_model("tiny")' in script
    assert 'tests/jfk.flac' in script
    assert "imageio_ffmpeg" in script
    assert '.paper_smoke_bin' in script
    assert "PAPER_SMOKE_README_EXAMPLE_OK" in script


def test_readme_python_example_rejects_doctest_transcript(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    block = """
>>> import numpy as np
>>> np.load('result.npz')
"""

    assert _sanitize_readme_example_block(block, repo_dir) is None
