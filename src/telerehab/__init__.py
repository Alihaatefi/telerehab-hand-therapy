"""Vision-based hand rehabilitation exercises with clinician reporting.

The practical component of a B.Sc. thesis in Biomedical Engineering, Amirkabir
University of Technology.

Layering, from the inside out:

``config``    settings, read once from the environment
``vision``    camera capture, hand landmarks, per-patient calibration
``games``     exercise rules: scoring, the two engines, calibration procedures
``api``       backend client and the records exchanged with it
``reports``   report data and export (CSV, PDF)
``ui``        the Qt interface: theme, widgets, pages, window

``vision.geometry``, ``vision.calibration``, ``games`` and ``api.models`` carry
the logic worth testing and depend on nothing heavier than the standard library,
which is why most of the test suite runs without a camera or a display. The
logic does not know what displays it: the only code outside ``ui`` that reaches
into it is the PDF export, which imports ``ui.charts`` lazily so that the same
drawing code paints the screen and the page.
"""
from .config import Settings, load_settings

__version__ = "2.0.0"
__all__ = ["Settings", "__version__", "load_settings"]
