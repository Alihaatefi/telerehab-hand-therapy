"""Vision-based hand rehabilitation exercises with clinician reporting.

Originally the practical component of a B.Sc. thesis in Biomedical Engineering
(Amirkabir University of Technology, 2024), rebuilt from a set of duplicated
scripts into a package.

Layering, from the inside out:

``config``    settings, read once from the environment
``vision``    camera capture, hand landmarks, per-patient calibration
``games``     exercise rules (``scoring``) and the two modes
``api``       backend client and the records exchanged with it
``reports``   matplotlib charts and the on-screen viewer
``ui``        theme, widgets and screen scaffolding
``app``       window setup and navigation

``vision.geometry``, ``vision.calibration``, ``games.scoring`` and ``api.models``
carry the logic worth testing and depend on nothing heavier than the standard
library, which is why the test suite runs without a camera or a display.
"""
from .config import Settings, load_settings

__version__ = "1.0.0"
__all__ = ["Settings", "load_settings", "__version__"]
