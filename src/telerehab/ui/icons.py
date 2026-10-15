"""Vector icons and the application mark, drawn from inline SVG.

Icons are 24x24 outline glyphs rendered on demand in whatever colour and size
the caller asks for, at the screen's device-pixel ratio, so they stay crisp on
high-DPI displays and never need a bitmap per colour.

The set follows the common 24px stroke-icon grid (the same geometry conventions
as Feather/Lucide, which are ISC/MIT licensed); the glyph paths are short
enough to be listed here directly.
"""
from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

_FRAME = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
    'stroke-linejoin="round">{body}</svg>'
)

_GLYPHS: dict[str, str] = {
    "home": '<path d="M3 11.5 12 4l9 7.5"/><path d="M5.5 10v10h13V10"/><path d="M10 20v-6h4v6"/>',
    "hand": (
        '<path d="M18 11V6a2 2 0 0 0-4 0"/><path d="M14 10V4a2 2 0 0 0-4 0v2"/>'
        '<path d="M10 10.5V6a2 2 0 0 0-4 0v8"/>'
        '<path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.9-6-2.3l-3.6-3.6a2 2 0 0 1 2.8-2.8L7 15"/>'
    ),
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "bar-chart": '<path d="M18 20V10"/><path d="M12 20V4"/><path d="M6 20v-6"/>',
    "sliders": (
        '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3"/>'
        '<path d="M1 14h6M9 8h6M17 16h6"/>'
    ),
    "user": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "user-plus": (
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
        '<path d="M19 8v6M22 11h-6"/>'
    ),
    "log-in": '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><path d="m10 17 5-5-5-5"/><path d="M15 12H3"/>',
    "play": '<path d="M7 4.5v15a1 1 0 0 0 1.5.86l12.4-7.5a1 1 0 0 0 0-1.72L8.5 3.64A1 1 0 0 0 7 4.5Z"/>',
    "pause": '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
    "square": '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "check-circle": '<path d="M22 11.1V12a10 10 0 1 1-5.9-9.1"/><path d="m22 4-10 10-3-3"/>',
    "alert": (
        '<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>'
        '<path d="M12 9v4M12 17h.01"/>'
    ),
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "minus": '<path d="M5 12h14"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "chevron-left": '<path d="m15 18-6-6 6-6"/>',
    "arrow-left": '<path d="M19 12H5M12 19l-7-7 7-7"/>',
    "arrow-right": '<path d="M5 12h14M12 5l7 7-7 7"/>',
    "camera": (
        '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2Z"/>'
        '<circle cx="12" cy="13" r="4"/>'
    ),
    "camera-off": (
        '<path d="M1 1l22 22"/><path d="M21 21H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h3m3-3h6l2 3h4a2 2 0 0 1 2 2v9.3"/>'
        '<path d="M14.1 14.1A3 3 0 1 1 9.9 9.9"/>'
    ),
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    "refresh": (
        '<path d="M23 4v6h-6M1 20v-6h6"/>'
        '<path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15"/>'
    ),
    "wifi": '<path d="M5 12.6a11 11 0 0 1 14.1 0M1.4 9a16 16 0 0 1 21.2 0M8.5 16.1a6 6 0 0 1 7 0M12 20h.01"/>',
    "wifi-off": (
        '<path d="M1 1l22 22M16.7 11.1A11 11 0 0 1 19 12.6M5 12.6a11 11 0 0 1 5.2-2.9M10.7 5.1A16 16 0 0 1 22.6 9M1.4 9a16 16 0 0 1 4.7-2.9M8.5 16.1a6 6 0 0 1 7 0M12 20h.01"/>'
    ),
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "file-text": (
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>'
    ),
    "repeat": '<path d="m17 1 4 4-4 4"/><path d="M3 11V9a4 4 0 0 1 4-4h14M7 23l-4-4 4-4"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/>',
    "trending-up": '<path d="m23 6-9.5 9.5-5-5L1 18"/><path d="M17 6h6v6"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "log-out": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    "lock": '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "shield": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/>',
    "rotate-ccw": '<path d="M1 4v6h6"/><path d="M3.5 15a9 9 0 1 0 2.1-9.4L1 10"/>',
}

# The application mark: five fingers fanned from a palm, on a teal tile.
_LOGO = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="tile" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#34D6C2"/>
      <stop offset="1" stop-color="#0B6B6A"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="16" fill="url(#tile)"/>
  <g stroke="#FFFFFF" stroke-width="5.2" stroke-linecap="round" fill="none">
    <path d="M32 40 32 15"/>
    <path d="M26.5 41 19.5 20"/>
    <path d="M37.5 41 44.5 20"/>
    <path d="M22 45 10.5 32"/>
    <path d="M42 45 53.5 32"/>
  </g>
  <circle cx="32" cy="45" r="11" fill="#FFFFFF"/>
  <circle cx="32" cy="45" r="4.2" fill="#0E7C7B" opacity="0.9"/>
</svg>
"""


def _device_ratio() -> float:
    screen = QGuiApplication.primaryScreen()
    return screen.devicePixelRatio() if screen else 1.0


def _render(svg: str, size: int, ratio: float) -> QPixmap:
    pixels = max(1, round(size * ratio))
    image = QImage(pixels, pixels, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(
        painter, QRectF(0, 0, pixels, pixels)
    )
    painter.end()

    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


@lru_cache(maxsize=512)
def pixmap(name: str, color: str = "#0F1C2E", size: int = 20, stroke: float = 1.8) -> QPixmap:
    """A glyph as a pixmap in ``color`` at ``size`` logical pixels."""
    try:
        body = _GLYPHS[name]
    except KeyError:
        raise KeyError(f"unknown icon {name!r}") from None
    svg = _FRAME.format(color=color, stroke=stroke, body=body)
    return _render(svg, size, _device_ratio())


def icon(name: str, color: str = "#0F1C2E", size: int = 20, *, disabled: str = "#A9B4C3") -> QIcon:
    """A :class:`QIcon` with a normal and a disabled rendering."""
    result = QIcon()
    result.addPixmap(pixmap(name, color, size), QIcon.Mode.Normal)
    result.addPixmap(pixmap(name, disabled, size), QIcon.Mode.Disabled)
    return result


@lru_cache(maxsize=16)
def logo(size: int = 40) -> QPixmap:
    """The application mark."""
    return _render(_LOGO, size, _device_ratio())


def names() -> list[str]:
    return sorted(_GLYPHS)
