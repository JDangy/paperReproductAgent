from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Iterator

CancelCheck = Callable[[], bool]

_current_cancel_check: ContextVar[CancelCheck | None] = ContextVar(
    "paper_smoke_cancel_check", default=None
)


class PipelineCancelled(RuntimeError):
    """Raised when the pipeline is cancelled mid-execution."""
    pass


@contextmanager
def cancellation(check: CancelCheck | None) -> Iterator[None]:
    token = _current_cancel_check.set(check)
    try:
        yield
    finally:
        _current_cancel_check.reset(token)


def is_cancelled() -> bool:
    check = _current_cancel_check.get()
    if check is None:
        return False
    try:
        return bool(check())
    except Exception:
        return False


def raise_if_cancelled() -> None:
    if is_cancelled():
        raise PipelineCancelled("cancelled")
