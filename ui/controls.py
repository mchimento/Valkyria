"""
Control bar: Play / Pause / Stop / Prev / Next and Volume + time label
"""

import logging
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable

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

        # Store button references for theme updates and hover behavior
        self.control_buttons = []
        self._button_colors = {}  # Store original and hover colors for each button

        left = ttk.Frame(self)
        left.pack(side=tk.LEFT, padx=6)

        # Create a larger font for the button symbols
        symbol_font = ("Segoe UI", 14, "bold")

        # Get button colors from theme palette
        palette = self.theme.palette if hasattr(self.theme, 'palette') else {}
        btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        btn_fg = palette.get("button_fg_color", "#ffffff")
        btn_hover = palette.get("button_hover", palette.get("accent_hover", "#106ebe"))
        
        # Create custom style for control buttons
        style = ttk.Style()
        style.configure('Control.TButton',
                       font=symbol_font,
                       padding=0,
                       width=3,
                       borderwidth=2,
                       relief='raised',
                       background=btn_bg,
                       foreground=btn_fg)
        style.map('Control.TButton',
                 background=[('active', btn_hover), ('pressed', btn_hover)],
                 relief=[('pressed', 'sunken'), ('!pressed', 'raised')])

        btn_play = ttk.Button(left, text="▶", command=lambda: self._on_play(from_user=True),
                             style='Control.TButton', width=3)
        btn_play.pack(side=tk.LEFT, padx=4, pady=2)
        self.control_buttons.append(btn_play)

        btn_pause = ttk.Button(left, text="⏸", command=self._on_pause,
                              style='Control.TButton', width=3)
        btn_pause.pack(side=tk.LEFT, padx=4, pady=2)
        self.control_buttons.append(btn_pause)

        btn_prev = ttk.Button(left, text="⏮", command=self._on_prev,
                             style='Control.TButton', width=3)
        btn_prev.pack(side=tk.LEFT, padx=4, pady=2)
        self.control_buttons.append(btn_prev)

        btn_stop = ttk.Button(left, text="⏹", command=self._on_stop,
                             style='Control.TButton', width=3)
        btn_stop.pack(side=tk.LEFT, padx=4, pady=2)
        self.control_buttons.append(btn_stop)

        btn_next = ttk.Button(left, text="⏭", command=self._on_next,
                             style='Control.TButton', width=3)
        btn_next.pack(side=tk.LEFT, padx=4, pady=2)
        self.control_buttons.append(btn_next)

        if self.tooltip_manager:
            self.tooltip_manager.attach(btn_play, lambda: "Play (Enter)")
            self.tooltip_manager.attach(btn_pause, lambda: "Pause/Resume (Space)")
            self.tooltip_manager.attach(btn_prev, lambda: "Previous Track (←)")
            self.tooltip_manager.attach(btn_stop, lambda: "Stop (S)")
            self.tooltip_manager.attach(btn_next, lambda: "Next Track (→)")

        # ---------------- TIME LABEL ----------------
        middle = ttk.Frame(self)
        middle.pack(side=tk.LEFT, padx=12)
        self.time_var = tk.StringVar(value="00:00 / 00:00")
        ttk.Label(middle, textvariable=self.time_var).pack(side=tk.LEFT)

        # Play on double-click checkbutton
        self.play_on_double_var = tk.BooleanVar(value=self.state.play_on_double)
        self.play_on_double_var.trace_add('write', lambda *args: self._on_play_on_double_change())
        ttk.Checkbutton(middle, text="Play on double-click", variable=self.play_on_double_var, style='TCheckbutton').pack(side=tk.LEFT, padx=(12, 0))

        # ---------------- VOLUME ----------------
        right = ttk.Frame(self)
        right.pack(side=tk.RIGHT, padx=6)

        # Get initial volume and mute state from settings
        initial_volume = self.settings.volume if self.settings else 80
        initial_mute = self.settings.mute if self.settings else False

        # Volume label variable (must be created before slider that uses it)
        self.volume_var = tk.StringVar(value=f"Volume: {initial_volume}%")

        # Volume label positioned above the volume slider
        volume_label = ttk.Label(right, textvariable=self.volume_var)
        volume_label.pack(side=tk.TOP, padx=(45, 0))

        # Mute button and volume slider in a horizontal frame
        volume_control_frame = ttk.Frame(right)
        volume_control_frame.pack(side=tk.TOP)

        # Mute button on the left
        self.mute_var = tk.BooleanVar(value=initial_mute)
        self.btn_mute = ttk.Button(volume_control_frame, text=self._get_mute_label(initial_mute),
                                    command=self._on_mute_toggle, width=3)
        self.btn_mute.pack(side=tk.LEFT, padx=2)

        if self.tooltip_manager:
            self.tooltip_manager.attach(self.btn_mute, lambda: self._get_mute_tooltip(initial_mute))

        # Volume slider on the right
        self.volume = ttk.Scale(volume_control_frame, from_=0, to=100, orient="horizontal",
                                command=self._on_volume_change)
        self.volume.set(initial_volume)
        self.volume.pack(side=tk.LEFT, padx=5)

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

    def _add_button_hover(self, button, normal_bg, normal_fg, hover_bg):
        """Add hover effect to a tk.Button."""
        self._button_colors[id(button)] = {
            'normal_bg': normal_bg,
            'normal_fg': normal_fg,
            'hover_bg': hover_bg
        }
        button.bind("<Enter>", lambda e: self._on_button_enter(button))
        button.bind("<Leave>", lambda e: self._on_button_leave(button))

    def _on_button_enter(self, button):
        """Handle mouse entering button."""
        colors = self._button_colors.get(id(button))
        if colors:
            button.configure(bg=colors['hover_bg'])

    def _on_button_leave(self, button):
        """Handle mouse leaving button."""
        colors = self._button_colors.get(id(button))
        if colors:
            button.configure(bg=colors['normal_bg'])

    def _on_play(self, from_user=False):
        if from_user and self.playlist_tree:
            selected = self.playlist_tree.selection()
            if selected:
                self.state.current_index = self.playlist_tree.index(selected[0])
            elif self.state.playlist and self.state.current_index is None:
                self.state.current_index = 0

        # default to first song
        if self.state.current_index is None and self.state.playlist:
            self.state.current_index = 0

        # play
        if self.state.current_index is not None:
            path = self.state.playlist[self.state.current_index]
            self.player.play(path)

        # highlight & auto-scroll (Suggestion #3)
        if self.playlist:
            self.playlist._highlight_current()
            try:
                self.playlist_tree.see(self.state.current_index)
            except Exception:
                pass

        self._send_status("play")

    def _on_pause(self):
        if self.player.is_playing() or self.player.is_paused():
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
        self._on_play(from_user=False)

    def pause(self):
        self.player.pause()

    def stop(self):
        self.player.stop()

    def _get_mute_label(self, is_muted: bool) -> str:
        """Get the mute button symbol based on mute state."""
        return "🔇" if is_muted else "🔊"

    def _get_mute_tooltip(self, is_muted: bool) -> str:
        """Get the mute button tooltip based on mute state."""
        return "Muted (M)" if is_muted else "Mute (M)"

    def _on_mute_toggle(self):
        """Toggle mute state."""
        current_state = self.player.get_mute_state()
        new_state = not current_state

        # Update player
        self.player.set_mute(new_state)

        # Update button label (symbol only)
        self.btn_mute.config(text=self._get_mute_label(new_state))

        # Update tooltip
        if self.tooltip_manager:
            self.tooltip_manager.attach(self.btn_mute, lambda: self._get_mute_tooltip(new_state))

        # Save to settings
        if self.settings:
            self.settings.mute = new_state
            try:
                self.settings.save()
            except Exception:
                pass

    def prev(self):
        if self.state.current_index is None:
            return
        if self.state.current_index - 1 >= 0:
            self.state.current_index -= 1
            self._on_play(from_user=False)

    def next(self):
        if self.state.current_index is None:
            return
        if self.state.current_index + 1 < len(self.state.playlist):
            self.state.current_index += 1
            self._on_play(from_user=False)

    # ---------------- VOLUME STEPS FOR + / - KEYS ----------------
    def _volume_step(self, delta):
        new = max(0, min(100, self.volume.get() + delta))
        self.volume.set(new)
        self.volume_var.set(f"Volume: {int(new)}%")
        try:
            self.player.set_volume(int(new))
        except Exception:
            pass

    def _on_volume_change(self, val):
        volume_int = int(float(val))
        self.volume_var.set(f"Volume: {volume_int}%")
        # Save volume to settings
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

    # ---------------- TIME UPDATE ----------------
    def _schedule_time_update(self):
        try:
            length_ms = self.player.get_length()
            pos_ms = self.player.get_time()
            if length_ms <= 0:
                self.time_var.set("00:00 / 00:00")
            else:
                cur_s = int(pos_ms // 1000)
                len_s = int(length_ms // 1000)
                self.time_var.set(f"{cur_s//60:02d}:{cur_s%60:02d} / {len_s//60:02d}:{len_s%60:02d}")
        except Exception:
            self.time_var.set("00:00 / 00:00")

        self._update_id = self.after(500, self._schedule_time_update)

    # ---------------- CLEANUP ----------------
    def update_theme(self):
        """Update button colors when theme changes."""
        palette = self.theme.palette if hasattr(self.theme, 'palette') else {}
        btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        btn_fg = palette.get("button_fg_color", "#ffffff")
        btn_hover = palette.get("button_hover", palette.get("accent_hover", "#106ebe"))

        for btn in self.control_buttons:
            btn.configure(bg=btn_bg, fg=btn_fg)
            # Update stored colors for hover effects
            self._button_colors[id(btn)] = {
                'normal_bg': btn_bg,
                'normal_fg': btn_fg,
                'hover_bg': btn_hover
            }

    def _on_play_on_double_change(self):
        """Handle play_on_double_click setting change."""
        self.state.play_on_double = self.play_on_double_var.get()

    def destroy(self):
        if self._update_id:
            try:
                self.after_cancel(self._update_id)
            except Exception:
                pass
        super().destroy()

    # ---------------- STATUS CALLBACK ----------------
    def _send_status(self, event_type):
        if callable(self.status_callback):
            self.status_callback(event_type)
