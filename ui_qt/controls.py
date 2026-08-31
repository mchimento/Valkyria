"""
Qt port of ui/controls.py — ControlsBar: Play/Pause/Prev/Stop/Next,
volume/mute, time labels, waveform seekbar, and the repeat/effects
ExtrasBar (ui/controls.py:16-56). Play/Prev/Next/repeat-toggle/effects-open
are emitted as signals rather than handled here directly — the actual
"which track" / "which index is next" / "open the effects window" policy
lives in MainWindowQt, which owns state and playlist_view (mirrors the
original's split between ControlsBar's play()/prev()/next() mechanism and
MainWindow's policy methods). Play in particular needs playlist_view's
current selection — ui/controls.py's ControlsBar._on_play(from_user=True)
plays whatever's selected, not just whatever was last loaded, which this
widget alone can't determine.
"""

import logging
import threading
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from ui_qt.waveform_seekbar import WaveformSeekbarQt

logger = logging.getLogger(__name__)


def _format_ms(ms) -> str:
    if not ms or ms <= 0:
        return "--:--"
    total_seconds = int(ms // 1000)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


class ControlsBarQt(QWidget):
    # Emitted from the stop-sequence worker thread once the fade-out wait
    # and player.stop() complete; Qt auto-queues delivery to the main thread
    # since this widget has main-thread affinity (same pattern as
    # ui_qt.player_bridge.PlayerBridge). Public (unlike a leading-underscore
    # name would suggest) because MainWindowQt also needs it — clearing
    # state.current_index and the playlist's now-playing highlight on stop
    # is policy that lives at that level, same as play/prev/next.
    stopped = Signal()

    play_requested = Signal()
    prev_requested = Signal()
    next_requested = Signal()
    repeat_toggle_requested = Signal()
    effects_requested = Signal()
    crossfade_requested = Signal()

    def __init__(self, player, settings, palette: dict, state=None, parent=None):
        super().__init__(parent)
        self.player = player
        self.settings = settings
        self.palette = palette
        self.state = state
        self._is_muted = False
        self._crossfade_fired = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(6)

        # Order matches ui/controls.py: play, pause, prev, stop, next.
        self.btn_play = QPushButton("▶")
        self.btn_pause = QPushButton("⏸")
        self.btn_prev = QPushButton("⏮")
        self.btn_stop = QPushButton("■")
        self.btn_next = QPushButton("⏭")
        for btn in (self.btn_play, self.btn_pause, self.btn_prev, self.btn_stop, self.btn_next):
            btn.setObjectName("TransportButton")
            btn.setFixedSize(44, 36)
            row.addWidget(btn)
        self.btn_play.setToolTip("Play (Enter)")
        self.btn_pause.setToolTip("Pause/Resume (Space)")
        self.btn_prev.setToolTip("Previous Track (←)")
        self.btn_stop.setToolTip("Stop (S)")
        self.btn_next.setToolTip("Next Track (→)")

        # Balances the stretch after total_time_label so the waveform group is centered.
        row.addStretch(1)

        # Matches ui/controls.py:165-181 exactly: current time, waveform,
        # total time all live inline in the same row as the transport
        # buttons ("middle" frame in the original) — not stacked above them
        # on a row of their own.
        self.current_time_label = QLabel("--:--")
        self.total_time_label = QLabel("--:--")
        # ui/controls.py sets width=8 (character cells) on these labels
        # specifically to stop them reflowing the row as the text changes
        # length every tick — without a fixed width, everything to the
        # right (the waveform included) visibly shifts sideways as the
        # elapsed-time text grows/shrinks digit by digit.
        time_width = QFontMetrics(self.current_time_label.font()).horizontalAdvance("00:00") + 10
        for label in (self.current_time_label, self.total_time_label):
            label.setFixedWidth(time_width)
            label.setAlignment(Qt.AlignCenter)
        row.addWidget(self.current_time_label)
        self.waveform = WaveformSeekbarQt(player, palette, width=360, height=40, parent=self)
        row.addWidget(self.waveform)
        row.addWidget(self.total_time_label)

        row.addStretch(1)

        self.btn_repeat = QPushButton("🔁")
        self.btn_effects = QPushButton("🎚")
        for btn in (self.btn_repeat, self.btn_effects):
            btn.setObjectName("TransportButton")
            btn.setFixedSize(48, 40)
        row.addWidget(self.btn_repeat)
        row.addWidget(self.btn_effects)
        self.btn_effects.setToolTip("Audio Effects (F7)")

        self.btn_mute = QPushButton("🔊")
        self.btn_mute.setObjectName("TransportButton")
        self.btn_mute.setFixedSize(44, 36)
        # Tooltip set dynamically by _init_mute()/_update_mute_tooltip() below.
        row.addWidget(self.btn_mute)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setFixedWidth(120)
        row.addWidget(self.volume_slider)

        self.volume_label = QLabel("0%")
        # Fixed width so its text change doesn't reshuffle the right-aligned group.
        volume_label_width = QFontMetrics(self.volume_label.font()).horizontalAdvance("100%") + 10
        self.volume_label.setFixedWidth(volume_label_width)
        self.volume_label.setAlignment(Qt.AlignCenter)
        row.addWidget(self.volume_label)

        layout.addLayout(row)

        self.btn_play.clicked.connect(self.play_requested)
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_prev.clicked.connect(self.prev_requested)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_next.clicked.connect(self.next_requested)
        self.btn_repeat.clicked.connect(self.repeat_toggle_requested)
        self.btn_effects.clicked.connect(self.effects_requested)
        self.btn_mute.clicked.connect(self._on_mute_toggle)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)

        self.stopped.connect(self._finish_stop, Qt.QueuedConnection)

        self._init_volume()
        self._init_mute()
        self.set_repeat_icon(self.state.repeat_mode if self.state else "none")

        self._time_timer = QTimer(self)
        self._time_timer.setInterval(500)
        self._time_timer.timeout.connect(self._schedule_time_update)
        self._time_timer.start()

    # ---------- initial state ----------

    def _init_volume(self) -> None:
        initial_volume = int(getattr(self.settings, "volume", 80) or 0)
        self.volume_slider.setValue(initial_volume)  # fires _on_volume_changed once, harmless
        try:
            self.player.set_volume(initial_volume)
        except Exception:
            logger.exception("Failed to apply initial volume")

    def _init_mute(self) -> None:
        # settings.mute is the source of truth here — the player is always
        # freshly constructed right before ControlsBarQt (see main_qt.py),
        # so get_mute_state() would just return its constructor default
        # (False) and silently reset a saved "muted" preference back to
        # unmuted on every launch. Push settings' value into the player
        # below, not the other way around.
        initial_mute = bool(getattr(self.settings, "mute", False))
        self._is_muted = initial_mute
        self.btn_mute.setText("🔇" if initial_mute else "🔊")
        self._update_mute_tooltip()
        try:
            self.player.set_mute(initial_mute)
        except Exception:
            logger.exception("Failed to apply initial mute state")
        self.settings.mute = initial_mute
        self._save_settings()

    # ---------- theming ----------

    def apply_palette(self, palette: dict) -> None:
        self.palette = palette
        self.waveform.apply_palette(palette)

    def set_repeat_icon(self, mode: str) -> None:
        """Called by MainWindowQt after it changes state.repeat_mode —
        matches ui/controls.py's ExtrasBar._update_repeat_icon: 'none' is
        the plain button, 'one' swaps to the single-repeat glyph, 'all'
        keeps the loop glyph but both 'one'/'all' get the active
        (button_pressed) background.

        Also updates the tooltip, matching ExtrasBar's dynamic
        `f"Repeat Mode: {mode.title()}"` tooltip (ui/controls.py:54) — an
        earlier version left the Qt tooltip as a static "Repeat Mode"
        string that never reflected the current mode, unlike Tk's."""
        pressed = self.palette.get("button_pressed", "#6023CB")
        if mode == "one":
            self.btn_repeat.setText("🔂")
            self.btn_repeat.setStyleSheet(f"background-color: {pressed};")
        elif mode == "all":
            self.btn_repeat.setText("🔁")
            self.btn_repeat.setStyleSheet(f"background-color: {pressed};")
        else:
            self.btn_repeat.setText("🔁")
            self.btn_repeat.setStyleSheet("")
        self.btn_repeat.setToolTip(f"Repeat Mode: {mode.title()}")

    # ---------- transport ----------

    def play_file(self, path: str) -> None:
        # Matches ui/controls.py:286-288's _on_play: reset the time labels
        # immediately rather than leaving the previous track's stale
        # elapsed/total time visible until the next 500ms timer tick.
        self.current_time_label.setText("00:00")
        self.total_time_label.setText("--:--")
        self._crossfade_fired = False
        threading.Thread(target=self.player.play, args=(path,), daemon=True).start()
        self.waveform.load_waveform(path)

    def _on_pause(self) -> None:
        try:
            self.player.pause()
        except Exception:
            logger.exception("pause() failed")

    def _on_stop(self) -> None:
        def _stop_sequence():
            try:
                wait = self.player.trigger_fade_out()
            except Exception:
                wait = 0
            if wait and wait > 0:
                time.sleep(wait)
            try:
                self.player.stop()
            except Exception:
                logger.exception("stop() failed")
            finally:
                self.stopped.emit()

        threading.Thread(target=_stop_sequence, daemon=True).start()

    def _finish_stop(self) -> None:
        self.waveform.clear()
        self.current_time_label.setText("--:--")
        self.total_time_label.setText("--:--")

    def on_track_ended(self) -> None:
        """Connected to PlayerBridge.track_ended. No playlist yet, so a
        finished track just stops cleanly rather than auto-advancing."""
        self._finish_stop()

    def _schedule_time_update(self) -> None:
        try:
            length_ms = self.player.get_length()
            time_ms = self.player.get_time()
        except Exception:
            return
        if length_ms and length_ms > 0:
            self.current_time_label.setText(_format_ms(time_ms))
            self.total_time_label.setText(_format_ms(length_ms))
            self._check_crossfade(time_ms, length_ms)
        else:
            self.current_time_label.setText("--:--")
            self.total_time_label.setText("--:--")

    def _check_crossfade(self, time_ms: int, length_ms: int) -> None:
        """Matches ui/controls.py:567-574: once within crossfade_duration
        of the end, request an early advance to the next track — the
        original's "crossfade" is really just early-advance timing, not
        real audio blending (audio/audio_player.py has no crossfade logic
        at all), so this matches it exactly rather than under- or
        over-implementing. state.crossfade_enabled/crossfade_duration were
        already fully wired end-to-end by the Playback Features dialog,
        but nothing here ever polled them, so toggling Crossfade on had no
        actual effect until now."""
        if self._crossfade_fired or self.state is None:
            return
        if not getattr(self.state, "crossfade_enabled", False):
            return
        try:
            if not self.player.is_playing() or self.player.is_paused():
                return
        except Exception:
            return
        duration_ms = getattr(self.state, "crossfade_duration", 5) * 1000
        remaining = length_ms - time_ms
        if 0 < remaining <= duration_ms:
            self._crossfade_fired = True
            self.crossfade_requested.emit()

    # ---------- volume / mute ----------

    def step_volume(self, delta: int) -> None:
        """Mirrors ui/controls.py's <plus>/<minus>-bound _volume_step —
        setValue() clamps to the slider's 0-100 range on its own."""
        self.volume_slider.setValue(self.volume_slider.value() + delta)

    def _on_volume_changed(self, value: int) -> None:
        self.volume_label.setText(f"{value}%")
        self.settings.volume = value
        self._save_settings()
        try:
            self.player.set_volume(value)
        except Exception:
            logger.exception("set_volume() failed")

    def _on_mute_toggle(self) -> None:
        new_state = not self._is_muted
        try:
            self.player.set_mute(new_state)
        except Exception:
            logger.exception("set_mute() failed")
        self._is_muted = new_state
        self.btn_mute.setText("🔇" if new_state else "🔊")
        self._update_mute_tooltip()
        self.settings.mute = new_state
        self._save_settings()

    def _update_mute_tooltip(self) -> None:
        # Matches ui/controls.py's _get_mute_tooltip: "Muted (M)"/"Mute (M)"
        # — an earlier version set this once at construction and never
        # again, unlike the repeat button's tooltip (see set_repeat_icon).
        self.btn_mute.setToolTip("Muted (M)" if self._is_muted else "Mute (M)")

    def _save_settings(self) -> None:
        try:
            self.settings.save()
        except Exception:
            logger.exception("Failed to save settings")
