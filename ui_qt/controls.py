"""
ControlsBar: Play/Pause/Prev/Stop/Next, volume/mute, time labels, waveform
seekbar, and the repeat/effects buttons.
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
    stopped = Signal()

    play_requested = Signal()
    prev_requested = Signal()
    next_requested = Signal()
    repeat_toggle_requested = Signal()
    effects_requested = Signal()
    crossfade_requested = Signal()
    time_limit_reached = Signal()
    paused_state_changed = Signal(bool)

    def __init__(self, player, settings, palette: dict, state=None, parent=None):
        super().__init__(parent)
        self.player = player
        self.settings = settings
        self.palette = palette
        self.state = state
        self._is_muted = False
        self._crossfade_fired = False
        self._time_limit_fired = False
        self.is_playing = False
        self.is_paused = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(6)

        # Built from the Geometric Shapes block (same as ▶/■) rather than the
        # Miscellaneous Technical "media control" glyphs (⏸/⏮/⏭) — Windows'
        # emoji font renders those in full color regardless of the text
        # variation selector, ignoring the button's theme color.
        self.btn_play = QPushButton("▶")
        self.btn_pause = QPushButton("▮▮")
        self.btn_prev = QPushButton("◀◀")
        self.btn_stop = QPushButton("■")
        self.btn_next = QPushButton("▶▶")
        for btn in (self.btn_play, self.btn_pause, self.btn_prev, self.btn_stop, self.btn_next):
            btn.setObjectName("TransportButton")
            btn.setFixedSize(44, 36)
            row.addWidget(btn)
        self.btn_play.setToolTip("Play (Enter)")
        self.btn_pause.setToolTip("Pause/Resume (Space)")
        self.btn_prev.setToolTip("Previous Track (←)")
        self.btn_stop.setToolTip("Stop (S)")
        self.btn_next.setToolTip("Next Track (→)")

        row.addStretch(1)

        self.current_time_label = QLabel("--:--")
        self.total_time_label = QLabel("--:--")
        time_width = QFontMetrics(self.current_time_label.font()).horizontalAdvance("00:00") + 10
        for label in (self.current_time_label, self.total_time_label):
            label.setFixedWidth(time_width)
            label.setAlignment(Qt.AlignCenter)
        row.addWidget(self.current_time_label)
        self.waveform = WaveformSeekbarQt(player, palette, width=360, height=40, parent=self)
        row.addWidget(self.waveform)
        row.addWidget(self.total_time_label)

        row.addStretch(1)

        self.btn_repeat = QPushButton("↻")
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

        row.addWidget(self.btn_mute)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setFixedWidth(120)
        row.addWidget(self.volume_slider)

        self.volume_label = QLabel("0%")
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
        self._update_play_pause_button_states()

    def _update_play_pause_button_states(self) -> None:
        """Whichever of Play/Pause reflects what's currently happening gets
        the button_pressed background, the other goes back to normal.
        """
        pressed = self.palette.get("button_pressed", "#6023CB")
        self.btn_play.setStyleSheet(f"background-color: {pressed};" if self.is_playing else "")
        self.btn_pause.setStyleSheet(f"background-color: {pressed};" if self.is_paused else "")

    def set_repeat_icon(self, mode: str) -> None:
        pressed = self.palette.get("button_pressed", "#6023CB")
        if mode == "one":
            self.btn_repeat.setText("↻¹")
            self.btn_repeat.setStyleSheet(f"background-color: {pressed};")
        elif mode == "all":
            self.btn_repeat.setText("↻")
            self.btn_repeat.setStyleSheet(f"background-color: {pressed};")
        else:
            self.btn_repeat.setText("↻")
            self.btn_repeat.setStyleSheet("")
        self.btn_repeat.setToolTip(f"Repeat Mode: {mode.title()}")

    # ---------- transport ----------

    def play_file(self, path: str) -> None:
        self.current_time_label.setText("00:00")
        self.total_time_label.setText("--:--")
        self._crossfade_fired = False
        self._time_limit_fired = False
        threading.Thread(target=self.player.play, args=(path,), daemon=True).start()
        self.waveform.load_waveform(path)
        self.is_playing = True
        self.is_paused = False
        self._update_play_pause_button_states()

    def _on_pause(self) -> None:
        try:
            if not (self.player.is_playing() or self.player.is_paused()):
                return
            self.player.pause()
            is_paused = self.player.is_paused()
            self.is_paused = is_paused
            self.is_playing = not is_paused
            self._update_play_pause_button_states()
            self.paused_state_changed.emit(is_paused)
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
        self.is_playing = False
        self.is_paused = False
        self._update_play_pause_button_states()

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
            self._check_time_limit(time_ms)
        else:
            self.current_time_label.setText("--:--")
            self.total_time_label.setText("--:--")

    def _check_crossfade(self, time_ms: int, length_ms: int) -> None:
        """Once within crossfade_duration of the end, request an early
        advance to the next track — this is really just early-advance
        timing, not real audio blending (audio/audio_player.py has no
        crossfade logic at all)."""
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

    def _check_time_limit(self, time_ms: int) -> None:
        """Signals MainWindowQt to advance via _on_track_ended — the same
        repeat-mode-aware path crossfade already uses above."""
        if self._time_limit_fired or self.state is None:
            return
        try:
            if not self.player.is_playing() or self.player.is_paused():
                return
        except Exception:
            return
        idx = self.state.current_index
        if idx is None or idx >= len(self.state.playlist):
            return
        limit_s = self.state.play_limits.get(self.state.playlist[idx])
        if limit_s is not None and time_ms >= limit_s * 1000:
            self._time_limit_fired = True
            self.time_limit_reached.emit()

    # ---------- volume / mute ----------

    def step_volume(self, delta: int) -> None:
        """setValue() clamps to the slider's 0-100 range on its own."""
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
        self.btn_mute.setToolTip("Muted (M)" if self._is_muted else "Mute (M)")

    def _save_settings(self) -> None:
        try:
            self.settings.save()
        except Exception:
            logger.exception("Failed to save settings")
