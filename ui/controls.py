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
                 tooltip_manager=None, status_callback: Optional[Callable] = None) -> None:
        super().__init__(master)

        self.player = player
        self.state = state
        self.theme = theme
        self.tooltip_manager = tooltip_manager
        self.status_callback = status_callback
        self.playlist = playlist
        self.playlist_tree = self.playlist.tree if self.playlist else None

        left = ttk.Frame(self)
        left.pack(side=tk.LEFT, padx=6)

        btn_play = ttk.Button(left, text="Play", command=lambda: self._on_play(from_user=True))
        btn_play.pack(side=tk.LEFT, padx=4)

        btn_pause = ttk.Button(left, text="Pause", command=self._on_pause)
        btn_pause.pack(side=tk.LEFT, padx=4)

        btn_prev = ttk.Button(left, text="Prev", command=self._on_prev)
        btn_prev.pack(side=tk.LEFT, padx=4)

        btn_stop = ttk.Button(left, text="Stop", command=self._on_stop)
        btn_stop.pack(side=tk.LEFT, padx=4)

        btn_next = ttk.Button(left, text="Next", command=self._on_next)
        btn_next.pack(side=tk.LEFT, padx=4)

        if self.tooltip_manager:
            self.tooltip_manager.attach(btn_play, lambda: "Play")
            self.tooltip_manager.attach(btn_pause, lambda: "Pause")
            self.tooltip_manager.attach(btn_prev, lambda: "Previous Track")
            self.tooltip_manager.attach(btn_stop, lambda: "Stop")
            self.tooltip_manager.attach(btn_next, lambda: "Next Track")

        # ---------------- TIME LABEL ----------------
        middle = ttk.Frame(self)
        middle.pack(side=tk.LEFT, padx=12)
        self.time_var = tk.StringVar(value="00:00 / 00:00")
        ttk.Label(middle, textvariable=self.time_var).pack()

        # ---------------- VOLUME ----------------
        right = ttk.Frame(self)
        right.pack(side=tk.RIGHT, padx=6)
        ttk.Label(right, text="Volume:").pack(side=tk.LEFT)
        self.volume = ttk.Scale(right, from_=0, to=100, orient="horizontal",
                                command=self._on_volume_change)
        self.volume.set(80)
        self.volume.pack(side=tk.LEFT)

        # time updater
        self._update_id = None
        self._schedule_time_update()

        # ---------------- KEYBOARD SHORTCUTS ----------------
        master.bind("<Return>", lambda e: self._on_play(True))
        master.bind("<space>", lambda e: self._on_pause())
        master.bind("<Left>", lambda e: self._on_prev())
        master.bind("<Right>", lambda e: self._on_next())
        master.bind("<s>", lambda e: self._on_stop())
        master.bind("<plus>", lambda e: self._volume_step(+5))
        master.bind("<minus>", lambda e: self._volume_step(-5))

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

    def pause(self):
        self.player.pause()

    def stop(self):
        self.player.stop()

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
        try:
            self.player.set_volume(int(new))
        except Exception:
            pass

    def _on_volume_change(self, val):
        try:
            self.player.set_volume(int(float(val)))
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
