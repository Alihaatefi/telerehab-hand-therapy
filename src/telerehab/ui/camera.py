"""The camera, read on its own thread.

Capturing a frame and running hand detection on it takes tens of milliseconds.
On the interface thread that would make every button feel sluggish, so a worker
thread owns the camera and MediaPipe, and hands finished
:class:`~telerehab.vision.hand_tracker.HandSample` objects across.

Frames are *dropped*, not queued, when the interface is still busy with the
previous one: for biofeedback the newest frame is the only one worth showing.
"""
from __future__ import annotations

import contextlib
from typing import Any, Callable

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QImage

Factory = Callable[[], Any]


def frame_to_image(frame: np.ndarray) -> QImage:
    """An OpenCV BGR frame as a :class:`QImage` that owns its pixels."""
    frame = np.ascontiguousarray(frame)
    height, width = frame.shape[:2]
    return QImage(
        frame.data, width, height, frame.strides[0], QImage.Format.Format_BGR888
    ).copy()


def describe(exc: BaseException) -> str:
    text = str(exc).strip()
    return text or type(exc).__name__


class _Worker(QObject):
    sample = Signal(object)
    failed = Signal(str)
    ready = Signal()

    def __init__(self, factory: Factory):
        super().__init__()
        self._factory = factory
        self._stop = False
        self._busy = False

    @Slot()
    def run(self) -> None:
        # Created here, not in the constructor, so the camera and MediaPipe both
        # belong to this thread for their whole life.
        try:
            tracker = self._factory()
        except Exception as exc:
            self.failed.emit(describe(exc))
            return

        self.ready.emit()
        try:
            while not self._stop:
                try:
                    sample = tracker.read()
                except Exception as exc:
                    self.failed.emit(describe(exc))
                    break
                if self._busy:
                    continue
                self._busy = True
                self.sample.emit(sample)
        finally:
            with contextlib.suppress(Exception):
                tracker.close()

    def stop(self) -> None:
        self._stop = True

    def release(self) -> None:
        self._busy = False


class CameraController(QObject):
    """Starts and stops a camera thread and re-emits what it produces.

    Signals are emitted on the interface thread, so slots connected to them may
    touch widgets freely.
    """

    sample = Signal(object)  # a HandSample
    failed = Signal(str)
    started = Signal()

    def __init__(self, factory: Factory, parent: QObject | None = None):
        super().__init__(parent)
        self._factory = factory
        self._thread: QThread | None = None
        self._worker: _Worker | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None

    def start(self) -> None:
        if self._thread is not None:
            return
        thread = QThread()
        worker = _Worker(self._factory)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.sample.connect(self._on_sample)
        worker.failed.connect(self._on_failed)
        worker.ready.connect(self.started)

        self._thread, self._worker = thread, worker
        thread.start()

    def stop(self) -> None:
        thread, worker = self._thread, self._worker
        if thread is None or worker is None:
            return
        self._thread = self._worker = None

        worker.stop()
        thread.quit()
        thread.wait(4000)
        worker.deleteLater()
        thread.deleteLater()

    # -- relays (interface thread) -------------------------------------------

    @Slot(object)
    def _on_sample(self, sample: object) -> None:
        worker = self._worker
        if worker is None:  # arrived after stop()
            return
        self.sample.emit(sample)
        worker.release()

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        if self._thread is None:
            return
        self.stop()
        self.failed.emit(message)
