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
import os
import re
from typing import Optional

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QSplitter, QVBoxLayout, QWidget

from app.paths import get_resource_path
from app.state import AppState
from audio import m3u as m3u_module
from ui_qt.browser_view import BrowserViewQt
from ui_qt.controls import ControlsBarQt
from ui_qt.menu_bar import CustomMenuBarQt
from ui_qt.playlist_view import PlaylistViewQt
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

        self.state = AppState(exts=tuple(getattr(settings, "supported_extensions", ()) or ()))

        self.central_area = QWidget(self)
        self.central_area.setObjectName("CentralArea")
        central_layout = QVBoxLayout(self.central_area)
        central_layout.setContentsMargins(8, 8, 8, 8)
        central_layout.setSpacing(8)

        splitter = QSplitter(Qt.Horizontal, self.central_area)
        # QSplitterHandle's size is determined via QStyle::pixelMetric, not
        # the stylesheet box model — QSS `width` on QSplitter::handle is
        # silently ignored (confirmed empirically). setHandleWidth() is the
        # only thing that actually reserves this much layout space; the
        # handle stays visually invisible (transparent background, from
        # theme_bridge.py) until hovered, but this is what makes it a real
        # gap between the panels rather than the two touching directly.
        splitter.setHandleWidth(16)
        self.playlist_view = PlaylistViewQt(self.state, self.theme.palette, parent=splitter)
        self.browser_view = BrowserViewQt(self.state, self.settings, playlist_view=self.playlist_view, player=self.player, parent=splitter)
        splitter.addWidget(self.playlist_view)
        splitter.addWidget(self.browser_view)
        # Matches ui/main_window.py's left_frame(expand=True)/right_frame(no
        # expand): the playlist absorbs all extra width on resize, the
        # browser only changes size if the user drags the handle.
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        central_layout.addWidget(splitter, 1)

        self.playlist_view.setVisible(bool(getattr(settings, "show_playlist", True)))
        self.browser_view.setVisible(bool(getattr(settings, "show_browser", True)))

        self.controls = ControlsBarQt(self.player, self.settings, self.theme.palette, state=self.state, parent=self.central_area)
        central_layout.addWidget(self.controls)
        layout.addWidget(self.central_area, 1)

        self.playlist_view.track_activated.connect(self._play_index)
        self.controls.prev_requested.connect(self._on_prev)
        self.controls.next_requested.connect(self._on_next)
        self.controls.repeat_toggle_requested.connect(self._toggle_repeat_mode)
        self.controls.effects_requested.connect(self._on_open_audio_effects)

        self._apply_initial_geometry()

    # ---------- menu content (stub — see ui/main_window.py._build_menu for the real items) ----------

    def _build_menu(self) -> None:
        media_items = [
            {"label": "Open File...", "command": self._on_open_file, "accelerator": "Ctrl+O"},
            {"label": "Open Multiple Files...", "command": self._on_open_files, "accelerator": "Ctrl+M"},
            {"label": "Open Folder...", "command": self._on_open_folder, "accelerator": "Ctrl+F"},
            {"label": "Open Playlist (M3U/M3U8)...", "command": self._on_open_playlist, "accelerator": "Ctrl+L"},
            {"separator": True},
            {"label": "Save Playlist", "command": self._on_save_playlist, "accelerator": "Ctrl+S"},
            {"label": "Save Playlist As...", "command": self._on_save_playlist_as, "accelerator": "Ctrl+Shift+S"},
            {"separator": True},
            {"label": "Quit", "command": self._on_quit, "accelerator": "Alt+F4"},
        ]
        self.menubar.add_menu("Media", media_items)

        sort_submenu = [
            {"label": "Shuffle", "command": lambda: self.playlist_view.shuffle(), "accelerator": "Ctrl+H"},
            {"label": "Sort by Title", "command": lambda: self.playlist_view.sort_by_title(), "accelerator": "Ctrl+T"},
            {"label": "Sort by Artist", "command": lambda: self.playlist_view.sort_by_artist(), "accelerator": "Ctrl+R"},
        ]
        operations_submenu = [
            {"label": "Move Up", "command": lambda: self.playlist_view.move_up(), "accelerator": "Ctrl+Up"},
            {"label": "Move Down", "command": lambda: self.playlist_view.move_down(), "accelerator": "Ctrl+Down"},
            {"separator": True},
            {"label": "Play After Current Song", "command": lambda: self.playlist_view.play_after_current_selected(), "accelerator": "Ctrl+N"},
            {"label": "Play for time..."},
            {"separator": True},
            {"label": "Remove Selected", "command": lambda: self.playlist_view.remove_selected(), "accelerator": "Delete"},
            {"label": "Clear", "command": lambda: self.playlist_view.clear(), "accelerator": "Ctrl+C"},
            {"separator": True},
            {"label": "Track Information", "accelerator": "Ctrl+I"},
            {"label": "Show Album booklet", "accelerator": "Ctrl+B"},
        ]
        repeat_submenu = [
            {"label": "No Repeat", "radiobutton": True, "group": "repeat_mode", "checked": True, "command": lambda: self._set_repeat_mode("none")},
            {"label": "Repeat One", "radiobutton": True, "group": "repeat_mode", "checked": False, "command": lambda: self._set_repeat_mode("one")},
            {"label": "Repeat All", "radiobutton": True, "group": "repeat_mode", "checked": False, "command": lambda: self._set_repeat_mode("all")},
        ]
        playback_items = [
            {"label": "Sort", "submenu": sort_submenu},
            {"label": "Operations", "submenu": operations_submenu},
            {"label": "Repeat Mode", "submenu": repeat_submenu},
        ]
        self.menubar.add_menu("Playback", playback_items)

        view_items = [
            {"label": "Show Playback", "checkbutton": True, "checked": bool(getattr(self.settings, "show_playlist", True)), "accelerator": "F9", "command": self._toggle_playlist_visibility},
            {"label": "Show Browser", "checkbutton": True, "checked": bool(getattr(self.settings, "show_browser", True)), "accelerator": "F10", "command": self._toggle_browser_visibility},
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
            self._load_playlist([path])

    def _on_open_files(self) -> None:
        exts = getattr(self.settings, "supported_extensions", ()) or ()
        pattern = " ".join(f"*{ext}" for ext in exts) or "*"
        paths, _filter = QFileDialog.getOpenFileNames(self, "Open Multiple Files", "", f"Audio Files ({pattern})")
        if paths:
            self._load_playlist(list(paths))

    def _on_open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if not folder:
            return
        exts = tuple(getattr(self.settings, "supported_extensions", ()) or ())
        files = []
        for root, _dirs, filenames in os.walk(folder):
            for name in filenames:
                if name.lower().endswith(exts):
                    files.append(os.path.join(root, name))
        files.sort()
        self._load_playlist(files)

    def _on_open_playlist(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "Open Playlist", "", "M3U Playlist (*.m3u *.m3u8)")
        if not path:
            return
        try:
            items = m3u_module.parse_m3u(path)
        except Exception:
            logger.exception("Failed to parse M3U playlist: %s", path)
            return
        self._load_playlist(items)
        self.state.current_playlist_path = path

    def _load_playlist(self, paths) -> None:
        self.state.playlist = paths
        self.state.current_index = None
        self.playlist_view.refresh()

    def _on_save_playlist(self) -> None:
        if self.state.current_playlist_path:
            self._write_playlist(self.state.current_playlist_path)
        else:
            self._on_save_playlist_as()

    def _on_save_playlist_as(self) -> None:
        path, _filter = QFileDialog.getSaveFileName(self, "Save Playlist As", "", "M3U Playlist (*.m3u)")
        if path:
            self._write_playlist(path)

    def _write_playlist(self, path: str) -> None:
        try:
            m3u_module.write_m3u(path, self.state.playlist)
            self.state.current_playlist_path = path
        except Exception:
            logger.exception("Failed to write M3U playlist: %s", path)

    def _set_repeat_mode(self, mode: str) -> None:
        self.state.repeat_mode = mode
        self.controls.set_repeat_icon(mode)

    def _toggle_repeat_mode(self) -> None:
        """Cycle none -> one -> all -> none, matching
        ui/main_window.py's toggle_repeat_mode. The menu's radiobuttons
        aren't re-synced to match (same known cosmetic gap noted for the
        "repeat one" auto-reset in _on_track_ended) — functionally correct
        either way since state.repeat_mode is the source of truth."""
        modes = ["none", "one", "all"]
        try:
            idx = modes.index(self.state.repeat_mode)
        except ValueError:
            idx = 0
        self._set_repeat_mode(modes[(idx + 1) % len(modes)])

    def _on_prev(self) -> None:
        if self.state.current_index is None:
            return
        if self.state.current_index - 1 >= 0:
            self._play_index(self.state.current_index - 1)

    def _on_next(self) -> None:
        if self.state.current_index is None:
            return
        if self.state.current_index + 1 < len(self.state.playlist):
            self._play_index(self.state.current_index + 1)

    def _on_open_audio_effects(self) -> None:
        logger.info("[ui_qt stub] Audio Effects window not ported yet")

    def _play_index(self, index: int) -> None:
        if not (0 <= index < len(self.state.playlist)):
            return
        self.state.current_index = index
        self.controls.play_file(self.state.playlist[index])
        self.playlist_view.refresh_highlight()

    def _on_track_ended(self) -> None:
        """Connected to PlayerBridge.track_ended (see main_qt.py) in place
        of controls.on_track_ended directly, now that there's a playlist to
        advance through. Ports ui/main_window.py's handle_track_end's
        repeat-mode branching; advancing calls _play_index directly rather
        than the full stop/reset path so moving between tracks doesn't
        visibly flash to a stopped state."""
        if self.state.current_index is None or not self.state.playlist:
            self.controls.on_track_ended()
            return

        repeat_mode = getattr(self.state, "repeat_mode", "none")
        if repeat_mode == "one":
            self._play_index(self.state.current_index)
            self._set_repeat_mode("none")
        elif repeat_mode == "all":
            next_index = self.state.current_index + 1
            if next_index >= len(self.state.playlist):
                next_index = 0
            self._play_index(next_index)
        else:
            next_index = self.state.current_index + 1
            if next_index < len(self.state.playlist):
                self._play_index(next_index)
            else:
                self.controls.on_track_ended()

    def _toggle_playlist_visibility(self) -> None:
        visible = not self.playlist_view.isVisible()
        self.playlist_view.setVisible(visible)
        self.settings.show_playlist = visible
        self._save_settings_safe()

    def _toggle_browser_visibility(self) -> None:
        visible = not self.browser_view.isVisible()
        self.browser_view.setVisible(visible)
        self.settings.show_browser = visible
        self._save_settings_safe()

    def _save_settings_safe(self) -> None:
        try:
            self.settings.save()
        except Exception:
            logger.exception("Failed to save settings")

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
        self.playlist_view.apply_palette(palette)

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
        try:
            self.browser_view.shutdown()
        except Exception:
            logger.exception("Failed to shut down browser preview player on close")
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
