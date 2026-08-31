"""Qt port of ui/status_frame_view.py — artwork, title/artist, format info,
and a time-limit countdown for the currently playing track."""

import logging
import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from audio.metadata import get_best_artwork, get_metadata

logger = logging.getLogger(__name__)

ARTWORK_SIZE = 100


class StatusViewQt(QWidget):
    def __init__(self, state, theme, settings, parent=None):
        super().__init__(parent)
        self.state = state
        self.theme = theme
        self.settings = settings
        self.palette = theme.palette
        self._base_meta_text = ""
        self._controls_ref = None

        self.setFixedHeight(150)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 12, 0, 0)

        self.panel = QFrame(self)
        self.panel.setObjectName("StatusPanel")
        self.panel.setAttribute(Qt.WA_StyledBackground, True)
        outer.addWidget(self.panel, 1)

        content = QHBoxLayout(self.panel)
        content.setContentsMargins(12, 10, 12, 10)
        content.setSpacing(12)

        self.artwork_label = QLabel(self.panel)
        self.artwork_label.setFixedSize(ARTWORK_SIZE, ARTWORK_SIZE)
        self.artwork_label.setAlignment(Qt.AlignCenter)
        content.addWidget(self.artwork_label, 0, Qt.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(4)

        self.title_label = QLabel("")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        text_col.addWidget(self.title_label)

        self.artist_label = QLabel("")
        artist_font = QFont()
        artist_font.setPointSize(15)
        self.artist_label.setFont(artist_font)
        text_col.addWidget(self.artist_label)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)
        meta_font = QFont()
        meta_font.setPointSize(14)
        self.meta_label = QLabel("")
        self.meta_label.setFont(meta_font)
        meta_row.addWidget(self.meta_label)

        time_limit_font = QFont()
        time_limit_font.setPointSize(14)
        time_limit_font.setBold(True)
        self.time_limit_label = QLabel("")
        self.time_limit_label.setFont(time_limit_font)
        meta_row.addWidget(self.time_limit_label)
        meta_row.addStretch(1)
        text_col.addLayout(meta_row)
        text_col.addStretch(1)

        content.addLayout(text_col, 1)

        self._restore_timer = QTimer(self)
        self._restore_timer.setSingleShot(True)
        self._restore_timer.timeout.connect(self.restore_status)

        self._time_limit_timer = QTimer(self)
        self._time_limit_timer.setInterval(1000)
        self._time_limit_timer.timeout.connect(self._update_time_limit)

        self._apply_colors()
        self._update_artwork(None)

    # ---------- public API ----------

    def restore_status(self) -> None:
        self._restore_timer.stop()

        idx = self.state.current_index
        if idx is None or idx >= len(self.state.playlist):
            self._clear_status()
            return

        path = self.state.playlist[idx]
        meta = get_metadata(path)
        title = meta.get("title") or os.path.basename(path)
        artist = meta.get("artist") or ""
        duration_s = meta.get("duration_s")
        bitrate = meta.get("bitrate")

        self._update_artwork(path)
        self.title_label.setText(title)
        self.artist_label.setText(artist)

        parts = []
        if duration_s:
            parts.append(f"{int(duration_s) // 60:02d}:{int(duration_s) % 60:02d}")
        if bitrate:
            parts.append(f"{bitrate} kbps")
        self._base_meta_text = " • ".join(parts)
        self.meta_label.setText(self._base_meta_text)
        self.time_limit_label.setText("")

    def set_temporary_status(self, message: str, duration: int = 3000) -> None:
        self.title_label.setText(message)
        self._restore_timer.stop()
        self._restore_timer.start(duration)

    def schedule_restore(self, delay: int = 3000) -> None:
        self._restore_timer.stop()
        self._restore_timer.start(delay)

    def handle_stop(self) -> None:
        self._restore_timer.stop()
        self._clear_status()

    def apply_palette(self, palette: dict) -> None:
        self.palette = palette
        self._apply_colors()
        idx = self.state.current_index
        if idx is not None and 0 <= idx < len(self.state.playlist):
            self._update_artwork(self.state.playlist[idx])

    # ---------- time-limit ticker ----------

    def _start_time_limit_updates(self, controls) -> None:
        self._controls_ref = controls
        self._time_limit_timer.stop()
        self._update_time_limit()
        self._time_limit_timer.start()

    def _stop_time_limit_updates(self) -> None:
        self._time_limit_timer.stop()

    def _update_time_limit(self) -> None:
        idx = self.state.current_index
        if idx is None or idx >= len(self.state.playlist):
            self.meta_label.setText(self._base_meta_text)
            self._stop_time_limit_updates()
            return

        filepath = self.state.playlist[idx]
        if filepath not in self.state.play_limits:
            self.meta_label.setText(self._base_meta_text)
            self._stop_time_limit_updates()
            return

        limit_seconds = int(self.state.play_limits[filepath])
        remaining_text = f"⏱ Time limit: {limit_seconds}s"
        if self._controls_ref is not None:
            try:
                pos_s = int(self._controls_ref.player.get_time() // 1000)
                remaining = max(0, limit_seconds - pos_s)
                remaining_text = f"⏱ Time limit: {remaining}s remaining"
            except Exception:
                logger.exception("Failed to read playback position for time limit")

        self.meta_label.setText(self._base_meta_text)
        self.time_limit_label.setText(remaining_text)

    # ---------- internals ----------

    def _clear_status(self) -> None:
        self._stop_time_limit_updates()
        self._base_meta_text = ""
        self.title_label.setText("")
        self.artist_label.setText("")
        self.meta_label.setText("")
        self.time_limit_label.setText("")
        self._update_artwork(None)

    def _apply_colors(self) -> None:
        # Qt's app-wide "QWidget { background-color: ... }" rule paints a
        # solid rect behind every QLabel too, not just transparent text —
        # override it so labels blend into the panel's own background.
        fg = self.palette.get("status_fg", "#202020")
        meta_fg = self.palette.get("status_meta_fg", "#505050")
        accent = self.palette.get("accent", "#0078D4")
        self.title_label.setStyleSheet(f"color: {fg}; background: transparent;")
        self.artist_label.setStyleSheet(f"color: {fg}; background: transparent;")
        self.meta_label.setStyleSheet(f"color: {meta_fg}; background: transparent;")
        self.time_limit_label.setStyleSheet(f"color: {accent}; background: transparent;")
        self.artwork_label.setStyleSheet("background: transparent;")

    def _update_artwork(self, filepath) -> None:
        pixmap = None
        if filepath:
            try:
                artwork_data = get_best_artwork(filepath)
            except Exception:
                artwork_data = None
            if artwork_data:
                candidate = QPixmap()
                if candidate.loadFromData(artwork_data):
                    pixmap = candidate.scaled(
                        ARTWORK_SIZE, ARTWORK_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
        if pixmap is None:
            pixmap = self._placeholder_pixmap()
        self.artwork_label.setPixmap(pixmap)

    def _placeholder_pixmap(self) -> QPixmap:
        # Qt handles "♫" glyph fallback natively — no PIL font-path search needed.
        pixmap = QPixmap(ARTWORK_SIZE, ARTWORK_SIZE)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QColor(self.palette.get("status_meta_fg", "#E0E0E0")))
        font = QFont()
        font.setPointSize(40)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "♫")
        painter.end()
        return pixmap
