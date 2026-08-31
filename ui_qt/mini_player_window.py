"""Qt port of ui/mini_player.py — a small always-on-top floating window
with transport controls + track info, shown while the main window is
minimized. No duplicate playback logic: it polls the shared AppState/
ControlsBarQt for display and emits Signals for every user action, which
MainWindowQt connects to the same handlers its own transport bar uses."""

import logging
import os

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QPainterPath, QRegion
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QProgressBar, QVBoxLayout, QWidget

from audio.metadata import get_metadata
from ui_qt.controls import _format_ms

logger = logging.getLogger(__name__)


class MiniPlayerWindowQt(QWidget):
    restore_requested = Signal()
    play_pause_requested = Signal()
    prev_requested = Signal()
    next_requested = Signal()

    def __init__(self, state, controls, palette: dict, parent=None):
        super().__init__(parent)
        self.state = state
        self.controls = controls

        self.setObjectName("MiniPlayerWindow")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedSize(450, 130)
        self._apply_rounded_mask()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(6)

        # Window controls stay pinned to the top of the view regardless of
        # where the transport/info block sits — a separate row, right-
        # aligned, added before the stretch below.
        window_btn_row = QHBoxLayout()
        window_btn_row.setSpacing(2)
        window_btn_row.addStretch(1)
        self.maximize_btn = QPushButton("□")
        self.maximize_btn.setFixedSize(24, 24)
        self.maximize_btn.setToolTip("Restore main window")
        self.maximize_btn.clicked.connect(self.restore_requested)
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("WinBtnClose")
        self.close_btn.setFixedSize(24, 24)
        self.close_btn.clicked.connect(self.restore_requested)
        window_btn_row.addWidget(self.maximize_btn)
        window_btn_row.addWidget(self.close_btn)
        outer.addLayout(window_btn_row)

        # Pushes the button/info block + time-limit line down to sit right
        # above the progress bar, instead of pinning them to the top of the
        # window with a dead gap opening up below them.
        outer.addStretch(1)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        transport_row = QHBoxLayout()
        transport_row.setSpacing(4)
        self.btn_prev = QPushButton("⏮")
        self.btn_play_pause = QPushButton("▶")
        self.btn_next = QPushButton("⏭")
        for btn in (self.btn_prev, self.btn_play_pause, self.btn_next):
            btn.setObjectName("TransportButton")
            btn.setFixedSize(40, 40)
            transport_row.addWidget(btn)
        self.btn_prev.clicked.connect(self.prev_requested)
        self.btn_play_pause.clicked.connect(self.play_pause_requested)
        self.btn_next.clicked.connect(self.next_requested)
        top_row.addLayout(transport_row)
        top_row.setAlignment(transport_row, Qt.AlignVCenter)

        # Title + time are the two lines the transport buttons should
        # visually center against. time_limit_label is almost always blank
        # (no active limit) — if it shared this VBox, its always-reserved
        # blank line would pull the "visual center" of title+time upward
        # relative to the buttons even though the box's math center matched.
        # It gets its own row below top_row instead (still always reserving
        # space there, so nothing shifts when a limit becomes active).
        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        self.title_label = QLabel("No track loaded")
        self.title_label.setStyleSheet("font-weight: bold; font-size: 12pt; background: transparent;")
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet("background: transparent;")
        info_col.addWidget(self.title_label)
        info_col.addWidget(self.time_label)
        top_row.addLayout(info_col, 1)
        top_row.setAlignment(info_col, Qt.AlignVCenter)

        outer.addLayout(top_row)

        self.time_limit_label = QLabel("")
        self.time_limit_label.setStyleSheet(f"color: {palette.get('highlight', '#EB5B00')}; background: transparent;")
        outer.addWidget(self.time_limit_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("MiniPlayerProgress")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setFixedHeight(8)
        outer.addWidget(self.progress_bar)

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._update_ui)

    # ---------- lifecycle ----------

    def _apply_rounded_mask(self) -> None:
        # Qt.WA_TranslucentBackground needs a compositor to blend properly;
        # without one the whole window can lose its background instead of
        # just the corners going transparent. A hard window-shape mask
        # clips the actual window to the rounded rect without needing
        # compositing at all, so it works the same on any WM — but on some
        # platforms a mask set before the native window surface exists gets
        # dropped, so this is reapplied in showEvent too, not just here.
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 12, 12)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_rounded_mask()

    def start_updates(self) -> None:
        self._update_ui()
        self._timer.start()

    def stop_updates(self) -> None:
        self._timer.stop()

    def _position_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else None
        if avail is not None:
            x = avail.x() + avail.width() - 470
            y = avail.y() + avail.height() - 170
        else:
            x, y = 100, 100
        self.move(x, y)

    # ---------- drag / restore ----------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            handle = self.windowHandle()
            if handle is not None:
                handle.startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.restore_requested.emit()
        super().mouseDoubleClickEvent(event)

    # ---------- polling ----------

    def _update_ui(self) -> None:
        if self.controls.is_playing and not self.controls.is_paused:
            self.btn_play_pause.setText("⏸")
        else:
            self.btn_play_pause.setText("▶")

        idx = self.state.current_index
        filepath = None
        if idx is not None and idx < len(self.state.playlist):
            filepath = self.state.playlist[idx]
            meta = get_metadata(filepath)
            title = meta.get("title") or os.path.basename(filepath)
            if len(title) > 50:
                title = title[:47] + "..."
            self.title_label.setText(title)
        else:
            self.title_label.setText("No track loaded")

        try:
            length_ms = self.controls.player.get_length()
            pos_ms = self.controls.player.get_time()
        except Exception:
            length_ms, pos_ms = 0, 0

        if length_ms and length_ms > 0 and pos_ms is not None and pos_ms >= 0:
            self.progress_bar.setValue(int(1000 * pos_ms / length_ms))
            self.time_label.setText(f"{_format_ms(pos_ms)} / {_format_ms(length_ms)}")
        else:
            self.progress_bar.setValue(0)
            self.time_label.setText("0:00 / 0:00")
            pos_ms = 0

        text = ""
        if filepath is not None and filepath in self.state.play_limits:
            limit_s = int(self.state.play_limits[filepath])
            remaining = max(0, limit_s - int(pos_ms // 1000))
            text = f"Time limit: {remaining}s remaining"
        self.time_limit_label.setText(text)
