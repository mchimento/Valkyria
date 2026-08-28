"""
This module composes the smaller UI components (PlaylistView, BrowserView, ControlsBar)
and wires them to the AppState, ThemeManager, AudioPlayer and Settings.
"""

import logging
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
import ctypes
import os
import sys
import threading
import time
from audio.metadata import metadata_extractor

from audio import m3u as m3u_module, playback
from ui.playlist_view import PlaylistView
from ui.browser_view import BrowserView
from ui.controls import ControlsBar
from ui.status_frame_view import StatusFrameView
from ui.dj_frame_view import DJFrameView
from ui.preferences_window import PreferencesWindow
from ui.tooltips import TooltipManager
from ui.media_info_window import MediaInfoWindow
from ui.booklet_viewer import BookletViewer
from ui.utils import center_window, apply_rounded_corners, force_taskbar_presence, set_win32_icon, make_window_independent, apply_theme_titlebar
from ui.custom_menu_bar import CustomMenuBar
from ui.documentation_view import open_documentation as open_doc_in_browser
from ui.audio_effects_window import AudioEffectsWindow
from ui.playback_features_view import PlaybackFeaturesView
from ui.time_limit_dialog import TimeLimitDialog
from ui.mini_player import MiniPlayer
from ui.playlist_generator_window import PlaylistGeneratorWindow
from app.paths import get_resource_path, get_generator_templates_path

logger = logging.getLogger(__name__)


class MainWindow:
    def __init__(self, state, theme, player, settings):
        self.state = state
        self.theme = theme
        self.player = player
        self.settings = settings

        # Root window
        ctk.set_appearance_mode("Dark" if self.settings.theme == "dark" else "Light")
        self.root = tk.Tk()
        self.root.title("Valkyria")
        self._set_app_icon()

        # Apply theme to root (styles + palette)
        self.theme.apply_to(self.root)

        self.palette = self.theme.palette

        # 1-px window border (VS Code style): root bg = border colour,
        # all content lives inside self._content which is padded by 1 px.
        _border = self.palette.get("border", "#3E3E3E")
        _bg     = self.palette.get("bg", "#1E1E1E")
        self.root.configure(bg=_border)
        self._content = tk.Frame(self.root, bg=_bg)
        self._content.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Tooltip manager (shared)
        self.tooltip_manager = TooltipManager(self.root, self.palette)

        # Build UI - menu first so it's at the top
        self._build_menu()
        self._build_layout()
        self._apply_initial_geometry()

        # Remove the native title bar; the menu bar provides window controls.
        # On Linux, overrideredirect() fights with the window manager/compositor
        # (most visibly under Wayland/XWayland+mutter): manual geometry() calls
        # during drag/resize and wm "zoomed" state changes cause the window to
        # flicker and appear to detach from its own chrome. Keep native
        # decorations there instead and skip the custom drag/resize/control-button
        # chrome that depends on overrideredirect being active.
        self._use_custom_chrome = sys.platform != "linux"
        if self._use_custom_chrome:
            self.root.overrideredirect(True)
            self.root.update_idletasks()
            apply_rounded_corners(self.root)
            force_taskbar_presence(self.root, get_resource_path("assets/app-icon.ico"))
            self._setup_resize()
            self.menubar.setup_window_controls(self._on_quit)

        # Keep the maximise icon in sync when the window state changes
        self.root.bind("<Configure>", self._on_root_configure, add="+")

        # Initialize mini player (hidden by default)
        self.mini_player = None
        # Respect persisted preference (default: enabled)
        self._mini_player_enabled = getattr(self.settings, 'mini_player_enabled', True)
        self._is_minimized = False
        self._last_window_state = None

        # Start polling for window state changes (for mini player)
        self._check_window_state()

        # Apply initial visibility from settings for playlist and browser
        self.toggle_playlist_visibility()
        self.toggle_browser_visibility()
        self.toggle_dj_visibility()

        # Bind custom events from subcomponents
        self.root.bind("<<BrowserAddSelected>>", self._on_browser_add_selected)
        self.root.bind("<<PlaylistDouble>>", self._on_playlist_double)
        self.root.bind("<<OpenPlaylist>>", lambda e: self.open_playlist())
        self.root.bind("<<SavePlaylist>>", lambda e: self.save_playlist_as())
        self.root.bind("<<MinimizeRequested>>", lambda e: self._on_minimize_requested())

        # Global click handler to clear playlist selection when clicking outside
        self.root.bind_all("<Button-1>", self._on_global_click, add="+")

        # Keep UI in sync initially
        self.refresh_all()
        self._update_track_info_state_from_player()

        # Ensure player stopped on exit and save geometry
        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)

        self._generator_win = None

    # ---------- Build UI ----------
    def _setup_resize(self):
        """Attach mouse-based resize to all four edges/corners of the frameless window."""
        BORDER = 6  # px from window edge that count as a resize zone
        self._resize_dir = None
        self._resize_start = {}  # x, y, w, h, wx, wy

        if sys.platform == "win32":
            _CURSOR_NW_SE, _CURSOR_NE_SW = "size_nw_se", "size_ne_sw"
            _CURSOR_WE, _CURSOR_NS = "size_we", "size_ns"
        elif sys.platform == "darwin":
            _CURSOR_NW_SE, _CURSOR_NE_SW = "resizenwse", "resizenesw"
            _CURSOR_WE, _CURSOR_NS = "resizeleftright", "resizeupdown"
        else:
            _CURSOR_NW_SE, _CURSOR_NE_SW = "top_left_corner", "top_right_corner"
            _CURSOR_WE, _CURSOR_NS = "sb_h_double_arrow", "sb_v_double_arrow"

        def _cursor_for(on_left, on_right, on_top, on_bottom):
            if (on_left and on_top) or (on_right and on_bottom):
                return _CURSOR_NW_SE
            if (on_right and on_top) or (on_left and on_bottom):
                return _CURSOR_NE_SW
            if on_left or on_right:
                return _CURSOR_WE
            if on_top or on_bottom:
                return _CURSOR_NS
            return ""

        def _dirs(event):
            x = event.x_root - self.root.winfo_x()
            y = event.y_root - self.root.winfo_y()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            return x < BORDER, x > w - BORDER, y < BORDER, y > h - BORDER

        def _on_motion(event):
            if self._resize_dir is not None:
                return
            on_left, on_right, on_top, on_bottom = _dirs(event)
            cur = _cursor_for(on_left, on_right, on_top, on_bottom)
            self.root.configure(cursor=cur)

        def _on_press(event):
            on_left, on_right, on_top, on_bottom = _dirs(event)
            if not any((on_left, on_right, on_top, on_bottom)):
                self._resize_dir = None
                return
            self._resize_dir = (on_left, on_right, on_top, on_bottom)
            self._resize_start = {
                "x": event.x_root, "y": event.y_root,
                "w": self.root.winfo_width(), "h": self.root.winfo_height(),
                "wx": self.root.winfo_x(), "wy": self.root.winfo_y(),
            }

        def _on_drag(event):
            if not self._resize_dir:
                return
            on_left, on_right, on_top, on_bottom = self._resize_dir
            s = self._resize_start
            dx = event.x_root - s["x"]
            dy = event.y_root - s["y"]
            x, y, w, h = s["wx"], s["wy"], s["w"], s["h"]
            min_w, min_h = self._min_win_w, self._min_win_h
            if on_right:
                w = max(min_w, w + dx)
            if on_bottom:
                h = max(min_h, h + dy)
            if on_left:
                new_w = max(min_w, w - dx)
                x = x + w - new_w
                w = new_w
            if on_top:
                new_h = max(min_h, h - dy)
                y = y + h - new_h
                h = new_h
            self.root.geometry(f"{w}x{h}+{x}+{y}")

        def _on_release(event):
            self._resize_dir = None
            self.root.configure(cursor="")

        self.root.bind("<Motion>",          _on_motion,  add="+")
        self.root.bind("<ButtonPress-1>",   _on_press,   add="+")
        self.root.bind("<B1-Motion>",       _on_drag,    add="+")
        self.root.bind("<ButtonRelease-1>", _on_release, add="+")

    def _build_menu(self):
        # Create custom menu bar and pack it at the top of the content frame
        self.menubar = CustomMenuBar(self._content, self.theme, parent_window=self.root)
        self.menubar.pack(side=tk.TOP, fill=tk.X)

        # Initialize variables for checkbuttons and radiobuttons
        show_playlist_initial = bool(getattr(self.settings, "show_playlist", True))
        show_browser_initial = bool(getattr(self.settings, "show_browser", True))
        self.show_playlist_var = tk.BooleanVar(value=show_playlist_initial)
        self.show_browser_var = tk.BooleanVar(value=show_browser_initial)
        show_dj_initial = bool(getattr(self.settings, "show_dj", True))
        self.show_dj_var = tk.BooleanVar(value=show_dj_initial)
        self.always_on_top_var = tk.BooleanVar(value=False)
        self.play_on_double_var = tk.BooleanVar(value=bool(getattr(self.settings, "play_on_double", False)))
        self.repeat_mode_var = tk.StringVar(value="none")
        self.audio_device_var = tk.StringVar()

        # Track playback requests to prevent overlapping play commands
        self._play_request_id = 0
        self._play_request_lock = threading.Lock()

        # Store menu item references for state management
        self.menu_item_refs = {}

        # Media menu
        media_items = [
            {"label": "Open File...", "command": self.open_file, "accelerator": "Ctrl+O"},
            {"label": "Open Multiple Files...", "command": self.open_files, "accelerator": "Ctrl+M"},
            {"label": "Open Folder...", "command": self.open_folder, "accelerator": "Ctrl+F"},
            {"label": "Open Playlist (M3U/M3U8)...", "command": self.open_playlist, "accelerator": "Ctrl+L"},
            {"separator": True},
            {"label": "Save Playlist", "command": self.save_playlist, "ref": "save_playlist", "accelerator": "Ctrl+S"},
            {"label": "Save Playlist As...", "command": self.save_playlist_as, "ref": "save_playlist_as", "accelerator": "Ctrl+Shift+S"},
            {"separator": True},
            {"label": "Quit", "command": self._on_quit, "accelerator": "Alt+F4"}
        ]
        self.menubar.add_menu("Media", media_items)
        self.menu_item_refs["save_playlist"] = media_items[5]
        self.menu_item_refs["save_playlist_as"] = media_items[6]

        # Playlist menu
        sort_submenu = [
            {"label": "Shuffle", "command": self.shuffle_playlist, "accelerator": "Ctrl+H"},
            {"label": "Sort by Title", "command": self.sort_playlist_by_title, "accelerator": "Ctrl+T"},
            {"label": "Sort by Artist", "command": self.sort_playlist_by_artist, "accelerator": "Ctrl+R"}
        ]

        operations_submenu = [
            {"label": "Move Up", "command": self.move_selected_up, "accelerator": "Ctrl+Up"},
            {"label": "Move Down", "command": self.move_selected_down, "accelerator": "Ctrl+Down"},
            {"separator": True},
            {"label": "Play After Current Song", "command": self.play_selected_after_current, "ref": "play_after_current", "accelerator": "Ctrl+N"},
            {"label": "Play for time...", "command": self.set_play_time_limit, "ref": "play_for_time"},
            {"separator": True},
            {"label": "Remove Selected", "command": self.remove_selected_from_playlist, "accelerator": "Delete"},
            {"label": "Clear", "command": self.clear_playlist, "accelerator": "Ctrl+C"},
            {"separator": True},
            {"label": "Track Information", "command": self.open_media_info, "ref": "track_info", "accelerator": "Ctrl+I"},
            {"label": "Show Album booklet", "command": self.show_booklet, "ref": "track_booklet", "accelerator": "Ctrl+B"}
        ]
        self.menu_item_refs["play_after_current"] = operations_submenu[3]
        self.menu_item_refs["play_for_time"] = operations_submenu[4]
        self.menu_item_refs["track_info"] = operations_submenu[9]
        self.menu_item_refs["track_booklet"] = operations_submenu[10]

        repeat_submenu = [
            {"label": "No Repeat", "radiobutton": True, "variable": self.repeat_mode_var,
             "value": "none", "command": lambda: self._set_repeat_mode("none")},
            {"label": "Repeat One", "radiobutton": True, "variable": self.repeat_mode_var,
             "value": "one", "command": lambda: self._set_repeat_mode("one")},
            {"label": "Repeat All", "radiobutton": True, "variable": self.repeat_mode_var,
             "value": "all", "command": lambda: self._set_repeat_mode("all")}
        ]

        playlist_items = [
            {"label": "Sort", "submenu": sort_submenu},
            {"label": "Operations", "submenu": operations_submenu},
            {"label": "Repeat Mode", "submenu": repeat_submenu, "ref": "playlist_menu"}
        ]
        self.menubar.add_menu("Playback", playlist_items)
        self.menu_item_refs["playlist_menu"] = playlist_items

        # View menu
        view_items = [
            {"label": "Show Playback", "checkbutton": True, "variable": self.show_playlist_var,
             "command": self.toggle_playlist_visibility, "accelerator": "F9"},
            {"label": "Show Browser", "checkbutton": True, "variable": self.show_browser_var,
             "command": self.toggle_browser_visibility, "accelerator": "F10"},
            {"label": "Show Live Audio Analysis", "checkbutton": True, "variable": self.show_dj_var,
             "command": self.toggle_dj_visibility, "accelerator": "F11"},
            {"separator": True},
            {"label": "Always on Top", "checkbutton": True, "variable": self.always_on_top_var,
             "command": self.toggle_always_on_top}
        ]
        self.menubar.add_menu("View", view_items)

        # Tools menu
        self.audio_device_items = []
        self._build_audio_device_menu_items()
        audio_device_item = {"label": "Audio Device", "submenu": self.audio_device_items}

        tools_items = [
            audio_device_item,
            {"label": "Audio Effects and Filters", "command": self.open_audio_effects, "accelerator": "F7"},
            {"label": "Playback features", "command": self.open_playback_features, "accelerator": "F8"},
            {"separator": True},
            {"label": "Playlist Generator", "command": self.open_playlist_generator, "accelerator": "F6"},
            {"separator": True},
            {"label": "Preferences", "command": self.open_preferences, "accelerator": "Ctrl+P"}
        ]
        self.menubar.add_menu("Tools", tools_items)
        self.menu_item_refs["audio_device"] = audio_device_item

        # Help menu
        documentation_submenu = [
            {"label": "User Guide", "command": lambda: self.open_documentation("user_guide.md")},
            {"label": "BPM Analysis", "command": lambda: self.open_documentation("bpm_analysis.md")}
        ]

        help_items = [
            {"label": "Documentation", "submenu": documentation_submenu},
            {"separator": True},
            {"label": "About", "command": self.open_about, "accelerator": "F1"}
        ]
        self.menubar.add_menu("Help", help_items)

        # Initialize menu state
        self._update_menu_state()

        # Bind keyboard accelerators
        self._bind_keyboard_accelerators()

    def _build_layout(self):
        # Main frame (playlist + browser)
        self.main_frame = ttk.Frame(self._content, padding=6, style="TFrame")

        # Left: Playlist view
        self.left_frame = ttk.Frame(self.main_frame, style="TFrame")
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,6))

        self.playlist_view = PlaylistView(
            self.left_frame,
            self.state,
            self.theme,
            tooltip_manager=self.tooltip_manager,
            select_callback=self._on_playlist_select,
            change_callback=self._update_menu_state,
            play_callback=self._on_context_play_song,
            metadata_callback=self._on_context_show_metadata,
            remove_callback=self._on_context_remove_song,
            play_after_current_callback=self._on_context_play_after_current,
            set_time_limit_callback=self.set_play_time_limit,
            clear_time_limit_callback=self.clear_play_time_limit
        )
        self.playlist_view.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Right: Browser view
        self.right_frame = ttk.Frame(self.main_frame, style="TFrame")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(6,0))

        self.browser_view = BrowserView(self.right_frame, self.state, self.theme, tooltip_manager=self.tooltip_manager, status_callback=self._controls_status_event, player=self.player)
        self.browser_view.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Link browser view to playlist view for drag and drop
        self.browser_view.set_playlist_view(self.playlist_view)

        # Bottom info frames container (packed below, once controls exists)
        self.bottom_info_frame = ttk.Frame(self._content, style="TFrame")

        # DJ Frame (right-aligned)
        self.dj_view = DJFrameView(self.bottom_info_frame, self.state, self.theme, self.settings, self.player)
        self.dj_view.pack(side=tk.RIGHT, anchor="n")

        # Register a global BPM listener so UI components can react when BPM is changed on disk
        try:
            metadata_extractor.register_bpm_listener(lambda fp: self._on_global_bpm_update(fp))
            metadata_extractor.register_key_listener(lambda fp: self._on_global_key_update(fp))
        except Exception:
            pass

        # Status bar with CustomTkinter (expands to fill remaining space)
        self.status_view = StatusFrameView(self.bottom_info_frame, self.state, self.theme, self.settings)
        self.status_view.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12), anchor="n")

        # Bottom: Controls bar
        self.controls = ControlsBar(
            self._content,
            self.player,
            self.state,
            self.theme,
            self.playlist_view,
            tooltip_manager=self.tooltip_manager,
            status_callback=self._controls_status_event,
            settings=self.settings,
            repeat_var=self.repeat_mode_var,
            on_toggle_repeat=self.toggle_repeat_mode,
            on_open_effects=self.open_audio_effects
        )
        self.controls.configure(padding=(0, 0, 0, 15))

        # Pack bottom-anchored rows first (see note above _build_layout) so
        # they always keep their full requested size; main_frame goes last
        # and yields space when the window is too small to fit everything.
        self.bottom_info_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=(12, 12), pady=(0, 20))
        self.controls.pack(side=tk.BOTTOM, fill=tk.X)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

    def _apply_initial_geometry(self):
        """Size and place the window relative to the current screen.

        With no saved geometry (first run), the window gets a harmonic
        size proportional to the screen and is centered.
        """
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        chrome_h = (self.menubar.winfo_reqheight()
                    + self.bottom_info_frame.winfo_reqheight()
                    + self.controls.winfo_reqheight())
        min_content_h = 220  # smallest still-usable playlist/browser strip
        min_h = min(chrome_h + min_content_h, screen_h)
        min_w = min(max(self.controls.winfo_reqwidth() + 40, 760), screen_w)
        self.root.minsize(min_w, min_h)
        self._min_win_w, self._min_win_h = min_w, min_h

        geometry = self.settings.window_geometry
        match = re.match(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$", geometry) if geometry else None
        if match:
            w, h, x, y = (int(v) for v in match.groups())
            w = max(min_w, min(w, screen_w))
            h = max(min_h, min(h, screen_h))
            # Keep a good chunk of the window reachable regardless of monitor layout
            x = max(-w + 150, min(x, screen_w - 150))
            y = max(0, min(y, screen_h - 150))
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            return

        # No usable saved geometry: pick a harmonic (golden-ratio) default
        # sized to this screen and center it.
        golden_ratio = 1.618
        target_h = int(screen_h * 0.78)
        target_w = int(target_h * golden_ratio)
        if target_w > screen_w * 0.9:
            target_w = int(screen_w * 0.9)
            target_h = int(target_w / golden_ratio)

        w = min(max(min_w, target_w), screen_w)
        h = min(max(min_h, target_h), screen_h)
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ----------- STATUS: ControlsBar event dispatcher -----------
    def _controls_status_event(self, event_type, count=0):
        if event_type == "play":
            self._restore_status()
            # Start dynamic time-limit updates only if the current track has a time limit
            idx = self.state.current_index
            if idx is not None and idx < len(self.state.playlist):
                current_file = self.state.playlist[idx]
                if current_file in self.state.play_limits and hasattr(self, 'controls'):
                    self.status_view._start_time_limit_updates(self.controls)
            self._update_menu_state()
            self._set_track_info_enabled(True)
        elif event_type == "resume":
            # Resume should update menu state but not re-run the full status restore
            idx = self.state.current_index
            if idx is not None and idx < len(self.state.playlist):
                current_file = self.state.playlist[idx]
                if current_file in self.state.play_limits and hasattr(self, 'controls'):
                    self.status_view._start_time_limit_updates(self.controls)
            self._update_menu_state()
            self._set_track_info_enabled(True)
        elif event_type == "pause":
            self.status_view._stop_time_limit_updates()
            self._update_menu_state()
            self._set_track_info_enabled(True)
        elif event_type == "stop":
            self.status_view._stop_time_limit_updates()
            self.status_view.handle_stop()
            self.dj_view._clear_info()
            self.state.current_index = None
            self.refresh_all()
            self._update_menu_state()
            self._set_track_info_enabled(False)
        elif event_type in ("prev", "next"):
            self._restore_status()
            idx = self.state.current_index
            if idx is not None and idx < len(self.state.playlist):
                current_file = self.state.playlist[idx]
                if current_file in self.state.play_limits and hasattr(self, 'controls'):
                    self.status_view._start_time_limit_updates(self.controls)
            self._update_menu_state()
        elif event_type == "browsed_files" or event_type == "browsed_folder":
            self._set_temporary_status(f"Added {count} file(s) to Songs list")
        elif event_type == "added_to_playlist":
            if count > 0:
                self.refresh_all()
                self._set_temporary_status(f"Added {count} file(s) to the bottom of the playlist")
            else:
                self._set_temporary_status("No new files added to playlist (duplicates skipped)")
        elif event_type == "added_to_playlist_below":
            if count > 0:
                self.playlist_view.refresh(preserve_selection=True)
                self._update_menu_state()
                self._set_temporary_status(f"Added {count} file(s) below current track in playlist")
            else:
                self._set_temporary_status("No new songs were added to playlist (duplicates skipped)")
        elif event_type == "crossfade":
            # Trigger next track logic when crossfade threshold is reached
            self.handle_track_end()

    def _on_global_bpm_update(self, filepath):
        """Handle global BPM updates by refreshing DJ view if it affects the current track."""
        try:
            idx = self.state.current_index
            if idx is None or idx >= len(self.state.playlist):
                return
            current_path = self.state.playlist[idx]
            if os.path.abspath(current_path) != os.path.abspath(filepath):
                return

            # Schedule update on main thread
            try:
                self.root.after(0, self.dj_view._on_bpm_metadata_changed, filepath)
            except Exception:
                pass
        except Exception:
            pass

    def _on_global_key_update(self, filepath):
        """Handle global Key updates by refreshing DJ view if it affects the current track."""
        try:
            idx = self.state.current_index
            if idx is None or idx >= len(self.state.playlist):
                return
            current_path = self.state.playlist[idx]
            if os.path.abspath(current_path) != os.path.abspath(filepath):
                return

            # Schedule update on main thread
            try:
                self.root.after(0, self.dj_view._on_key_metadata_changed, filepath)
            except Exception:
                pass
        except Exception:
            pass

    # ---------- Mini Player Management ----------
    def _on_minimize_requested(self):
        """Minimize the frameless window using withdraw() + mini player.

        overrideredirect(True) prevents iconify() from working on Windows, so we
        hide the window ourselves and rely on the mini player for restore.
        """
        self._is_minimized = True
        if self._mini_player_enabled:
            self._show_mini_player()
        self.root.withdraw()

    def _check_window_state(self):
        """Periodically check window state for mini player activation."""
        try:
            if not self.root.winfo_exists():
                return

            current_state = self.root.state()

            if current_state == 'iconic' and not self._is_minimized:
                if self._mini_player_enabled:
                    logger.info("Main window minimized, showing mini player")
                    self._is_minimized = True
                    self._show_mini_player()
            elif current_state not in ('iconic', 'withdrawn') and self._is_minimized:
                logger.info("Main window restored, hiding mini player")
                self._is_minimized = False
                self._hide_mini_player()

            self._last_window_state = current_state
        except Exception as e:
            logger.error(f"Error checking window state: {e}", exc_info=True)

        try:
            if self.root.winfo_exists():
                self.root.after(500, self._check_window_state)
        except:
            pass

    def _on_window_state_change(self, event):
        """Handle window minimize/restore events."""
        # This method is kept for compatibility but polling is used instead
        pass

    def _show_mini_player(self):
        """Show the mini player window."""
        try:
            if self.mini_player is None:
                logger.info("Creating mini player instance")
                self.mini_player = MiniPlayer(
                    self.root,
                    self.state,
                    self.theme,
                    self.controls,
                    self._restore_main_window
                )
                # Position mini player in bottom-right corner
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                x = screen_width - 470
                y = screen_height - 170
                self.mini_player.geometry(f"+{x}+{y}")
                logger.info(f"Mini player positioned at ({x}, {y})")

                # Sever Win32 owner link before first show so root.withdraw()
                # does not drag the mini player down with it.
                make_window_independent(self.mini_player)

            self.mini_player.deiconify()
            set_win32_icon(self.mini_player, get_resource_path("assets/app-icon.ico"))
            logger.info("Mini player shown")
        except Exception as e:
            logger.error(f"Failed to show mini player: {e}", exc_info=True)
            self.mini_player = None

    def _hide_mini_player(self):
        """Hide the mini player window."""
        if self.mini_player:
            try:
                logger.info("Hiding mini player")
                self.mini_player.withdraw()
            except Exception as e:
                logger.error(f"Failed to hide mini player: {e}", exc_info=True)

    def _restore_main_window(self):
        """Restore the main window from minimized state."""
        try:
            logger.info("Restoring main window")
            self._is_minimized = False
            self._hide_mini_player()
            self.root.deiconify()
            self.root.state('normal')
            self.root.lift()
            self.root.focus_force()
            # Re-apply Win32 icon — deiconify resets it to the process default.
            set_win32_icon(self.root, get_resource_path("assets/app-icon.ico"))
            # Re-trigger BPM/key analysis
            self.root.after(0, self._restore_status)
        except Exception as e:
            logger.error(f"Failed to restore main window: {e}", exc_info=True)

    # ---------- Refresh helpers ----------
    def refresh_all(self):
        self.playlist_view.refresh()
        self._update_menu_state()

    def _update_menu_state(self):
        """Enable/disable menu items based on playlist state."""
        has_songs = len(self.state.playlist) > 0
        state = "normal" if has_songs else "disabled"

        # Update Save Playlist items in Media menu
        if "save_playlist" in self.menu_item_refs:
            self.menu_item_refs["save_playlist"]["state"] = state
        if "save_playlist_as" in self.menu_item_refs:
            self.menu_item_refs["save_playlist_as"]["state"] = state

        # Update Track Information item - disable when no songs in playlist
        if "track_info" in self.menu_item_refs:
            self.menu_item_refs["track_info"]["state"] = state

        # Update Show Album booklet item - disable when no songs in playlist
        if "track_booklet" in self.menu_item_refs:
            self.menu_item_refs["track_booklet"]["state"] = state

        # Update Play After Current - disable if no current track is playing
        if "play_after_current" in self.menu_item_refs:
            play_after_state = "normal" if (has_songs and self.state.current_index is not None) else "disabled"
            self.menu_item_refs["play_after_current"]["state"] = play_after_state

        # Update Playlist menu state
        if "playlist_menu" in self.menu_item_refs:
            playlist_menu_item = self.menu_item_refs["playlist_menu"]
            # The playlist menu itself doesn't need to be disabled, but we could disable submenus
            # For now, we'll leave it enabled but individual items can be disabled if needed

    def _update_track_info_state_from_player(self):
        """Set Track Information menu state based on current player status and playlist state."""
        try:
            has_songs = len(self.state.playlist) > 0
            # First check if there are songs - if not, always disable
            if not has_songs:
                state = "disabled"
            else:
                # Only enable if something is playing or paused
                is_playing = self.player.is_playing()
                is_paused = self.player.is_paused()
                state = "normal" if (is_playing or is_paused) else "disabled"

            if "track_info" in self.menu_item_refs:
                self.menu_item_refs["track_info"]["state"] = state

            if "track_booklet" in self.menu_item_refs:
                self.menu_item_refs["track_booklet"]["state"] = state
        except Exception:
            # Fail silently; menu state is not critical
            pass

    def _set_track_info_enabled(self, enabled: bool):
        """Enable or disable the Track Information menu item explicitly."""
        try:
            state = "normal" if enabled else "disabled"
            if "track_info" in self.menu_item_refs:
                self.menu_item_refs["track_info"]["state"] = state
            if "track_booklet" in self.menu_item_refs:
                self.menu_item_refs["track_booklet"]["state"] = state
        except Exception:
            pass

    # ---------- Checkbutton ----------
    def on_change(self, *args):
        self.state.play_on_double = self.play_on_double_var.get()

    # ---------- Cursor helpers ----------
    def _show_busy_cursor(self):
        if sys.platform == "win32":
            try:
                wait = ctypes.windll.user32.LoadCursorW(None, 32514)  # IDC_WAIT
                copy = ctypes.windll.user32.CopyImage(wait, 2, 0, 0, 0x0040)  # IMAGE_CURSOR, LR_DEFAULTSIZE
                ctypes.windll.user32.SetSystemCursor(copy, 32512)  # OCR_NORMAL
                self._win32_busy = True
            except Exception:
                self._win32_busy = False
        else:
            self.root.configure(cursor="watch")

    def _hide_busy_cursor(self):
        if sys.platform == "win32" and getattr(self, "_win32_busy", False):
            try:
                ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 0)  # SPI_SETCURSORS
            except Exception:
                pass
            self._win32_busy = False
        else:
            self.root.configure(cursor="")

    # ---------- Menu / File actions ----------
    def open_file(self):
        path = filedialog.askopenfilename(parent=self.root, title="Open File",
                                         filetypes=[("Audio files", "*.mp3 *.wav *.flac *.ogg *.m4a"), ("All files", "*.*")])
        if not path:
            return
        self._show_busy_cursor()
        def _do():
            try:
                self.state.playlist = [path]
                self.refresh_all()
                self._restore_status()
            finally:
                self._hide_busy_cursor()
        self.root.after(10, _do)

    def open_files(self):
        paths = filedialog.askopenfilenames(parent=self.root, title="Open Multiple Files",
                                            filetypes=[("Audio files", "*.mp3 *.wav *.flac *.ogg *.m4a"), ("All files", "*.*")])
        if not paths:
            return
        self._show_busy_cursor()
        def _do():
            try:
                self.state.playlist = list(paths)
                self.refresh_all()
                self._restore_status()
            finally:
                self._hide_busy_cursor()
        self.root.after(10, _do)

    def open_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title="Open Folder")
        if not folder:
            return
        self._show_busy_cursor()
        def _do():
            try:
                self._load_files_into_playlist(folder)
                self._restore_status()
            finally:
                self._hide_busy_cursor()
        self.root.after(10, _do)

    def open_playlist(self):
        path = filedialog.askopenfilename(parent=self.root, title="Open Playlist",
                                          filetypes=[("M3U playlist", "*.m3u *.m3u8"), ("All files", "*.*")])
        if not path:
            return
        self._show_busy_cursor()
        def _do():
            try:
                items = m3u_module.parse_m3u(path)
                if not items:
                    self._set_temporary_status("No entries found in playlist")
                    return
                self.state.playlist = items
                self.state.current_playlist_path = path
                self.refresh_all()
                self._set_temporary_status(f"Playlist {path} was loaded")
                self._restore_status()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load playlist: {e}", parent=self.root)
            finally:
                self._hide_busy_cursor()
        self.root.after(10, _do)

    def save_playlist(self):
        if not self.state.current_playlist_path:
            self.save_playlist_as()
        try:
            m3u_module.write_m3u(self.state.current_playlist_path, self.state.playlist)
            self._set_temporary_status(f'Playlist saved')
        except Exception as e:
            messagebox.showerror('Error', f'Failed to save playlist: {e}')

    def save_playlist_as(self):
        path = filedialog.asksaveasfilename(parent=self.root, title="Save Playlist As",
                                            defaultextension=".m3u8",
                                            filetypes=[("M3U8 playlist", "*.m3u8"), ("M3U playlist", "*.m3u")])
        if not path:
            return
        try:
            m3u_module.write_m3u(path, self.state.playlist)
            self.state.current_playlist_path = path
            self._set_temporary_status("Playlist saved")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save playlist: {e}", parent=self.root)

    def _build_audio_device_menu_items(self):
        """Populate the Audio Device submenu items list with available devices."""
        # Clear existing items
        self.audio_device_items.clear()

        try:
            devices = self.player.get_audio_devices()

            if not devices:
                self.audio_device_items.append({"label": "No devices found", "state": "disabled"})
                return

            # Set default device as first item
            default_device_id, default_device_name = devices[0] if devices else ('default', 'Default Audio Device')
            self.audio_device_var.set(default_device_id)

            # Add each device as a menu item
            for i, (device_id, device_name) in enumerate(devices):
                # Mark the first device as system default
                label = device_name if i > 0 else f"{device_name} (system default)"
                self.audio_device_items.append({
                    "label": label,
                    "radiobutton": True,
                    "variable": self.audio_device_var,
                    "value": device_id,
                    "command": lambda dev_id=device_id: self.set_audio_device(dev_id)
                })
        except Exception as e:
            logger.error(f"Failed to build audio device menu: {e}")
            self.audio_device_items.append({"label": "Error loading devices", "state": "disabled"})

    def set_audio_device(self, device_id: str):
        """Set the audio output device."""
        try:
            self.player.set_audio_device(device_id)
            if hasattr(self, 'browser_view'):
                self.browser_view.refresh_preview_devices()
            device_name = [name for did, name in self.player.get_audio_devices() if did == device_id]
            device_name = device_name[0] if device_name else device_id
            self._set_temporary_status(f"Audio device set to: {device_name}")
        except Exception as e:
            logger.error(f"Failed to set audio device: {e}")
            messagebox.showerror("Error", f"Failed to set audio device: {e}", parent=self.root)

    def update_theme_colors(self):
        """Update colors for all widgets when theme changes"""
        # Close any open dropdown menus before updating theme to avoid errors
        if hasattr(self, 'menubar') and self.menubar:
            if hasattr(self.menubar, 'active_dropdown'):
                try:
                    self.menubar._close_active_menu()
                except:
                    pass

        # Update CTk appearance
        ctk.set_appearance_mode("Dark" if self.settings.theme == "dark" else "Light")
        self.theme.apply_to(self.root)

        self.palette = self.theme.palette
        self.tooltip_manager.palette = self.palette

        is_dark = self.settings.theme.lower() == 'dark'

        # Force root window background update to fix corner artifacts
        root_bg = self.palette.get('bg', '#1E1E1E' if is_dark else '#FAFAFA')
        border_color = self.palette.get('border', '#3E3E3E' if is_dark else '#D0D0D0')
        try:
            self.root.configure(bg=border_color)
            if hasattr(self, '_content'):
                self._content.configure(bg=root_bg)
            # Use direct Tk call to ensure root background is updated everywhere
            self.root.tk.call(self.root._w, 'configure', '-bg', border_color)
            self.root.update_idletasks()
        except:
            pass

        try:
            style = ttk.Style(self.root)
            style.configure("TFrame", background=root_bg)
        except:
            pass

        # Update status view
        if hasattr(self, 'status_view'):
            self.status_view.update_theme()

        # Update DJ view
        if hasattr(self, 'dj_view'):
            self.dj_view.update_theme()

        # Update controls
        self.controls.update_theme()

        # Update PlaylistView colors (handled by styles but might need refresh)
        self.playlist_view.update_theme()
        if hasattr(self.browser_view, 'update_theme'):
             self.browser_view.update_theme()

        # Update custom menu bar theme
        if hasattr(self, 'menubar') and self.menubar:
            self.menubar.update_theme()

        # Update mini player theme
        if self.mini_player:
            try:
                self.mini_player.update_theme()
            except Exception:
                pass

        # Update main_frame background to ensure padding areas are correct
        if hasattr(self, 'main_frame'):
            try:
                self.main_frame.configure(style="TFrame")
            except:
                pass

        # Update open windows - use winfo_children on root to find all toplevels
        # Need to check all descendants since some windows may be parented to widgets
        def find_all_toplevels(widget):
            """Recursively find all Toplevel windows."""
            toplevels = []
            for child in widget.winfo_children():
                if isinstance(child, tk.Toplevel):
                    toplevels.append(child)
                toplevels.extend(find_all_toplevels(child))
            return toplevels

        for window in find_all_toplevels(self.root):
            if isinstance(window, AudioEffectsWindow):
                try:
                    window.update_theme()
                except Exception:
                    pass
            elif isinstance(window, PlaybackFeaturesView):
                try:
                    window.update_theme()
                except Exception:
                    pass
            elif isinstance(window, BookletViewer):
                try:
                    window.update_theme()
                except Exception:
                    pass
            elif hasattr(window, 'update_theme'):
                # Handle other windows with update_theme method
                try:
                    window.update_theme()
                except Exception:
                    pass

        # Trigger refresh to redraw
        self.refresh_all()

    def open_preferences(self):
        def on_apply(selected_theme):
            # Update settings with lowercase theme
            self.settings.theme = selected_theme
            # Apply theme to all components
            self.theme.reload()
            # Update main window and all child components
            self.update_theme_colors()
            # Update mini player enabled flag from settings
            self._mini_player_enabled = getattr(self.settings, 'mini_player_enabled', True)
            # Update playlist and browser themes
            self.playlist_view.update_theme()
            self.browser_view.update_theme()
            # Update controls theme
            self.controls.update_theme()
            # Update mini player theme
            if self.mini_player:
                try:
                    self.mini_player.update_theme()
                except Exception:
                    pass
            # Update any open TimeLimitDialog windows
            for window in self.root.winfo_children():
                if hasattr(window, 'update_theme') and window.__class__.__name__ == 'TimeLimitDialog':
                    try:
                        window.update_theme()
                    except Exception:
                        pass

        def on_bpm_preference_change():
            # Refresh only BPM display to avoid interfering with playback
            if self.playlist_view:
                self.playlist_view.refresh_bpm_display_only()
            # Refresh any open media info windows
            for window in self.root.winfo_children():
                if isinstance(window, tk.Toplevel) and hasattr(window, '_refresh_bpm'):
                    try:
                        window._refresh_bpm()
                    except Exception:
                        pass

        PreferencesWindow(self.root, self.settings, self.theme, on_apply=on_apply, on_bpm_preference_change=on_bpm_preference_change)

    def open_playback_features(self):
        """Open the Playback Features window."""
        try:
            PlaybackFeaturesView(self.root, self.state, self.settings, self.theme, self.player)
        except Exception as e:
            logger.error(f"Failed to open playback features: {e}", exc_info=True)

    def open_playlist_generator(self):
        """Open the Playlist Generator window, or raise it if already open."""
        if self._generator_win is not None:
            try:
                self._generator_win.deiconify()
                self._generator_win.lift()
                self._generator_win.focus_force()
                return
            except tk.TclError:
                self._generator_win = None
        try:
            win = PlaylistGeneratorWindow(
                self.root, self.theme,
                on_generate=self._on_playlist_generated,
                templates_path=str(get_generator_templates_path()),
                on_close=self._on_generator_win_closed,
            )
            self._generator_win = win
            win.protocol("WM_DELETE_WINDOW", self._on_generator_win_closed)
        except Exception as e:
            logger.error(f"Failed to open playlist generator: {e}", exc_info=True)

    def _on_generator_win_closed(self):
        if self._generator_win is not None:
            try:
                self._generator_win.destroy()
            except tk.TclError:
                pass
            self._generator_win = None

    def _on_root_configure(self, event):
        if event.widget is not self.root:
            return
        if self._use_custom_chrome:
            self.menubar.sync_maximize_button()
        if getattr(self, "_generator_win", None) is not None:
            try:
                apply_theme_titlebar(self._generator_win, self.theme.palette)
            except Exception:
                pass

    def _on_playlist_generated(self, songs: list, mode: str):
        """Receive generated songs and route them to the playlist or browser."""
        if not songs:
            return
        if mode == "browser":
            self.state.browser_files.clear()
            self.state.browser_files.extend(songs)
            self.browser_view.refresh()
            return
        if mode == "replace":
            self.state.playlist.clear()
            self.state.current_index = None
            self.player.stop()
        for path in songs:
            self.state.playlist.append(path)
        if mode == "replace" and self.state.playlist:
            self.state.current_index = 0
        self.refresh_all()

    def open_audio_effects(self):
        """Open the Audio Effects window."""
        AudioEffectsWindow(self.root, self.player, self.theme)

    def open_media_info(self):
        """Open media information dialog for the currently selected track in playlist."""
        # Check if there are any selected tracks in the playlist
        if not self.playlist_view.tree.selection():
            # Create custom silent dialog instead of messagebox
            info_window = tk.Toplevel(self.root)
            info_window.title("Media Information")
            info_window.geometry("300x130")
            info_window.resizable(False, False)
            info_window.transient(self.root)

            # Hide window initially to prevent flickering during positioning
            info_window.withdraw()

            content_frame = ttk.Frame(info_window, padding=20)
            content_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(content_frame, text="No track is selected").pack(pady=10)
            ttk.Button(content_frame, text="OK", command=info_window.destroy, padding=(10, 5)).pack(pady=5)

            info_window.bind("<Return>", lambda e: info_window.destroy())
            info_window.bind("<Escape>", lambda e: info_window.destroy())

            center_window(info_window, self.root)

            # Show window after positioning
            info_window.deiconify()
            return

        # Get the first selected track (handle multiple selections by showing the first one)
        selected_items = self.playlist_view.tree.selection()
        first_selected_index = self.playlist_view.tree.index(selected_items[0])

        if 0 <= first_selected_index < len(self.state.playlist):
            track = self.state.playlist[first_selected_index]
            MediaInfoWindow(self.root, track, theme_manager=self.theme)

    def show_booklet(self):
        # Check if there are any selected tracks in the playlist
        if not self.playlist_view.tree.selection():
            # Create custom silent dialog instead of messagebox
            info_window = tk.Toplevel(self.root)
            info_window.title("Album Booklet Information")
            info_window.geometry("300x130")
            info_window.resizable(False, False)
            info_window.transient(self.root)

            # Hide window initially to prevent flickering during positioning
            info_window.withdraw()

            content_frame = ttk.Frame(info_window, padding=20)
            content_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(content_frame, text="No track is selected").pack(pady=10)
            ttk.Button(content_frame, text="OK", command=info_window.destroy, padding=(10, 5)).pack(pady=5)

            info_window.bind("<Return>", lambda e: info_window.destroy())
            info_window.bind("<Escape>", lambda e: info_window.destroy())

            center_window(info_window, self.root)

            # Show window after positioning
            info_window.deiconify()
            return

        selected_items = self.playlist_view.tree.selection()
        first_selected_index = self.playlist_view.tree.index(selected_items[0])

        if 0 <= first_selected_index < len(self.state.playlist):
            track = self.state.playlist[first_selected_index]
            BookletViewer(self.root, track, theme=self.theme)

    def _set_app_icon(self):
        try:
            from PIL import Image, ImageTk
            icon_path = get_resource_path("assets/app-icon.png")
            if icon_path.exists():
                img = ImageTk.PhotoImage(Image.open(icon_path).resize((64, 64), Image.LANCZOS))
                self.root.iconphoto(True, img)
                self._app_icon = img  # prevent garbage collection
        except Exception:
            pass

    def open_about(self):
        # Create custom dialog using CustomTkinter
        about_window = ctk.CTkToplevel(self.root)
        about_window.title("About")
        about_window.geometry("400x300")
        about_window.resizable(False, False)

        # Hide window initially to prevent flickering during positioning
        about_window.withdraw()

        # Center the window
        about_window.transient(self.root)
        # Don't grab focus - let main window stay focused

        # Get theme colors
        palette = self.theme.palette
        bg_color = palette.get("bg", "#1E1E1E" if self.settings.theme == "dark" else "#FAFAFA")
        fg_color = palette.get("fg", "#FFFFFF" if self.settings.theme == "dark" else "#000000")
        accent_color = palette.get("accent", "#0078d4")

        about_window.configure(fg_color=bg_color)

        # Content frame
        content_frame = ctk.CTkFrame(about_window, fg_color="transparent")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Logo image
        try:
            from PIL import Image
            logo_path = get_resource_path("assets/logo-no-background.png")
            if logo_path.exists():
                logo_pil = Image.open(logo_path)
                logo_ctk = ctk.CTkImage(light_image=logo_pil, dark_image=logo_pil, size=(280, 93))
                logo_label = ctk.CTkLabel(content_frame, image=logo_ctk, text="")
                logo_label.pack(pady=(0, 12))
            else:
                raise FileNotFoundError
        except Exception:
            # Fallback to text title if image unavailable
            ctk.CTkLabel(
                content_frame,
                text="Valkyria",
                font=("Segoe UI", 24, "bold"),
                text_color=accent_color
            ).pack(pady=(0, 15))

        # Description
        desc_label = ctk.CTkLabel(
            content_frame,
            text="A modern audio player with playback features for music enthusiasts and DJs",
            font=("Segoe UI", 13),
            text_color=fg_color,
            wraplength=350
        )
        desc_label.pack(pady=4)

        # Version
        version_label = ctk.CTkLabel(
            content_frame,
            text="Version 1.0.0",
            font=("Segoe UI", 12),
            text_color=fg_color
        )
        version_label.pack(pady=5)

        # OK button
        ok_button = ctk.CTkButton(
            content_frame,
            text="OK",
            font=("Segoe UI", 12),
            fg_color=accent_color,
            hover_color=palette.get("accent_hover", "#106ebe"),
            text_color="#ffffff",
            width=80,
            height=32,
            command=about_window.destroy
        )
        ok_button.pack(pady=(10, 0))
        ok_button.focus_set()

        # Bind Enter and Escape to close
        about_window.bind("<Return>", lambda e: about_window.destroy())
        about_window.bind("<Escape>", lambda e: about_window.destroy())

        # Center window after all setup is complete
        center_window(about_window, self.root)

        # Show window after all setup is complete
        about_window.deiconify()

    def open_documentation(self, doc_filename):
        """Open a documentation file in the default web browser."""
        open_doc_in_browser(doc_filename, self.theme)

    def _on_quit(self):
        logger.info("Shutting down Valkyria")
        if self.mini_player:
            try:
                self.mini_player.cleanup()
                self.mini_player.destroy()
            except Exception:
                logger.error("Failed to clean up mini player", exc_info=True)
        try:
            self.settings.window_geometry = self.root.geometry()
            self.settings.save()
        except Exception:
            logger.error("Failed to save window geometry on exit", exc_info=True)
        try:
            self.player.stop()
        except Exception:
            logger.error("Failed to stop player on exit", exc_info=True)
        try:
            self.root.destroy()
        except Exception:
            logger.error("Failed to destroy window on exit", exc_info=True)
        logger.info("Valkyria shut down complete")
        import sys
        sys.exit(0)

    # ---------- Playlist operations (menu) ----------
    def shuffle_playlist(self):
        self._show_busy_cursor()
        t0 = time.perf_counter()
        def _do():
            self.state.playlist, self.state.current_index = playback.shuffle_playlist(self.state.playlist, self.state.current_index)
            self.refresh_all()
            self._set_temporary_status("Playlist shuffled")
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            self.root.after(max(0, 200 - elapsed_ms), self._hide_busy_cursor)
        self.root.after(10, _do)

    def clear_playlist(self):
        if not self.state.playlist:
            return

        if messagebox.askyesno("Clear Playlist", "Are you sure you want to clear the playlist?", parent=self.root):
            self.state.playlist, self.state.current_index = playback.clear_playlist()
            self.player.stop()
            self.refresh_all()
            self._set_temporary_status("Playlist cleared")

    # ---------- Repeat Mode ----------
    def toggle_repeat_mode(self):
        """Cycle through repeat modes: none -> all -> one -> none."""
        modes = ["none", "one", "all"]
        current = self.repeat_mode_var.get()
        try:
            idx = modes.index(current)
        except ValueError:
            idx = 0
        new_mode = modes[(idx + 1) % len(modes)]
        self.repeat_mode_var.set(new_mode)
        self._set_repeat_mode(new_mode)

    def _set_repeat_mode(self, mode):
        """Set the repeat mode (none, one, all)."""
        self.state.repeat_mode = mode
        self._set_temporary_status(f"Repeat: {mode.title()}")

    # ---------- Playlist Operations ----------
    def remove_selected_from_playlist(self):
        """Remove selected song from playlist."""
        selected_indices = self.playlist_view.get_selected_indices()
        if not selected_indices:
            return

        self.state.playlist, self.state.current_index = playback.remove_selected_from_playlist(
            self.state.playlist, selected_indices, self.state.current_index
        )

        if self.state.current_index is None:
            self.player.stop()

        self.refresh_all()
        self._set_temporary_status(f"Removed {len(selected_indices)} item(s) from playlist")

    def move_selected_up(self):
        """Move selected song up in playlist."""
        selected_indices = self.playlist_view.get_selected_indices()
        if not selected_indices or 0 in selected_indices:
            return  # Can't move up if first item is selected

        # Move items up
        new_playlist = playback.move_selected_up(
            self.state.playlist,
            selected_indices
        )

        # Update current index if it was moved
        if self.state.current_index is not None:
            if self.state.current_index in selected_indices:
                self.state.current_index -= 1
            elif self.state.current_index - 1 in selected_indices:
                self.state.current_index += 1

        self.state.playlist = new_playlist

        # Update selection (shift indices up)
        new_selection = [i-1 if i > 0 and i-1 not in selected_indices else i
                        for i in selected_indices]
        self.playlist_view.tree.selection_set(*[
            self.playlist_view.tree.get_children()[i]
            for i in new_selection
            if 0 <= i < len(self.state.playlist)
        ])
        self.refresh_all()

    def move_selected_down(self):
        """Move selected song down in playlist."""
        selected_indices = self.playlist_view.get_selected_indices()
        if not selected_indices or max(selected_indices) >= len(self.state.playlist) - 1:
            return  # Can't move down if last item is selected

        # Move items down
        new_playlist = playback.move_selected_down(
            self.state.playlist,
            selected_indices
        )

        # Update current index if it was moved
        if self.state.current_index is not None:
            if self.state.current_index in selected_indices:
                self.state.current_index += 1
            elif self.state.current_index + 1 in selected_indices:
                self.state.current_index -= 1

        self.state.playlist = new_playlist

        # Update selection (shift indices down)
        new_selection = [i+1 if i < len(self.state.playlist) - 1 and i+1 not in selected_indices else i
                        for i in selected_indices]
        self.playlist_view.tree.selection_set(*[
            self.playlist_view.tree.get_children()[i]
            for i in new_selection
            if 0 <= i < len(self.state.playlist)
        ])
        self.refresh_all()

    def sort_playlist_by_title(self):
        self._show_busy_cursor()
        t0 = time.perf_counter()
        def _do():
            self.state.playlist, self.state.current_index = playback.sort_playlist_by_title(self.state.playlist, self.state.current_index)
            self.refresh_all()
            self._set_temporary_status("Playlist sorted by title")
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            self.root.after(max(0, 200 - elapsed_ms), self._hide_busy_cursor)
        self.root.after(10, _do)

    def sort_playlist_by_artist(self):
        self._show_busy_cursor()
        t0 = time.perf_counter()
        def _do():
            self.state.playlist, self.state.current_index = playback.sort_playlist_by_artist(self.state.playlist, self.state.current_index)
            self.refresh_all()
            self._set_temporary_status("Playlist sorted by artist")
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            self.root.after(max(0, 200 - elapsed_ms), self._hide_busy_cursor)
        self.root.after(10, _do)

    def play_selected_after_current(self):
        """Move selected tracks to play immediately after the currently playing track."""
        selected_indices = self.playlist_view.get_selected_indices()
        if not selected_indices:
            return

        # Check if there's a currently playing track
        if self.state.current_index is None:
            return

        # Move tracks after current
        self.state.playlist, self.state.current_index = playback.play_after_current(
            self.state.playlist, selected_indices, self.state.current_index
        )

        self.refresh_all()
        count = len(selected_indices)
        if self.state.current_index in selected_indices:
            count -= 1  # Don't count current track
        if count > 0:
            self._set_temporary_status(f"Moved {count} track(s) to play after current song")

    def set_play_time_limit(self, index=None):
        """Set a playback time limit for the selected track."""
        if index is None:
            selected_indices = self.playlist_view.get_selected_indices()
            if not selected_indices:
                messagebox.showinfo("No Selection", "Please select a track first.", parent=self.root)
                return
            # Use the first selected track
            index = selected_indices[0]
        if index >= len(self.state.playlist):
            return

        filepath = self.state.playlist[index]
        current_limit = self.state.play_limits.get(filepath)

        # Open dialog
        dialog = TimeLimitDialog(self.root, self.theme, current_limit)
        result = dialog.get_result()

        if result == "CANCEL":
            return
        elif result is None:
            # Clear the limit
            if filepath in self.state.play_limits:
                del self.state.play_limits[filepath]
            self._set_temporary_status("Playback time limit cleared")
            # If this was the current playing track, stop status updates
            if self.state.current_index is not None and self.state.playlist[self.state.current_index] == filepath:
                self.status_view._stop_time_limit_updates()
        else:
            # Set the limit
            self.state.play_limits[filepath] = result
            self._set_temporary_status(f"Playback time limit set to {int(result)}s")
            # If this was the current playing track and player is playing, start updates
            if self.state.current_index is not None and self.state.playlist[self.state.current_index] == filepath:
                if hasattr(self, 'controls'):
                    self.status_view._start_time_limit_updates(self.controls)

        # Refresh displays
        self.refresh_all()

    def clear_play_time_limit(self, index=None):
        """Clear the playback time limit for a track."""
        if index is None:
            selected_indices = self.playlist_view.get_selected_indices()
            if not selected_indices:
                return
            index = selected_indices[0]

        if index >= len(self.state.playlist):
            return

        filepath = self.state.playlist[index]
        if filepath in self.state.play_limits:
            del self.state.play_limits[filepath]
            self._set_temporary_status("Playback time limit cleared")
            self.refresh_all()

    # ---------- View Menu ----------
    def toggle_playlist_visibility(self):
        """Toggle playlist visibility."""
        if self.show_playlist_var.get():
            self.playlist_view.pack(fill=tk.BOTH, expand=True)
        else:
            self.playlist_view.pack_forget()
        # Persist setting
        if hasattr(self, "settings"):
            try:
                self.settings.show_playlist = self.show_playlist_var.get()
                self.settings.save()
            except Exception:
                pass

    def toggle_browser_visibility(self):
        """Toggle browser visibility."""
        if self.show_browser_var.get():
            # Show browser frame
            self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(6,0))
            self.browser_view.pack(fill=tk.BOTH, expand=True)
        else:
            # Hide browser frame
            self.browser_view.pack_forget()
            self.right_frame.pack_forget()
        # Persist setting
        if hasattr(self, "settings"):
            try:
                self.settings.show_browser = self.show_browser_var.get()
                self.settings.save()
            except Exception:
                pass

    def toggle_dj_visibility(self):
        """Toggle DJ (Live Audio Analysis) visibility."""
        if self.show_dj_var.get():
            try:
                self.dj_view.pack(side=tk.RIGHT, anchor="n")
                # Register audio metrics callback so player begins producing metrics
                try:
                    if hasattr(self, 'player') and hasattr(self.dj_view, '_on_audio_metrics_update'):
                        self.player.set_audio_metrics_callback(self.dj_view._on_audio_metrics_update)
                except Exception:
                    pass
                # Ensure the geometry manager processes the change immediately
                try:
                    self.dj_view.update_idletasks()
                except Exception:
                    pass
                # Trigger update to start analysis for current track if playing
                try:
                    if self.state.current_index is not None:
                        self.dj_view.update_info()
                except Exception:
                    pass
            except Exception:
                pass
        else:
            try:
                # Unregister audio metrics callback to avoid unnecessary computations
                try:
                    if hasattr(self, 'player'):
                        self.player.set_audio_metrics_callback(None)
                except Exception:
                    pass
                self.dj_view.pack_forget()
            except Exception:
                pass
        # Persist setting
        if hasattr(self, "settings"):
            try:
                self.settings.show_dj = self.show_dj_var.get()
                self.settings.save()
            except Exception:
                pass

    def toggle_always_on_top(self):
        """Toggle always on top window attribute."""
        self.root.attributes('-topmost', self.always_on_top_var.get())

    # ---------- Handlers for custom events from subcomponents ----------
    def _on_global_click(self, event):
        """Handle global clicks to clear playlist selection when clicking outside playlist."""
        # Check if there are any selected items in the playlist
        if not self.playlist_view.tree.selection():
            return  # No selection to clear

        # Get the widget that was clicked
        widget = event.widget

        # Check if the click is within the playlist treeview
        if widget == self.playlist_view.tree:
            return  # Click was on playlist, don't clear selection

        # Check if the click is within the playlist view container (including scrollbar)
        playlist_container = self.playlist_view
        if widget == playlist_container:
            return  # Click was within playlist container, don't clear selection

        # Check if the click is on any child of the playlist view
        current = widget
        while current:
            if current == playlist_container:
                return  # Click was within playlist hierarchy, don't clear selection
            try:
                current = current.master
            except:
                break

        # Check if the click is on the menu bar or its dropdowns
        if hasattr(self, 'menubar'):
            # Check if click is on menu bar buttons or their children
            for menu_button in self.menubar.menu_buttons.values():
                # Check if the clicked widget is the menu button itself
                if widget == menu_button:
                    return  # Click was on menu bar, don't clear selection

                # Check if the clicked widget is a child of the menu button
                current = widget
                while current:
                    if current == menu_button:
                        return  # Click was on menu bar child, don't clear selection
                    try:
                        current = current.master
                    except:
                        break

            # Check if click is within menu bar
            if widget == self.menubar:
                return  # Click was on menu bar, don't clear selection

            # Check if click is on any dropdown menu
            if hasattr(self.menubar, 'active_dropdown') and self.menubar.active_dropdown:
                current = widget
                while current:
                    if current == self.menubar.active_dropdown:
                        return  # Click was on dropdown menu, don't clear selection
                    try:
                        current = current.master
                    except:
                        break

        # If we get here, the click was outside the playlist and menu system
        self.playlist_view.clear_selection()

    def _on_browser_add_selected(self, event):
        """
        BrowserView emits <<BrowserAddSelected>> and stores the actual selected paths
        at self.browser_view._last_add (see BrowserView implementation).
        """
        sel_paths = getattr(self.browser_view, "_last_add", None)
        if not sel_paths:
            return
        added = 0
        for p in sel_paths:
            self.state.playlist.append(p)
            added += 1
        if added:
            self.refresh_all()
            self._set_temporary_status(f"Added {added} file(s) to playlist")

    def _on_playlist_double(self, event):
        """
        PlaylistView emits <<PlaylistDouble>> and stores the last double-clicked index
        on the playlist view as _last_double_index.
        """
        idx = getattr(self.playlist_view, "_last_double_index", None)
        if idx is None:
            idx = self.state.current_index
        if idx is None:
            return

        if 0 <= idx < len(self.state.playlist):
            with self._play_request_lock:
                self._play_request_id += 1
                my_id = self._play_request_id

            if self.player.is_playing() and self.settings.fade_out_enabled:
                # Fade out is active: run in background thread so we can wait for it
                def _transition():
                    wait = self.player.trigger_fade_out()
                    if wait > 0:
                        time.sleep(wait)
                    with self._play_request_lock:
                        if self._play_request_id != my_id:
                            return
                    def _force_play():
                        with self._play_request_lock:
                            if self._play_request_id != my_id:
                                return
                        self.state.current_index = idx
                        self.refresh_all()
                        self.controls._on_play()
                        self._restore_status()
                    self.root.after(0, _force_play)
                threading.Thread(target=_transition, daemon=True).start()
            else:
                # No fade out — play immediately on the main thread, same as next/previous
                self.state.current_index = idx
                self.refresh_all()
                self.controls._on_play()
                self._restore_status()

    def _on_playlist_select(self, index):
        """
        Called when the user selects a row in the playlist (single-click).
        Tracks selection but does NOT update current_index since that's for playing state.
        Does NOT start playback — double-click or menu actions do that.
        """

    # ---------- Context Menu Callbacks ----------
    def _on_context_play_song(self, index):
        """Play the song at the given index from context menu."""
        if index is None or not self.state.playlist:
            return
        if 0 <= index < len(self.state.playlist):
            self.state.current_index = index
            self.refresh_all()
            self.controls._on_play()
            self._restore_status()

    def _on_context_show_metadata(self, index):
        """Show metadata window for the song at the given index from context menu."""
        if index is None or not self.state.playlist:
            return
        if 0 <= index < len(self.state.playlist):
            track = self.state.playlist[index]
            MediaInfoWindow(self.root, track, theme_manager=self.theme,
                         metadata_saved_callback=self._on_metadata_saved_from_info_window)

    def _on_metadata_saved_from_info_window(self, filepath):
        """Handle metadata saved from media info window by refreshing relevant UI components."""
        try:
            # Update metadata cache for the modified file
            metadata_extractor.update_cache(filepath)

            # Check if this is the currently playing file
            if (self.state.current_index is not None and
                self.state.current_index < len(self.state.playlist) and
                self.state.playlist[self.state.current_index] == filepath):
                # Refresh status display for current track
                self._restore_status()

            # Refresh playlist to show updated metadata
            if self.playlist_view:
                self.playlist_view.refresh_metadata_for_file(filepath)

        except Exception as e:
            logger.error(f"Error refreshing after metadata save: {e}")

    def _on_context_remove_song(self, index):
        """Remove the song at the given index from playlist via context menu."""
        if index is None or not self.state.playlist:
            return
        if 0 <= index < len(self.state.playlist):
            # If this is the currently playing song, stop it
            if self.state.current_index == index:
                was_playing = self.player.is_playing()
                if was_playing:
                    self.player.stop()
                self.state.current_index = None
            elif self.state.current_index is not None and index < self.state.current_index:
                # Adjust current_index if we're removing a song before it
                self.state.current_index -= 1
            del self.state.playlist[index]
            self.refresh_all()
            self._set_temporary_status("Removed song from playlist")

    def _on_context_play_after_current(self, index):
        """Move the song at the given index to play after the current song via context menu."""
        if index is None or not self.state.playlist:
            return

        if self.state.current_index is None:
            messagebox.showinfo("No Track Playing", "Please start playing a track first.", parent=self.root)
            return

        if 0 <= index < len(self.state.playlist):
            self.state.playlist, self.state.current_index = playback.play_after_current(
                self.state.playlist, [index], self.state.current_index
            )
            self.refresh_all()
            self._set_temporary_status("Moved track to play after current song")

    # ---------- Helper to load folder into playlist (open_folder) ----------
    def _load_files_into_playlist(self, folder):
        if not os.path.isdir(folder):
            return
        exts = self.state.exts
        files = []
        for root, _, filenames in os.walk(folder):
            for fn in filenames:
                if fn.lower().endswith(exts):
                    files.append(os.path.join(root, fn))
        if not files:
            self._set_temporary_status("No audio files found in folder.")
            return
        self.state.playlist = files
        self.refresh_all()

    # ---------- Methods used by the audio backend to safely notify the UI ----------
    def on_track_end_from_backend(self):
        """
        Called by the application coordinator when the AudioPlayer reports end-of-track.
        Schedule UI-safe call on Tk's event loop.
        """
        try:
            self.root.after(0, self.handle_track_end)
        except Exception:
            pass

    def handle_track_end(self):
        """
        Handle end-of-track based on repeat mode:
        - 'none': Stop at end of playlist
        - 'one': Replay current track once, then reset to 'none'
        - 'all': Loop to beginning of playlist
        """
        if self.state.current_index is None or not self.state.playlist:
            return

        repeat_mode = getattr(self.state, 'repeat_mode', 'none')

        if repeat_mode == 'one':
            # Replay current track once, then reset to 'none'
            self.refresh_all()
            self.controls.play()
            # Reset repeat mode to 'none' after replaying
            self.state.repeat_mode = 'none'
            self.repeat_mode_var.set('none')

            self._restore_status()
            if hasattr(self, 'status_view'):
                self.status_view.schedule_restore(3000)
        elif repeat_mode == 'all':
            # Loop to beginning
            if self.state.current_index + 1 < len(self.state.playlist):
                self.state.current_index += 1
            else:
                # End of playlist, loop back to start
                self.state.current_index = 0
            self.refresh_all()
            self.controls.play()
        else:  # 'none'
            # Default: advance to next track
            if self.state.current_index + 1 < len(self.state.playlist):
                self.state.current_index += 1
                self.refresh_all()
                self.controls.play()
            else:
                # end of playlist: stop player
                try:
                    if hasattr(self, 'controls') and self.controls:
                        self.controls.stop()
                    else:
                        self.player.stop()
                        # Ensure status is updated to clear artwork when playlist ends
                        self._controls_status_event("stop")
                except Exception:
                    pass

    # ---------- Status bar helpers ----------
    def _set_temporary_status(self, message, duration=3000):
        """Show temporary status message, then restore now-playing."""
        if hasattr(self, 'status_view'):
            self.status_view.set_temporary_status(message, duration)

    def _restore_status(self):
        """Restore playing status and populate metadata line."""
        if hasattr(self, 'status_view'):
            self.status_view.restore_status()
        if hasattr(self, 'dj_view'):
            self.dj_view.update_info()

    # ---------- Keyboard Accelerators ----------
    def _bind_keyboard_accelerators(self):
        """Bind keyboard accelerators to their corresponding commands."""
        # Alt+key shortcuts for main menu bar navigation
        self.root.bind("<Alt-f>", lambda e: self._open_menu_by_key("Media"))
        self.root.bind("<Alt-p>", lambda e: self._open_menu_by_key("Playback"))
        self.root.bind("<Alt-v>", lambda e: self._open_menu_by_key("View"))
        self.root.bind("<Alt-t>", lambda e: self._open_menu_by_key("Tools"))
        self.root.bind("<Alt-h>", lambda e: self._open_menu_by_key("Help"))

        # Escape to close menus
        self.root.bind("<Escape>", lambda e: self._close_active_menu())

        # Media menu accelerators
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-m>", lambda e: self.open_files())
        self.root.bind("<Control-f>", lambda e: self.open_folder())
        self.root.bind("<Control-l>", lambda e: self.open_playlist())
        self.root.bind("<Control-s>", lambda e: self.save_playlist())
        self.root.bind("<Control-Shift-S>", lambda e: self.save_playlist_as())

        # Playback menu accelerators
        self.root.bind("<Control-h>", lambda e: self.shuffle_playlist())
        self.root.bind("<Control-t>", lambda e: self.sort_playlist_by_title())
        self.root.bind("<Control-r>", lambda e: self.sort_playlist_by_artist())
        self.root.bind("<Control-Up>", lambda e: self.move_selected_up())
        self.root.bind("<Control-Down>", lambda e: self.move_selected_down())
        self.root.bind("<Control-n>", lambda e: self.play_selected_after_current())
        self.root.bind("<Delete>", lambda e: self.remove_selected_from_playlist())
        self.root.bind("<Control-c>", lambda e: self.clear_playlist())
        self.root.bind("<Control-i>", lambda e: self.open_media_info())
        self.root.bind("<Control-b>", lambda e: self.show_booklet())

        # View menu accelerators
        self.root.bind_all("<F9>", lambda e: self._toggle_playlist_visibility())
        self.root.bind_all("<F10>", lambda e: self._toggle_browser_visibility())
        self.root.bind_all("<F11>", lambda e: self._toggle_dj_visibility())

        # Tools menu accelerators
        self.root.bind_all("<Control-p>", lambda e: self.open_preferences())
        # Use bind_all for function keys so accelerators work regardless of focus
        self.root.bind_all("<F6>", lambda e: self.open_playlist_generator())
        self.root.bind_all("<F7>", lambda e: self.open_audio_effects())
        self.root.bind_all("<F8>", lambda e: self.open_playback_features())

        # Help menu accelerators
        self.root.bind("<F1>", lambda e: self.open_about())

    def _open_menu_by_key(self, menu_label: str):
        """Open a menu by its label using keyboard shortcut."""
        if hasattr(self.menubar, '_toggle_menu'):
            self.menubar._toggle_menu(menu_label)

    def _close_active_menu(self):
        """Close the currently active menu."""
        if hasattr(self.menubar, '_close_active_menu'):
            self.menubar._close_active_menu()

    def _toggle_playlist_visibility(self):
        """Toggle playlist visibility for keyboard accelerator."""
        self.show_playlist_var.set(not self.show_playlist_var.get())
        self.toggle_playlist_visibility()

    def _toggle_browser_visibility(self):
        """Toggle browser visibility for keyboard accelerator."""
        self.show_browser_var.set(not self.show_browser_var.get())
        self.toggle_browser_visibility()

    def _toggle_dj_visibility(self):
        """Toggle DJ visibility for keyboard accelerator."""
        self.show_dj_var.set(not self.show_dj_var.get())
        self.toggle_dj_visibility()

    # ---------- Start UI mainloop ----------
    def start(self):
        self.root.mainloop()
