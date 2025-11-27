"""
Control bar: Play / Pause / Stop / Prev / Next and Volume + time label
"""

import tkinter as tk
from tkinter import ttk

class ControlsBar(ttk.Frame):
    def __init__(self, master, player, state, theme, playlist=None, tooltip_manager=None, status_callback=None):
        super().__init__(master)
        self.player = player
        self.state = state
        self.theme = theme
        self.tooltip_manager = tooltip_manager
        self.status_callback = status_callback
        self.playlist = playlist
        self.playlist_tree = self.playlist.tree

        left = ttk.Frame(self)
        left.pack(side=tk.LEFT, padx=6)

        ttk.Button(left, text="Play", command=self._on_play).pack(side=tk.LEFT, padx=4)
        ttk.Button(left, text="Pause", command=self.pause).pack(side=tk.LEFT, padx=4)
        ttk.Button(left, text="Prev", command=self._on_prev).pack(side=tk.LEFT, padx=4)
        ttk.Button(left, text="Stop", command=self._on_stop).pack(side=tk.LEFT, padx=4)
        ttk.Button(left, text="Next", command=self._on_next).pack(side=tk.LEFT, padx=4)

        middle = ttk.Frame(self)
        middle.pack(side=tk.LEFT, padx=12)
        self.time_var = tk.StringVar(value="00:00 / 00:00")
        ttk.Label(middle, textvariable=self.time_var).pack()

        right = ttk.Frame(self)
        right.pack(side=tk.RIGHT, padx=6)
        ttk.Label(right, text="Volume:").pack(side=tk.LEFT)
        self.volume = ttk.Scale(right, from_=0, to=100, orient="horizontal", command=self._on_volume_change)
        self.volume.set(80)
        self.volume.pack(side=tk.LEFT)

        if tooltip_manager:
            tooltip_manager.attach(self, lambda: "Playback controls")

        self._update_id = None
        self._schedule_time_update()

    def _on_play(self):
        if self.playlist_tree:
            selected = self.playlist_tree.selection()
            if selected:
                self.state.current_index = self.playlist_tree.index(selected[0])
            elif self.state.playlist and self.state.current_index is None:
                self.state.current_index = 0  # fallback to first song
        elif self.state.current_index is None and self.state.playlist:
            self.state.current_index = 0

        self.play()
        self.playlist._highlight_current()
        self._send_status("play")

    def pause(self):
        self.player.pause()
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

    def _on_volume_change(self, val):
        try:
            self.player.set_volume(int(float(val)))
        except Exception:
            pass

    def play(self):
        if self.state.current_index is None and self.state.playlist:
            self.state.current_index = 0
        if self.state.current_index is not None:
            path = self.state.playlist[self.state.current_index]
            self.player.play(path)

    def stop(self):
        self.player.stop()

    def prev(self):
        if self.state.current_index is None:
            return
        if self.state.current_index - 1 >= 0:
            self.state.current_index -= 1
            self.play()
        self.playlist._highlight_current()

    def next(self):
        if self.state.current_index is None:
            return
        if self.state.current_index + 1 < len(self.state.playlist):
            self.state.current_index += 1
            self.play()
        self.playlist._highlight_current()

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

    def destroy(self):
        if self._update_id:
            try:
                self.after_cancel(self._update_id)
            except Exception:
                pass
        super().destroy()

    def _send_status(self, event_type):
        if self.status_callback:
            self.status_callback(event_type)
