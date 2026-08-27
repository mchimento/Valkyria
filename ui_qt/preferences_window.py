"""
Qt port of ui/preferences_window.py.

Scoped to what PreferencesWindow actually owns: theme (Light/Dark), mini
player enabled, BPM mode. Fade in/out and silence detection belong to
ui/playback_features_view.py, a separate window not ported yet.

Theme switching gets special care here (see ui_qt/theme_bridge.py's
ThemeSignal docstring for the two root causes this design avoids): the
only notification path is one `theme_signal.changed.emit(palette)` call,
and there is no manual per-widget restyle walk in this file at all —
apply_theme() (called by whoever owns the ThemeSignal connection) re-skins
this dialog the same as everything else, since it's just another QWidget
under the app-wide stylesheet.
"""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class _DialogTitleBar(QWidget):
    """Minimal themed titlebar for frameless dialogs — a plain QDialog gets
    a native OS titlebar that Qt's QSS can't recolor (Wayland/GNOME draws
    it, not Qt), which is why it stayed system-gray regardless of theme.
    Reuses the same startSystemMove() drag pattern as
    ui_qt/menu_bar.py's _DragSpacer."""

    def __init__(self, dialog: QDialog, title: str):
        super().__init__(dialog)
        self.dialog = dialog
        self.setObjectName("DialogTitleBar")
        # Qt's QSS auto-detection for plain QWidget only special-cases
        # background-color and the full `border` shorthand; border-bottom
        # alone silently doesn't paint without this attribute forcing full
        # stylesheet-aware rendering.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        label = QLabel(title)
        # Plain QWidget renders background-color from the generic `QWidget`
        # QSS rule regardless of WA_StyledBackground, so without this the
        # label paints its own bg-colored rect on top of the titlebar's
        # menubar_bg strip.
        label.setStyleSheet("background: transparent;")
        layout.addWidget(label)
        layout.addStretch(1)

        close_btn = QPushButton("✕")
        close_btn.setObjectName("WinBtnClose")
        close_btn.setFixedSize(36, 30)
        close_btn.clicked.connect(dialog.reject)
        layout.addWidget(close_btn)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            handle = self.dialog.windowHandle()
            if handle is not None:
                handle.startSystemMove()


class PreferencesWindowQt(QDialog):
    def __init__(self, parent, settings, theme, theme_signal):
        super().__init__(parent)
        self.settings = settings
        self.theme = theme
        self.theme_signal = theme_signal
        self._original_theme = settings.theme

        self.setObjectName("MainWindow")  # reuses the main window's QSS border treatment
        self.setWindowTitle("Preferences")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setModal(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        outer.addWidget(_DialogTitleBar(self, "Preferences"))

        body = QWidget(self)
        layout = QVBoxLayout(body)
        outer.addWidget(body, 1)

        theme_group = QGroupBox("Theme")
        theme_layout = QHBoxLayout(theme_group)
        self.radio_light = QRadioButton("Light")
        self.radio_dark = QRadioButton("Dark")
        self._theme_buttons = QButtonGroup(self)
        self._theme_buttons.addButton(self.radio_light)
        self._theme_buttons.addButton(self.radio_dark)
        if settings.theme == "dark":
            self.radio_dark.setChecked(True)
        else:
            self.radio_light.setChecked(True)
        theme_layout.addWidget(self.radio_light)
        theme_layout.addWidget(self.radio_dark)
        layout.addWidget(theme_group)
        self.radio_light.toggled.connect(lambda checked: checked and self._preview_theme("light"))
        self.radio_dark.toggled.connect(lambda checked: checked and self._preview_theme("dark"))

        misc_group = QGroupBox("General")
        misc_layout = QVBoxLayout(misc_group)
        self.checkbox_mini_player = QCheckBox("Enable mini player")
        self.checkbox_mini_player.setChecked(bool(getattr(settings, "mini_player_enabled", True)))
        misc_layout.addWidget(self.checkbox_mini_player)
        layout.addWidget(misc_group)

        bpm_group = QGroupBox("BPM Mode")
        bpm_layout = QHBoxLayout(bpm_group)
        self.radio_bpm_perceived = QRadioButton("Perceived")
        self.radio_bpm_raw = QRadioButton("Raw")
        self._bpm_buttons = QButtonGroup(self)
        self._bpm_buttons.addButton(self.radio_bpm_perceived)
        self._bpm_buttons.addButton(self.radio_bpm_raw)
        if getattr(settings, "bpm_mode", "raw") == "perceived":
            self.radio_bpm_perceived.setChecked(True)
        else:
            self.radio_bpm_raw.setChecked(True)
        bpm_layout.addWidget(self.radio_bpm_perceived)
        bpm_layout.addWidget(self.radio_bpm_raw)
        layout.addWidget(bpm_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._center_on_parent()

    def _center_on_parent(self) -> None:
        self.adjustSize()
        parent = self.parentWidget()
        if parent is None:
            return
        parent_geo = parent.frameGeometry()
        x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
        y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
        self.move(x, y)

    def _preview_theme(self, name: str) -> None:
        self.settings.theme = name
        self.theme.reload()
        self.theme_signal.changed.emit(self.theme.palette)

    def _on_save(self) -> None:
        self.settings.mini_player_enabled = self.checkbox_mini_player.isChecked()
        self.settings.bpm_mode = "perceived" if self.radio_bpm_perceived.isChecked() else "raw"
        try:
            self.settings.save()
        except Exception:
            logger.exception("Failed to save settings")
        self.accept()

    def reject(self) -> None:
        # Covers the Cancel button, the window's X close, and Escape — Qt
        # routes all three through reject(), so this one override is the
        # single rollback path (no separate close-protocol wiring needed).
        if self.settings.theme != self._original_theme:
            self.settings.theme = self._original_theme
            self.theme.reload()
            self.theme_signal.changed.emit(self.theme.palette)
        super().reject()
