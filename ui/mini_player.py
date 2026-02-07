"""Mini player window that appears when main window is minimized."""
import tkinter as tk
import customtkinter as ctk
import os


class MiniPlayer(ctk.CTkToplevel):
    """Always-on-top mini player window with essential controls."""

    def __init__(self, parent, state, theme_manager, controls, on_restore_callback):
        super().__init__(parent)

        self.app_state = state
        self.theme = theme_manager
        self.controls = controls
        self.on_restore = on_restore_callback

        # Window configuration
        self.title("Tango Studio - Mini Player")
        self.geometry("450x130")
        self.resizable(False, False)

        # Always on top
        self.attributes("-topmost", True)

        # Hide from taskbar (Windows specific)
        try:
            self.attributes("-toolwindow", True)
        except:
            pass

        # Remove window decorations for modern look
        self.overrideredirect(True)

        # Make window draggable
        self._drag_start_x = 0
        self._drag_start_y = 0

        # Update loop ID
        self._update_id = None

        # Build UI
        self._build_ui()

        # Bind events
        self.bind("<Button-1>", self._start_drag)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<Double-Button-1>", self._on_double_click)

        # Handle close button - don't stop playback
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Start update loop
        self._schedule_update()

    def _build_ui(self):
        """Build the mini player interface."""
        palette = self.theme.palette
        bg = palette.get("bg", "#1E1E1E")
        fg = palette.get("fg", "#FFFFFF")
        border_color = palette.get("status_border", "#3E3E3E")

        # Use same button colors as main controls
        btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        btn_fg = palette.get("button_fg_color", "#ffffff")
        btn_hover = palette.get("button_hover", palette.get("accent_hover", "#106ebe"))
        accent = palette.get("accent", "#BB86FC")

        self.configure(fg_color=bg)

        # Main container with rounded corners
        main_frame = ctk.CTkFrame(
            self,
            fg_color=bg,
            border_color=border_color,
            border_width=1,
            corner_radius=12
        )
        main_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Content container with padding
        content_frame = ctk.CTkFrame(main_frame, fg_color="transparent", corner_radius=0)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        # Top section: Controls and title
        top_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        top_frame.pack(fill=tk.X, pady=(0, 10))

        # Transport controls on the left
        controls_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        controls_frame.pack(side=tk.LEFT, padx=(0, 15))

        btn_width = 40
        btn_height = 40
        symbol_font = ctk.CTkFont(family="Segoe UI Symbol", size=18, weight="bold")

        self.btn_prev = ctk.CTkButton(
            controls_frame,
            text="⏮",
            width=btn_width,
            height=btn_height,
            font=symbol_font,
            command=self._on_prev,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=btn_hover,
        )
        self.btn_prev.pack(side=tk.LEFT, padx=4)

        self.btn_play_pause = ctk.CTkButton(
            controls_frame,
            text="▶",
            width=btn_width,
            height=btn_height,
            font=symbol_font,
            command=self._on_play_pause,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=btn_hover,
        )
        self.btn_play_pause.pack(side=tk.LEFT, padx=4)

        self.btn_next = ctk.CTkButton(
            controls_frame,
            text="⏭",
            width=btn_width,
            height=btn_height,
            font=symbol_font,
            command=self._on_next,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=btn_hover,
        )
        self.btn_next.pack(side=tk.LEFT, padx=4)

        # Track info container
        info_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor="n")

        # Track title with better styling
        self.title_label = ctk.CTkLabel(
            info_frame,
            text="No track loaded",
            anchor="w",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=fg,
        )
        self.title_label.pack(fill=tk.X, pady=(10, 0))

        # Time display below title
        self.time_label = ctk.CTkLabel(
            info_frame,
            text="0:00 / 0:00",
            anchor="w",
            font=ctk.CTkFont(size=12),
            text_color=fg,
        )
        self.time_label.pack(fill=tk.X, pady=(2, 0))

        # Time limit indicator below time
        self.time_limit_label = ctk.CTkLabel(
            info_frame,
            text="",
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=accent,
        )
        self.time_limit_label.pack(fill=tk.X, pady=(2, 0))

        # Bottom section: Progress bar
        progress_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        progress_frame.pack(fill=tk.X, pady=(0, 0))

        # Modern progress bar with better styling
        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            height=8,
            progress_color=accent,
            fg_color=palette.get("scrollbar_track", "#282828"),
            corner_radius=4,
        )
        self.progress_bar.pack(fill=tk.X, padx=0)
        self.progress_bar.set(0)

        # Close button in top-right corner
        close_btn = ctk.CTkButton(
            main_frame,
            text="✕",
            width=24,
            height=24,
            font=ctk.CTkFont(size=14),
            command=self._on_close,
            fg_color="transparent",
            hover_color=palette.get("button_hover", "#3A3A3A"),
            corner_radius=6,
            border_width=0,
        )
        close_btn.place(relx=1.0, rely=0.0, x=-8, y=8, anchor="ne")

    def _start_drag(self, event):
        """Start dragging the window."""
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag(self, event):
        """Handle window dragging."""
        x = self.winfo_x() + event.x - self._drag_start_x
        y = self.winfo_y() + event.y - self._drag_start_y
        self.geometry(f"+{x}+{y}")

    def _on_double_click(self, event):
        """Restore main window on double click."""
        if self.on_restore:
            self.on_restore()

    def _on_close(self):
        """Handle window close - hide instead of destroy."""
        self.withdraw()

    def _on_prev(self):
        """Previous track."""
        if self.controls:
            self.controls._on_prev()

    def _on_play_pause(self):
        """Toggle play/pause. Respect paused state to resume instead of restarting."""
        if not self.controls:
            return

        # If paused, call pause handler to resume
        if getattr(self.controls, 'is_paused', False):
            self.controls._on_pause()
            return

        # If currently playing, pause it
        if getattr(self.controls, 'is_playing', False) and not getattr(self.controls, 'is_paused', False):
            self.controls._on_pause()
            return

        # Otherwise, start playback
        self.controls._on_play(from_user=True)

    def _on_next(self):
        """Next track."""
        if self.controls:
            self.controls._on_next()

    def _schedule_update(self):
        """Schedule periodic UI updates."""
        self._update_ui()
        self._update_id = self.after(500, self._schedule_update)

    def _update_ui(self):
        """Update UI state from player."""
        # Update play/pause button
        if self.controls:
            if self.controls.is_playing and not self.controls.is_paused:
                self.btn_play_pause.configure(text="⏸")
            else:
                self.btn_play_pause.configure(text="▶")

        # Update track title
        if self.app_state.current_index is not None and self.app_state.current_index < len(self.app_state.playlist):
            filepath = self.app_state.playlist[self.app_state.current_index]
            filename = os.path.basename(filepath)
            # Try to get title from metadata if available
            title = filename
            if hasattr(self.controls, 'player'):
                from audio.metadata import get_metadata
                meta = get_metadata(filepath)
                title = meta.get("title", filename)

            # Truncate if too long
            if len(title) > 50:
                title = title[:47] + "..."

            self.title_label.configure(text=title)
        else:
            self.title_label.configure(text="No track loaded")

        # Update progress bar and time display
        if self.controls and hasattr(self.controls, 'player'):
            try:
                length_ms = self.controls.player.get_length()
                pos_ms = self.controls.player.get_time()
                if length_ms > 0 and pos_ms >= 0:
                    progress = pos_ms / length_ms
                    self.progress_bar.set(progress)

                    # Format time display
                    pos_s = int(pos_ms // 1000)
                    length_s = int(length_ms // 1000)
                    pos_min, pos_sec = divmod(pos_s, 60)
                    length_min, length_sec = divmod(length_s, 60)
                    time_text = f"{pos_min}:{pos_sec:02d} / {length_min}:{length_sec:02d}"
                    self.time_label.configure(text=time_text)
                else:
                    self.progress_bar.set(0)
                    self.time_label.configure(text="0:00 / 0:00")
            except:
                self.progress_bar.set(0)
                self.time_label.configure(text="0:00 / 0:00")

        # Update time limit indicator
        time_limit_text = ""
        if self.app_state.current_index is not None and self.app_state.current_index < len(self.app_state.playlist):
            filepath = self.app_state.playlist[self.app_state.current_index]
            if filepath in self.app_state.play_limits:
                limit_seconds = self.app_state.play_limits[filepath]
                # Calculate remaining time
                if self.controls and hasattr(self.controls, 'player'):
                    try:
                        pos_ms = self.controls.player.get_time()
                        pos_s = int(pos_ms // 1000)
                        remaining = max(0, int(limit_seconds) - pos_s)
                        time_limit_text = f"⏱ Time limit: {remaining}s remaining"
                    except:
                        time_limit_text = f"⏱ Time limit: {int(limit_seconds)}s"

        self.time_limit_label.configure(text=time_limit_text)

    def update_theme(self):
        """Update colors when theme changes."""
        palette = self.theme.palette
        bg = palette.get("bg", "#1E1E1E")
        fg = palette.get("fg", "#FFFFFF")
        accent = palette.get("accent", "#BB86FC")
        btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        btn_fg = palette.get("button_fg_color", "#ffffff")
        btn_hover = palette.get("button_hover", palette.get("accent_hover", "#106ebe"))

        self.configure(fg_color=bg)
        self.title_label.configure(text_color=fg)
        self.progress_bar.configure(
            progress_color=accent,
            fg_color=palette.get("scrollbar_track", "#282828")
        )
        self.time_limit_label.configure(text_color=accent)

        for btn in [self.btn_prev, self.btn_play_pause, self.btn_next]:
            btn.configure(fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover)

    def cleanup(self):
        """Clean up resources."""
        if self._update_id:
            try:
                self.after_cancel(self._update_id)
            except:
                pass
            self._update_id = None
