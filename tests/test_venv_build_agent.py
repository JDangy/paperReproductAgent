from app.agents.venv_build_agent import (
    _extract_requirement_name,
    _is_self_vcs_requirement,
    _local_project_names,
    _module_name_for_package,
    _target_bootstrap_specs,
    relax_requirement_line,
)


def test_relax_requirement_line_removes_version_pins_and_extras():
    assert relax_requirement_line("transformers[torch]==4.40.0") == "transformers"
    assert relax_requirement_line("numpy>=1.24 ; python_version >= '3.8'") == "numpy"


def test_relax_requirement_line_preserves_comments_and_urls():
    assert relax_requirement_line("# keep comment") == "# keep comment"
    assert relax_requirement_line("git+https://github.com/example/project.git") == "git+https://github.com/example/project.git"


def test_self_vcs_requirement_is_skipped_for_local_project(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    package_dir = repo_dir / "mobile_sam"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")

    local_names = _local_project_names(repo_dir)

    assert _is_self_vcs_requirement("git+https://github.com/dhkim2810/MobileSAM.git", local_names)
    assert not _is_self_vcs_requirement("git+https://github.com/example/other-lib.git", local_names)


def test_extract_requirement_name_for_importable_filter():
    assert _extract_requirement_name("torchvision>=0.13 ; python_version >= '3.8'") == "torchvision"
    assert _extract_requirement_name("opencv-python==4.8.0") == "opencv-python"
    assert _extract_requirement_name("git+https://github.com/example/repo.git") is None


def test_module_name_for_common_packages():
    assert _module_name_for_package("opencv-python") == "cv2"
    assert _module_name_for_package("opencv-contrib-python") == "cv2"
    assert _module_name_for_package("open_clip_torch") == "open_clip"


def test_target_bootstrap_specs_extracts_gradio(tmp_path):
    req = tmp_path / "requirements.txt"
    req.write_text("gradio==3.16.2\nnumpy\n", encoding="utf-8")

    assert _target_bootstrap_specs(req) == ["gradio==3.16.2"]
