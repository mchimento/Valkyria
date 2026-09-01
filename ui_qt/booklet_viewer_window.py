"""Pages through booklet/liner-note images embedded in an audio file's
tags (plus folder art)."""

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from audio.metadata import get_booklet_images
from ui_qt.preferences_window import _DialogTitleBar

logger = logging.getLogger(__name__)


class BookletViewerWindowQt(QDialog):
    def __init__(self, parent, file_path: str, palette: dict):
        super().__init__(parent)
        self.file_path = file_path
        self.palette = palette
        self.images = get_booklet_images(file_path)
        self.current_index = 0
        self._current_pixmap = None

        self.setObjectName("MainWindow")
        self.setWindowTitle("Album Booklet Viewer")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setModal(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        outer.addWidget(_DialogTitleBar(self, "Album Booklet Viewer"))

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        outer.addWidget(body, 1)

        self.image_panel = QFrame(body)
        self.image_panel.setObjectName("BookletImagePanel")
        self.image_panel.setAttribute(Qt.WA_StyledBackground, True)
        panel_layout = QVBoxLayout(self.image_panel)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        panel_layout.addWidget(self.image_label)
        body_layout.addWidget(self.image_panel, 1)

        nav_row = QHBoxLayout()
        self.prev_button = QPushButton("Previous")
        self.prev_button.setObjectName("DialogButton")
        self.prev_button.clicked.connect(self._previous_image)
        self.counter_label = QLabel("")
        self.counter_label.setAlignment(Qt.AlignCenter)
        self.next_button = QPushButton("Next")
        self.next_button.setObjectName("DialogButton")
        self.next_button.clicked.connect(self._next_image)
        nav_row.addWidget(self.prev_button)
        nav_row.addWidget(self.counter_label, 1)
        nav_row.addWidget(self.next_button)
        body_layout.addLayout(nav_row)

        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        body_layout.addWidget(self.info_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        close_btn = buttons.button(QDialogButtonBox.Close)
        close_btn.setObjectName("DialogButton")
        close_btn.setIcon(QIcon())
        buttons.rejected.connect(self.reject)
        body_layout.addWidget(buttons)

        self.resize(800, 600)
        self._center_on_parent()
        self._load_current_image()

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        parent_geo = parent.frameGeometry()
        x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
        y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
        self.move(x, y)

    # ---------- image display ----------

    def _load_current_image(self) -> None:
        if not self.images:
            self._show_no_images()
            return

        data, description, image_type = self.images[self.current_index]
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self._show_error("Error loading image: image data is corrupted")
        else:
            self._current_pixmap = pixmap
            self._render_scaled()
            self.info_label.setText(f"Type: {image_type} | Description: {description}")

        self.counter_label.setText(f"Image {self.current_index + 1} of {len(self.images)}")
        self.prev_button.setEnabled(self.current_index > 0)
        self.next_button.setEnabled(self.current_index < len(self.images) - 1)

    def _render_scaled(self) -> None:
        if self._current_pixmap is None:
            return
        target = self.image_label.size()
        pm = self._current_pixmap
        # Never upscale — QPixmap.scaled() alone will stretch a small
        # image to fill a larger panel, unlike PIL's min(scale, 1.0) cap.
        if pm.width() <= target.width() and pm.height() <= target.height():
            self.image_label.setPixmap(pm)
        else:
            self.image_label.setPixmap(pm.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _show_no_images(self) -> None:
        self._current_pixmap = None
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText("No booklet images available for this track.")
        self.counter_label.setText("")
        self.info_label.setText("")
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)

    def _show_error(self, message: str) -> None:
        self._current_pixmap = None
        self.image_label.setPixmap(QPixmap())
        self.image_label.setText(message)
        self.info_label.setText("")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._current_pixmap is not None:
            self._render_scaled()

    def _previous_image(self) -> None:
        if self.current_index > 0:
            self.current_index -= 1
            self._load_current_image()

    def _next_image(self) -> None:
        if self.current_index < len(self.images) - 1:
            self.current_index += 1
            self._load_current_image()
