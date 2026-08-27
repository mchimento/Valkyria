"""
Qt port of ui/main_window.py — Phase 1 (window chrome/menu) + Phase 2
(waveform + playback controls, wired to the real AudioPlayer).

Browser/playlist, DJ view, status bar and all secondary dialogs are NOT
here yet — see the ui_qt migration plan for what comes next.

Reuses the real app.settings.Settings and themes.theme_manager.ThemeManager
as-is: only Settings' plain fields and ThemeManager's .palette/.reload() are
touched. ThemeManager.apply_to() is Tk-specific and is never called here.
"""

import logging
import re
from typing import Optional

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QVBoxLayout, QWidget

from app.paths import get_resource_path
from ui_qt.controls import ControlsBarQt
from ui_qt.menu_bar import CustomMenuBarQt
from ui_qt.preferences_window import PreferencesWindowQt
from ui_qt.theme_bridge import apply_theme

logger = logging.getLogger(__name__)

RESIZE_MARGIN = 6  # px from window edge that count as a resize zone
DEFAULT_SIZE = (1280, 800)

_GEOMETRY_RE = re.compile(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$")


class MainWindowQt(QWidget):
    def __init__(self, settings, theme, player, theme_signal):
        super().__init__()
        self.settings = settings
        self.theme = theme
        self.player = player
        self.theme_signal = theme_signal
        self._preferences_win: Optional[PreferencesWindowQt] = None
        theme_signal.changed.connect(self._on_theme_changed)

        self.setObjectName("MainWindow")
        self.setWindowTitle("Valkyria")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowIcon(QIcon(str(get_resource_path("assets/app-icon.ico"))))
        self.setMouseTracking(True)

        self._resize_edges = Qt.Edges()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)  # leaves room for the 1px QSS border
        layout.setSpacing(0)

        self.menubar = CustomMenuBarQt(self, self.theme.palette, parent_window=self)
        layout.addWidget(self.menubar)
        self._build_menu()
        self.menubar.setup_window_controls(self._on_quit, show_maximize=True)

        self.central_area = QWidget(self)
        self.central_area.setObjectName("CentralArea")
        central_layout = QVBoxLayout(self.central_area)
        central_layout.addStretch(1)  # browser/playlist/DJ view land here in later phases
        self.controls = ControlsBarQt(self.player, self.settings, self.theme.palette, parent=self.central_area)
        central_layout.addWidget(self.controls)
        layout.addWidget(self.central_area, 1)

        self._apply_initial_geometry()

    # ---------- menu content (stub — see ui/main_window.py._build_menu for the real items) ----------

    def _build_menu(self) -> None:
        media_items = [
            {"label": "Open File...", "command": self._on_open_file, "accelerator": "Ctrl+O"},
            {"label": "Open Multiple Files...", "accelerator": "Ctrl+M"},
            {"label": "Open Folder...", "accelerator": "Ctrl+F"},
            {"label": "Open Playlist (M3U/M3U8)...", "accelerator": "Ctrl+L"},
            {"separator": True},
            {"label": "Save Playlist", "accelerator": "Ctrl+S"},
            {"label": "Save Playlist As...", "accelerator": "Ctrl+Shift+S"},
            {"separator": True},
            {"label": "Quit", "command": self._on_quit, "accelerator": "Alt+F4"},
        ]
        self.menubar.add_menu("Media", media_items)

        sort_submenu = [
            {"label": "Shuffle", "accelerator": "Ctrl+H"},
            {"label": "Sort by Title", "accelerator": "Ctrl+T"},
            {"label": "Sort by Artist", "accelerator": "Ctrl+R"},
        ]
        operations_submenu = [
            {"label": "Move Up", "accelerator": "Ctrl+Up"},
            {"label": "Move Down", "accelerator": "Ctrl+Down"},
            {"separator": True},
            {"label": "Play After Current Song", "accelerator": "Ctrl+N"},
            {"label": "Play for time..."},
            {"separator": True},
            {"label": "Remove Selected", "accelerator": "Delete"},
            {"label": "Clear", "accelerator": "Ctrl+C"},
            {"separator": True},
            {"label": "Track Information", "accelerator": "Ctrl+I"},
            {"label": "Show Album booklet", "accelerator": "Ctrl+B"},
        ]
        repeat_submenu = [
            {"label": "No Repeat", "radiobutton": True, "group": "repeat_mode", "checked": True},
            {"label": "Repeat One", "radiobutton": True, "group": "repeat_mode", "checked": False},
            {"label": "Repeat All", "radiobutton": True, "group": "repeat_mode", "checked": False},
        ]
        playback_items = [
            {"label": "Sort", "submenu": sort_submenu},
            {"label": "Operations", "submenu": operations_submenu},
            {"label": "Repeat Mode", "submenu": repeat_submenu},
        ]
        self.menubar.add_menu("Playback", playback_items)

        view_items = [
            {"label": "Show Playback", "checkbutton": True, "checked": bool(getattr(self.settings, "show_playlist", True)), "accelerator": "F9"},
            {"label": "Show Browser", "checkbutton": True, "checked": bool(getattr(self.settings, "show_browser", True)), "accelerator": "F10"},
            {"label": "Show Live Audio Analysis", "checkbutton": True, "checked": bool(getattr(self.settings, "show_dj", True)), "accelerator": "F11"},
            {"separator": True},
            {"label": "Always on Top", "checkbutton": True, "checked": False},
        ]
        self.menubar.add_menu("View", view_items)

        tools_items = [
            {"label": "Audio Device", "submenu": []},
            {"label": "Audio Effects and Filters", "accelerator": "F7"},
            {"label": "Playback features", "accelerator": "F8"},
            {"separator": True},
            {"label": "Playlist Generator", "accelerator": "F6"},
            {"separator": True},
            {"label": "Preferences", "command": self._on_open_preferences, "accelerator": "Ctrl+P"},
        ]
        self.menubar.add_menu("Tools", tools_items)

        documentation_submenu = [
            {"label": "User Guide"},
            {"label": "BPM Analysis"},
        ]
        help_items = [
            {"label": "Documentation", "submenu": documentation_submenu},
            {"separator": True},
            {"label": "About", "accelerator": "F1"},
        ]
        self.menubar.add_menu("Help", help_items)

    def _on_open_file(self) -> None:
        exts = getattr(self.settings, "supported_extensions", ()) or ()
        pattern = " ".join(f"*{ext}" for ext in exts) or "*"
        path, _ = QFileDialog.getOpenFileName(self, "Open File", "", f"Audio Files ({pattern})")
        if path:
            self.controls.play_file(path)

    def _on_open_preferences(self) -> None:
        if self._preferences_win is not None:
            self._preferences_win.show()
            self._preferences_win.raise_()
            self._preferences_win.activateWindow()
            return
        win = PreferencesWindowQt(self, self.settings, self.theme, self.theme_signal)
        win.finished.connect(lambda _: setattr(self, "_preferences_win", None))
        self._preferences_win = win
        win.show()

    def _on_theme_changed(self, palette: dict) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, palette)
        self.controls.apply_palette(palette)

    # ---------- geometry persistence ----------

    def _apply_initial_geometry(self) -> None:
        saved = getattr(self.settings, "window_geometry_qt", None)
        if saved:
            match = _GEOMETRY_RE.match(saved)
            if match:
                w, h, x, y = (int(v) for v in match.groups())
                self.setGeometry(x, y, w, h)
                return
        w, h = DEFAULT_SIZE
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            x = avail.x() + (avail.width() - w) // 2
            y = avail.y() + (avail.height() - h) // 2
        else:
            x, y = 100, 100
        self.setGeometry(x, y, w, h)

    def _save_geometry(self) -> None:
        g = self.geometry()
        self.settings.window_geometry_qt = f"{g.width()}x{g.height()}+{g.x()}+{g.y()}"

    # ---------- window lifecycle ----------

    def _on_quit(self) -> None:
        self.close()

    def closeEvent(self, event) -> None:
        try:
            self.player.stop()
        except Exception:
            logger.exception("Failed to stop player on close")
        self._save_geometry()
        try:
            self.settings.save()
        except Exception:
            logger.exception("Failed to save settings on close")
        super().closeEvent(event)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.WindowStateChange:
            self.menubar.sync_maximize_button()
        super().changeEvent(event)

    # ---------- native edge/corner resize ----------

    def _edge_at(self, pos) -> Qt.Edges:
        edges = Qt.Edges()
        if pos.x() <= RESIZE_MARGIN:
            edges |= Qt.LeftEdge
        elif pos.x() >= self.width() - RESIZE_MARGIN:
            edges |= Qt.RightEdge
        if pos.y() <= RESIZE_MARGIN:
            edges |= Qt.TopEdge
        elif pos.y() >= self.height() - RESIZE_MARGIN:
            edges |= Qt.BottomEdge
        return edges

    def mouseMoveEvent(self, event) -> None:
        if self.windowState() & Qt.WindowMaximized:
            super().mouseMoveEvent(event)
            return
        edges = self._edge_at(event.position().toPoint())
        self.setCursor(_cursor_for_edges(edges))
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and not (self.windowState() & Qt.WindowMaximized):
            edges = self._edge_at(event.position().toPoint())
            if edges:
                handle = self.windowHandle()
                if handle is not None:
                    handle.startSystemResize(edges)
                    return
        super().mousePressEvent(event)


def _cursor_for_edges(edges: Qt.Edges):
    horiz = bool(edges & (Qt.LeftEdge | Qt.RightEdge))
    vert = bool(edges & (Qt.TopEdge | Qt.BottomEdge))
    diag_nw_se = (edges & Qt.LeftEdge and edges & Qt.TopEdge) or (edges & Qt.RightEdge and edges & Qt.BottomEdge)
    diag_ne_sw = (edges & Qt.RightEdge and edges & Qt.TopEdge) or (edges & Qt.LeftEdge and edges & Qt.BottomEdge)
    if diag_nw_se:
        return Qt.SizeFDiagCursor
    if diag_ne_sw:
        return Qt.SizeBDiagCursor
    if horiz:
        return Qt.SizeHorCursor
    if vert:
        return Qt.SizeVerCursor
    return Qt.ArrowCursor
