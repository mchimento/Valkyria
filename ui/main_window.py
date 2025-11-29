"""
This module composes the smaller UI components (PlaylistView, BrowserView, ControlsBar)
and wires them to the AppState, ThemeManager, AudioPlayer and Settings.
"""

import logging
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import random

from audio import m3u as m3u_module

from ui.playlist_view import PlaylistView
from ui.browser_view import BrowserView
from ui.controls import ControlsBar
from ui.preferences_window import PreferencesWindow
from ui.tooltips import TooltipManager
from ui.media_info_window import MediaInfoWindow
from ui.utils import center_window

from mutagen import File as MutagenFile

logger = logging.getLogger(__name__)

class MainWindow:
    def __init__(self, state, theme, player, settings):
        self.state = state
        self.theme = theme
        self.player = player
        self.settings = settings

        # Root window
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

        # Build UI
        self._build_menu()
        self._build_layout()

        # Bind custom events from subcomponents
        self.root.bind("<<BrowserAddSelected>>", self._on_browser_add_selected)
        self.root.bind("<<PlaylistDouble>>", self._on_playlist_double)
        self.root.bind("<<OpenPlaylist>>", lambda e: self.open_playlist())
        self.root.bind("<<SavePlaylist>>", lambda e: self.save_playlist_as())

        # Keep UI in sync initially
        self.refresh_all()

        # Ensure player stopped on exit and save geometry
        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)

    # ---------- Build UI ----------
    def _build_menu(self):
        menubar = tk.Menu(self.root)
        # File menu
        self.filemenu = tk.Menu(menubar, tearoff=0)
        self.filemenu.add_command(label="Open File...", command=self.open_file, underline=0)
        self.filemenu.add_command(label="Open Multiple Files...", command=self.open_files, underline=5)
        self.filemenu.add_command(label="Open Folder...", command=self.open_folder, underline=5)
        self.filemenu.add_command(label="Open Playlist (M3U/M3U8)...", command=self.open_playlist, underline=5)
        self.filemenu.add_separator()
        self.filemenu.add_command(label="Save Playlist", command=self.save_playlist, underline=0)
        self.filemenu.add_command(label="Save Playlist As...", command=self.save_playlist_as, underline=14)
        self.filemenu.add_separator()
        self.filemenu.add_command(label="Quit", command=self._on_quit, underline=0)
        menubar.add_cascade(label="Media", menu=self.filemenu, underline=0)

        # Store indices for save menu items (to enable/disable them)
        self.save_playlist_index = 5  # Index of "Save Playlist" in filemenu
        self.save_playlist_as_index = 6  # Index of "Save Playlist As..." in filemenu

        # Playlist menu
        playlist_menu = tk.Menu(menubar, tearoff=0)
        playlist_menu.add_command(label="Shuffle", command=self.shuffle_playlist, underline=0)
        playlist_menu.add_separator()
        playlist_menu.add_command(label="Clear Playlist", command=self.clear_playlist, underline=0)
        menubar.add_cascade(label="Playlist", menu=playlist_menu, underline=0)

        # Tools menu
        # Tools menu
        self.toolsmenu = tk.Menu(menubar, tearoff=0)
        self.toolsmenu.add_command(label="Track Information", command=self.open_media_info, underline=0)
        self.toolsmenu.add_separator()

        # Audio Device submenu
        self.audio_device_var = tk.StringVar()
        self.audio_device_menu = tk.Menu(self.toolsmenu, tearoff=0)
        self._build_audio_device_menu()
        self.toolsmenu.add_cascade(label="Audio Device", menu=self.audio_device_menu, underline=0)

        self.toolsmenu.add_separator()
        self.toolsmenu.add_command(label="Preferences", command=self.open_preferences, underline=0)
        menubar.add_cascade(label="Tools", menu=self.toolsmenu, underline=0)

        # Store index for track info menu item
        self.track_info_index = 0

        # Help menu
        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="About", command=self.open_about, underline=0)
        menubar.add_cascade(label="Help", menu=helpmenu, underline=0)

        self.root.config(menu=menubar)

        # Initialize menu state
        self._update_menu_state()

    def _build_layout(self):
        # Main frame
        main = ttk.Frame(self.root, padding=6, style="TFrame")
        main.pack(fill=tk.BOTH, expand=True)

        # Left: Playlist view
        left_frame = ttk.Frame(main, style="TFrame")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,6))

        self.playlist_view = PlaylistView(left_frame, self.state, tooltip_manager=self.tooltip_manager, select_callback=self._on_playlist_select, change_callback=self._update_menu_state)
        self.playlist_view.pack(fill=tk.BOTH, expand=True)

        # Right: Browser view
        right_frame = ttk.Frame(main, style="TFrame")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6,0))

        self.browser_view = BrowserView(right_frame, self.state, tooltip_manager=self.tooltip_manager, status_callback=self._controls_status_event)
        self.browser_view.pack(fill=tk.BOTH, expand=True)

        # Middle: Buttons column
        mid_frame = ttk.Frame(main, style="TFrame")
        mid_frame.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=6)

        ttk.Button(mid_frame, text="Browse Folder", command=self.browser_view.browse_folder).pack(pady=6)
        ttk.Button(mid_frame, text="Browse Song", command=self.browser_view.browse_files).pack(pady=6)
        ttk.Button(mid_frame, text="<- Add", command=self.add_selected_to_playlist).pack(pady=8)
        ttk.Button(mid_frame, text="<- Add below", command=self.add_selected_below_playlist).pack(pady=8)

        self.play_on_double_var = tk.BooleanVar(value=self.state.play_on_double)
        self.play_on_double_var.trace_add('write', self.on_change)
        ttk.Checkbutton(mid_frame, text="Play song on double-click", variable=self.play_on_double_var, style='TCheckbutton').pack(pady=5)

        # Status bar
        self.status_frame = ttk.Frame(self.root, style="StatusBar.TFrame")
        self.status_frame.configure(padding=(0, 10, 0, 0))
        self.status_frame.pack(
            side=tk.BOTTOM,
            fill=tk.X,
            padx=6,
            pady=(0, 12)
        )

        self.meta_var = tk.StringVar(value="")
        self.meta_label = ttk.Label(
            self.status_frame,
            textvariable=self.meta_var,
            anchor="w",
            style="StatusBarMeta.TLabel"
        )
        self.meta_label.pack(side=tk.BOTTOM, anchor="w", padx=4, pady=(4, 2))

        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(
            self.status_frame,
            textvariable=self.status_var,
            anchor="w",
            style="StatusBarMain.TLabel"
        )
        self.status_label.pack(side=tk.BOTTOM, anchor="w", padx=4, pady=(4, 2))

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
        elif event_type == "pause":
            if self.status_var.get().startswith("Pause:"):
                self._restore_status()
            else:
                self._restore_status(prefix="Pause")
            self._update_menu_state()
        elif event_type == "stop":
            if self.status_var.get():
                self.status_var.set("")
            self.meta_var.set("")
            self._update_menu_state()
        elif event_type in ("prev", "next"):
            self._restore_status()
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
        state = tk.NORMAL if has_songs else tk.DISABLED
        self.filemenu.entryconfig(self.save_playlist_index, state=state)
        self.filemenu.entryconfig(self.save_playlist_as_index, state=state)

        # Track info enabled if playing or paused
        is_playing = self.player.is_playing()
        is_paused = self.player.is_paused()
        track_info_state = tk.NORMAL if (is_playing or is_paused) else tk.DISABLED
        self.toolsmenu.entryconfig(self.track_info_index, state=track_info_state)

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

    def _build_audio_device_menu(self):
        """Populate the Audio Device submenu with available devices."""
        # Clear existing items
        self.audio_device_menu.delete(0, tk.END)

        try:
            devices = self.player.get_audio_devices()

            if not devices:
                self.audio_device_menu.add_command(label="No devices found", state=tk.DISABLED)
                return

            # Set default device as first item
            default_device_id, default_device_name = devices[0] if devices else ('default', 'Default Audio Device')
            self.audio_device_var.set(default_device_id)

            # Add each device as a menu item
            for i, (device_id, device_name) in enumerate(devices):
                # Mark the first device as system default
                label = device_name if i > 0 else f"{device_name} (system default)"
                self.audio_device_menu.add_radiobutton(
                    label=label,
                    variable=self.audio_device_var,
                    value=device_id,
                    command=lambda dev_id=device_id: self.set_audio_device(dev_id)
                )
        except Exception as e:
            logger.error(f"Failed to build audio device menu: {e}")
            self.audio_device_menu.add_command(label="Error loading devices", state=tk.DISABLED)

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

    def open_preferences(self):
        original_theme = self.settings.theme

        def on_apply(selected_theme):
            # Reload theme
            self.theme.reload()

            # Apply globally to the main window
            self.theme.apply_to(self.root)

            # Update palette for tooltips and controls
            self.palette = self.theme.palette
            self.tooltip_manager.palette = self.palette

            # Refresh playlist highlight and UI
            self.refresh_all()

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
        # Create custom dialog to avoid Windows system sound
        about_window = tk.Toplevel(self.root)
        about_window.title("About")
        about_window.geometry("400x200")
        about_window.resizable(False, False)

        # Center the window
        about_window.transient(self.root)
        about_window.grab_set()

        # Content frame
        content_frame = ttk.Frame(about_window, padding=20)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            content_frame,
            text="Tango Studio",
            font=("TkDefaultFont", 16, "bold")
        )
        title_label.pack(pady=(0, 10))

        # Description
        desc_label = ttk.Label(
            content_frame,
            text="A modern audio player.",
            justify=tk.CENTER
        )
        desc_label.pack(pady=5)

        # Version
        version_label = ttk.Label(
            content_frame,
            text="Version 1.0",
            justify=tk.CENTER
        )
        version_label.pack(pady=5)

        # OK button
        ok_button = ttk.Button(
            content_frame,
            text="OK",
            command=about_window.destroy
        )
        ok_button.pack(pady=(20, 0))
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
            # Highlight will be refreshed by playlist_view.refresh when needed


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
        Default behavior: advance to next track if available, otherwise set status.
        """
        if self.state.current_index is None:
            return
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
