"""
This module composes the smaller UI components (PlaylistView, BrowserView, ControlsBar)
and wires them to the AppState, ThemeManager, AudioPlayer and Settings.
"""

import logging
import os
import io
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
import threading
from app.paths import get_resource_path
from audio.metadata import get_metadata, get_display_title, get_best_artwork, analyze_bpm, write_bpm, metadata_extractor
from PIL import Image, ImageTk, ImageDraw, ImageFont

from audio import m3u as m3u_module, playback
from ui.playlist_view import PlaylistView
from ui.browser_view import BrowserView
from ui.controls import ControlsBar
from ui.preferences_window import PreferencesWindow
from ui.tooltips import TooltipManager
from ui.media_info_window import MediaInfoWindow
from ui.booklet_viewer import BookletViewer
from ui.utils import center_window
from ui.custom_menu_bar import CustomMenuBar

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

        # Global click handler to clear playlist selection when clicking outside
        self.root.bind_all("<Button-1>", self._on_global_click, add="+")

        # Keep UI in sync initially
        self.refresh_all()
        self._update_track_info_state_from_player()

        # Ensure player stopped on exit and save geometry
        self.root.protocol("WM_DELETE_WINDOW", self._on_quit)

        # Store current artwork image reference
        self.current_artwork_image = None
        self.current_artwork_photo = None

        # Register as BPM listener to refresh status when BPM is calculated
        metadata_extractor.register_bpm_listener(self._on_bpm_updated)

    def _create_placeholder_image(self):
        """Create a placeholder image with music note symbol."""
        import platform

        placeholder_image = Image.new('RGBA', (100, 100), (0, 0, 0, 0))  # transparent background
        draw = ImageDraw.Draw(placeholder_image)

        # Get theme color for the symbol
        text_color = self.palette.get('status_meta_fg', '#E0E0E0')

        # Try different fonts based on platform
        system = platform.system().lower()
        font = None

        # Try platform-specific fonts first
        if system == "windows":
            font_paths = [
                r"C:\Windows\Fonts\seguisym.ttf",  # Segoe UI Symbol
                r"C:\Windows\Fonts\arial.ttf",     # Arial
                r"C:\Windows\Fonts\tahoma.ttf",    # Tahoma
            ]
        elif system == "darwin":  # macOS
            font_paths = [
                "/System/Library/Fonts/Apple Symbols.ttf",
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Arial.ttf",
            ]
        else:  # Linux and others
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/TTF/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ]

        # Try font paths
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, 48)
                break
            except (OSError, IOError):
                continue

        # If no font path worked, try common font names
        if font is None:
            common_fonts = ["Arial", "Helvetica", "DejaVu Sans", "Liberation Sans", "FreeSans"]
            for font_name in common_fonts:
                try:
                    font = ImageFont.truetype(font_name, 48)
                    break
                except (OSError, IOError):
                    continue

        # Ultimate fallback
        if font is None:
            font = ImageFont.load_default()

        draw.text((50, 45), "♫", fill=text_color, font=font, anchor="mm")  # Two quavers

        ctk_image = ctk.CTkImage(placeholder_image, size=(100, 100))
        return ctk_image, placeholder_image

    def _on_bpm_updated(self, filepath):
        """Handle BPM update notifications by refreshing status if current track matches."""
        try:
            # Check if the updated file is currently playing track
            idx = self.state.current_index
            if idx is not None and idx < len(self.state.playlist):
                current_path = self.state.playlist[idx]
                if current_path == filepath:
                    # Use _update_meta_with_temp_bpm instead of _restore_status to preserve button states
                    self._update_meta_with_temp_bpm()
        except Exception:
            # Fail silently - BPM updates are not critical
            pass

    def _update_artwork(self, filepath):
        """Update the artwork display for a given file."""
        try:
            # Get artwork data using the fallback hierarchy
            artwork_data = get_best_artwork(filepath)

            if artwork_data:
                # Load image from bytes
                image = Image.open(io.BytesIO(artwork_data))

                # Resize to fit the artwork frame (100x100)
                image = image.resize((100, 100), Image.Resampling.LANCZOS)

                # Convert to CTkImage for CustomTkinter compatibility
                ctk_image = ctk.CTkImage(image, size=(100, 100))

                # Update the label to show the image
                self.artwork_label.configure(image=ctk_image, text="")
                self.artwork_label.image = ctk_image  # Keep a reference

                # Store reference to prevent garbage collection
                self.current_artwork_photo = ctk_image
                self.current_artwork_image = image
            else:
                # No artwork found, create music note placeholder image
                ctk_image, placeholder_image = self._create_placeholder_image()

                self.artwork_label.configure(image=ctk_image, text="")
                self.artwork_label.image = ctk_image

                self.current_artwork_photo = ctk_image
                self.current_artwork_image = placeholder_image

        except Exception:
            # On error, also show music note placeholder
            ctk_image, placeholder_image = self._create_placeholder_image()

            self.artwork_label.configure(image=ctk_image, text="")
            self.artwork_label.image = ctk_image

            self.current_artwork_photo = ctk_image
            self.current_artwork_image = placeholder_image

    def _on_bpm_button_click(self):
        """Handle single BPM button click based on current state."""
        try:
            idx = self.state.current_index
            if idx is None or idx >= len(self.state.playlist):
                return

            filepath = self.state.playlist[idx]

            if self.bpm_button_state == "analyze":
                # Start BPM analysis
                self.bpm_button_state = "analyzing"
                self.btn_bpm.configure(state="disabled", text="Analyzing...")

                # Start BPM analysis in background thread
                thread = threading.Thread(target=self._analyze_bpm_worker, args=(filepath,), daemon=True)
                thread.start()

            elif self.bpm_button_state == "save":
                # Save BPM to file
                if self.current_temp_bpm is not None:
                    self.bpm_button_state = "saving"
                    self.btn_bpm.configure(state="disabled", text="Saving...")

                    # Start save operation in background thread
                    thread = threading.Thread(target=self._save_bpm_worker, args=(filepath, self.current_temp_bpm), daemon=True)
                    thread.start()

        except Exception as e:
            logger.error(f"Error in BPM button click: {e}")
            # Reset to analyze state on error
            self.bpm_button_state = "analyze"
            self.btn_bpm.configure(state="normal", text="Analyze BPM")

    def _analyze_bpm_worker(self, filepath):
        """Worker function to analyze BPM in background."""
        try:
            analyzed_bpm = analyze_bpm(filepath)

            # Update UI in main thread
            self.root.after(0, self._on_bpm_analysis_complete, filepath, analyzed_bpm)

        except Exception as e:
            logger.error(f"Error in BPM analysis worker: {e}")
            self.root.after(0, self._reset_bpm_button_to_analyze)

    def _on_bpm_analysis_complete(self, filepath, bpm_value):
        """Handle BPM analysis completion."""
        try:
            if bpm_value is not None:
                # Store temporary BPM value
                self.current_temp_bpm = bpm_value

                # Update metadata cache temporarily (don't write to file)
                metadata_extractor._cache[filepath]['bpm'] = bpm_value

                # Update meta label to include the temporary BPM
                self._update_meta_with_temp_bpm()

                # Change button to Save state
                self.bpm_button_state = "save"
                self.btn_bpm.configure(state="normal", text="Save BPM")
            else:
                # Analysis failed, reset to analyze state
                self._reset_bpm_button_to_analyze()
                self._set_temporary_status("BPM analysis failed")

        except Exception as e:
            logger.error(f"Error handling BPM analysis completion: {e}")
            self._reset_bpm_button_to_analyze()

    def _reset_bpm_button_to_analyze(self):
        """Reset BPM button back to analyze state."""
        self.bpm_button_state = "analyze"
        self.btn_bpm.configure(state="normal", text="Analyze BPM")

    def _update_meta_with_temp_bpm(self):
        """Update the meta label to include temporary BPM without calling _restore_status."""
        try:
            idx = self.state.current_index
            if idx is None or idx >= len(self.state.playlist):
                return

            path = self.state.playlist[idx]
            meta = get_metadata(path)

            duration_s = meta.get("duration_s")
            bitrate = meta.get("bitrate")
            bpm = meta.get("bpm")  # This will now include the temporary BPM from cache

            # Build metadata line parts (duration, bitrate, bpm, format)
            parts = []
            if duration_s:
                parts.append(f"{int(duration_s)//60:02d}:{int(duration_s)%60:02d}")
            if bitrate:
                parts.append(f"{bitrate} kbps")
            if bpm:
                bpm_str = f" • {bpm} BPM"
            else:
                bpm_str =  " • BPM info missing"

            self.meta_var.set(" • ".join(parts) + bpm_str)

            # Notify BPM listeners to update playlist
            metadata_extractor._notify_bpm_listeners(path)

        except Exception as e:
            logger.error(f"Error updating meta with temporary BPM: {e}")

    def _save_bpm_worker(self, filepath, bpm_value):
        """Worker function to save BPM to file metadata."""
        try:
            success = write_bpm(filepath, bpm_value)

            # Update UI in main thread
            self.root.after(0, self._on_bpm_save_complete, filepath, bpm_value, success)

        except Exception as e:
            logger.error(f"Error in BPM save worker: {e}")
            self.root.after(0, self._reset_bpm_button_to_analyze)

    def _on_bpm_save_complete(self, filepath, bpm_value, success):
        """Handle BPM save completion."""
        try:
            if success:
                # Clear temporary BPM since it's now saved
                self.current_temp_bpm = None

                # Update metadata cache to reflect saved BPM
                metadata_extractor.update_cache(filepath)

                # Update UI to show the saved BPM
                self._restore_status()

                # Hide BPM control frame since BPM is now saved
                self.bpm_control_frame.pack_forget()

                # Show success message
                self._set_temporary_status(f"BPM value saved to file")
            else:
                # Save failed, reset to save state
                self.bpm_button_state = "save"
                self.btn_bpm.configure(state="normal", text="Save BPM")
                self._set_temporary_status("Failed to save BPM to file")

        except Exception as e:
            logger.error(f"Error handling BPM save completion: {e}")
            self._reset_bpm_button_to_analyze()

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
        self.play_on_double_var = tk.BooleanVar(value=bool(getattr(self.settings, "play_on_double", False)))
        self.repeat_mode_var = tk.StringVar(value="none")
        self.audio_device_var = tk.StringVar()

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
            {"label": "Remove Selected", "command": self.remove_selected_from_playlist, "accelerator": "Delete"},
            {"label": "Clear", "command": self.clear_playlist, "accelerator": "Ctrl+C"},
            {"separator": True},
            {"label": "Track Information", "command": self.open_media_info, "ref": "track_info", "accelerator": "Ctrl+I"},
            {"label": "Show Album booklet", "command": self.show_booklet, "ref": "track_booklet", "accelerator": "Ctrl+B"}
        ]
        self.menu_item_refs["track_info"] = operations_submenu[6]
        self.menu_item_refs["track_booklet"] = operations_submenu[7]

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
            {"separator": True},
            {"label": "Preferences", "command": self.open_preferences, "accelerator": "Ctrl+P"}
        ]
        self.menubar.add_menu("Tools", tools_items)
        self.menu_item_refs["audio_device"] = audio_device_item

        # Help menu
        help_items = [
            {"label": "About", "command": self.open_about, "accelerator": "F1"}
        ]
        self.menubar.add_menu("Help", help_items)

        # Initialize menu state
        self._update_menu_state()

        # Bind keyboard accelerators
        self._bind_keyboard_accelerators()

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
        self.playlist_view.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Right: Browser view
        self.right_frame = ttk.Frame(self.main_frame, style="TFrame")
        self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(6,0))

        self.browser_view = BrowserView(self.right_frame, self.state, self.theme, tooltip_manager=self.tooltip_manager, status_callback=self._controls_status_event)
        self.browser_view.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

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
            pady=(0, 20)
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
        self.status_bg.pack(fill=tk.X, pady=(3, 0), padx=0, expand=True)

        # Status text with larger, more prominent styling
        self.status_var = tk.StringVar(value="")
        initial_status_fg = self.palette.get('status_fg', '#202020' if not is_dark else '#FFFFFF')
        initial_meta_fg = self.palette.get('status_meta_fg', '#505050' if not is_dark else '#E0E0E0')

        # Create content frame for horizontal layout
        self.status_content = ctk.CTkFrame(self.status_bg, fg_color="transparent", height=120)
        self.status_content.pack(fill=tk.X, padx=12, pady=10)
        self.status_content.pack_propagate(False)  # Prevent frame from resizing based on content

        # Artwork frame on the left
        self.artwork_frame = ctk.CTkFrame(self.status_content, fg_color="transparent", width=100, height=100)
        self.artwork_frame.pack(side=tk.LEFT, padx=(0, 12))
        self.artwork_frame.pack_propagate(False)  # Prevent frame from shrinking

        # Artwork label (will display the image)
        self.artwork_label = ctk.CTkLabel(
            self.artwork_frame,
            text="",
            font=ctk.CTkFont(size=40),
            text_color=initial_meta_fg,
            fg_color="transparent",
            anchor="center"
        )
        self.artwork_label.pack(side=tk.TOP, fill=tk.BOTH)

        self.text_frame = ctk.CTkFrame(self.status_content, fg_color="transparent")
        self.text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 0))

        self.status_label = ctk.CTkLabel(
            self.text_frame,
            textvariable=self.status_var,
            anchor="w",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=initial_status_fg,
            bg_color=initial_status_bg,
            justify="left"
        )
        self.status_label.pack(side=tk.TOP, fill=tk.X, pady=(15, 40))

        # Meta info frame - container for metadata and BPM controls
        self.meta_frame = ctk.CTkFrame(self.text_frame, fg_color="transparent")
        self.meta_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 2))

        # Meta info label
        self.meta_var = tk.StringVar(value="")
        self.meta_label = ctk.CTkLabel(
            self.meta_frame,
            textvariable=self.meta_var,
            anchor="w",
            font=ctk.CTkFont(size=14),
            text_color=initial_meta_fg,
            bg_color=initial_status_bg,
            justify="left",
            height=1
        )
        self.meta_label.pack(side=tk.LEFT, fill=tk.X)

        # BPM control frame (initially hidden)
        self.bpm_control_frame = ctk.CTkFrame(self.meta_frame, fg_color="transparent")
        self.bpm_control_frame.pack(side=tk.LEFT, padx=(8, 0))
        self.bpm_control_frame.pack_forget()  # Initially hidden

        # BPM buttons container
        self.bpm_buttons_frame = ctk.CTkFrame(self.bpm_control_frame, fg_color="transparent")
        self.bpm_buttons_frame.pack(side=tk.LEFT)

        # Get button colors from theme palette
        btn_bg = self.palette.get("button_bg_color", self.palette.get("accent", "#0078d4"))
        btn_fg = self.palette.get("button_fg_color", "#ffffff")
        btn_hover = self.palette.get("button_hover", self.palette.get("accent_hover", "#106ebe"))

        # Single BPM button (starts as Analyze, becomes Save after analysis)
        self.btn_bpm = ctk.CTkButton(
            self.bpm_buttons_frame,
            text="Analyze BPM",
            command=self._on_bpm_button_click,
            width=100,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=btn_hover
        )
        self.btn_bpm.pack(side=tk.LEFT)

        # Store current temporary BPM value and button state
        self.current_temp_bpm = None
        self.bpm_button_state = "analyze"  # Can be "analyze", "analyzing", "save", "saving"

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
            self._set_track_info_enabled(True)
        elif event_type == "pause":
            if self.status_var.get().startswith("Pause:"):
                self._restore_status()
            else:
                self._restore_status(prefix="Pause")
            self._update_menu_state()
            self._set_track_info_enabled(True)
        elif event_type == "stop":
            if self.status_var.get():
                self.status_var.set("")
            self.meta_var.set("")

            if hasattr(self, "_status_restore_job"):
                self.root.after_cancel(self._status_restore_job)
                self._status_restore_job = None

            self.state.current_index = None

            try:
                self.artwork_frame.pack_forget()
            except Exception:
                pass

            # Hide BPM control frame when stopping
            try:
                self.bpm_control_frame.pack_forget()
            except Exception:
                pass

            self.refresh_all()
            self._update_menu_state()
            self._set_track_info_enabled(False)
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

        try:
            style = ttk.Style(self.root)
            style.configure("TFrame", background=root_bg)
        except:
            pass

        # Update sidebar buttons specifically
        btn_bg = self.palette.get("button_bg_color", self.palette.get("accent", "#0078d4"))
        btn_fg = self.palette.get("button_fg_color", "#ffffff")
        btn_hover = self.palette.get("button_hover", self.palette.get("accent_hover", "#106ebe"))

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
            self.status_frame.configure(
                fg_color=frame_bg,
                bg_color=frame_bg  # Critical: bg_color affects frame edges/corners
            )

            # Update status bar frame with subtle border for better visibility
            self.status_bg.configure(
                fg_color=status_bg_color,
                bg_color=frame_bg,  # This controls corner colors - must match parent
                border_color=status_border_color,  # Subtle border for separation
                border_width=1
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

        # Update artwork if there's a current track to refresh placeholder colors
        if self.state.current_index is not None and 0 <= self.state.current_index < len(self.state.playlist):
            self._update_artwork(self.state.playlist[self.state.current_index])

    def open_preferences(self):
        def on_apply(selected_theme):
            # Update settings with lowercase theme
            self.settings.theme = selected_theme
            # Apply theme to all components
            self.theme.reload()
            # Update main window and all child components
            self.update_theme_colors()
            # Update playlist and browser themes
            self.playlist_view.update_theme()
            self.browser_view.update_theme()
            # Update controls theme
            self.controls.update_theme()

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
            BookletViewer(self.root, track)

    def open_about(self):
        # Create custom dialog using CustomTkinter
        about_window = ctk.CTkToplevel(self.root)
        about_window.title("About")
        about_window.geometry("400x250")
        about_window.resizable(False, False)

        # Hide window initially to prevent flickering during positioning
        about_window.withdraw()

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

        # Center window after all setup is complete
        center_window(about_window, self.root)

        # Show window after all setup is complete
        about_window.deiconify()

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
        self.state.playlist, self.state.current_index = playback.shuffle_playlist(self.state.playlist, self.state.current_index)
        self.refresh_all()
        self._set_temporary_status("Playlist shuffled")

    def clear_playlist(self):
        if not self.state.playlist:
            return

        if messagebox.askyesno("Clear Playlist", "Are you sure you want to clear the playlist?", parent=self.root):
            self.state.playlist, self.state.current_index = playback.clear_playlist()
            self.player.stop()
            self.refresh_all()
            self._set_temporary_status("Playlist cleared")

    # ---------- Repeat Mode ----------
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
        self.state.playlist, self.state.current_index = playback.sort_playlist_by_title(self.state.playlist, self.state.current_index)
        self.refresh_all()
        self._set_temporary_status("Playlist sorted by title")

    def sort_playlist_by_artist(self):
        self.state.playlist, self.state.current_index = playback.sort_playlist_by_artist(self.state.playlist, self.state.current_index)
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
            # Show browser frame and middle buttons
            self.right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(6,0))
            self.browser_view.pack(fill=tk.BOTH, expand=True)
            self.mid_frame.pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=6)
        else:
            # Hide browser frame and middle buttons
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
        Tracks selection but does NOT update current_index since that's for playing state.
        Does NOT start playback — double-click or menu actions do that.
        """
        # Selection is already tracked in the playlist view via state.selected_indices
        # No need to update current_index here as that represents the playing song

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
                    # Ensure status is updated to clear artwork when playlist ends
                    self._controls_status_event("stop")
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

        Uses the centralized metadata module to read tags (title, artist), duration and bitrate.
        """
        idx = self.state.current_index
        if idx is None or idx >= len(self.state.playlist):
            self.status_var.set("")
            self.meta_var.set("")
            self.artwork_label.configure(image=None)
            self.artwork_label.image = None
            # Hide artwork frame when no track is active
            try:
                self.artwork_frame.pack_forget()
            except Exception:
                pass
            return

        # Show artwork frame when there is a current track
        try:
            self.artwork_frame.pack(side=tk.LEFT, padx=(0, 12), before=self.text_frame)
        except Exception:
            pass

        path = self.state.playlist[idx]
        name = os.path.basename(path)

        # Get metadata using the centralized module
        meta = get_metadata(path)

        title = meta.get("title") or name
        artist = meta.get("artist")
        duration_s = meta.get("duration_s")
        bitrate = meta.get("bitrate")
        fmt = meta.get("format")
        bpm = meta.get("bpm")

        # Update artwork display
        self._update_artwork(path)

        if artist:
            self.status_var.set(f"{prefix}: {title} — {artist}")
        else:
            self.status_var.set(f"{prefix}: {title}")

        # Build metadata line parts (duration, bitrate, bpm, format)
        parts = []
        if duration_s:
            parts.append(f"{int(duration_s)//60:02d}:{int(duration_s)%60:02d}")
        if bitrate:
            parts.append(f"{bitrate} kbps")

        if bpm:
            bpm_str = f" • {bpm} BPM"
        else:
            bpm_str =  " • BPM info missing"

        self.meta_var.set(" • ".join(parts) + bpm_str)

        # Handle BPM buttons visibility
        if bpm is None:
            # Show BPM control frame when BPM is missing
            self.bpm_control_frame.pack(side=tk.LEFT, padx=(8, 0))
            # Reset button state and text
            self.bpm_button_state = "analyze"
            self.btn_bpm.configure(state="normal", text="Analyze BPM")
            self.current_temp_bpm = None
        else:
            # Hide BPM control frame when BPM is present
            self.bpm_control_frame.pack_forget()
            self.current_temp_bpm = None

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
        self.root.bind("<Delete>", lambda e: self.remove_selected_from_playlist())
        self.root.bind("<Control-c>", lambda e: self.clear_playlist())
        self.root.bind("<Control-i>", lambda e: self.open_media_info())
        self.root.bind("<Control-b>", lambda e: self.show_booklet())

        # View menu accelerators
        self.root.bind_all("<F9>", lambda e: self._toggle_playlist_visibility())
        self.root.bind_all("<F10>", lambda e: self._toggle_browser_visibility())

        # Tools menu accelerators
        self.root.bind("<Control-p>", lambda e: self.open_preferences())

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

    # ---------- Start UI mainloop ----------
    def start(self):
        self.root.mainloop()
