"""
Shared floating "what's being dragged" indicator for the browser ->
playlist drag.
"""

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QWidget

CURSOR_OFFSET = QPoint(18, 18)
CHIP_ICON = "♫"
CHIP_MAX_TEXT_WIDTH = 220


def build_chip_pixmap(font, label: str) -> QPixmap:
    """The dragged-item chip shown by both the browser and playlist trees."""
    metrics = QFontMetrics(font)
    text = metrics.elidedText(label, Qt.ElideMiddle, CHIP_MAX_TEXT_WIDTH)
    icon_width = metrics.horizontalAdvance(CHIP_ICON)
    text_width = metrics.horizontalAdvance(text)

    pad_x, pad_y, gap = 12, 8, 6
    width = pad_x * 2 + icon_width + gap + text_width
    height = pad_y * 2 + metrics.height()

    pixmap = QPixmap(width, height)
    pixmap.fill(QColor(20, 20, 20))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)

    pen = QPen(QColor(255, 255, 255, 90))
    pen.setWidthF(1.0)
    painter.setPen(pen)
    painter.drawRect(QRectF(0.5, 0.5, width - 1, height - 1))

    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255))
    y = pad_y + metrics.ascent()
    painter.drawText(pad_x, y, CHIP_ICON)
    painter.drawText(pad_x + icon_width + gap, y, text)
    painter.end()
    return pixmap


class DragGhost(QLabel):
    def __init__(self, pixmap: QPixmap, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setPixmap(pixmap)
        self.setFixedSize(pixmap.size())

    def follow(self, global_pos: QPoint) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.move(parent.mapFromGlobal(global_pos + CURSOR_OFFSET))


_active: DragGhost | None = None


def set_active(ghost: DragGhost | None) -> None:
    global _active
    _active = ghost


def update_position(global_pos: QPoint) -> None:
    if _active is not None:
        _active.follow(global_pos)
