import pytest

from app import cli
from app.core.paths import TaskPaths, generate_task_id


def test_generate_task_id_includes_microseconds():
    task_id = generate_task_id()

    assert task_id.startswith("task_")
    assert len(task_id.rsplit("_", 1)[-1]) == 6


def test_task_paths_refuses_to_reuse_existing_task_dir(tmp_path):
    paths = TaskPaths(str(tmp_path), "task_fixed")
    paths.create_all_dirs()

    with pytest.raises(FileExistsError):
        paths.create_all_dirs()


def test_create_fresh_task_paths_retries_on_collision(tmp_path, monkeypatch):
    existing = TaskPaths(str(tmp_path), "task_collision")
    existing.create_all_dirs()
    ids = iter(["task_collision", "task_fresh"])
    monkeypatch.setattr(cli, "generate_task_id", lambda: next(ids))

    task_id, paths = cli._create_fresh_task_paths(str(tmp_path))

    assert task_id == "task_fresh"
    assert paths.task_dir.exists()
