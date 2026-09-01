"""Small, non-modal About dialog (logo, description, version, OK).
Constructed fresh each time, not kept as a singleton — no live state here
to diverge."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from app.paths import get_resource_path
from app.version import __version__
from ui_qt.preferences_window import _DialogTitleBar


class AboutWindowQt(QDialog):
    def __init__(self, parent, palette: dict):
        super().__init__(parent)

        self.setObjectName("MainWindow")
        self.setWindowTitle("About")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setModal(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        outer.addWidget(_DialogTitleBar(self, "About"))

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 20, 20, 20)
        body_layout.setSpacing(8)
        body_layout.setAlignment(Qt.AlignHCenter)
        outer.addWidget(body, 1)

        logo_path = get_resource_path("assets/logo-no-background.png")
        pixmap = QPixmap(str(logo_path)) if logo_path.exists() else QPixmap()
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        if not pixmap.isNull():
            logo_label.setPixmap(pixmap.scaled(280, 93, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            logo_label.setText("Valkyria")
            accent = palette.get("accent", "#BB86FC")
            logo_label.setStyleSheet(f"color: {accent}; font-size: 20pt; font-weight: bold; background: transparent;")
        body_layout.addWidget(logo_label)

        desc_label = QLabel("A modern audio player with playback features for music enthusiasts and DJs")
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setFixedWidth(350)
        body_layout.addWidget(desc_label)

        version_label = QLabel(f"Version {__version__}")
        version_label.setAlignment(Qt.AlignCenter)
        body_layout.addWidget(version_label)

        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("DialogButton")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        body_layout.addWidget(ok_btn, 0, Qt.AlignCenter)

        self.resize(400, 300)
        self._center_on_parent()

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        parent_geo = parent.frameGeometry()
        x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
        y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
        self.move(x, y)
