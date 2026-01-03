"""
Control bar: Play / Pause / Stop / Prev / Next and Volume + time label
"""

import logging
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from typing import Optional, Callable
import threading
from audio.metadata import get_metadata, analyze_bpm, metadata_extractor
from ui.waveform_seekbar import WaveformSeekbar

logger = logging.getLogger(__name__)


class ControlsBar(ttk.Frame):
    def __init__(self, master, player, state, theme, playlist=None,
                 tooltip_manager=None, status_callback: Optional[Callable] = None, settings=None) -> None:
        super().__init__(master)

        self.player = player
        self.state = state
        self.theme = theme
        self.tooltip_manager = tooltip_manager
        self.status_callback = status_callback
        self.settings = settings
        self.playlist = playlist
        self.playlist_tree = self.playlist.tree if self.playlist else None
        self.is_paused = False
        self.is_playing = False
        self.is_muted = False
        self.crossfade_triggered = False

        left = ttk.Frame(self)
        left.pack(side=tk.LEFT, padx=6)

        # Create a larger font for the button symbols
        symbol_font = ("Segoe UI Symbol", 18, "bold")

        # Get button colors from theme palette
        palette = self.theme.palette if hasattr(self.theme, 'palette') else {}
        btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        btn_fg = palette.get("button_fg_color", "#ffffff")
        btn_hover = palette.get("button_hover", palette.get("accent_hover", "#106ebe"))

        # Common button config
        btn_width = 40
        btn_height = 40

        self.btn_play = ctk.CTkButton(left, text="⏵", command=lambda: self._on_play(from_user=True),
                             font=symbol_font, width=btn_width, height=btn_height,
                             fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover)
        self.btn_play.pack(side=tk.LEFT, padx=4, pady=2)

        self.btn_pause = ctk.CTkButton(left, text="⏸", command=self._on_pause,
                              font=symbol_font, width=btn_width, height=btn_height,
                              fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover)
        self.btn_pause.pack(side=tk.LEFT, padx=4, pady=2)

        self.btn_prev = ctk.CTkButton(left, text="⏮", command=self._on_prev,
                             font=symbol_font, width=btn_width, height=btn_height,
                             fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover)
        self.btn_prev.pack(side=tk.LEFT, padx=4, pady=2)

        self.btn_stop = ctk.CTkButton(left, text="◼", command=self._on_stop,
                             font=symbol_font, width=btn_width, height=btn_height,
                             fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover)
        self.btn_stop.pack(side=tk.LEFT, padx=4, pady=2)

        self.btn_next = ctk.CTkButton(left, text="⏭", command=self._on_next,
                             font=symbol_font, width=btn_width, height=btn_height,
                             fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover)
        self.btn_next.pack(side=tk.LEFT, padx=4, pady=2)

        if self.tooltip_manager:
            self.tooltip_manager.attach(self.btn_play, lambda: "Play (Enter)")
            self.tooltip_manager.attach(self.btn_pause, lambda: "Pause/Resume (Space)")
            self.tooltip_manager.attach(self.btn_prev, lambda: "Previous Track (←)")
            self.tooltip_manager.attach(self.btn_stop, lambda: "Stop (S)")
            self.tooltip_manager.attach(self.btn_next, lambda: "Next Track (→)")

        # ---------------- WAVEFORM SEEKBAR ----------------
        middle = ttk.Frame(self)
        middle.pack(side=tk.LEFT, padx=12)

        # Current time label (left side)
        self.current_time_var = tk.StringVar(value="--:--")
        self.current_time_label = ttk.Label(middle, textvariable=self.current_time_var, width=8, anchor="center")
        self.current_time_label.pack(side=tk.LEFT)

        # Create waveform seekbar with same height as control buttons
        self.waveform_seekbar = WaveformSeekbar(middle, self.player, self.theme, width=360, height=40)
        self.waveform_seekbar.pack(side=tk.LEFT, pady=2)

        # Total time label (right side)
        self.total_time_var = tk.StringVar(value="--:--")
        self.total_time_label = ttk.Label(middle, textvariable=self.total_time_var, width=8, anchor="center")
        self.total_time_label.pack(side=tk.LEFT)

        # ---------------- VOLUME ----------------
        right = ttk.Frame(self)
        right.pack(side=tk.RIGHT, padx=6)

        # Get initial volume and mute state from settings
        initial_volume = self.settings.volume if self.settings else 80
        initial_mute = self.settings.mute if self.settings else False

        # Mute button and volume slider in a horizontal frame
        volume_control_frame = ttk.Frame(right)
        volume_control_frame.pack(side=tk.TOP)

        # Mute button on the left
        self.mute_var = tk.BooleanVar(value=initial_mute)
        self.btn_mute = ctk.CTkButton(volume_control_frame, text=self._get_mute_label(initial_mute),
                                    command=self._on_mute_toggle, font=(symbol_font, 20), width=30, height=35,
                                    fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover)
        self.btn_mute.pack(side=tk.LEFT, padx=2)

        if self.tooltip_manager:
            self.tooltip_manager.attach(self.btn_mute, lambda: self._get_mute_tooltip(initial_mute))

        # Volume slider on the right - using CustomTkinter for modern look
        palette = self.theme.palette if hasattr(self.theme, 'palette') else {}
        slider_fg = palette.get("slider_fg", palette.get("accent", "#0078d4"))
        slider_bg = palette.get("slider_bg", "#E0E0E0")
        slider_hover = palette.get("slider_hover", palette.get("accent_hover", "#106ebe"))
        slider_progress = palette.get("slider_progress", palette.get("accent", "#0078d4"))
        frame_bg = palette.get("bg", "#FAFAFA")

        self.volume = ctk.CTkSlider(volume_control_frame, from_=0, to=100,
                                  command=self._on_volume_change,
                                  fg_color=slider_bg,
                                  bg_color=frame_bg,
                                  progress_color=slider_progress,
                                  button_color=slider_fg,
                                  button_hover_color=slider_hover,
                                  corner_radius=8,
                                  width=100,
                                  height=19)
        self.volume.set(initial_volume)
        self.volume.pack(side=tk.LEFT, padx=(5, 2))

        # Volume percentage label
        self.volume_percent_label = ctk.CTkLabel(volume_control_frame,
                                                text=f"{initial_volume}%",
                                                text_color=palette.get("fg", "#202020"),
                                                font=("Segoe UI", 14),
                                                width=40)
        self.volume_percent_label.pack(side=tk.LEFT, padx=(2, 5))

        # time updater
        self._update_id = None
        self._schedule_time_update()

        # ---------------- KEYBOARD SHORTCUTS ----------------
        master.bind("<Return>", lambda e: self._on_play(True))
        master.bind("<space>", lambda e: self._on_pause())
        master.bind("<Left>", lambda e: self._on_prev())
        master.bind("<Right>", lambda e: self._on_next())
        master.bind("<s>", lambda e: self._on_stop())
        master.bind("<m>", lambda e: self._on_mute_toggle())
        master.bind("<plus>", lambda e: self._volume_step(+5))
        master.bind("<minus>", lambda e: self._volume_step(-5))

    def _on_play(self, from_user=False):
        if from_user and self.playlist_tree:
            selected = self.playlist_tree.selection()
            if selected:
                self.state.current_index = self.playlist_tree.index(selected[0])
            elif self.state.playlist and self.state.current_index is None:
                self.state.current_index = 0

        if self.state.current_index is None and self.state.playlist:
            self.state.current_index = 0

        if self.state.current_index is not None:
            path = self.state.playlist[self.state.current_index]

            # Run player.play in a thread to prevent UI blocking
            threading.Thread(target=self.player.play, args=(path,), daemon=True).start()

            self.crossfade_triggered = False
            # Load waveform for the new track
            self.waveform_seekbar.load_waveform(path)

        # Set play button to pressed state and reset pause button only if playlist has songs
        if self.state.playlist and len(self.state.playlist) > 0:
            self.is_playing = True
            self.is_paused = False
            self._update_play_button_state()
            self._update_pause_button_state()
        else:
            # Reset both buttons to normal if playlist is empty
            self.is_playing = False
            self.is_paused = False
            self._update_play_button_state()
            self._update_pause_button_state()

        if self.playlist:
            self.playlist._highlight_current()
            try:
                self.playlist_tree.see(self.state.current_index)
            except Exception:
                pass

        self._send_status("play")

    def _on_pause(self):
        if self.player.is_playing() or self.player.is_paused():
            if self.is_paused:
                # Resume playback - set play button to pressed state
                self.player.pause()  # VLC's pause() method toggles - resumes when paused
                self.is_paused = False
                self.is_playing = True
                self._update_pause_button_state()
                self._update_play_button_state()
                self._send_status("play")
            else:
                # Pause playback - reset play button to normal
                self.pause()
                self._send_status("pause")

    def _on_stop(self):
        self.stop()
        self._send_status("stop")

    def _on_prev(self):
        self.prev()
        self._send_status("prev")

    def _on_next(self):
        self.next()
        self._send_status("next")

    def play(self):
        self.player.stop()
        self.is_paused = False
        self._update_pause_button_state()
        self._on_play(from_user=False)

    def pause(self):
        self.player.pause()
        self.is_paused = True
        self.is_playing = False
        self._update_pause_button_state()
        self._update_play_button_state()

    def stop(self):
        self.player.stop()
        self.is_paused = False
        self.is_playing = False
        # Clear current index to remove playing highlight
        self.state.current_index = None
        # Clear waveform when stopped
        self.waveform_seekbar.clear()
        # Update playlist highlight if available
        if self.playlist:
            self.playlist._highlight_current()
        self._update_pause_button_state()
        self._update_play_button_state()

    def prev(self):
        if self.state.current_index is None:
            return
        if self.state.current_index - 1 >= 0:
            # Stop current playback before changing to previous song
            self.player.stop()
            self.state.current_index -= 1
            self.is_paused = False
            self._update_pause_button_state()
            self._on_play(from_user=False)

    def next(self):
        if self.state.current_index is None:
            return
        if self.state.current_index + 1 < len(self.state.playlist):
            # Stop current playback before changing to next song
            self.player.stop()
            self.state.current_index += 1
            self.is_paused = False
            self._update_pause_button_state()
            self._on_play(from_user=False)

    def _on_mute_toggle(self):
        """Toggle mute state."""
        # Use local state when no media is playing, otherwise query player
        if self.player.is_playing() or self.player.is_paused():
            current_state = self.player.get_mute_state()
        else:
            current_state = self.is_muted

        new_state = not current_state

        # Update player
        self.player.set_mute(new_state)

        # Update mute button state and appearance
        self.is_muted = new_state
        self._update_mute_button_state()

        # Update button label (symbol only)
        self.btn_mute.configure(text=self._get_mute_label(new_state))

        # Update tooltip
        if self.tooltip_manager:
            self.tooltip_manager.attach(self.btn_mute, lambda: self._get_mute_tooltip(new_state))

        # Save to settings
        if self.settings:
            self.settings.mute = new_state
        new = int(self.volume.get())
        try:
            self.player.set_volume(int(new))
        except Exception:
            pass

    def _on_volume_change(self, val):
        volume_int = int(float(val))
        self.volume_percent_label.configure(text=f"{volume_int}%")
        if self.settings:
            self.settings.volume = volume_int
            try:
                self.settings.save()
            except Exception:
                pass
        try:
            self.player.set_volume(volume_int)
        except Exception:
            pass

    def _get_mute_label(self, is_muted: bool) -> str:
        """Get the mute button symbol based on mute state."""
        return "🔇" if is_muted else "🔊"

    def _get_mute_tooltip(self, is_muted: bool) -> str:
        """Get the mute button tooltip based on mute state."""
        return "Muted (M)" if is_muted else "Mute (M)"

    def _update_play_button_state(self):
        """Update play button color based on playing state."""
        palette = self.theme.palette if hasattr(self.theme, 'palette') else {}
        btn_bg = palette.get("button_bg_color")
        btn_pressed = palette.get("button_pressed")
        btn_fg = palette.get("button_fg_color")
        btn_hover = palette.get("button_hover")
        frame_bg = palette.get("bg")

        try:
            if self.is_playing:
                self.btn_play.configure(fg_color=btn_pressed, text_color=btn_fg, hover_color=btn_hover, bg_color=frame_bg)
            else:
                self.btn_play.configure(fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover, bg_color=frame_bg)
        except Exception:
            pass

    def _update_pause_button_state(self):
        """Update pause button color based on pause state."""
        palette = self.theme.palette if hasattr(self.theme, 'palette') else {}
        btn_bg = palette.get("button_bg_color")
        btn_pressed = palette.get("button_pressed")
        btn_fg = palette.get("button_fg_color")
        btn_hover = palette.get("button_hover")
        frame_bg = palette.get("bg")

        try:
            if self.is_paused:
                self.btn_pause.configure(fg_color=btn_pressed, text_color=btn_fg, hover_color=btn_hover, bg_color=frame_bg)
            else:
                self.btn_pause.configure(fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover, bg_color=frame_bg)
        except Exception:
            pass

    def _update_mute_button_state(self):
        """Update mute button color based on mute state."""
        palette = self.theme.palette if hasattr(self.theme, 'palette') else {}
        btn_bg = palette.get("button_bg_color")
        btn_pressed = palette.get("button_pressed")
        btn_fg = palette.get("button_fg_color")
        btn_hover = palette.get("button_hover")
        frame_bg = palette.get("bg")

        try:
            if self.is_muted:
                self.btn_mute.configure(fg_color=btn_pressed, text_color=btn_fg, hover_color=btn_hover, bg_color=frame_bg)
            else:
                self.btn_mute.configure(fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover, bg_color=frame_bg)
        except Exception:
            pass

    def _schedule_time_update(self):
        try:
            length_ms = self.player.get_length()
            pos_ms = self.player.get_time()
            if length_ms <= 0:
                self.current_time_var.set("--:--")
                self.total_time_var.set("--:--")
            else:
                cur_s = int(pos_ms // 1000)
                len_s = int(length_ms // 1000)
                self.current_time_var.set(f"{cur_s//60:02d}:{cur_s%60:02d}")
                self.total_time_var.set(f"{len_s//60:02d}:{len_s%60:02d}")

                # Check for crossfade trigger
                if self.is_playing and not self.is_paused and not self.crossfade_triggered:
                    if self.settings and getattr(self.settings, "crossfade_enabled", False):
                        duration = getattr(self.settings, "crossfade_duration", 5) * 1000 # ms
                        remaining = length_ms - pos_ms
                        if 0 < remaining <= duration:
                            self.crossfade_triggered = True
                            self._send_status("crossfade")
        except Exception:
            self.current_time_var.set("--:--")
            self.total_time_var.set("--:--")

        self._update_id = self.after(500, self._schedule_time_update)

    # ---------------- CLEANUP ----------------
    def update_theme(self):
        """Update button colors when theme changes."""
        palette = self.theme.palette if hasattr(self.theme, 'palette') else {}
        button_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        button_fg = palette.get("button_fg_color", "#ffffff")
        button_hover = palette.get("button_hover", palette.get("accent_hover", "#106ebe"))
        frame_bg = palette.get("bg", "#1E1E1E")

        # Update buttons (except play, pause, and mute buttons which have special state handling)
        for btn in [self.btn_prev, self.btn_stop, self.btn_next]:
            try:
                btn.configure(fg_color=button_bg, text_color=button_fg, hover_color=button_hover, bg_color=frame_bg)
            except Exception:
                pass

        # Update play, pause, and mute buttons with state-aware colors
        self._update_play_button_state()
        self._update_pause_button_state()
        self._update_mute_button_state()

        # Update volume slider
        try:
            slider_fg = palette.get("slider_fg", palette.get("accent", "#0078d4"))
            slider_bg = palette.get("slider_bg", "#E0E0E0")
            slider_hover = palette.get("slider_hover", palette.get("accent_hover", "#106ebe"))
            slider_progress = palette.get("slider_progress", palette.get("accent", "#0078d4"))

            self.volume.configure(fg_color=slider_bg,
                                bg_color=frame_bg,
                                progress_color=slider_progress,
                                button_color=slider_fg,
                                button_hover_color=slider_hover)

            self.volume_percent_label.configure(text_color=palette.get("fg", "#202020"),
                                                fg_color=frame_bg)
        except Exception:
            pass

        # Update waveform seekbar theme
        try:
            if hasattr(self, 'waveform_seekbar'):
                self.waveform_seekbar.update_theme()
        except Exception:
            pass

    def destroy(self):
        if self._update_id:
            try:
                self.after_cancel(self._update_id)
            except Exception:
                pass
        # Clean up waveform seekbar
        if hasattr(self, 'waveform_seekbar'):
            self.waveform_seekbar.destroy()
        super().destroy()

    # ---------------- STATUS CALLBACK ----------------
    def _send_status(self, event_type):
        if callable(self.status_callback):
            self.status_callback(event_type)

    def _check_and_analyze_bpm(self, filepath):
        """Check if BPM is missing and analyze it in a background thread."""
        try:
            # Get current metadata to check if BPM exists
            metadata = get_metadata(filepath)
            if metadata.get('bpm') is None:
                thread = threading.Thread(target=self._analyze_bpm_worker, args=(filepath,), daemon=True)
                thread.start()
        except Exception as e:
            logger.error(f"Error checking BPM for {filepath}: {e}")

    def _analyze_bpm_worker(self, filepath):
        """Worker function to analyze BPM and update UI temporarily."""
        try:
            analyzed_bpm = analyze_bpm(filepath)

            if analyzed_bpm is not None:
                # Store temporary BPM in metadata extractor cache without writing to file
                metadata_extractor._cache[filepath]['bpm'] = analyzed_bpm
                # Notify listeners to update UI with temporary BPM
                metadata_extractor._notify_bpm_listeners(filepath)
            else:
                logger.warning(f"BPM analysis returned None for {filepath}")
        except Exception as e:
            logger.error(f"Error in BPM analysis worker for {filepath}: {e}")