"""Chart rendering and on-screen report browsing."""
from .charts import progress_chart, session_chart, to_surface

__all__ = ["progress_chart", "session_chart", "to_surface", "ChartViewer"]


def __getattr__(name: str):  # pragma: no cover - thin lazy-import shim
    if name == "ChartViewer":
        from .viewer import ChartViewer

        return ChartViewer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
