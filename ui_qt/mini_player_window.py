"""Small floating window with transport controls + track
info, shown while the main window is minimized. No duplicate playback
logic: it polls the shared AppState/ControlsBarQt for display and emits
Signals for every user action, which MainWindowQt connects to the same
handlers its own transport bar uses."""

import logging
import os

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QProgressBar, QVBoxLayout, QWidget

from audio.metadata import get_metadata
from ui_qt.controls import _format_ms
from ui_qt.marquee_label import MarqueeLabel

logger = logging.getLogger(__name__)

WINDOW_WIDTH = 380


class MiniPlayerWindowQt(QWidget):
    restore_requested = Signal()
    play_pause_requested = Signal()
    prev_requested = Signal()
    next_requested = Signal()

    def __init__(self, state, controls, palette: dict, parent=None):
        super().__init__(parent)
        self.state = state
        self.controls = controls
        self.palette = palette
        self._sized_once = False

        self.setObjectName("MiniPlayerWindow")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 10, 10)
        outer.setSpacing(8)

        window_btn_row = QHBoxLayout()
        window_btn_row.setSpacing(2)
        window_btn_row.addStretch(1)
        self.maximize_btn = QPushButton("⤢")
        self.maximize_btn.setObjectName("MiniPlayerWinBtn")
        self.maximize_btn.setFixedSize(20, 20)
        self.maximize_btn.setToolTip("Restore main window")
        self.maximize_btn.clicked.connect(self.restore_requested)
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("WinBtnClose")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.clicked.connect(self.restore_requested)
        window_btn_row.addWidget(self.maximize_btn)
        window_btn_row.addWidget(self.close_btn)
        outer.addLayout(window_btn_row)

        main_row = QHBoxLayout()
        main_row.setSpacing(12)

        transport_row = QHBoxLayout()
        transport_row.setSpacing(6)
        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setObjectName("MiniSecondaryButton")
        self.btn_prev.setFixedSize(34, 34)
        self.btn_play_pause = QPushButton("▶")
        self.btn_play_pause.setObjectName("MiniPlayButton")
        self.btn_play_pause.setFixedSize(48, 48)
        self.btn_next = QPushButton("⏭")
        self.btn_next.setObjectName("MiniSecondaryButton")
        self.btn_next.setFixedSize(34, 34)
        self.btn_prev.clicked.connect(self.prev_requested)
        self.btn_play_pause.clicked.connect(self.play_pause_requested)
        self.btn_next.clicked.connect(self.next_requested)
        transport_row.addWidget(self.btn_prev, 0, Qt.AlignVCenter)
        transport_row.addWidget(self.btn_play_pause, 0, Qt.AlignVCenter)
        transport_row.addWidget(self.btn_next, 0, Qt.AlignVCenter)
        main_row.addLayout(transport_row)
        main_row.setAlignment(transport_row, Qt.AlignVCenter)

        info_col = QVBoxLayout()
        info_col.setSpacing(3)
        info_col.addStretch(1)
        self.title_label = MarqueeLabel("No track loaded")
        self.title_label.setObjectName("MiniPlayerTitle")
        info_col.addWidget(self.title_label)
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("MiniPlayerSubtitle")
        info_col.addWidget(self.time_label)
        self.time_limit_label = QLabel("")
        self.time_limit_label.setStyleSheet(
            f"color: {palette.get('highlight', '#EB5B00')}; background: transparent; font-size: 9pt;"
        )
        info_col.addWidget(self.time_limit_label)
        info_col.addStretch(1)
        main_row.addLayout(info_col, 1)
        main_row.setAlignment(info_col, Qt.AlignVCenter)

        outer.addLayout(main_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("MiniPlayerProgress")
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setFixedHeight(4)
        outer.addWidget(self.progress_bar)

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._update_ui)

    # ---------- lifecycle ----------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._sized_once:
            self._sized_once = True
            self.adjustSize()
            self.setFixedSize(WINDOW_WIDTH, self.height())
            self._position_bottom_right()

    def start_updates(self) -> None:
        self._update_ui()
        self._timer.start()

    def stop_updates(self) -> None:
        self._timer.stop()

    def _position_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else None
        if avail is not None:
            x = avail.x() + avail.width() - self.width() - 20
            y = avail.y() + avail.height() - self.height() - 40
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
