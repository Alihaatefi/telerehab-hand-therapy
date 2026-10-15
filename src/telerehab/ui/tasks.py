"""Running blocking calls off the interface thread.

The backend client uses blocking HTTP with a timeout of several seconds. Called
directly from a button handler, an unreachable backend would freeze the whole
window for that long. :func:`run_async` runs the call on a worker thread and
delivers the outcome back on the interface thread.
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from shiboken6 import isValid

#: Handles stay referenced until delivered, so a task cannot be collected while
#: its worker is still running.
_alive: set[TaskHandle] = set()


class TaskHandle(QObject):
    """Carries one task's outcome from the worker thread to the interface thread."""

    finished = Signal(object, object)  # (result, exception)

    def __init__(
        self,
        on_done: Callable[[Any], None] | None,
        on_error: Callable[[Exception], None] | None,
        owner: QObject | None,
    ):
        super().__init__()
        self._on_done = on_done
        self._on_error = on_error
        self._owner = owner
        # The receiver lives on the interface thread, so emitting from the
        # worker thread is delivered there as a queued call.
        self.finished.connect(self._deliver)

    @Slot(object, object)
    def _deliver(self, result: Any, error: Exception | None) -> None:
        _alive.discard(self)
        try:
            # A page can be closed while its request is in flight; drop the
            # outcome rather than touching a widget that no longer exists.
            if self._owner is not None and not isValid(self._owner):
                return
            if error is not None:
                if self._on_error:
                    self._on_error(error)
            elif self._on_done:
                self._on_done(result)
        finally:
            self.deleteLater()


class _Job(QRunnable):
    def __init__(self, fn: Callable[[], Any], handle: TaskHandle):
        super().__init__()
        self._fn = fn
        self._handle = handle

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:
            self._handle.finished.emit(None, exc)
            return
        self._handle.finished.emit(result, None)


def run_async(
    fn: Callable[[], Any],
    on_done: Callable[[Any], None] | None = None,
    on_error: Callable[[Exception], None] | None = None,
    *,
    owner: QObject | None = None,
) -> TaskHandle:
    """Run ``fn`` on a worker thread; call back on this thread when it finishes.

    ``owner`` is the widget the callbacks belong to: if it is destroyed before
    the task completes, the callbacks are skipped.
    """
    handle = TaskHandle(on_done, on_error, owner)
    _alive.add(handle)
    QThreadPool.globalInstance().start(_Job(fn, handle))
    return handle
