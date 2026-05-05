from app.core.progress import ProgressEvent, emit_progress, progress_events


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
