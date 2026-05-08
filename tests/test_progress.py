from app.core.progress import ProgressEvent, emit_progress, progress_events
from app.runtime.session import make_progress_bridge


def test_emit_progress_calls_active_handler():
    events = []

    with progress_events(events.append):
        emit_progress("Stage", "message", level="warning", detail="details", value=1)

    assert events == [
        ProgressEvent(
            stage="Stage",
            message="message",
            level="warning",
            detail="details",
            data={"value": 1},
        )
    ]


def test_emit_progress_without_handler_is_noop():
    emit_progress("Stage", "message")


def test_progress_bridge_preserves_phase_and_data():
    events = []
    bridge = make_progress_bridge(events.append)

    bridge(
        ProgressEvent(
            stage="Stage",
            message="doing work",
            phase="progress",
            detail="details",
            data={"value": 1},
        )
    )
    bridge(
        ProgressEvent(
            stage="Stage",
            message="done",
            level="success",
            phase="finish",
            data={"duration_ms": 123},
        )
    )

    assert [event.type for event in events] == ["tool_progress", "tool_finished"]
    assert events[0].payload == {
        "stage": "Stage",
        "message": "doing work",
        "level": "info",
        "phase": "progress",
        "detail": "details",
        "data": {"value": 1},
    }
    assert events[1].payload["data"] == {"duration_ms": 123}
