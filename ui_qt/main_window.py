"""
Main application window: chrome/menu, waveform + playback controls,
browser/playlist, DJ view, status bar, and secondary dialogs.
"""

import logging
import os
import re
import threading
import time
from typing import Optional

from PySide6.QtCore import Qt, QEvent, QTimer, Signal
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QMessageBox, QSplitter, QVBoxLayout, QWidget

from app.documentation_view import open_documentation as open_doc_in_browser
from app.paths import get_generator_templates_path, get_resource_path
from app.state import AppState
from audio import m3u as m3u_module
from audio.audio_player import filter_selectable_audio_devices
from audio.bpm import analysis_manager
from audio.metadata import metadata_extractor
from ui_qt.about_window import AboutWindowQt
from ui_qt.audio_effects_window import AudioEffectsWindowQt
from ui_qt.booklet_viewer_window import BookletViewerWindowQt
from ui_qt.browser_view import BrowserViewQt
from ui_qt.controls import ControlsBarQt
from ui_qt.dj_view import DJViewQt
from ui_qt.media_info_window import MediaInfoWindowQt
from ui_qt.menu_bar import CustomMenuBarQt
from ui_qt.mini_player_window import MiniPlayerWindowQt
from ui_qt.playback_features_window import PlaybackFeaturesWindowQt
from ui_qt.playlist_generator_window import PlaylistGeneratorWindowQt
from ui_qt.playlist_view import PlaylistViewQt
from ui_qt.preferences_window import PreferencesWindowQt
from ui_qt.status_view import StatusViewQt
from ui_qt.theme_bridge import apply_theme
from ui_qt.time_limit_dialog import TimeLimitDialogQt

logger = logging.getLogger(__name__)

RESIZE_MARGIN = 6  # px from window edge that count as a resize zone
DEFAULT_SIZE = (1280, 800)
MIN_SIZE = (640, 480)

_GEOMETRY_RE = re.compile(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$")


class MainWindowQt(QWidget):
    _track_switch_ready = Signal(int)

    def __init__(self, settings, theme, player, theme_signal):
        super().__init__()
        self.settings = settings
        self.theme = theme
        self.player = player
        self.theme_signal = theme_signal
        self._current_palette: dict = theme.palette
        self._preferences_win: Optional[PreferencesWindowQt] = None
        self._playback_features_win: Optional[PlaybackFeaturesWindowQt] = None
        self._audio_effects_win: Optional[AudioEffectsWindowQt] = None
        self._playlist_generator_win: Optional[PlaylistGeneratorWindowQt] = None
        self.mini_player: Optional[MiniPlayerWindowQt] = None
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

        self._action_save_playlist = self._find_action(self.menubar._menus["&Media"], "Save Playlist")
        self._action_save_playlist_as = self._find_action(self.menubar._menus["&Media"], "Save Playlist As...")
        self._action_play_after_current = self._find_action(self.menubar._menus["&Playback"], "Play After Current Song")
        self._action_track_info = self._find_action(self.menubar._menus["&Playback"], "Track Information")
        self._action_track_booklet = self._find_action(self.menubar._menus["&Playback"], "Show Album Booklet")
        self._track_info_windows = []
        self._track_booklet_windows = []

        self.state = AppState(exts=tuple(getattr(settings, "supported_extensions", ()) or ()))
        self.state.play_on_double = bool(getattr(settings, "play_on_double", True))
        self.state.crossfade_enabled = bool(getattr(settings, "crossfade_enabled", False))
        self.state.crossfade_duration = int(getattr(settings, "crossfade_duration", 5))
        self.state.silence_detection_enabled = bool(getattr(settings, "silence_detection_enabled", False))

        self.central_area = QWidget(self)
        self.central_area.setObjectName("CentralArea")
        central_layout = QVBoxLayout(self.central_area)
        central_layout.setContentsMargins(8, 8, 8, 8)
        central_layout.setSpacing(8)

        splitter = QSplitter(Qt.Horizontal, self.central_area)
        splitter.setHandleWidth(16)
        self.playlist_view = PlaylistViewQt(self.state, self.theme.palette, player=self.player, parent=splitter)
        self.browser_view = BrowserViewQt(
            self.state, self.settings, playlist_view=self.playlist_view, player=self.player, parent=splitter,
            palette=self.theme.palette,
        )
        splitter.addWidget(self.playlist_view)
        splitter.addWidget(self.browser_view)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        central_layout.addWidget(splitter, 1)

        self.playlist_view.setVisible(bool(getattr(settings, "show_playlist", True)))
        self.browser_view.setVisible(bool(getattr(settings, "show_browser", True)))

        self.controls = ControlsBarQt(self.player, self.settings, self.theme.palette, state=self.state, parent=self.central_area)
        central_layout.addWidget(self.controls)

        self.bottom_info_bar = QWidget(self.central_area)
        bottom_layout = QHBoxLayout(self.bottom_info_bar)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        self.status_view = StatusViewQt(self.state, self.theme, self.settings, parent=self.bottom_info_bar)
        self.dj_view = DJViewQt(self.state, self.theme, self.settings, self.player, parent=self.bottom_info_bar)
        bottom_layout.addWidget(self.status_view, 1)
        bottom_layout.addWidget(self.dj_view, 0)
        central_layout.addWidget(self.bottom_info_bar)
        show_dj = bool(getattr(settings, "show_dj", True))
        self.dj_view.setVisible(show_dj)
        if not show_dj:
            self.player.set_audio_metrics_callback(None)

        layout.addWidget(self.central_area, 1)

        self.playlist_view.track_activated.connect(self._play_index)
        self.controls.play_requested.connect(self._on_play_requested)
        self.controls.prev_requested.connect(self._on_prev)
        self.controls.next_requested.connect(self._on_next)
        self.controls.repeat_toggle_requested.connect(self._toggle_repeat_mode)
        self.controls.effects_requested.connect(self._on_open_audio_effects)
        self.controls.stopped.connect(self._on_stopped)
        self.controls.crossfade_requested.connect(self._on_track_ended)
        self.controls.time_limit_reached.connect(self._on_track_ended)
        self.controls.paused_state_changed.connect(self._on_pause_toggled)
        self._track_switch_ready.connect(self._play_index, Qt.QueuedConnection)
        self.playlist_view.playlist_changed.connect(self._update_menu_state)
        self.playlist_view.selection_changed.connect(self._update_menu_state)
        self.playlist_view.show_track_info_requested.connect(lambda i: self._open_track_info(self.state.playlist[i]))
        self.playlist_view.show_booklet_requested.connect(lambda i: self._open_booklet(self.state.playlist[i]))
        self.playlist_view.set_time_limit_requested.connect(self._set_time_limit)
        self.playlist_view.clear_time_limit_requested.connect(self._clear_time_limit)
        self.playlist_view.playback_stopped.connect(self.controls.stopped)
        self._update_menu_state()

        self._bind_transport_shortcuts()
        self._apply_initial_geometry()

    # ---------- keyboard shortcuts ----------

    def _bind_transport_shortcuts(self) -> None:
        """QShortcut with the default Qt.WindowShortcut context fires
        whenever this top-level window has focus, regardless of which
        child widget inside it does — same mechanism the menu bar's own
        QAction shortcuts already use.
        """

        def shortcut(key: str, slot) -> None:
            QShortcut(QKeySequence(key), self, activated=slot)

        shortcut("Return", self.controls.btn_play.click)
        shortcut("Enter", self.controls.btn_play.click)  # numpad Enter
        shortcut("Space", self.controls.btn_pause.click)
        shortcut("Left", self._on_prev)
        shortcut("Right", self._on_next)
        shortcut("S", self.controls.btn_stop.click)
        shortcut("M", self.controls.btn_mute.click)
        shortcut("+", lambda: self.controls.step_volume(5))
        shortcut("-", lambda: self.controls.step_volume(-5))

    # ---------- menu content ----------

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
        self.menubar.add_menu("&Media", media_items)

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
            {"label": "Play for time...", "command": self._on_play_for_time_menu},
            {"separator": True},
            {"label": "Remove Selected", "command": lambda: self.playlist_view.remove_selected(), "accelerator": "Delete"},
            {"label": "Clear", "command": lambda: self.playlist_view.clear(), "accelerator": "Ctrl+C"},
            {"separator": True},
            {"label": "Track Information", "command": self._on_open_track_info, "accelerator": "Ctrl+I"},
            {"label": "Show Album Booklet", "command": self._on_open_booklet, "accelerator": "Ctrl+B"},
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
        self.menubar.add_menu("&Playback", playback_items)

        view_items = [
            {"label": "Show Playback", "checkbutton": True, "checked": bool(getattr(self.settings, "show_playlist", True)), "accelerator": "F9", "command": self._toggle_playlist_visibility},
            {"label": "Show Browser", "checkbutton": True, "checked": bool(getattr(self.settings, "show_browser", True)), "accelerator": "F10", "command": self._toggle_browser_visibility},
            {"label": "Show Live Audio Analysis", "checkbutton": True, "checked": bool(getattr(self.settings, "show_dj", True)), "accelerator": "F11", "command": self._toggle_dj_visibility},
        ]
        self.menubar.add_menu("&View", view_items)

        tools_items = [
            {"label": "Audio Device", "submenu": self._build_audio_device_items()},
            {"label": "Audio Effects and Filters", "command": self._on_open_audio_effects, "accelerator": "F7"},
            {"label": "Playback features", "command": self._on_open_playback_features, "accelerator": "F8"},
            {"separator": True},
            {"label": "Playlist Generator", "command": self._on_open_playlist_generator, "accelerator": "F6"},
            {"separator": True},
            {"label": "Preferences", "command": self._on_open_preferences, "accelerator": "Ctrl+P"},
        ]
        self.menubar.add_menu("&Tools", tools_items)

        documentation_submenu = [
            {"label": "User Guide", "command": lambda: self._open_documentation("user_guide.md")},
            {"label": "BPM Analysis", "command": lambda: self._open_documentation("bpm_analysis.md")},
        ]
        help_items = [
            {"label": "Documentation", "submenu": documentation_submenu},
            {"separator": True},
            {"label": "About", "command": self._on_open_about, "accelerator": "F1"},
        ]
        self.menubar.add_menu("&Help", help_items)

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
        path, _filter = QFileDialog.getSaveFileName(
            self, "Save Playlist As", "", "M3U8 Playlist (*.m3u8);;M3U Playlist (*.m3u)"
        )
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".m3u8"
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
        """Cycle none -> one -> all -> none. The menu's radiobuttons
        aren't re-synced to match — functionally correct either way since
        state.repeat_mode is the source of truth."""
        modes = ["none", "one", "all"]
        try:
            idx = modes.index(self.state.repeat_mode)
        except ValueError:
            idx = 0
        self._set_repeat_mode(modes[(idx + 1) % len(modes)])

    def _on_play_requested(self) -> None:
        """The Play button/Enter plays whatever's currently selected in the
        playlist — falling back to index 0 only if nothing has ever played
        yet, or to just restarting whatever's already at
        state.current_index if there's no selection and something was
        already playing/loaded."""
        selected = self.playlist_view.get_selected_indices()
        if selected:
            self.state.current_index = selected[0]
        elif self.state.playlist and self.state.current_index is None:
            self.state.current_index = 0
        if self.state.current_index is not None:
            self._play_index(self.state.current_index)

    def _on_prev(self) -> None:
        if self.state.current_index is None:
            return
        if self.state.current_index - 1 >= 0:
            self._fade_then_play(self.state.current_index - 1)

    def _on_next(self) -> None:
        if self.state.current_index is None:
            return
        if self.state.current_index + 1 < len(self.state.playlist):
            self._fade_then_play(self.state.current_index + 1)

    def _fade_then_play(self, index: int) -> None:
        """Trigger a fade-out and wait for it before switching tracks —
        same sequence ControlsBarQt._on_stop already uses for Stop."""
        def _sequence():
            try:
                wait = self.player.trigger_fade_out()
            except Exception:
                wait = 0
            if wait and wait > 0:
                time.sleep(wait)
            self._track_switch_ready.emit(index)

        threading.Thread(target=_sequence, daemon=True).start()

    def _on_stopped(self) -> None:
        self.state.current_index = None
        self.playlist_view.refresh_highlight()
        self._update_menu_state()
        self.status_view._stop_time_limit_updates()
        self.status_view.handle_stop()
        self.dj_view._clear_info()

    def _on_pause_toggled(self, is_paused: bool) -> None:
        if is_paused:
            self.status_view._stop_time_limit_updates()
            return
        idx = self.state.current_index
        if idx is not None and idx < len(self.state.playlist) and self.state.playlist[idx] in self.state.play_limits:
            self.status_view._start_time_limit_updates(self.controls)

    def _find_action(self, menu, label: str):
        for action in menu.actions():
            if action.text() == label:
                return action
            if action.menu() is not None:
                found = self._find_action(action.menu(), label)
                if found is not None:
                    return found
        return None

    def _update_menu_state(self) -> None:
        has_songs = bool(self.state.playlist)
        if self._action_save_playlist is not None:
            self._action_save_playlist.setEnabled(has_songs)
        if self._action_save_playlist_as is not None:
            self._action_save_playlist_as.setEnabled(has_songs)
        if self._action_play_after_current is not None:
            self._action_play_after_current.setEnabled(has_songs and self.state.current_index is not None)
        has_target = self._resolve_track_target_index() is not None
        if self._action_track_info is not None:
            self._action_track_info.setEnabled(has_target)
        if self._action_track_booklet is not None:
            self._action_track_booklet.setEnabled(has_target)

    def _resolve_track_target_index(self):
        selected = self.playlist_view.get_selected_indices()
        if selected:
            return selected[0]
        return self.state.current_index

    def _on_open_track_info(self) -> None:
        index = self._resolve_track_target_index()
        if index is None or not (0 <= index < len(self.state.playlist)):
            QMessageBox.information(self, "No Track Selected", "No track is selected")
            return
        self._open_track_info(self.state.playlist[index])

    def _on_open_booklet(self) -> None:
        index = self._resolve_track_target_index()
        if index is None or not (0 <= index < len(self.state.playlist)):
            QMessageBox.information(self, "No Track Selected", "No track is selected")
            return
        self._open_booklet(self.state.playlist[index])

    def _open_track_info(self, filepath: str) -> None:
        win = MediaInfoWindowQt(self, filepath, self._current_palette, metadata_saved_callback=self._on_metadata_saved)
        self._track_info_windows.append(win)
        win.finished.connect(lambda _: self._track_info_windows.remove(win) if win in self._track_info_windows else None)
        win.show()

    def _open_booklet(self, filepath: str) -> None:
        win = BookletViewerWindowQt(self, filepath, self._current_palette)
        self._track_booklet_windows.append(win)
        win.finished.connect(lambda _: self._track_booklet_windows.remove(win) if win in self._track_booklet_windows else None)
        win.show()

    def _on_play_for_time_menu(self) -> None:
        index = self._resolve_track_target_index()
        if index is None or not (0 <= index < len(self.state.playlist)):
            QMessageBox.information(self, "No Track Selected", "No track is selected")
            return
        self._set_time_limit(index)

    def _set_time_limit(self, index: int) -> None:
        if not (0 <= index < len(self.state.playlist)):
            return
        filepath = self.state.playlist[index]
        current = self.state.play_limits.get(filepath)
        dialog = TimeLimitDialogQt(self, current)
        dialog.exec()
        result = dialog.result
        if result == "CANCEL":
            return
        is_current = self.state.current_index == index
        if result is None:
            self.state.play_limits.pop(filepath, None)
            self.status_view.set_temporary_status("Playback time limit cleared")
            if is_current:
                self.status_view._stop_time_limit_updates()
        else:
            self.state.play_limits[filepath] = result
            self.status_view.set_temporary_status(f"Playback time limit set to {int(result)}s")
            if is_current:
                self.status_view._start_time_limit_updates(self.controls)
        self.playlist_view.refresh_time_limit_display(index)

    def _clear_time_limit(self, index: int) -> None:
        if not (0 <= index < len(self.state.playlist)):
            return
        filepath = self.state.playlist[index]
        if filepath in self.state.play_limits:
            del self.state.play_limits[filepath]
            self.status_view.set_temporary_status("Playback time limit cleared")
            if self.state.current_index == index:
                self.status_view._stop_time_limit_updates()
            self.playlist_view.refresh_time_limit_display(index)

    def _on_metadata_saved(self, filepath: str) -> None:
        try:
            metadata_extractor.update_cache(filepath)
        except Exception:
            logger.exception("Failed to update metadata cache after save")
        self.playlist_view.refresh()
        idx = self.state.current_index
        if idx is not None and 0 <= idx < len(self.state.playlist) and self.state.playlist[idx] == filepath:
            self.status_view.restore_status()
            self.dj_view.update_info()

    def _on_open_audio_effects(self) -> None:
        if self._audio_effects_win is not None:
            self._audio_effects_win.show()
            self._audio_effects_win.raise_()
            self._audio_effects_win.activateWindow()
            return
        win = AudioEffectsWindowQt(self, self.player, self._current_palette, self.theme_signal)
        win.finished.connect(lambda _: setattr(self, "_audio_effects_win", None))
        self._audio_effects_win = win
        win.show()

    def _on_open_about(self) -> None:
        win = AboutWindowQt(self, self._current_palette)
        win.show()

    def _play_index(self, index: int) -> None:
        if not (0 <= index < len(self.state.playlist)):
            return
        self.state.current_index = index
        self.controls.play_file(self.state.playlist[index])
        self.playlist_view.refresh_highlight()
        self._update_menu_state()
        self.status_view.restore_status()
        self.dj_view.update_info()
        if self.state.playlist[index] in self.state.play_limits:
            self.status_view._start_time_limit_updates(self.controls)

    def _on_track_ended(self) -> None:
        """Connected to PlayerBridge.track_ended (see main.py). Advancing
        calls _play_index directly rather than the full stop/reset path so
        moving between tracks doesn't visibly flash to a stopped state."""
        if self.state.current_index is None or not self.state.playlist:
            self.controls.on_track_ended()
            return

        repeat_mode = getattr(self.state, "repeat_mode", "none")
        if repeat_mode == "one":
            self._play_index(self.state.current_index)
            self._set_repeat_mode("none")
            self.status_view.schedule_restore(3000)
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

    def _toggle_dj_visibility(self) -> None:
        visible = not self.dj_view.isVisible()
        self.dj_view.setVisible(visible)
        if visible:
            self.player.set_audio_metrics_callback(self.dj_view._emit_metrics)
            if self.state.current_index is not None:
                self.dj_view.update_info()
        else:
            self.player.set_audio_metrics_callback(None)
        self.settings.show_dj = visible
        self._save_settings_safe()

    def _build_audio_device_items(self) -> list:
        try:
            devices = self.player.get_audio_devices()
        except Exception:
            logger.exception("Failed to load audio devices")
            return [{"label": "Error loading devices", "state": "disabled"}]
        devices = filter_selectable_audio_devices(devices)
        if not devices:
            return [{"label": "No devices found", "state": "disabled"}]
        current_id = getattr(self.player, "_device_id", None)
        try:
            _alsa_card, default_description = self.player.get_default_output_info()
        except Exception:
            default_description = None
        default_suffix = f" (currently: {default_description})" if default_description else " (system default)"
        items = []
        for i, (device_id, device_name) in enumerate(devices):
            label = device_name if i > 0 else f"{device_name}{default_suffix}"
            checked = (device_id == current_id) if current_id is not None else (i == 0)
            items.append({
                "label": label,
                "radiobutton": True,
                "group": "audio_device",
                "checked": checked,
                "command": lambda dev_id=device_id: self._set_audio_device(dev_id),
            })
        return items

    def _set_audio_device(self, device_id: str) -> None:
        try:
            self.player.set_audio_device(device_id)
            self.browser_view.refresh_preview_devices()
        except Exception:
            logger.exception("Failed to set audio device: %s", device_id)
            QMessageBox.critical(self, "Error", f"Failed to set audio device: {device_id}")

    def _open_documentation(self, doc_filename: str) -> None:
        open_doc_in_browser(doc_filename, self.theme)

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

    def _on_open_playback_features(self) -> None:
        if self._playback_features_win is not None:
            self._playback_features_win.show()
            self._playback_features_win.raise_()
            self._playback_features_win.activateWindow()
            return
        win = PlaybackFeaturesWindowQt(self, self.state, self.settings, self.player, self._current_palette, self.theme_signal)
        win.finished.connect(lambda _: setattr(self, "_playback_features_win", None))
        self._playback_features_win = win
        win.show()

    def _on_open_playlist_generator(self) -> None:
        if self._playlist_generator_win is not None:
            self._playlist_generator_win.show()
            self._playlist_generator_win.raise_()
            self._playlist_generator_win.activateWindow()
            return
        win = PlaylistGeneratorWindowQt(self, str(get_generator_templates_path()), self._current_palette)
        win.playlist_generated.connect(self._on_playlist_generated)
        win.finished.connect(lambda _: setattr(self, "_playlist_generator_win", None))
        self._playlist_generator_win = win
        win.show()

    def _on_playlist_generated(self, songs: list, mode: str) -> None:
        if mode == "browser":
            self.state.browser_files = list(songs)
            self.browser_view.refresh()
            return
        if mode == "replace":
            self.state.playlist = list(songs)
            self.state.current_index = None
            self.player.stop()
            self.controls.stopped.emit()
            if songs:
                self.state.current_index = 0
        else:  # append
            self.state.playlist = self.state.playlist + list(songs)
        self.playlist_view.refresh()

    def _on_theme_changed(self, palette: dict) -> None:
        self._current_palette = palette
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, palette)
        self.controls.apply_palette(palette)
        self.playlist_view.apply_palette(palette)
        self.status_view.apply_palette(palette)
        self.dj_view.apply_palette(palette)

    # ---------- geometry persistence ----------

    def _apply_initial_geometry(self) -> None:
        self.setMinimumSize(*MIN_SIZE)
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else None

        saved = getattr(self.settings, "window_geometry_qt", None)
        if saved:
            match = _GEOMETRY_RE.match(saved)
            if match:
                w, h, x, y = (int(v) for v in match.groups())
                w = max(w, MIN_SIZE[0])
                h = max(h, MIN_SIZE[1])
                if avail is not None:
                    x = max(avail.x() - w + 150, min(x, avail.x() + avail.width() - 150))
                    y = max(avail.y() - h + 150, min(y, avail.y() + avail.height() - 150))
                self.setGeometry(x, y, w, h)
                return

        w, h = DEFAULT_SIZE
        if avail is not None:
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
        try:
            self.dj_view.shutdown()
        except Exception:
            logger.exception("Failed to shut down DJ view on close")
        try:
            analysis_manager.shutdown()
        except Exception:
            logger.exception("Failed to shut down BPM/Key analysis process on close")
        try:
            if self.mini_player is not None:
                self.mini_player.stop_updates()
                self.mini_player.close()
        except Exception:
            logger.exception("Failed to clean up mini player on close")
        self._save_geometry()
        try:
            self.settings.save()
        except Exception:
            logger.exception("Failed to save settings on close")
        super().closeEvent(event)

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.WindowStateChange:
            self.menubar.sync_maximize_button()
            if self.isMinimized() and bool(getattr(self.settings, "mini_player_enabled", True)):
                self._show_mini_player()
        super().changeEvent(event)

    # ---------- mini player ----------

    def _show_mini_player(self) -> None:
        if self.mini_player is None:
            self.mini_player = MiniPlayerWindowQt(self.state, self.controls, self._current_palette)
            self.mini_player.restore_requested.connect(self._restore_from_mini_player)
            self.mini_player.play_pause_requested.connect(self._on_mini_player_play_pause)
            self.mini_player.prev_requested.connect(self._on_prev)
            self.mini_player.next_requested.connect(self._on_next)
        self.mini_player._position_bottom_right()
        self.mini_player.show()
        self.mini_player.start_updates()

    def _hide_mini_player(self) -> None:
        if self.mini_player is not None:
            self.mini_player.stop_updates()
            self.mini_player.hide()

    def _restore_from_mini_player(self) -> None:
        self._hide_mini_player()
        self.showNormal()
        QTimer.singleShot(0, self._focus_after_restore)

    def _focus_after_restore(self) -> None:
        self.raise_()
        self.activateWindow()

    def _on_mini_player_play_pause(self) -> None:
        """Paused->resume and playing->pause both call controls._on_pause(),
        collapsing into one `is_playing or is_paused` check. Otherwise
        (nothing loaded/stopped) reuses _on_play_requested — the same
        selection-aware start the main transport bar's Play button makes."""
        if self.controls.is_playing or self.controls.is_paused:
            self.controls._on_pause()
        else:
            self._on_play_requested()

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
