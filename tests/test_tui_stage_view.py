from __future__ import annotations

"""Tests for StageView and pipeline panel logic."""

from app.tui.panels.pipeline_panel import StageView, PipelinePanel, PIPELINE_STAGES, STAGE_LABELS_CN, STATUS_LABELS_CN
from app.tui.panels.session_panel import _mode_cn, _status_cn


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


def test_stage_labels_cn():
    assert STAGE_LABELS_CN["Ingest paper"] == "解析论文"
    assert STAGE_LABELS_CN["Write report"] == "生成报告"
    assert STAGE_LABELS_CN["Build conda env"] == "构建 conda 环境"
    assert STAGE_LABELS_CN["Run smoke command"] == "运行冒烟测试"


def test_status_labels_cn():
    assert STATUS_LABELS_CN["queued"] == "等待中"
    assert STATUS_LABELS_CN["running"] == "运行中"
    assert STATUS_LABELS_CN["disabled"] == "未启用"


def test_stage_view_label_cn():
    sv = StageView(name="Ingest paper")
    assert sv.label_cn == "解析论文"


def test_mode_cn():
    assert _mode_cn("act") == "执行"
    assert _mode_cn("plan") == "计划"


def test_status_cn():
    assert _status_cn("draft") == "草稿"
    assert _status_cn("running") == "运行中"
    assert _status_cn("failed") == "失败"
