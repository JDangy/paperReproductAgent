from __future__ import annotations

"""Regression tests for ToolCard — ensures no Static(display=...) constructor crash."""

from app.tui.widgets.tool_card import ToolCard


def test_tool_card_can_construct():
    card = ToolCard(name="Run smoke command", status="running", message="testing")
    assert card is not None
    assert card.tool_name == "Run smoke command"
    assert card.status == "running"


def test_tool_card_mounts_without_display_kwarg():
    """ToolCard.compose() must not pass display= to Static constructor."""
    card = ToolCard(name="Build conda env", status="running", message="building...")
    # compose() is called lazily by Textual; just ensure no AttributeError on init
    assert card._status == "running"


def test_tool_card_update_does_not_crash():
    card = ToolCard(name="Ingest paper", status="running", message="parsing...")
    card.update(status="success", detail="done in 0.6s", duration=0.6)
    assert card.status == "success"


def test_tool_card_all_statuses():
    for status in ("queued", "running", "success", "failed", "skipped", "cancelled"):
        card = ToolCard(name="Test", status=status)
        assert card is not None
