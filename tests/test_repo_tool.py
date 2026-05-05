from pathlib import Path

from app.tools.repo_tool import (
    compute_runnable_score,
    extract_pip_requirements_from_environment_file,
    find_requirement_files,
    scan_repo_structure,
)


def test_scan_simple_demo_repo():
    repo_dir = Path("tests/fixtures/simple_demo_repo")
    scan = scan_repo_structure(repo_dir)

    assert scan["has_readme"]
    assert scan["has_requirements"]
    assert "demo.py" in scan["candidate_scripts"]


def test_scan_research_demo_entrypoints(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("demo", encoding="utf-8")
    (repo_dir / "gradio_canny2image.py").write_text("", encoding="utf-8")
    scripts_dir = repo_dir / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "amg.py").write_text("", encoding="utf-8")
    app_dir = repo_dir / "app"
    app_dir.mkdir()
    (app_dir / "app.py").write_text("", encoding="utf-8")

    scan = scan_repo_structure(repo_dir)

    assert "app/app.py" in scan["candidate_scripts"]
    assert "gradio_canny2image.py" in scan["candidate_scripts"]
    assert "scripts/amg.py" in scan["candidate_scripts"]


def test_find_requirement_files_in_common_subdirectories(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "requirements.txt").write_text("numpy\n", encoding="utf-8")
    app_dir = repo_dir / "app"
    app_dir.mkdir()
    (app_dir / "requirements.txt").write_text("gradio\n", encoding="utf-8")
    nested_dir = repo_dir / "metric_depth"
    nested_dir.mkdir()
    (nested_dir / "requirements-extra.txt").write_text("torch\n", encoding="utf-8")

    files = [path.relative_to(repo_dir).as_posix() for path in find_requirement_files(repo_dir)]

    assert files == [
        "requirements.txt",
        "app/requirements.txt",
        "metric_depth/requirements-extra.txt",
    ]


def test_runnable_score_positive():
    scan = {
        "has_readme": True,
        "has_requirements": True,
        "has_environment_yml": False,
        "has_dockerfile": False,
        "has_setup_py_or_pyproject": False,
        "candidate_scripts": ["demo.py"],
    }
    assert compute_runnable_score(scan) >= 0.5


def test_extract_pip_requirements_from_environment_file(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "environment.yml").write_text(
        """
name: demo
dependencies:
  - python=3.10
  - pytorch=2.1
  - numpy=1.26
  - pip
  - pip:
      - transformers==4.40.0
      - git+https://github.com/example/project.git
""".strip()
        + "\n",
        encoding="utf-8",
    )

    requirements = extract_pip_requirements_from_environment_file(repo_dir)

    assert requirements == [
        "torch==2.1",
        "numpy==1.26",
        "transformers==4.40.0",
        "git+https://github.com/example/project.git",
    ]


def test_extract_pip_requirements_from_environment_file_missing(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    assert extract_pip_requirements_from_environment_file(repo_dir) == []
