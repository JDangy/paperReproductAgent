from __future__ import annotations

"""Tests for app/tools/conda_env_manager.py"""

import sys
from pathlib import Path

from app.tools.conda_env_manager import (
    project_env_root, is_relative_to, env_python_path,
    read_env_marker, write_project_env_marker,
    discover_project_conda_envs,
    find_env_by_selector, is_safe_project_env_path,
    format_env_table,
)


def test_project_env_root():
    assert project_env_root(Path("/ws")) == Path("/ws").resolve() / "envs"


def test_is_relative_to(tmp_path):
    parent = tmp_path / "envs"
    child = parent / "abc"
    child.mkdir(parents=True)
    assert is_relative_to(child, parent)
    assert not is_relative_to(tmp_path, child)


def test_env_python_path():
    p = env_python_path(Path("/env"))
    if sys.platform == "win32":
        assert p.name == "python.exe"
    else:
        assert "bin" in str(p)


def test_marker_read_write(tmp_path):
    env = tmp_path / "envs" / "test-env"
    env.mkdir(parents=True)
    write_project_env_marker(env, task_id="t1", paper_slug="test-env",
                             paper_path="paper.pdf", repo_url="url", workspace=str(tmp_path),
                             python_executable=str(env / "bin" / "python"))
    marker = read_env_marker(env)
    assert marker["created_by"] == "paperReproductAgent"
    assert marker["paper_slug"] == "test-env"


def test_discover_legacy_env(tmp_path):
    env = tmp_path / "envs" / "paper-a"
    env.mkdir(parents=True)
    py = env_python_path(env)
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("", encoding="utf-8")

    envs = discover_project_conda_envs(tmp_path)
    assert len(envs) == 1
    assert envs[0].slug == "paper-a"
    assert envs[0].has_marker is False


def test_discover_with_marker(tmp_path):
    env = tmp_path / "envs" / "paper-b"
    env.mkdir(parents=True)
    py = env_python_path(env)
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("", encoding="utf-8")
    write_project_env_marker(env, task_id="t1", paper_slug="paper-b",
                             paper_path="p", repo_url="u", workspace=str(tmp_path),
                             python_executable=str(py))

    envs = discover_project_conda_envs(tmp_path)
    assert len(envs) == 1
    assert envs[0].has_marker is True


def test_find_env_by_selector_index(tmp_path):
    env = tmp_path / "envs" / "paper-c"
    env.mkdir(parents=True)
    py = env_python_path(env)
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("", encoding="utf-8")
    write_project_env_marker(env, task_id="t1", paper_slug="paper-c",
                             paper_path="p", repo_url="u", workspace=str(tmp_path),
                             python_executable=str(py))

    envs = discover_project_conda_envs(tmp_path)
    found = find_env_by_selector("1", envs)
    assert found is not None
    assert found.slug == "paper-c"

    found2 = find_env_by_selector("paper-c", envs)
    assert found2 is not None


def test_safe_rejects_outside_workspace(tmp_path):
    outside = tmp_path / "outside_env"
    outside.mkdir()
    ok, reason = is_safe_project_env_path(outside, tmp_path)
    assert not ok


def test_safe_allows_inside_workspace_envs(tmp_path):
    env = tmp_path / "envs" / "my-env"
    env.mkdir(parents=True)
    ok, reason = is_safe_project_env_path(env, tmp_path)
    assert ok


def test_format_env_table(tmp_path):
    env = tmp_path / "envs" / "paper-d"
    env.mkdir(parents=True)
    py = env_python_path(env)
    py.parent.mkdir(parents=True, exist_ok=True)
    py.write_text("", encoding="utf-8")

    envs = discover_project_conda_envs(tmp_path)
    table = format_env_table(envs)
    assert "paper-d" in table
    assert "旧版" in table


def test_conda_env_commands_registered():
    from app.tui.commands import COMMANDS
    assert "conda-envs" in COMMANDS
    assert "envs" in COMMANDS
