"""
This module composes the smaller UI components (PlaylistView, BrowserView, ControlsBar)
and wires them to the AppState, ThemeManager, AudioPlayer and Settings.
"""

import logging
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
import random

from audio import m3u as m3u_module
from ui.playlist_view import PlaylistView
from ui.browser_view import BrowserView
from ui.controls import ControlsBar
from ui.preferences_window import PreferencesWindow
from ui.tooltips import TooltipManager
from ui.media_info_window import MediaInfoWindow
from ui.utils import center_window
from ui.custom_menu_bar import CustomMenuBar

from mutagen import File as MutagenFile

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
        self.root.title("Tango Studio")
        if self.settings.window_geometry:
            try:
                self.root.geometry(self.settings.window_geometry)
            except Exception:
                pass

        # Apply theme to root (styles + palette)
        self.theme.apply_to(self.root)

        self.palette = self.theme.palette
        self._meta_cache = {}

        # Tooltip manager (shared)
        self.tooltip_manager = TooltipManager(self.root, self.palette)

        # Build UI - menu first so it's at the top
        self._build_menu()
        self._build_layout()

        # Ensure no default menu bar is shown
        self.root.config(menu="")

        # Apply initial visibility from settings for playlist and browser
        self.toggle_playlist_visibility()
        self.toggle_browser_visibility()

        # Bind custom events from subcomponents
        self.root.bind("<<BrowserAddSelected>>", self._on_browser_add_selected)
        self.root.bind("<<PlaylistDouble>>", self._on_playlist_double)
        self.root.bind("<<OpenPlaylist>>", lambda e: self.open_playlist())
        self.root.bind("<<SavePlaylist>>", lambda e: self.save_playlist_as())

        # Keep UI in sync initially
        self.refresh_all()
        self._update_track_info_state_from_player()

        # Ensure player stopped on exit and save geometry
        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)

    # ---------- Build UI ----------
    def _build_menu(self):
        # Create custom menu bar and pack it at the top
        self.menubar = CustomMenuBar(self.root, self.theme)
        self.menubar.pack(side=tk.TOP, fill=tk.X)

        # Initialize variables for checkbuttons and radiobuttons
        show_playlist_initial = bool(getattr(self.settings, "show_playlist", True))
        show_browser_initial = bool(getattr(self.settings, "show_browser", True))
        self.show_playlist_var = tk.BooleanVar(value=show_playlist_initial)
        self.show_browser_var = tk.BooleanVar(value=show_browser_initial)
        self.always_on_top_var = tk.BooleanVar(value=False)
        self.repeat_mode_var = tk.StringVar(value="none")
        self.audio_device_var = tk.StringVar()

        # Store menu item references for state management
        self.menu_item_refs = {}

        # Media menu
        media_items = [
            {"label": "Open File...", "command": self.open_file},
            {"label": "Open Multiple Files...", "command": self.open_files},
            {"label": "Open Folder...", "command": self.open_folder},
            {"label": "Open Playlist (M3U/M3U8)...", "command": self.open_playlist},
            {"separator": True},
            {"label": "Save Playlist", "command": self.save_playlist, "ref": "save_playlist"},
            {"label": "Save Playlist As...", "command": self.save_playlist_as, "ref": "save_playlist_as"},
            {"separator": True},
            {"label": "Quit", "command": self._on_quit, "accelerator": "Alt+F4"}
        ]
        self.menubar.add_menu("Media", media_items)
        self.menu_item_refs["save_playlist"] = media_items[5]
        self.menu_item_refs["save_playlist_as"] = media_items[6]

        # Playlist menu
        sort_submenu = [
            {"label": "Shuffle", "command": self.shuffle_playlist},
            {"label": "Sort by Title", "command": self.sort_playlist_by_title},
            {"label": "Sort by Artist", "command": self.sort_playlist_by_artist}
        ]

        operations_submenu = [
            {"label": "Move Up", "command": self.move_selected_up},
            {"label": "Move Down", "command": self.move_selected_down},
            {"separator": True},
            {"label": "Remove Selected", "command": self.remove_selected_from_playlist},
            {"label": "Remove All", "command": self.clear_playlist},
            {"separator": True},
            {"label": "Track Information", "command": self.open_media_info, "ref": "track_info"}
        ]
        self.menu_item_refs["track_info"] = operations_submenu[6]

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
        self.menubar.add_menu("Playlist", playlist_items)
        self.menu_item_refs["playlist_menu"] = playlist_items

        # View menu
        view_items = [
            {"label": "Show Playlist", "checkbutton": True, "variable": self.show_playlist_var,
             "command": self.toggle_playlist_visibility},
            {"label": "Show Browser", "checkbutton": True, "variable": self.show_browser_var,
             "command": self.toggle_browser_visibility},
            {"separator": True},
            {"label": "Always on Top", "checkbutton": True, "variable": self.always_on_top_var,
             "command": self.toggle_always_on_top}
        ]
        self.menubar.add_menu("View", view_items)

        # Tools menu
        # Audio device submenu will be built dynamically
        self.audio_device_items = []
        self._build_audio_device_menu_items()

        # Create audio device menu item with reference to the list
        audio_device_item = {"label": "Audio Device", "submenu": self.audio_device_items}

        tools_items = [
            audio_device_item,
            {"separator": True},
            {"label": "Preferences", "command": self.open_preferences}
        ]
        self.menubar.add_menu("Tools", tools_items)
        self.menu_item_refs["audio_device"] = audio_device_item

        # Help menu
        help_items = [
            {"label": "About", "command": self.open_about}
        ]
        self.menubar.add_menu("Help", help_items)

        # Initialize menu state
        self._update_menu_state()

    def _build_layout(self):
        # Main frame
        self.main_frame = ttk.Frame(self.root, padding=6, style="TFrame")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

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
            remove_callback=self._on_context_remove_song
        )
        self.playlist_view.pack(fill=tk.BOTH, expand=True)

        # Right: Browser view
        self.right_frame = ttk.Frame(self.main_frame, style="TFrame")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6,0))

        self.browser_view = BrowserView(self.right_frame, self.state, self.theme, tooltip_manager=self.tooltip_manager, status_callback=self._controls_status_event)
        self.browser_view.pack(fill=tk.BOTH, expand=True)

        # Link browser view to playlist view for drag and drop
        self.browser_view.set_playlist_view(self.playlist_view)

        # Middle: Buttons column
        self.mid_frame = ttk.Frame(self.main_frame, style="TFrame")
        self.mid_frame.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=6)

        # Create a container to center buttons vertically
        button_container = ttk.Frame(self.mid_frame, style="TFrame")
        button_container.pack(expand=True, fill=tk.BOTH)

        # Create another frame to center buttons horizontally within the container
        center_frame = ttk.Frame(button_container, style="TFrame")
        center_frame.pack(expand=True)

        # Get button colors from theme palette (already available in self.palette)
        btn_bg = self.palette.get("button_bg_color", self.palette.get("accent", "#0078d4"))
        btn_fg = self.palette.get("button_fg_color", "#ffffff")
        btn_hover = self.palette.get("button_hover", self.palette.get("accent_hover", "#106ebe"))

        ctk.CTkButton(center_frame, text="📂 Folder", command=self.browser_view.browse_folder, width=120,
                      fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover).pack(pady=6)
        ctk.CTkButton(center_frame, text="🎵 File", command=self.browser_view.browse_files, width=120,
                      fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover).pack(pady=6)
        ctk.CTkButton(center_frame, text="➕ Add", command=self.add_selected_to_playlist, width=120,
                      fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover).pack(pady=8)
        ctk.CTkButton(center_frame, text="⬇ Add Below", command=self.add_selected_below_playlist, width=120,
                      fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover).pack(pady=8)

        # Status bar with CustomTkinter
        # Use root background color instead of transparent for better theme support
        is_dark = self.settings.theme.lower() == 'dark'
        initial_bg = self.palette.get('bg', '#1E1E1E' if is_dark else '#FAFAFA')
        self.status_frame = ctk.CTkFrame(
            self.root,
            fg_color=initial_bg,
            bg_color=initial_bg,  # Match root background for seamless edges
            corner_radius=0  # No rounded corners on outer frame
        )
        self.status_frame.pack(
            side=tk.BOTTOM,
            fill=tk.X,
            padx=(12, 12),  # (left, right) - 6px left, 12px right
            pady=(0, 12)
        )

        # Status bar background - larger with more padding
        # Use status_bg from theme for better visibility, with more contrasting colors
        initial_status_bg = self.palette.get('status_bg', '#E8E8E8' if not is_dark else '#2A2A2A')
        initial_border = self.palette.get('status_border', '#D0D0D0' if not is_dark else '#3E3E3E')
        self.status_bg = ctk.CTkFrame(
            self.status_frame,
            corner_radius=6,
            fg_color=initial_status_bg,
            bg_color=initial_bg,  # Match parent frame for seamless corners
            border_color=initial_border,
            border_width=1  # Add border for better visibility
        )
        self.status_bg.pack(fill=tk.X, pady=(12, 0), padx=0, expand=True)

        # Status text with larger, more prominent styling
        self.status_var = tk.StringVar(value="")
        initial_status_fg = self.palette.get('status_fg', '#202020' if not is_dark else '#FFFFFF')
        self.status_label = ctk.CTkLabel(
            self.status_bg,
            textvariable=self.status_var,
            anchor="w",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=initial_status_fg,
            bg_color=initial_status_bg,
            justify="left",
            height=28
        )
        self.status_label.pack(side=tk.TOP, fill=tk.X, padx=12, pady=6)

        # Meta info with subtle but more visible styling
        self.meta_var = tk.StringVar(value="")
        initial_meta_fg = self.palette.get('status_meta_fg', '#505050' if not is_dark else '#E0E0E0')
        self.meta_label = ctk.CTkLabel(
            self.status_bg,
            textvariable=self.meta_var,
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color=initial_meta_fg,
            bg_color=initial_status_bg,
            justify="left",
            height=30
        )
        self.meta_label.pack(side=tk.TOP, fill=tk.X, padx=12, pady=(0, 8))

        # Bottom: Controls bar
        self.controls = ControlsBar(
            self.root,
            self.player,
            self.state,
            self.theme,
            self.playlist_view,
            tooltip_manager=self.tooltip_manager,
            status_callback=self._controls_status_event,
            settings=self.settings
        )
        self.controls.configure(padding=(0, 0, 0, 15))
        self.controls.pack(side=tk.BOTTOM, fill=tk.X)

    # ----------- STATUS: ControlsBar event dispatcher -----------
    def _controls_status_event(self, event_type, count=0):
        if event_type == "play":
            self._restore_status()
            self._update_menu_state()
            # Track info should be available while playing
            self._set_track_info_enabled(True)
        elif event_type == "pause":
            if self.status_var.get().startswith("Pause:"):
                self._restore_status()
            else:
                self._restore_status(prefix="Pause")
            self._update_menu_state()
            # Track info should remain available while paused
            self._set_track_info_enabled(True)
        elif event_type == "stop":
            if self.status_var.get():
                self.status_var.set("")
            self.meta_var.set("")
            self._update_menu_state()
            # Disable Track Information when nothing is playing/paused
            self._set_track_info_enabled(False)
        elif event_type in ("prev", "next"):
            self._restore_status()
            # Do not change Track Information availability on prev/next;
            # just keep playlist/menu state in sync.
            self._update_menu_state()
        elif event_type == "browsed_files" or event_type == "browsed_folder":
            self._set_temporary_status(f"Added {count} file(s) to Songs list")
        elif event_type == "added_to_playlist":
            if count > 0:
                self._set_temporary_status(f"Added {count} file(s) to the bottom of the playlist")
            else:
                self._set_temporary_status("No new files added to playlist (duplicates skipped)")
        elif event_type == "added_to_playlist_below":
            if count > 0:
                self._set_temporary_status(f"Added {count} file(s) below current track in playlist")
            else:
                self._set_temporary_status("No new songs were added to playlist (duplicates skipped)")

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
        except Exception:
            # Fail silently; menu state is not critical
            pass

    def _set_track_info_enabled(self, enabled: bool):
        """Enable or disable the Track Information menu item explicitly."""
        try:
            state = "normal" if enabled else "disabled"
            if "track_info" in self.menu_item_refs:
                self.menu_item_refs["track_info"]["state"] = state
        except Exception:
            pass

    # ---------- Checkbutton ----------
    def on_change(self, *args):
        self.state.play_on_double = self.play_on_double_var.get()

    # ---------- Menu / File actions ----------
    def open_file(self):
        path = filedialog.askopenfilename(parent=self.root, title="Open File",
                                         filetypes=[("Audio files", "*.mp3 *.wav *.flac *.ogg *.m4a"), ("All files", "*.*")])
        if not path:
            return
        self.state.playlist = [path]
        self.refresh_all()
        self._restore_status()

    def open_files(self):
        paths = filedialog.askopenfilenames(parent=self.root, title="Open Multiple Files",
                                            filetypes=[("Audio files", "*.mp3 *.wav *.flac *.ogg *.m4a"), ("All files", "*.*")])
        if not paths:
            return
        self.state.playlist = list(paths)
        self.refresh_all()
        self._restore_status()

    def open_folder(self):
        folder = filedialog.askdirectory(parent=self.root, title="Open Folder")
        if not folder:
            return
        self._load_files_into_playlist(folder)
        self._restore_status()

    def open_playlist(self):
        path = filedialog.askopenfilename(parent=self.root, title="Open Playlist",
                                          filetypes=[("M3U playlist", "*.m3u *.m3u8"), ("All files", "*.*")])
        if not path:
            return
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

        # Reload styles (standard Tkinter/TTK)
        self.theme.apply_to(self.root)

        # Update palette references
        self.palette = self.theme.palette
        self.tooltip_manager.palette = self.palette

        # Note: theme.apply_to() already sets root window background
        # We close dropdown menus first to prevent errors when it tries to update child widgets

        # Determine theme mode for color calculations
        is_dark = self.settings.theme.lower() == 'dark'

        # Force root window background update to fix corner artifacts
        root_bg = self.palette.get('bg', '#1E1E1E' if is_dark else '#FAFAFA')
        try:
            # Use direct Tk call to ensure root background is updated everywhere
            self.root.tk.call(self.root._w, 'configure', '-bg', root_bg)
            # Also force update the root window immediately
            self.root.update_idletasks()
        except:
            pass

        # Update TFrame style to fix padding areas (main_frame padding=6)
        try:
            style = ttk.Style(self.root)
            style.configure("TFrame", background=root_bg)
        except:
            pass

        # Update sidebar buttons specifically
        btn_bg = self.palette.get("button_bg_color", self.palette.get("accent", "#0078d4"))
        btn_fg = self.palette.get("button_fg_color", "#ffffff")
        btn_hover = self.palette.get("button_hover", self.palette.get("accent_hover", "#106ebe"))

        # Find all buttons in the nested frame structure
        def update_buttons_in_frame(frame):
            for widget in frame.winfo_children():
                if isinstance(widget, ctk.CTkButton):
                    # Ensure button background matches surrounding frame
                    frame_bg = self.palette.get("bg", "#1E1E1E" if self.settings.theme == "Dark" else "#FAFAFA")
                    widget.configure(fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover, bg_color=frame_bg)
                elif isinstance(widget, ttk.Frame):
                    # Recursively search in nested frames
                    update_buttons_in_frame(widget)

        update_buttons_in_frame(self.mid_frame)

        # Update controls
        self.controls.update_theme()

        # Update PlaylistView colors (handled by styles but might need refresh)
        self.playlist_view.update_theme()
        if hasattr(self.browser_view, 'update_theme'):
             self.browser_view.update_theme()

        # Update custom menu bar theme
        if hasattr(self, 'menubar') and self.menubar:
            self.menubar.update_theme()

        # Update status bar colors
        if hasattr(self, 'status_bg'):
            # Use status_bg from theme with more contrasting colors for better visibility
            if is_dark:
                status_bg_color = self.palette.get('status_bg', '#2A2A2A')  # Lighter than bg for contrast
                status_text_color = self.palette.get('status_fg', '#FFFFFF')
                status_meta_color = self.palette.get('status_meta_fg', '#E0E0E0')
                status_border_color = self.palette.get('status_border', '#3E3E3E')
            else:
                # Light mode: use a darker gray for clear contrast against light background
                status_bg_color = self.palette.get('status_bg', '#E8E8E8')  # Darker gray for visibility
                status_text_color = self.palette.get('status_fg', '#202020')
                status_meta_color = self.palette.get('status_meta_fg', '#505050')
                status_border_color = self.palette.get('status_border', '#D0D0D0')

            frame_bg = self.palette.get('bg', '#1E1E1E' if is_dark else '#FAFAFA')

            # Update parent frame background - ensure it matches root background
            # Both fg_color and bg_color must match root for seamless edges
            self.status_frame.configure(
                fg_color=frame_bg,
                bg_color=frame_bg  # Critical: bg_color affects frame edges/corners
            )

            # Update status bar frame with subtle border for better visibility
            # bg_color is critical for rounded corners - must match parent frame
            self.status_bg.configure(
                fg_color=status_bg_color,  # Use status_bg for better visibility
                bg_color=frame_bg,  # This controls corner colors - must match parent
                border_color=status_border_color,  # Subtle border for separation
                border_width=1  # Add border for better visibility
            )

            # Update status and meta labels
            self.status_label.configure(
                text_color=status_text_color,
                bg_color=status_bg_color
            )
            self.meta_label.configure(
                text_color=status_meta_color,
                bg_color=status_bg_color
            )

            # Force update the frames to prevent visual glitches
            self.status_frame.update_idletasks()
            self.status_bg.update_idletasks()

        # Update main_frame background to ensure padding areas are correct
        if hasattr(self, 'main_frame'):
            try:
                self.main_frame.configure(style="TFrame")
            except:
                pass

        # Trigger refresh to redraw
        self.refresh_all()

    def open_preferences(self):
        original_theme = self.settings.theme

        def on_apply(selected_theme):
            # Update settings with lowercase theme
            self.settings.theme = selected_theme

            # Reload theme
            self.theme.reload()

            # Use centralized update method
            self.update_theme_colors()

        PreferencesWindow(self.root, self.settings, self.theme, on_apply=on_apply)

    def open_media_info(self):
        """Open media information dialog for the currently selected track."""
        if self.state.current_index is None or not self.state.playlist:
            # Create custom silent dialog instead of messagebox
            info_window = tk.Toplevel(self.root)
            info_window.title("Media Information")
            info_window.geometry("300x100")
            info_window.resizable(False, False)
            info_window.transient(self.root)
            info_window.grab_set()

            content_frame = ttk.Frame(info_window, padding=20)
            content_frame.pack(fill=tk.BOTH, expand=True)

            ttk.Label(content_frame, text="No track is playing.").pack(pady=10)
            ttk.Button(content_frame, text="OK", command=info_window.destroy).pack()

            info_window.bind("<Return>", lambda e: info_window.destroy())
            info_window.bind("<Escape>", lambda e: info_window.destroy())

            center_window(info_window, self.root)
            return

        current_track = self.state.playlist[self.state.current_index]
        MediaInfoWindow(self.root, current_track, theme_manager=self.theme)

    def open_about(self):
        # Create custom dialog using CustomTkinter
        about_window = ctk.CTkToplevel(self.root)
        about_window.title("About")
        about_window.geometry("400x250")
        about_window.resizable(False, False)

        # Remove icon from About dialog
        try:
            about_window.iconbitmap("assets/transparent.ico")
        except:
            pass

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

        # Title
        title_label = ctk.CTkLabel(
            content_frame,
            text="Tango Studio",
            font=("Segoe UI", 24, "bold"),
            text_color=accent_color
        )
        title_label.pack(pady=(0, 15))

        # Description
        desc_label = ctk.CTkLabel(
            content_frame,
            text="A modern audio player with custom themes and intuitive controls.",
            font=("Segoe UI", 14),
            text_color=fg_color,
            wraplength=350
        )
        desc_label.pack(pady=5)

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

        center_window(about_window, self.root)

    def _on_quit(self):
        logger.info("Shutting down Tango Studio")
        # Save geometry
        try:
            self.settings.window_geometry = self.root.geometry()
            self.settings.save()
        except Exception:
            logger.error("Failed to save window geometry on exit", exc_info=True)
        # Stop player
        try:
            self.player.stop()
        except Exception:
            logger.error("Failed to stop player on exit", exc_info=True)
        # Destroy window
        try:
            self.root.destroy()
        except Exception:
            logger.error("Failed to destroy window on exit", exc_info=True)
        logger.info("Tango Studio shut down complete")

    # ---------- Playlist operations (menu) ----------
    def shuffle_playlist(self):
        random.shuffle(self.state.playlist)
        if self.state.current_index is not None:
            current_path = self.state.playlist[self.state.current_index]
            # find new index
            try:
                self.state.current_index = self.state.playlist.index(current_path)
            except ValueError:
                self.state.current_index = None
        self.refresh_all()

    def clear_playlist(self):
        if messagebox.askyesno("Clear Playlist", "Clear all entries from the playlist?", parent=self.root):
            self.state.playlist.clear()
            self.state.current_index = None
            self.refresh_all()

    # ---------- Repeat Mode ----------
    def _set_repeat_mode(self, mode):
        """Set the repeat mode (none, one, all)."""
        self.state.repeat_mode = mode
        self._set_temporary_status(f"Repeat: {mode.title()}")

    # ---------- Playlist Operations ----------
    def remove_selected_from_playlist(self):
        """Remove selected song from playlist."""
        if not self.playlist_view or not self.playlist_view.tree:
            return
        selected = self.playlist_view.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a song to remove.", parent=self.root)
            return

        for item in selected:
            idx = self.playlist_view.tree.index(item)
            if 0 <= idx < len(self.state.playlist):
                if self.state.current_index == idx:
                    self.state.current_index = None
                del self.state.playlist[idx]

        self.refresh_all()
        self._set_temporary_status(f"Removed {len(selected)} song(s)")

    def move_selected_up(self):
        """Move selected song up in playlist."""
        if not self.playlist_view or not self.playlist_view.tree:
            return
        selected = self.playlist_view.tree.selection()
        if not selected or len(selected) != 1:
            messagebox.showwarning("Selection Error", "Please select exactly one song to move.", parent=self.root)
            return

        idx = self.playlist_view.tree.index(selected[0])
        if idx > 0 and idx < len(self.state.playlist):
            self.state.playlist[idx], self.state.playlist[idx-1] = self.state.playlist[idx-1], self.state.playlist[idx]
            if self.state.current_index == idx:
                self.state.current_index = idx - 1
            elif self.state.current_index == idx - 1:
                self.state.current_index = idx
            self.refresh_all()

    def move_selected_down(self):
        """Move selected song down in playlist."""
        if not self.playlist_view or not self.playlist_view.tree:
            return
        selected = self.playlist_view.tree.selection()
        if not selected or len(selected) != 1:
            messagebox.showwarning("Selection Error", "Please select exactly one song to move.", parent=self.root)
            return

        idx = self.playlist_view.tree.index(selected[0])
        if idx >= 0 and idx < len(self.state.playlist) - 1:
            self.state.playlist[idx], self.state.playlist[idx+1] = self.state.playlist[idx+1], self.state.playlist[idx]
            if self.state.current_index == idx:
                self.state.current_index = idx + 1
            elif self.state.current_index == idx + 1:
                self.state.current_index = idx
            self.refresh_all()

    def sort_playlist_by_title(self):
        """Sort playlist by title (from metadata) or filename."""
        if not self.state.playlist:
            messagebox.showinfo("Empty Playlist", "Playlist is empty.", parent=self.root)
            return

        from ui.utils import get_display_title

        current_path = self.state.playlist[self.state.current_index] if self.state.current_index is not None else None
        self.state.playlist.sort(key=lambda x: get_display_title(x).lower())

        if current_path:
            try:
                self.state.current_index = self.state.playlist.index(current_path)
            except ValueError:
                self.state.current_index = None

        self.refresh_all()
        self._set_temporary_status("Playlist sorted by title")

    def sort_playlist_by_artist(self):
        """Sort playlist by artist (from metadata) or filename."""
        if not self.state.playlist:
            messagebox.showinfo("Empty Playlist", "Playlist is empty.", parent=self.root)
            return

        def get_artist(file_path):
            """Get artist from metadata or return empty string."""
            try:
                audio = MutagenFile(file_path, easy=True)
                if audio and audio.tags:
                    artist = audio.get('artist', [''])[0]
                    return artist.lower() if artist else ''
            except Exception:
                pass
            return ''

        current_path = self.state.playlist[self.state.current_index] if self.state.current_index is not None else None
        self.state.playlist.sort(key=get_artist)

        if current_path:
            try:
                self.state.current_index = self.state.playlist.index(current_path)
            except ValueError:
                self.state.current_index = None

        self.refresh_all()
        self._set_temporary_status("Playlist sorted by artist")

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
        """Toggle browser visibility and mid_frame buttons."""
        if self.show_browser_var.get():
            # Restore right frame and middle buttons
            self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6,0))
            self.browser_view.pack(fill=tk.BOTH, expand=True)
            self.mid_frame.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=6)
        else:
            # Hide browser area entirely so playlist uses full width
            self.browser_view.pack_forget()
            self.right_frame.pack_forget()
            self.mid_frame.pack_forget()
        # Persist setting
        if hasattr(self, "settings"):
            try:
                self.settings.show_browser = self.show_browser_var.get()
                self.settings.save()
            except Exception:
                pass

    def toggle_always_on_top(self):
        """Toggle always on top window attribute."""
        self.root.attributes('-topmost', self.always_on_top_var.get())

    # ---------- Middle Buttons: Browse Song, Add, Add below ----------
    def add_selected_to_playlist(self):
        self.browser_view.add_selected_to_playlist()
        self.refresh_all()

    def add_selected_below_playlist(self):
        self.browser_view.add_selected_below_playlist()
        self.refresh_all()

    # ---------- Handlers for custom events from subcomponents ----------
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
            if p not in self.state.playlist:
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
            # fallback to currently selected
            sels = self.playlist_view.tree.selection()
            if not sels:
                return
            idx = self.playlist_view.tree.index(sels[0])

        if 0 <= idx < len(self.state.playlist):
            self.state.current_index = idx
            self.refresh_all()
            # fade_out behavior not implemented; just play
            self.controls._on_play()
            self._restore_status()

    def _on_playlist_select(self, index):
        """
        Called when the user selects a row in the playlist (single-click).
        Keeps state.current_index in sync with UI selection.
        Does NOT start playback — double-click or menu actions do that.
        """
        if index is None:
            return
        if 0 <= index < len(self.state.playlist):
            self.state.current_index = index

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
            MediaInfoWindow(self.root, track, theme_manager=self.theme)

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



    # ---------- Helper to load folder into playlist (open_folder) ----------
    def _load_files_into_playlist(self, folder):
        if not os.path.isdir(folder):
            return
        exts = (".mp3", ".wav", ".flac", ".ogg", ".m4a")
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
            self._set_temporary_status("Repeat: None")
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
                    self.player.stop()
                except Exception:
                    pass

    # ---------- Status bar helpers ----------
    def _set_temporary_status(self, message, duration=3000):
        """Show temporary status message, then restore now-playing."""
        self.status_var.set(message)

        # Cancel prior restore timer if any
        if hasattr(self, "_status_restore_job"):
            self.root.after_cancel(self._status_restore_job)

        # Restore after timeout
        self._status_restore_job = self.root.after(duration, self._restore_status)

    def _restore_status(self, prefix="Playing"):
        """
        Restore playing status and populate metadata line.

        Uses mutagen to read tags (title, artist), duration and bitrate.
        Caches results per-file for responsiveness.
        """
        idx = self.state.current_index
        if idx is None or idx >= len(self.state.playlist):
            self.status_var.set("")
            self.meta_var.set("")
            return

        path = self.state.playlist[idx]
        name = os.path.basename(path)

        # Prefer tag title if available, else filename
        meta = self._meta_cache.get(path)
        if meta is None:
            meta = self._read_metadata(path)
            # store even empty dict to avoid repeated failed reads
            self._meta_cache[path] = meta

        title = meta.get("title") or name
        artist = meta.get("artist")
        duration_s = meta.get("duration")
        bitrate = meta.get("bitrate")
        fmt = meta.get("format")

        if artist:
            self.status_var.set(f"{prefix}: {title} — {artist}")
        else:
            self.status_var.set(f"{prefix}: {title}")

        # Build metadata line parts
        parts = []
        if duration_s:
            parts.append(f"{int(duration_s)//60:02d}:{int(duration_s)%60:02d}")
        if bitrate:
            parts.append(f"{bitrate} kbps")
        if fmt:
            parts.append(fmt.upper())

        self.meta_var.set(" • ".join(parts))

    def _read_metadata(self, path):
        """
        Use mutagen to extract: title, artist, duration (s), bitrate (kbps), format.
        Returns a dict with keys possibly missing.
        """
        md = {}
        try:
            f = MutagenFile(path, easy=True)
            if f is None:
                return md
            # title/artist (easy tags)
            title = None
            artist = None
            try:
                title = f.get("title", [None])[0]
                artist = f.get("artist", [None])[0]
            except Exception:
                # some formats expose tags differently; try generic tags
                tags = getattr(f, "tags", None)
                if tags:
                    title = title or tags.get("TITLE") or tags.get("\xa9nam")
                    artist = artist or tags.get("ARTIST") or tags.get("\xa9ART")
                    # tags may be lists, extract first string
                    if isinstance(title, (list, tuple)):
                        title = title[0]
                    if isinstance(artist, (list, tuple)):
                        artist = artist[0]

            # duration in seconds
            duration = None
            try:
                duration = int(f.info.length) if getattr(f, "info", None) and getattr(f.info, "length", None) else None
            except Exception:
                duration = None

            # bitrate (some formats)
            bitrate = None
            try:
                if getattr(f, "info", None) and getattr(f.info, "bitrate", None):
                    # mutagen gives bits per second for many formats
                    bitrate = int(getattr(f.info, "bitrate") // 1000)
            except Exception:
                bitrate = None

            # format: mime or extension
            fmt = None
            try:
                # Try to infer format from class name or filename extension
                cls_name = f.__class__.__name__.lower()
                if "mp3" in cls_name:
                    fmt = "mp3"
                elif "flac" in cls_name:
                    fmt = "flac"
                elif "ogg" in cls_name:
                    fmt = "ogg"
                elif "m4a" in cls_name or "mp4" in cls_name:
                    fmt = "m4a"
                else:
                    # fallback to file extension
                    fmt = os.path.splitext(path)[1].lstrip(".").lower()
            except Exception:
                fmt = None

            if title:
                md["title"] = str(title)
            if artist:
                md["artist"] = str(artist)
            if duration:
                md["duration"] = int(duration)
            if bitrate:
                md["bitrate"] = int(bitrate)
            if fmt:
                md["format"] = fmt
        except Exception:
            # don't let metadata errors break the UI
            return md

        return md

    # ---------- Start UI mainloop ----------
    def start(self):
        self.root.mainloop()
