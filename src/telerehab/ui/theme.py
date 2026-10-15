"""Design tokens and the application stylesheet.

Every colour, size and weight the interface uses is named here, so a visual
change is made in one place rather than hunted for across the pages.

The look is deliberately calm and clinical: cool neutral surfaces, one teal
accent for the primary action, and colour reserved for *meaning* — green for
success, amber for caution, red for error — never for decoration.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

# -- palette -----------------------------------------------------------------

# Surfaces
CANVAS = "#F2F5F8"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F7F9FB"
BORDER = "#E2E8EF"
BORDER_STRONG = "#CBD5E1"

# Sidebar
SIDEBAR = "#0F2A30"
SIDEBAR_HOVER = "#17383F"
SIDEBAR_TEXT = "#A9C0C4"
SIDEBAR_MUTED = "#6F8D92"
SIDEBAR_RULE = "#1E414A"

# Text
TEXT = "#0F1C2E"
TEXT_MUTED = "#52627A"
TEXT_SUBTLE = "#8392A8"
TEXT_ON_PRIMARY = "#FFFFFF"

# Brand / accents
PRIMARY = "#0E7C7B"
PRIMARY_HOVER = "#0B6665"
PRIMARY_PRESSED = "#095251"
PRIMARY_SOFT = "#E2F3F2"
PRIMARY_TEXT = "#0A5D5C"
MINT = "#2DD4BF"

ACCENT = "#2F6FDE"
ACCENT_SOFT = "#E8F0FC"

# Status
SUCCESS = "#15803D"
SUCCESS_SOFT = "#E4F5EA"
WARNING = "#B45309"
WARNING_SOFT = "#FDF1DD"
DANGER = "#B42318"
DANGER_SOFT = "#FCE9E7"
DANGER_HOVER = "#8F1B12"

# Camera / exercise stage
STAGE_DARK = "#0B1B20"
STAGE_PANEL = "#12272D"

# Data series, in the order they are assigned.
SERIES = ("#0E7C7B", "#2F6FDE", "#D97706", "#7C3AED")

# -- typography --------------------------------------------------------------

FONT_FAMILIES = [
    "Segoe UI Variable Text",
    "Segoe UI",
    "Inter",
    "SF Pro Text",
    "Helvetica Neue",
    "Arial",
]

RADIUS = 12
RADIUS_LG = 16


def qcolor(value: str, alpha: float = 1.0) -> QColor:
    """A colour from a ``#RRGGBB`` token, optionally translucent (0..1)."""
    colour = QColor(value)
    colour.setAlphaF(alpha)
    return colour


def app_font(pixel_size: int = 14, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


# -- stylesheet --------------------------------------------------------------


def stylesheet() -> str:
    return f"""
* {{
    font-size: 14px;
    color: {TEXT};
}}

QWidget#Page, QWidget#Root {{
    background: {CANVAS};
}}

QLabel {{ background: transparent; }}
QLabel[role="display"] {{ font-size: 30px; font-weight: 700; }}
QLabel[role="h1"]      {{ font-size: 26px; font-weight: 700; }}
QLabel[role="h2"]      {{ font-size: 18px; font-weight: 600; }}
QLabel[role="h3"]      {{ font-size: 15px; font-weight: 600; }}
QLabel[role="muted"]   {{ color: {TEXT_MUTED}; }}
QLabel[role="caption"] {{ color: {TEXT_SUBTLE}; font-size: 12px; }}
QLabel[role="eyebrow"] {{ color: {PRIMARY}; font-size: 12px; font-weight: 700; }}
QLabel[role="stat"]    {{ font-size: 30px; font-weight: 700; }}
QLabel[role="mono"]    {{ font-family: "Cascadia Mono", Consolas, monospace; color: {TEXT_MUTED}; font-size: 12px; }}
QLabel[role="onDark"]  {{ color: #FFFFFF; }}
QLabel[role="onDarkMuted"] {{ color: {SIDEBAR_TEXT}; }}

/* -- cards ---------------------------------------------------------------- */
QFrame[card="true"] {{
    background: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_LG}px;
}}
QFrame[card="soft"] {{
    background: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: {RADIUS}px;
}}
QFrame[card="true"] QLabel, QFrame[card="soft"] QLabel {{ border: none; }}

QFrame[rule="true"] {{ background: {BORDER}; border: none; max-height: 1px; min-height: 1px; }}

/* Panels floating over the exercise scene. */
QFrame[hud="true"] {{
    background: rgba(255,255,255,0.90);
    border: 1px solid rgba(255,255,255,0.65);
    border-radius: 14px;
}}
QFrame[hud="true"] QLabel {{ border: none; }}

/* -- buttons -------------------------------------------------------------- */
QPushButton {{
    background: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS - 2}px;
    padding: 9px 16px;
    font-weight: 600;
    color: {TEXT};
}}
QPushButton:hover    {{ background: #EEF2F6; }}
QPushButton:pressed  {{ background: #E2E8EF; }}
QPushButton:focus    {{ border: 1px solid {PRIMARY}; }}
QPushButton:disabled {{ background: #EEF1F5; color: {TEXT_SUBTLE}; border-color: {BORDER}; }}

QPushButton[variant="primary"] {{
    background: {PRIMARY}; border: 1px solid {PRIMARY}; color: {TEXT_ON_PRIMARY};
}}
QPushButton[variant="primary"]:hover   {{ background: {PRIMARY_HOVER}; border-color: {PRIMARY_HOVER}; }}
QPushButton[variant="primary"]:pressed {{ background: {PRIMARY_PRESSED}; }}
QPushButton[variant="primary"]:disabled {{ background: #9CC9C8; border-color: #9CC9C8; color: #F2FAFA; }}

QPushButton[variant="danger"] {{
    background: {SURFACE}; border: 1px solid #E8B4AE; color: {DANGER};
}}
QPushButton[variant="danger"]:hover {{ background: {DANGER_SOFT}; }}

QPushButton[variant="ghost"] {{
    background: transparent; border: 1px solid transparent; color: {TEXT_MUTED};
}}
QPushButton[variant="ghost"]:hover {{ background: #E8EDF2; color: {TEXT}; }}

QPushButton[variant="onDark"] {{
    background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.18); color: #FFFFFF;
}}
QPushButton[variant="onDark"]:hover {{ background: rgba(255,255,255,0.18); }}
QPushButton[variant="onDark"]:disabled {{ color: rgba(255,255,255,0.4); background: rgba(255,255,255,0.05); }}

QPushButton[size="lg"] {{ padding: 13px 22px; font-size: 15px; border-radius: {RADIUS}px; }}
QPushButton[size="sm"] {{ padding: 6px 12px; font-size: 13px; }}

QPushButton[chip="true"] {{
    background: {SURFACE}; border: 1px solid {BORDER_STRONG}; border-radius: 15px;
    padding: 6px 14px; font-weight: 600; color: {TEXT_MUTED};
}}
QPushButton[chip="true"]:checked {{
    background: {PRIMARY_SOFT}; border-color: {PRIMARY}; color: {PRIMARY_TEXT};
}}

QPushButton[tab="true"] {{
    background: transparent; border: none; border-bottom: 2px solid transparent;
    border-radius: 0; padding: 10px 4px; margin-right: 18px; color: {TEXT_MUTED}; font-weight: 600;
}}
QPushButton[tab="true"]:checked {{ color: {PRIMARY_TEXT}; border-bottom: 2px solid {PRIMARY}; }}
QPushButton[tab="true"]:hover {{ background: transparent; color: {TEXT}; }}

/* -- navigation ----------------------------------------------------------- */
QFrame#Sidebar {{ background: {SIDEBAR}; border: none; }}
QFrame#Sidebar QLabel {{ background: transparent; }}

QPushButton[nav="true"] {{
    background: transparent; border: none; border-radius: {RADIUS - 2}px;
    padding: 11px 14px; text-align: left; color: {SIDEBAR_TEXT}; font-weight: 600;
}}
QPushButton[nav="true"]:hover   {{ background: {SIDEBAR_HOVER}; color: #FFFFFF; }}
QPushButton[nav="true"]:checked {{ background: rgba(45,212,191,0.16); color: #FFFFFF; }}
QPushButton[nav="true"]:disabled {{ color: {SIDEBAR_MUTED}; background: transparent; }}

/* -- inputs --------------------------------------------------------------- */
QLineEdit, QComboBox {{
    background: {SURFACE};
    border: 1px solid {BORDER_STRONG};
    border-radius: {RADIUS - 2}px;
    padding: 9px 12px;
    selection-background-color: {PRIMARY};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {PRIMARY}; }}
QLineEdit[invalid="true"] {{ border: 1px solid {DANGER}; }}
QLineEdit:disabled {{ background: #EEF1F5; color: {TEXT_SUBTLE}; }}
QLineEdit::placeholder {{ color: {TEXT_SUBTLE}; }}
/* The number inside a SpinField: no box of its own, the field draws it. */
QLineEdit[bare="true"] {{
    border: none; background: transparent; padding: 9px 4px; font-weight: 600; font-size: 16px;
}}
QLineEdit[bare="true"]:focus {{ border: none; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; border: 1px solid {BORDER_STRONG}; selection-background-color: {PRIMARY_SOFT};
    selection-color: {PRIMARY_TEXT}; outline: none; padding: 4px;
}}

QFrame[field="true"] {{
    background: {SURFACE}; border: 1px solid {BORDER_STRONG}; border-radius: {RADIUS - 2}px;
}}
QFrame[field="true"][focused="true"] {{ border: 1px solid {PRIMARY}; }}
QFrame[field="true"] QPushButton {{
    border: none; background: transparent; padding: 0; border-radius: 8px;
}}
QFrame[field="true"] QPushButton:hover {{ background: #E8EDF2; }}

/* -- pills ---------------------------------------------------------------- */
QLabel[pill] {{ border-radius: 11px; padding: 3px 10px; font-size: 12px; font-weight: 600; }}
QLabel[pill="neutral"] {{ background: #E8EDF2; color: {TEXT_MUTED}; }}
QLabel[pill="success"] {{ background: {SUCCESS_SOFT}; color: {SUCCESS}; }}
QLabel[pill="warning"] {{ background: {WARNING_SOFT}; color: {WARNING}; }}
QLabel[pill="danger"]  {{ background: {DANGER_SOFT}; color: {DANGER}; }}
QLabel[pill="info"]    {{ background: {ACCENT_SOFT}; color: {ACCENT}; }}
QLabel[pill="brand"]   {{ background: {PRIMARY_SOFT}; color: {PRIMARY_TEXT}; }}
QLabel[pill="onDark"]  {{ background: rgba(255,255,255,0.14); color: #FFFFFF; }}

/* -- banners -------------------------------------------------------------- */
QFrame[banner="info"]    {{ background: {ACCENT_SOFT};  border: 1px solid #C9DBF8; border-radius: {RADIUS - 2}px; }}
QFrame[banner="success"] {{ background: {SUCCESS_SOFT}; border: 1px solid #BFE3CB; border-radius: {RADIUS - 2}px; }}
QFrame[banner="warning"] {{ background: {WARNING_SOFT}; border: 1px solid #F1D9A8; border-radius: {RADIUS - 2}px; }}
QFrame[banner="danger"]  {{ background: {DANGER_SOFT};  border: 1px solid #F0C1BC; border-radius: {RADIUS - 2}px; }}
QFrame[banner] QLabel {{ border: none; }}

/* -- tables --------------------------------------------------------------- */
QTableWidget {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {RADIUS}px;
    gridline-color: transparent; alternate-background-color: {SURFACE_ALT};
    selection-background-color: {PRIMARY_SOFT}; selection-color: {TEXT}; outline: none;
}}
QTableWidget::item {{ padding: 8px 12px; border: none; }}
QHeaderView::section {{
    background: {SURFACE}; color: {TEXT_MUTED}; font-size: 12px; font-weight: 700;
    border: none; border-bottom: 1px solid {BORDER}; padding: 10px 12px;
}}
QTableCornerButton::section {{ background: {SURFACE}; border: none; }}

/* -- scrolling ------------------------------------------------------------ */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #C5CFDB; border-radius: 4px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: #A9B6C6; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #C5CFDB; border-radius: 4px; min-width: 36px; }}

QToolTip {{
    background: {TEXT}; color: #FFFFFF; border: none; padding: 6px 9px; border-radius: 6px;
}}
QMessageBox {{ background: {SURFACE}; }}
"""


def apply_theme(app: QApplication) -> None:
    """Install the font, palette and stylesheet on the whole application."""
    app.setStyle("Fusion")
    app.setFont(app_font())

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, qcolor(CANVAS))
    palette.setColor(QPalette.ColorRole.WindowText, qcolor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, qcolor(SURFACE))
    palette.setColor(QPalette.ColorRole.AlternateBase, qcolor(SURFACE_ALT))
    palette.setColor(QPalette.ColorRole.Text, qcolor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, qcolor(SURFACE))
    palette.setColor(QPalette.ColorRole.ButtonText, qcolor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, qcolor(PRIMARY))
    palette.setColor(QPalette.ColorRole.HighlightedText, qcolor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, qcolor(TEXT_SUBTLE))
    app.setPalette(palette)

    app.setStyleSheet(stylesheet())
