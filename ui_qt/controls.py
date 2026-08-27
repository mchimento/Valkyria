"""
Qt port of ui/controls.py — ControlsBar (Phase 2 scope only: Play/Pause/Stop,
volume/mute, time labels, waveform seekbar). No Prev/Next (needs a playlist
to navigate — not ported yet), no repeat/effects ExtrasBar.
"""

import logging
import threading
import time

from PySide6.QtCore import Qt, QTimer, Signal
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
    # ui_qt.player_bridge.PlayerBridge).
    _stop_finished = Signal()

    def __init__(self, player, settings, palette: dict, parent=None):
        super().__init__(parent)
        self.player = player
        self.settings = settings
        self.palette = palette
        self._is_muted = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.waveform = WaveformSeekbarQt(player, palette, width=360, height=40, parent=self)
        layout.addWidget(self.waveform)

        row = QHBoxLayout()
        row.setSpacing(6)

        self.btn_play = QPushButton("▶")
        self.btn_pause = QPushButton("⏸")
        self.btn_stop = QPushButton("■")
        for btn in (self.btn_play, self.btn_pause, self.btn_stop):
            btn.setObjectName("TransportButton")
            btn.setFixedSize(36, 28)
            row.addWidget(btn)

        self.current_time_label = QLabel("--:--")
        row.addWidget(self.current_time_label)
        row.addWidget(QLabel("/"))
        self.total_time_label = QLabel("--:--")
        row.addWidget(self.total_time_label)

        row.addStretch(1)

        self.btn_mute = QPushButton("🔊")
        self.btn_mute.setObjectName("TransportButton")
        self.btn_mute.setFixedSize(36, 28)
        row.addWidget(self.btn_mute)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        self.volume_slider.setFixedWidth(120)
        row.addWidget(self.volume_slider)

        self.volume_label = QLabel("0%")
        row.addWidget(self.volume_label)

        layout.addLayout(row)

        self.btn_play.clicked.connect(self._on_play_clicked)
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_stop.clicked.connect(self._on_stop)
        self.btn_mute.clicked.connect(self._on_mute_toggle)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)

        self._stop_finished.connect(self._finish_stop, Qt.QueuedConnection)

        self._init_volume()
        self._init_mute()

        self._time_timer = QTimer(self)
        self._time_timer.setInterval(500)
        self._time_timer.timeout.connect(self._schedule_time_update)
        self._time_timer.start()

        self._pending_path = None

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
        try:
            player_mute = self.player.get_mute_state()
            if player_mute is not None:
                initial_mute = bool(player_mute)
        except Exception:
            pass
        self._is_muted = initial_mute
        self.btn_mute.setText("🔇" if initial_mute else "🔊")
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

    # ---------- transport ----------

    def play_file(self, path: str) -> None:
        self._pending_path = path
        threading.Thread(target=self.player.play, args=(path,), daemon=True).start()
        self.waveform.load_waveform(path)

    def _on_play_clicked(self) -> None:
        if self._pending_path:
            self.play_file(self._pending_path)

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
                self._stop_finished.emit()

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
        else:
            self.current_time_label.setText("--:--")
            self.total_time_label.setText("--:--")

    # ---------- volume / mute ----------

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
        self.settings.mute = new_state
        self._save_settings()

    def _save_settings(self) -> None:
        try:
            self.settings.save()
        except Exception:
            logger.exception("Failed to save settings")
