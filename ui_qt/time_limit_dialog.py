"""Lets the user set or clear a playback time limit (state.play_limits)
for a track."""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui_qt.preferences_window import _DialogTitleBar

_PRESETS = [
    ("10 seconds", 10),
    ("30 seconds", 30),
    ("1 minute", 60),
    ("2 minutes", 120),
]


class TimeLimitDialogQt(QDialog):
    def __init__(self, parent, current_limit: Optional[float] = None):
        super().__init__(parent)
        self.result = "CANCEL"

        self.setObjectName("MainWindow")
        self.setWindowTitle("Play for Time")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setModal(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        outer.addWidget(_DialogTitleBar(self, "Play for Time"))

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        outer.addWidget(body, 1)

        body_layout.addWidget(QLabel("Play selected track for:"))

        preset_grid = QGridLayout()
        for i, (label, seconds) in enumerate(_PRESETS):
            btn = QPushButton(label)
            btn.setObjectName("DialogButton")
            btn.clicked.connect(lambda checked=False, s=seconds: self._apply_preset(s))
            preset_grid.addWidget(btn, i // 2, i % 2)
        body_layout.addLayout(preset_grid)

        entry_row = QHBoxLayout()
        entry_row.addWidget(QLabel("Custom (seconds):"))
        self.entry = QLineEdit()
        if current_limit is not None:
            self.entry.setText(str(int(current_limit)))
        self.entry.returnPressed.connect(self._on_set)
        entry_row.addWidget(self.entry, 1)
        self.set_btn = QPushButton("Set")
        self.set_btn.setObjectName("DialogButton")
        self.set_btn.clicked.connect(self._on_set)
        entry_row.addWidget(self.set_btn)
        body_layout.addLayout(entry_row)

        button_row = QHBoxLayout()
        self.clear_btn = QPushButton("Clear Limit")
        self.clear_btn.setObjectName("DialogButton")
        self.clear_btn.clicked.connect(self._on_clear)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("DialogButton")
        self.cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(self.clear_btn)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_btn)
        body_layout.addLayout(button_row)

        self.resize(360, 280)
        self._center_on_parent()

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        parent_geo = parent.frameGeometry()
        x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
        y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
        self.move(x, y)

    def _apply_preset(self, seconds: int) -> None:
        self.entry.setText(str(seconds))

    def _on_set(self) -> None:
        text = self.entry.text().strip()
        try:
            seconds = float(text)
        except ValueError:
            return
        if seconds <= 0:
            return
        self.result = seconds
        self.accept()

    def _on_clear(self) -> None:
        self.result = None
        self.accept()
