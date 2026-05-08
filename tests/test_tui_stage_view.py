from __future__ import annotations

"""Tests for StageView and pipeline panel logic."""

from app.tui.panels.pipeline_panel import StageView, PipelinePanel, PIPELINE_STAGES


def test_stage_view_default_status_queued():
    sv = StageView(name="Ingest paper")
    assert sv.status == "queued"
    assert sv.icon == "○"


def test_stage_view_running():
    sv = StageView(name="Ingest paper", status="running")
    assert sv.status == "running"
    assert sv.icon == "●"


def test_stage_view_success():
    sv = StageView(name="Ingest paper", status="success")
    assert sv.status == "success"
    assert sv.icon == "✓"


def test_stage_view_failed():
    sv = StageView(name="Ingest paper", status="failed")
    assert sv.status == "failed"
    assert sv.icon == "✗"


def test_pipeline_panel_reset_conda():
    panel = PipelinePanel(backend="conda")
    assert panel._stages["Build conda env"].status in ("queued",)
    assert panel._stages["Build virtualenv"].status == "disabled"
    assert panel._stages["Build Docker image"].status == "disabled"


def test_pipeline_panel_reset_venv():
    panel = PipelinePanel(backend="venv")
    assert panel._stages["Build conda env"].status == "disabled"
    assert panel._stages["Build virtualenv"].status in ("queued",)
    assert panel._stages["Build Docker image"].status == "disabled"


def test_pipeline_panel_reset_none():
    panel = PipelinePanel(backend="none")
    for stage_name in PIPELINE_STAGES:
        sv = panel._stages[stage_name]
        if stage_name in ("Run smoke command", "Run benchmark reproduction", "Run simple reproduction"):
            assert sv.status == "disabled", f"{stage_name} should be disabled for backend=none"
        elif "Build" in stage_name:
            assert sv.status == "disabled", f"{stage_name} should be disabled for backend=none"


def test_pipeline_panel_update_stage():
    panel = PipelinePanel(backend="conda")
    panel.update_stage(StageView(name="Ingest paper", status="running", message="parsing..."))
    assert panel._stages["Ingest paper"].status == "running"
    assert panel._stages["Ingest paper"].message == "parsing..."


def test_pipeline_panel_attempt_count_on_rerun():
    panel = PipelinePanel(backend="conda")
    panel.update_stage(StageView(name="Ingest paper", status="failed"))
    panel.update_stage(StageView(name="Ingest paper", status="running"))
    assert panel._stages["Ingest paper"].attempts == 1


def test_stage_view_duration():
    sv = StageView(name="Test", status="success", duration=3.5)
    assert sv.duration == 3.5
