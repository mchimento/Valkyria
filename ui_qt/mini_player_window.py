"""Small always-on-top floating window with transport controls + track
info, shown while the main window is minimized. No duplicate playback
logic: it polls the shared AppState/ControlsBarQt for display and emits
Signals for every user action, which MainWindowQt connects to the same
handlers its own transport bar uses."""

import logging
import os

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRegion
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QProgressBar, QVBoxLayout, QWidget

from audio.metadata import get_best_artwork, get_metadata
from ui_qt.controls import _format_ms

logger = logging.getLogger(__name__)

ARTWORK_SIZE = 56
ARTWORK_RADIUS = 10
WINDOW_WIDTH = 460
CORNER_RADIUS = 16


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
        self._last_artwork_path = False  # sentinel: never equals a real path or None
        self._sized_once = False
        self._bg_top = QColor(palette.get("bg", "#1E1E1E"))
        self._bg_bottom = QColor(palette.get("tree_bg", "#252526"))
        self._border_color = QColor(palette.get("border", "#3E3E3E"))

        self.setObjectName("MiniPlayerWindow")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 10, 10)
        outer.setSpacing(8)

        # Window controls stay pinned to the top-right of the view — a
        # separate row, right-aligned, added before the content below.
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

        self.artwork_label = QLabel()
        self.artwork_label.setObjectName("MiniPlayerArtwork")
        self.artwork_label.setFixedSize(ARTWORK_SIZE, ARTWORK_SIZE)
        self.artwork_label.setAlignment(Qt.AlignCenter)
        main_row.addWidget(self.artwork_label, 0, Qt.AlignVCenter)

        info_col = QVBoxLayout()
        info_col.setSpacing(3)
        info_col.addStretch(1)
        self.title_label = QLabel("No track loaded")
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

        self._update_artwork(None)

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._update_ui)

    # ---------- lifecycle ----------

    def _rounded_path(self) -> QPainterPath:
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), CORNER_RADIUS, CORNER_RADIUS)
        return path

    def _apply_rounded_mask(self) -> None:
        # A hard window-shape mask clips to a rounded rect without needing
        # compositing (Qt.WA_TranslucentBackground can lose the whole
        # background without one) — reapplied in showEvent too, since a
        # mask set before the native window surface exists can get dropped.
        self.setMask(QRegion(self._rounded_path().toFillPolygon().toPolygon()))

    def paintEvent(self, event) -> None:
        # QSS background-color/border-radius on a plain QWidget fills the
        # full bounding rect regardless of radius (confirmed by pixel
        # sampling) — the mask alone then has to do all the rounding, with
        # no antialiasing. The actual corner-cutting is left entirely to
        # _apply_rounded_mask(); this always fills the *whole* rect (not
        # just the rounded path) so that if the window-shape mask doesn't
        # take effect on a given window manager, the fallback is a plain
        # square dark window rather than unpainted (black) corners.
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, self._bg_top)
        gradient.setColorAt(1.0, self._bg_bottom)
        painter.fillRect(self.rect(), gradient)
        pen = QPen(self._border_color)
        pen.setWidthF(1.0)
        painter.setPen(pen)
        painter.drawPath(self._rounded_path())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._sized_once:
            self._sized_once = True
            # Deferred to the first real show, not done in __init__: a
            # not-yet-shown/polished QSS-styled widget tree can report an
            # inflated sizeHint() (see CLAUDE.md's Qt gotchas). adjustSize()
            # computes the natural height; width is then forced to the
            # fixed design width.
            self.adjustSize()
            self.setFixedSize(WINDOW_WIDTH, self.height())
            self._position_bottom_right()
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

    # ---------- artwork ----------

    def _update_artwork(self, filepath) -> None:
        if filepath == self._last_artwork_path:
            return
        self._last_artwork_path = filepath

        pixmap = None
        if filepath:
            try:
                data = get_best_artwork(filepath)
            except Exception:
                data = None
            if data:
                candidate = QPixmap()
                if candidate.loadFromData(data):
                    scaled = candidate.scaled(
                        ARTWORK_SIZE, ARTWORK_SIZE, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                    )
                    x = max(0, (scaled.width() - ARTWORK_SIZE) // 2)
                    y = max(0, (scaled.height() - ARTWORK_SIZE) // 2)
                    pixmap = scaled.copy(x, y, ARTWORK_SIZE, ARTWORK_SIZE)
        if pixmap is None:
            pixmap = self._placeholder_pixmap()
        self.artwork_label.setPixmap(self._round_pixmap(pixmap))

    def _placeholder_pixmap(self) -> QPixmap:
        pixmap = QPixmap(ARTWORK_SIZE, ARTWORK_SIZE)
        pixmap.fill(QColor(self.palette.get("tree_bg", "#252526")))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QColor(self.palette.get("fg_dim", "#888888")))
        font = QFont()
        font.setPointSize(20)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "♫")
        painter.end()
        return pixmap

    def _round_pixmap(self, pixmap: QPixmap) -> QPixmap:
        rounded = QPixmap(pixmap.size())
        rounded.fill(Qt.transparent)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(pixmap.rect()), ARTWORK_RADIUS, ARTWORK_RADIUS)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        return rounded

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
        self._update_artwork(filepath)

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
