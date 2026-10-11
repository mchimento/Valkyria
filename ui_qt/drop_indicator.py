"""
Custom drag-drop line indicator shared by the browser and playlist
trees, painted directly instead of using Qt's native ::drop-indicator.
"""

from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QPainter, QPen

LINE_THICKNESS = 3


def compute_drop_line_y(tree, pos: QPoint):
    """Viewport-relative y for the drop line given the cursor position,
    or None if the tree has nothing to drop onto."""
    item = tree.itemAt(pos)
    if item is None:
        count = tree.topLevelItemCount()
        if count == 0:
            return None
        return tree.visualItemRect(tree.topLevelItem(count - 1)).bottom()
    rect = tree.visualItemRect(item)
    midpoint = rect.top() + rect.height() // 2
    return rect.top() if pos.y() < midpoint else rect.bottom()


def paint_drop_line(tree, y: int, color: str) -> None:
    painter = QPainter(tree.viewport())
    pen = QPen(QColor(color))
    pen.setWidth(LINE_THICKNESS)
    painter.setPen(pen)
    painter.drawLine(0, y, tree.viewport().width(), y)
    painter.end()
