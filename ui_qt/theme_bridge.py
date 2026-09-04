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
    accent = palette.get("accent", "#BB86FC")

    slider_bg = palette.get("slider_bg", "#404040")
    slider_progress = palette.get("slider_progress", "#BB86FC")
    slider_button = palette.get("slider_button", "#BB86FC")
    slider_hover = palette.get("slider_hover", "#985EFF")

    tree_bg = palette.get("tree_bg", "#252526")
    tree_header = palette.get("tree_header", bg)
    select_bg = palette.get("select_bg", "#3E3E3E")
    select_fg = palette.get("select_fg", fg)
    hover_bg = palette.get("hover_bg", "#2A2A2A")
    striped_bg = palette.get("striped_bg", tree_bg)

    entry_bg = palette.get("entry_bg", "#2A2A2A")
    fg_dim = palette.get("fg_dim", "#888888")

    status_bg = palette.get("status_bg", "#E8E8E8")
    status_border = palette.get("status_border", "#D0D0D0")

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

    QFrame#StatusPanel, QFrame#DJPanel {{
        background-color: {status_bg};
        border: 1px solid {status_border};
        border-radius: 6px;
    }}

    QWidget#DJButtonRow {{
        background: transparent;
    }}

    QFrame#BookletImagePanel {{
        background-color: {tree_bg};
        border: 1px solid {border};
        border-radius: 4px;
    }}

    QTabWidget::pane {{
        border: 1px solid {border};
        border-radius: 4px;
        background-color: {bg};
    }}
    QTabBar::tab {{
        background-color: {dropdown_bg};
        color: {dropdown_text};
        padding: 6px 14px;
        border: 1px solid {dropdown_border};
        border-bottom: none;
    }}
    QTabBar::tab:selected {{
        background-color: {accent};
        color: #ffffff;
    }}
    QTabBar::tab:hover {{
        background-color: {button_hover};
        color: {fg};
    }}

    QLabel#SectionHeader {{
        color: {fg};
        font-weight: bold;
        background: transparent;
    }}

    QGroupBox {{
        color: {fg};
        border: 1px solid {border};
        border-radius: 6px;
        margin-top: 10px;
        padding-top: 12px;
        font-weight: bold;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 10px;
        padding: 0 4px;
    }}

    QWidget#MiniPlayerWindow {{
        background-color: {bg};
        border: 1px solid {border};
    }}
    #MiniPlayerTitle {{
        color: {fg};
        font-weight: 600;
        font-size: 12pt;
        background: transparent;
    }}
    QLabel#MiniPlayerSubtitle {{
        color: {fg_dim};
        font-size: 9pt;
        background: transparent;
    }}
    QProgressBar#MiniPlayerProgress {{
        background-color: {scrollbar_track};
        border: none;
        border-radius: 2px;
    }}
    QProgressBar#MiniPlayerProgress::chunk {{
        background-color: {accent};
        border-radius: 2px;
    }}

    QPushButton#MiniPlayerWinBtn {{
        background-color: transparent;
        color: {fg_dim};
        border: none;
        border-radius: 10px;
        font-size: 9pt;
    }}
    QPushButton#MiniPlayerWinBtn:hover {{
        background-color: {hover_bg};
        color: {fg};
    }}
    QWidget#MiniPlayerWindow QPushButton#WinBtnClose {{
        background-color: transparent;
        color: {fg_dim};
        border: none;
        border-radius: 10px;
        font-size: 9pt;
    }}
    QWidget#MiniPlayerWindow QPushButton#WinBtnClose:hover {{
        color: #ffffff;
    }}

    QPushButton#MiniPlayButton {{
        background-color: {button_bg};
        color: {button_fg};
        border: none;
        border-radius: 24px;
        font-size: 14pt;
    }}
    QPushButton#MiniPlayButton:hover {{
        background-color: {button_hover};
    }}
    QPushButton#MiniPlayButton:pressed {{
        background-color: {button_pressed};
    }}

    QPushButton#MiniSecondaryButton {{
        background-color: transparent;
        color: {fg};
        border: none;
        border-radius: 17px;
        font-size: 11pt;
    }}
    QPushButton#MiniSecondaryButton:hover {{
        background-color: {hover_bg};
    }}
    QPushButton#MiniSecondaryButton:pressed {{
        background-color: {select_bg};
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
        border-radius: 8px;
        font-size: 13pt;
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
        border-radius: 8px;
        padding: 5px 16px;
        min-width: 60px;
        min-height: 32px;
    }}
    QPushButton#DialogButton:hover {{
        background-color: {button_hover};
    }}
    QPushButton#DialogButton:pressed {{
        background-color: {button_pressed};
    }}

    QPushButton#BrowserActionButton {{
        background-color: {button_bg};
        color: {button_fg};
        border-radius: 8px;
        padding: 4px 10px;
        min-width: 100px;
        min-height: 28px;
    }}
    QPushButton#BrowserActionButton:hover {{
        background-color: {button_hover};
    }}
    QPushButton#BrowserActionButton:pressed {{
        background-color: {button_pressed};
    }}

    QPushButton#CompactButton {{
        background-color: {button_bg};
        color: {button_fg};
        border-radius: 6px;
        padding: 2px 6px;
        min-width: 56px;
        min-height: 22px;
        font-size: 9pt;
    }}
    QPushButton#CompactButton:hover {{
        background-color: {button_hover};
    }}
    QPushButton#CompactButton:pressed {{
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

    QLabel#PanelHeader {{
        color: {fg};
        font-size: 18pt;
        font-weight: bold;
        background: transparent;
    }}

    QLineEdit#SearchEntry {{
        background-color: {entry_bg};
        color: {fg};
        border: none;
        border-radius: 4px;
        padding: 5px 8px;
    }}
    QLabel#SearchIcon {{
        color: {fg_dim};
        background: transparent;
    }}

    QComboBox {{
        background-color: {entry_bg};
        color: {fg};
        border: 1px solid {border};
        border-radius: 4px;
        padding: 4px 8px;
    }}
    QComboBox:disabled {{
        color: {fg_dim};
    }}
    QComboBox::drop-down {{
        border: none;
    }}
    QComboBox QAbstractItemView {{
        background-color: {dropdown_bg};
        color: {dropdown_text};
        selection-background-color: {dropdown_hover};
        outline: 0;
    }}

    QScrollBar:vertical {{
        background: {scrollbar_track};
        width: 10px;
        margin: 0;
    }}
    QScrollBar:horizontal {{
        background: {scrollbar_track};
        height: 10px;
        margin: 0;
    }}
    QScrollBar::handle {{
        background: {scrollbar_thumb};
        border-radius: 4px;
    }}
    QScrollBar::handle:hover {{
        background: {scrollbar_hover};
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        height: 0;
        width: 0;
        border: none;
        background: none;
    }}
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: none;
    }}

    QTreeWidget {{
        background-color: {tree_bg};
        alternate-background-color: {striped_bg};
        color: {fg};
        border: 1px solid {border};
        border-radius: 4px;
        outline: 0;
        font-size: 10pt;
    }}
    
    QTreeWidget#PlaylistTree {{
        background-color: {bg};
        border: none;
        border-radius: 0;
    }}
    QTreeWidget::item {{
        padding: 7px 6px;
    }}
    
    QTreeWidget::item:hover {{
        background-color: {hover_bg};
    }}
    QTreeWidget::item:selected {{
        background-color: {select_bg};
        color: {select_fg};
    }}
    QTreeWidget::branch {{
        background-color: transparent;
    }}
    QHeaderView::section {{
        background-color: {tree_header};
        color: {fg};
        padding: 7px 6px;
        border: none;
        border-bottom: 2px solid {border};
        font-weight: bold;
        font-size: 10pt;
    }}

    QSplitter::handle {{
        background-color: transparent;
    }}
    QSplitter::handle:hover {{
        background-color: {menubar_hover};
    }}

    
    """


def apply_theme(app: QApplication, palette: dict) -> None:
    """Apply the palette app-wide. Call on startup and again on theme change."""
    app.setStyleSheet(build_stylesheet(palette))
