"""A QLabel-like widget that horizontally scrolls its text in a seamless,
looping marquee when the text is wider than the widget, instead of
clipping or eliding it. Font/color come from the same QSS/`setStyleSheet`
mechanisms a QLabel would use — Qt's style engine applies `color`/`font-*`
properties to any QWidget's palette/font regardless of subclass, it's only
background/border painting that needs QLabel or WA_StyledBackground."""

from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

PAUSE_TICKS = 30
TICK_INTERVAL_MS = 40
LOOP_GAP = 40


class MarqueeLabel(QWidget):
    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._text = text
        self._offset = 0
        self._paused_ticks = 0

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_INTERVAL_MS)
        self._timer.timeout.connect(self._advance)

    # ---------- QLabel-compatible API ----------

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:
        if text == self._text:
            return
        self._text = text
        self._offset = 0
        self._paused_ticks = 0
        self._update_scrolling()
        self.update()

    def setFont(self, font) -> None:
        super().setFont(font)
        self._update_scrolling()

    # ---------- sizing ----------

    def sizeHint(self) -> QSize:
        return QSize(100, self.fontMetrics().height())

    def minimumSizeHint(self) -> QSize:
        return QSize(20, self.fontMetrics().height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_scrolling()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._update_scrolling()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    # ---------- scrolling ----------

    def _text_width(self) -> int:
        return self.fontMetrics().horizontalAdvance(self._text)

    def _update_scrolling(self) -> None:
        overflow = self.isVisible() and self._text_width() > self.width()
        if overflow and not self._timer.isActive():
            self._offset = 0
            self._paused_ticks = 0
            self._timer.start()
        elif not overflow and self._timer.isActive():
            self._timer.stop()
            self._offset = 0
            self.update()

    def _advance(self) -> None:
        # Brief pause at the start of each loop before scrolling begins.
        if self._paused_ticks < PAUSE_TICKS:
            self._paused_ticks += 1
            return
        self._offset += 1
        if self._offset >= self._text_width() + LOOP_GAP:
            self._offset = 0
            self._paused_ticks = 0
        self.update()

    # ---------- painting ----------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.setFont(self.font())
        metrics = self.fontMetrics()
        y = (self.height() + metrics.ascent() - metrics.descent()) // 2

        if not self._timer.isActive():
            painter.drawText(0, y, self._text)
            return

        painter.setClipRect(self.rect())
        text_width = self._text_width()
        x = -self._offset
        painter.drawText(x, y, self._text)
        painter.drawText(x + text_width + LOOP_GAP, y, self._text)
