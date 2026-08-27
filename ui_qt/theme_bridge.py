"""
Bridges themes.theme_manager.ThemeManager's palette dict to Qt.

ThemeManager itself stays framework-neutral (it only loads a flat
key -> hex-string palette from themes/*.json and exposes .palette /
.reload()); its Tk-specific apply_to(root) is never called from Qt code.
This module turns the same palette into a QSS stylesheet instead.
"""

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication


class ThemeSignal(QObject):
    """Single shared notification path for theme changes. Anything that
    changes settings.theme + calls theme.reload() emits `changed` with the
    new palette; nothing fans out manually beyond that (see the class
    docstring below for why that matters)."""

    changed = Signal(dict)


def build_stylesheet(palette: dict) -> str:
    """Turn a theme palette dict (see themes/dark.json) into an app-wide QSS string."""
    bg = palette.get("bg", "#1E1E1E")
    fg = palette.get("fg", "#CCCCCB")
    border = palette.get("border", "#3E3E3E")
    font = palette.get("ui_font", "Segoe UI")

    menubar_bg = palette.get("menubar_bg", "#323233")
    menubar_hover = palette.get("menubar_hover", "#2A2D2E")
    menubar_text = palette.get("menubar_text", "#CCCCCC")

    dropdown_bg = palette.get("dropdown_bg", "#252526")
    dropdown_hover = palette.get("dropdown_hover", "#2A2D2E")
    dropdown_text = palette.get("dropdown_text", "#CCCCCC")
    dropdown_disabled = palette.get("dropdown_disabled", "#666666")
    dropdown_separator = palette.get("dropdown_separator", "#454545")
    dropdown_border = palette.get("dropdown_border", "#3E3E42")
    dropdown_shortcut = palette.get("dropdown_shortcut", "#858585")

    scrollbar_track = palette.get("scrollbar_track", "#1E1E1E")
    scrollbar_thumb = palette.get("scrollbar_thumb", "#525252")
    scrollbar_hover = palette.get("scrollbar_hover", "#999292")

    tooltip_bg = palette.get("tooltip_bg", "#2A2A2A")
    tooltip_fg = palette.get("tooltip_fg", "#FFFFFF")

    button_fg = palette.get("button_fg_color", "#1E1E1E")
    button_bg = palette.get("button_bg_color", "#BB86FC")
    button_hover = palette.get("button_hover", "#985EFF")
    button_pressed = palette.get("button_pressed", "#6023CB")

    slider_bg = palette.get("slider_bg", "#404040")
    slider_progress = palette.get("slider_progress", "#BB86FC")
    slider_button = palette.get("slider_button", "#BB86FC")
    slider_hover = palette.get("slider_hover", "#985EFF")

    return f"""
    QWidget {{
        background-color: {bg};
        color: {fg};
        font-family: "{font}";
    }}

    QWidget#MainWindow {{
        border: 1px solid {border};
    }}

    QWidget#MenuBarContainer, QWidget#MenuBarSpacer {{
        background-color: {menubar_bg};
    }}

    QWidget#DialogTitleBar {{
        background-color: {menubar_bg};
        border-bottom: 1px solid {border};
    }}

    QWidget#CentralArea {{
        background-color: {bg};
    }}

    QMenuBar {{
        background-color: {menubar_bg};
        color: {menubar_text};
        border: none;
        spacing: 0px;
    }}
    QMenuBar::item {{
        background: transparent;
        padding: 6px 10px;
    }}
    QMenuBar::item:selected {{
        background-color: {menubar_hover};
    }}

    QMenu {{
        background-color: {dropdown_bg};
        color: {dropdown_text};
        border: 1px solid {dropdown_border};
        padding: 2px 0px;
    }}
    QMenu::item {{
        padding: 5px 24px 5px 16px;
    }}
    QMenu::item:selected {{
        background-color: {dropdown_hover};
    }}
    QMenu::item:disabled {{
        color: {dropdown_disabled};
    }}
    QMenu::separator {{
        height: 1px;
        background: {dropdown_separator};
        margin: 4px 8px;
    }}
    QMenu::right-arrow {{
        width: 10px;
    }}

    QPushButton {{
        background-color: transparent;
        color: {menubar_text};
        border: none;
    }}
    QPushButton:hover {{
        background-color: {menubar_hover};
    }}
    QPushButton#WinBtnClose:hover {{
        background-color: #C42B1C;
    }}

    QPushButton#TransportButton {{
        background-color: {button_bg};
        color: {button_fg};
        border-radius: 3px;
    }}
    QPushButton#TransportButton:hover {{
        background-color: {button_hover};
    }}
    QPushButton#TransportButton:pressed {{
        background-color: {button_pressed};
    }}

    QPushButton#DialogButton {{
        background-color: {button_bg};
        color: {button_fg};
        border-radius: 3px;
        padding: 5px 16px;
        min-width: 60px;
    }}
    QPushButton#DialogButton:hover {{
        background-color: {button_hover};
    }}
    QPushButton#DialogButton:pressed {{
        background-color: {button_pressed};
    }}

    QSlider::groove:horizontal {{
        height: 4px;
        background: {slider_bg};
        border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{
        background: {slider_progress};
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {slider_button};
        width: 12px;
        margin: -5px 0;
        border-radius: 6px;
    }}
    QSlider::handle:horizontal:hover {{
        background: {slider_hover};
    }}

    QToolTip {{
        background-color: {tooltip_bg};
        color: {tooltip_fg};
        border: 1px solid {border};
        padding: 4px;
    }}

    QScrollBar:vertical, QScrollBar:horizontal {{
        background: {scrollbar_track};
    }}
    QScrollBar::handle {{
        background: {scrollbar_thumb};
    }}
    QScrollBar::handle:hover {{
        background: {scrollbar_hover};
    }}

    /* dropdown_shortcut is applied per-widget (QAction shortcut text color
       isn't stylable via QSS); kept here as a documented palette key. */
    """


def apply_theme(app: QApplication, palette: dict) -> None:
    """Apply the palette app-wide. Call on startup and again on theme change."""
    app.setStyleSheet(build_stylesheet(palette))
