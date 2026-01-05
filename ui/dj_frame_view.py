import tkinter as tk
import customtkinter as ctk
from audio.metadata import get_metadata, get_display_bpm, analyze_bpm

import logging
import threading

logger = logging.getLogger(__name__)


class DJFrameView(ctk.CTkFrame):
    """Encapsulates the DJ info display with meter, BPM, Key, and Energy analysis"""

    def __init__(self, master, state, theme_manager, settings, player=None):
        self.state = state
        self.theme = theme_manager
        self.settings = settings
        self.player = player
        self.palette = theme_manager.palette

        is_dark = settings.theme.lower() == "dark"
        initial_bg = self.palette.get("bg", "#1E1E1E" if is_dark else "#FAFAFA")

        super().__init__(master, fg_color=initial_bg, bg_color=initial_bg, corner_radius=0, height=150, width=365)
        self.pack_propagate(False)

        self.bpm_var = tk.StringVar(value="--")
        self.key_var = tk.StringVar(value="--")

        # Audio metering values
        self.lufs_value = -60.0  # LUFS value (-60 to 0)
        self.overall_lufs_value = -60.0  # Overall track LUFS
        self.peak_dbfs = -60.0   # Peak dBFS (-60 to 0)
        self.limiter_activity = 0.0  # Limiter activity (0.0 to 1.0)
        self.energy_level = 0.0  # Energy level (0.0 to 1.0)

        self._build_widgets(is_dark=is_dark, frame_bg=initial_bg)

        # Get root window for thread-safe UI updates
        self._tk_root = master.winfo_toplevel()

        # Register audio metrics callback if player provided
        if self.player:
            self.player.set_audio_metrics_callback(self._on_audio_metrics_update)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_widgets(self, is_dark, frame_bg):
        dj_bg = self.palette.get("status_bg", "#E8E8E8" if not is_dark else "#2A2A2A")
        dj_border = self.palette.get("status_border", "#D0D0D0" if not is_dark else "#3E3E3E")
        dj_fg = self.palette.get("status_meta_fg", "#202020" if not is_dark else "#FFFFFF")
        meta_fg = self.palette.get("status_fg", "#505050" if not is_dark else "#E0E0E0")

        self.dj_bg = ctk.CTkFrame(
            self,
            corner_radius=6,
            fg_color=dj_bg,
            bg_color=frame_bg,
            border_color=dj_border,
            border_width=1,
        )
        self.dj_bg.pack(fill=tk.X, pady=(3, 0), padx=0)

        self.dj_content = ctk.CTkFrame(self.dj_bg, fg_color="transparent", height=120)
        self.dj_content.pack(fill=tk.X, padx=12, pady=10)
        self.dj_content.pack_propagate(False)

        # Left column: Meters
        self.left_column = ctk.CTkFrame(self.dj_content, fg_color="transparent", width=140)
        self.left_column.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        self.left_column.pack_propagate(False)

        # LUFS row
        lufs_row = ctk.CTkFrame(self.left_column, fg_color="transparent", height=30)
        lufs_row.pack(side=tk.TOP, fill=tk.X, pady=(5, 3))

        lufs_title = ctk.CTkLabel(
            lufs_row,
            text="LUFS",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=meta_fg,
            anchor="w",
            width=100
        )
        lufs_title.pack(side=tk.LEFT)
        self.lufs_title = lufs_title

        self.lufs_label = ctk.CTkLabel(
            lufs_row,
            text="-60.0",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=dj_fg,
            anchor="e",
            width=80
        )
        self.lufs_label.pack(side=tk.LEFT)

        # Overall LUFS row
        overall_lufs_row = ctk.CTkFrame(self.left_column, fg_color="transparent", height=25)
        overall_lufs_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 3))

        self.overall_lufs_title = ctk.CTkLabel(
            overall_lufs_row,
            text="LUFS (Overall)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=meta_fg,
            anchor="w",
            width=100
        )
        self.overall_lufs_title.pack(side=tk.LEFT)

        self.overall_lufs_label = ctk.CTkLabel(
            overall_lufs_row,
            text="-60.0",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=dj_fg,
            anchor="e",
            width=80
        )
        self.overall_lufs_label.pack(side=tk.LEFT)

        # PEAK row
        peak_row = ctk.CTkFrame(self.left_column, fg_color="transparent", height=30)
        peak_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 3))

        peak_title = ctk.CTkLabel(
            peak_row,
            text="PEAK",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=meta_fg,
            anchor="w",
            width=50
        )
        peak_title.pack(side=tk.LEFT)
        self.peak_title = peak_title

        self.peak_canvas = ctk.CTkCanvas(
            peak_row,
            width=80,
            height=14,
            bg=dj_bg,
            highlightthickness=0
        )
        self.peak_canvas.pack(side=tk.LEFT, pady=(0, 0))
        self._draw_peak_meter(dj_border, dj_bg)

        # LIMIT row
        limit_row = ctk.CTkFrame(self.left_column, fg_color="transparent", height=30)
        limit_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 3))

        limit_title = ctk.CTkLabel(
            limit_row,
            text="LIMIT",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=meta_fg,
            anchor="w",
            width=50
        )
        limit_title.pack(side=tk.LEFT)
        self.limit_title = limit_title

        self.limiter_canvas = ctk.CTkCanvas(
            limit_row,
            width=80,
            height=14,
            bg=dj_bg,
            highlightthickness=0
        )
        self.limiter_canvas.pack(side=tk.LEFT, pady=(0, 0))
        self._draw_limiter_meter(dj_border, dj_bg)

        # Right column: Info
        self.right_column = ctk.CTkFrame(self.dj_content, fg_color="transparent")
        self.right_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # BPM row
        bpm_row = ctk.CTkFrame(self.right_column, fg_color="transparent", height=30)
        bpm_row.pack(side=tk.TOP, fill=tk.X, pady=(5, 3))

        bpm_title = ctk.CTkLabel(
            bpm_row,
            text="BPM",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=meta_fg,
            anchor="w",
            width=60
        )
        bpm_title.pack(side=tk.LEFT)
        self.bpm_title = bpm_title

        self.bpm_label = ctk.CTkLabel(
            bpm_row,
            textvariable=self.bpm_var,
            anchor="w",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=dj_fg
        )
        self.bpm_label.pack(side=tk.LEFT, padx=(10, 0))

        # KEY row
        key_row = ctk.CTkFrame(self.right_column, fg_color="transparent", height=30)
        key_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 3))

        key_title = ctk.CTkLabel(
            key_row,
            text="KEY",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=meta_fg,
            anchor="w",
            width=60
        )
        key_title.pack(side=tk.LEFT)
        self.key_title = key_title

        self.key_label = ctk.CTkLabel(
            key_row,
            textvariable=self.key_var,
            anchor="w",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=dj_fg
        )
        self.key_label.pack(side=tk.LEFT, padx=(10, 0))

        # ENERGY row
        energy_row = ctk.CTkFrame(self.right_column, fg_color="transparent", height=30)
        energy_row.pack(side=tk.TOP, fill=tk.X, pady=(0, 3))

        energy_title = ctk.CTkLabel(
            energy_row,
            text="ENERGY",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=meta_fg,
            anchor="w",
            width=60
        )
        energy_title.pack(side=tk.LEFT)
        self.energy_title = energy_title

        self.energy_canvas = ctk.CTkCanvas(
            energy_row,
            width=100,
            height=14,
            bg=dj_bg,
            highlightthickness=0
        )
        self.energy_canvas.pack(side=tk.LEFT, padx=(10, 0), pady=(0, 0))
        self._draw_energy_meter(dj_border, dj_bg)

    def _draw_limiter_meter(self, border_color, bg_color):
        """Draw the horizontal limiter activity meter"""
        self.limiter_canvas.delete("all")

        # Draw meter border
        self.limiter_canvas.create_rectangle(1, 1, 79, 11, outline=border_color, width=1)

        # Draw limiter activity (fill from left)
        if self.limiter_activity > 0:
            width = int(75 * self.limiter_activity)

            # Color coding based on activity level
            if self.limiter_activity < 0.3:
                color = "#00FF00"  # Green - light limiting
            elif self.limiter_activity < 0.7:
                color = "#FFAA00"  # Orange - moderate limiting
            else:
                color = "#FF0000"  # Red - heavy limiting

            self.limiter_canvas.create_rectangle(3, 3, 3 + width, 9, fill=color, outline="")

    def _draw_peak_meter(self, border_color, bg_color):
        """Draw the horizontal peak level meter"""
        self.peak_canvas.delete("all")

        # Draw meter border
        self.peak_canvas.create_rectangle(1, 1, 79, 11, outline=border_color, width=1)

        # Convert dBFS to 0-1 scale for bar display
        # -60 dBFS = 0.0 (empty)
        # 0 dBFS = 1.0 (full/clipping)
        if self.peak_dbfs > -60.0:
            normalized_peak = (self.peak_dbfs + 60.0) / 60.0  # Convert -60..0 to 0..1
            normalized_peak = max(0.0, min(1.0, normalized_peak))
        else:
            normalized_peak = 0.0

        if normalized_peak > 0:
            width = int(75 * normalized_peak)

            # Color gradient based on peak level
            if normalized_peak < 0.4:
                color = "#4080FF"  # Blue - low level
            elif normalized_peak < 0.7:
                color = "#00FF00"  # Green - good level
            else:
                color = "#FF4040"  # Red - hot signal (clipping risk)

            self.peak_canvas.create_rectangle(3, 3, 3 + width, 9, fill=color, outline="")

    def _draw_energy_meter(self, border_color, bg_color):
        """Draw the horizontal energy level meter"""
        self.energy_canvas.delete("all")

        # Draw meter border
        self.energy_canvas.create_rectangle(1, 1, 99, 11, outline=border_color, width=1)

        # Draw energy level (fill from left)
        if self.energy_level > 0:
            width = int(95 * self.energy_level)

            # Color gradient based on energy level
            if self.energy_level < 0.4:
                color = "#4080FF"  # Blue - low energy
            elif self.energy_level < 0.7:
                color = "#00FF00"  # Green - medium energy
            else:
                color = "#FF4040"  # Red - high energy

            self.energy_canvas.create_rectangle(3, 3, 3 + width, 9, fill=color, outline="")

    def _on_audio_metrics_update(self, lufs_value, overall_lufs_value, peak_dbfs, limiter_activity, energy_level):
        """Called from audio thread; schedule main-thread UI update."""
        try:
            if self._tk_root:
                self._tk_root.after(0, self._update_audio_metrics_display, lufs_value, overall_lufs_value, peak_dbfs, limiter_activity, energy_level)
        except Exception as e:
            logger.error(f"Error scheduling audio metrics update: {e}")

    def _update_audio_metrics_display(self, lufs_value, overall_lufs_value, peak_dbfs, limiter_activity, energy_level):
        """Update all audio metrics (LUFS, Peak, Limiter, Energy) on main thread."""
        try:
            self.lufs_value = lufs_value
            self.overall_lufs_value = overall_lufs_value
            self.peak_dbfs = peak_dbfs
            self.limiter_activity = limiter_activity
            self.energy_level = energy_level

            self.lufs_label.configure(text=f"{lufs_value:.1f}")
            self.overall_lufs_label.configure(text=f"{overall_lufs_value:.1f}")

            # Update peak, limiter, and energy meters
            is_dark = self.settings.theme.lower() == "dark"
            dj_bg = self.palette.get("status_bg", "#E8E8E8" if not is_dark else "#2A2A2A")
            dj_border = self.palette.get("status_border", "#D0D0D0" if not is_dark else "#3E3E3E")
            self._draw_peak_meter(dj_border, dj_bg)
            self._draw_limiter_meter(dj_border, dj_bg)
            self._draw_energy_meter(dj_border, dj_bg)
        except Exception as e:
            logger.error(f"Error updating audio metrics display: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def update_info(self, filepath=None):
        """Update DJ info based on current track"""
        if filepath is None:
            idx = self.state.current_index
            if idx is None or idx >= len(self.state.playlist):
                self._clear_info()
                return
            filepath = self.state.playlist[idx]

        meta = get_metadata(filepath)

        # Update BPM
        bpm = meta.get("bpm")
        display_bpm = get_display_bpm(bpm)
        if display_bpm:
            self.bpm_var.set(display_bpm)
        else:
            self.bpm_var.set("Estimating...")

            def estimate_bpm():
                try:
                    import os
                    import sys
                    # Lower thread priority to avoid interfering with audio playback
                    try:
                        if sys.platform == 'win32':
                            import ctypes
                            # Windows: Set thread priority to below normal
                            handle = ctypes.windll.kernel32.GetCurrentThread()
                            ctypes.windll.kernel32.SetThreadPriority(handle, -1)
                        else:
                            # Unix/Linux/Mac: Increase nice value (lower priority)
                            os.nice(10)
                    except Exception:
                        # If priority setting fails, continue anyway
                        pass

                    # Analyze with reduced duration and sample rate for faster processing
                    bpm = analyze_bpm(filepath, sr=16000, duration=30)
                    display_bpm = get_display_bpm(bpm)
                    if display_bpm:
                        self.bpm_var.set(display_bpm)
                    else:
                        self.bpm_var.set("--")
                except Exception as e:
                    logger.error(f"BPM estimation error: {e}")
                    self.bpm_var.set("--")

            threading.Thread(target=estimate_bpm, daemon=True).start()

        # Update Key (placeholder - requires key detection implementation)
        # For now, show placeholder
        self.key_var.set("--")

    def update_meter_values(self, lufs=-60.0, peak_dbfs=-60.0, limiter_activity=0.0):
        """Update the meter values

        Args:
            lufs: LUFS value (-60 to 0)
            peak_dbfs: Peak dBFS (-60 to 0)
            limiter_activity: Limiter activity (0.0 to 1.0)
        """
        self.lufs_value = max(-60.0, min(0.0, lufs))
        self.peak_dbfs = max(-60.0, min(0.0, peak_dbfs))
        self.limiter_activity = max(0.0, min(1.0, limiter_activity))

        # Update labels
        self.lufs_label.configure(text=f"{self.lufs_value:.1f}")

        # Redraw meters
        is_dark = self.settings.theme.lower() == "dark"
        dj_bg = self.palette.get("status_bg", "#E8E8E8" if not is_dark else "#2A2A2A")
        dj_border = self.palette.get("status_border", "#D0D0D0" if not is_dark else "#3E3E3E")
        self._draw_peak_meter(dj_border, dj_bg)
        self._draw_limiter_meter(dj_border, dj_bg)

    def update_energy_level(self, energy=0.0):
        """Update the energy level (0.0 to 1.0)"""
        self.energy_level = max(0.0, min(1.0, energy))

        # Redraw energy meter
        is_dark = self.settings.theme.lower() == "dark"
        dj_bg = self.palette.get("status_bg", "#E8E8E8" if not is_dark else "#2A2A2A")
        dj_border = self.palette.get("status_border", "#D0D0D0" if not is_dark else "#3E3E3E")
        self._draw_energy_meter(dj_border, dj_bg)

    def update_meter_level(self, level):
        """Legacy method for backward compatibility - now updates LUFS and Peak"""
        # Convert 0-1 level to approximate dBFS (-60 to 0)
        if level > 0:
            dbfs = -60 + (level * 60)
            self.update_meter_values(lufs=dbfs, peak_dbfs=dbfs, limiter_activity=level * 0.5)

    def _clear_info(self):
        """Clear all displayed info"""
        self.bpm_var.set("--")
        self.key_var.set("--")
        self.lufs_value = -60.0
        self.peak_dbfs = -60.0
        self.limiter_activity = 0.0
        self.energy_level = 0.0
        self.lufs_label.configure(text="-60.0")
        is_dark = self.settings.theme.lower() == "dark"
        dj_bg = self.palette.get("status_bg", "#E8E8E8" if not is_dark else "#2A2A2A")
        dj_border = self.palette.get("status_border", "#D0D0D0" if not is_dark else "#3E3E3E")
        self._draw_peak_meter(dj_border, dj_bg)
        self._draw_limiter_meter(dj_border, dj_bg)
        self._draw_energy_meter(dj_border, dj_bg)

    def update_theme(self):
        """Update colors based on current theme"""
        self.palette = self.theme.palette
        is_dark = self.settings.theme.lower() == "dark"
        frame_bg = self.palette.get("bg", "#1E1E1E" if is_dark else "#FAFAFA")

        dj_bg = self.palette.get("status_bg", "#E8E8E8" if not is_dark else "#2A2A2A")
        dj_border = self.palette.get("status_border", "#D0D0D0" if not is_dark else "#3E3E3E")
        dj_fg = self.palette.get("status_meta_fg", "#202020" if not is_dark else "#FFFFFF")
        meta_fg = self.palette.get("status_fg", "#505050" if not is_dark else "#E0E0E0")

        self.configure(fg_color=frame_bg, bg_color=frame_bg)
        self.dj_bg.configure(fg_color=dj_bg, bg_color=frame_bg, border_color=dj_border)

        # Update title labels
        self.lufs_title.configure(text_color=meta_fg)
        self.overall_lufs_title.configure(text_color=meta_fg)
        self.peak_title.configure(text_color=meta_fg)
        self.limit_title.configure(text_color=meta_fg)
        self.bpm_title.configure(text_color=meta_fg)
        self.key_title.configure(text_color=meta_fg)
        self.energy_title.configure(text_color=meta_fg)

        # Update value labels
        self.bpm_label.configure(text_color=dj_fg)
        self.key_label.configure(text_color=dj_fg)
        self.lufs_label.configure(text_color=dj_fg)
        self.overall_lufs_label.configure(text_color=dj_fg)

        # Update canvas backgrounds
        self.limiter_canvas.configure(bg=dj_bg)
        self.peak_canvas.configure(bg=dj_bg)
        self.energy_canvas.configure(bg=dj_bg)

        self._draw_peak_meter(dj_border, dj_bg)
        self._draw_limiter_meter(dj_border, dj_bg)
        self._draw_energy_meter(dj_border, dj_bg)
