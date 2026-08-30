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

import json
import logging

import audio.metadata as metadata_module
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
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

from app.paths import get_resource_path
from ui_qt.toggle_switch import ToggleSwitch

logger = logging.getLogger(__name__)


def _load_palette(theme_name: str) -> dict:
    """Load a theme palette by name without touching settings/ThemeManager —
    used for live preview so nothing shared/persisted is mutated until Save
    is actually clicked. Mirrors themes.theme_manager.ThemeManager.reload()'s
    file-loading logic exactly, just without the settings.theme dependency."""
    path = get_resource_path(f"themes/{theme_name}.json")
    if not path.exists():
        path = get_resource_path("themes/light.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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
        mini_player_row = QHBoxLayout()
        mini_player_row.setSpacing(8)
        self.checkbox_mini_player = ToggleSwitch(theme.palette)
        self.checkbox_mini_player.setChecked(bool(getattr(settings, "mini_player_enabled", True)))
        mini_player_row.addWidget(self.checkbox_mini_player)
        mini_player_row.addWidget(QLabel("Enable mini player"))
        mini_player_row.addStretch(1)
        misc_layout.addLayout(mini_player_row)
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
        # The app-wide QPushButton QSS rule is flat/transparent (it's meant
        # for the toolbar-style menu bar and window-control buttons), which
        # leaves ordinary dialog action buttons with no visible chrome at
        # all. Give these the same treatment as the transport buttons.
        for role in (QDialogButtonBox.Save, QDialogButtonBox.Cancel):
            btn = buttons.button(role)
            if btn is not None:
                btn.setObjectName("DialogButton")
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
        # Deliberately does not touch self.settings.theme or self.theme —
        # those are shared, persisted objects, and anything else in the app
        # that calls settings.save() while this preview is live (adjusting
        # volume, toggling mute, even just closing the whole app) would
        # otherwise silently bake the uncommitted preview into config.json.
        # Preview only broadcasts a palette for display; nothing is
        # committed until _on_save().
        self.theme_signal.changed.emit(_load_palette(name))

    def _on_save(self) -> None:
        self.settings.theme = "dark" if self.radio_dark.isChecked() else "light"
        self.theme.reload()
        self.settings.mini_player_enabled = self.checkbox_mini_player.isChecked()
        self.settings.bpm_mode = "perceived" if self.radio_bpm_perceived.isChecked() else "raw"
        # Matches ui/preferences_window.py:400-401 — without this,
        # audio.metadata.BPM_PREFERENCE never picks up the new choice
        # until the next full app restart (main_qt.py only applies the
        # startup value once), same gap as the one main_qt.py itself had.
        try:
            metadata_module.set_bpm_preference(self.settings.bpm_mode)
        except Exception:
            logger.exception("Failed to apply BPM preference")
        try:
            self.settings.save()
        except Exception:
            logger.exception("Failed to save settings")
        self.accept()

    def reject(self) -> None:
        # Covers the Cancel button, the window's X close, and Escape — Qt
        # routes all three through reject(), so this one override is the
        # single rollback path (no separate close-protocol wiring needed).
        # settings.theme/self.theme were never touched by preview, so
        # there's nothing to roll back there — just restore the visible
        # app to whatever theme.palette actually still says (in case a
        # preview changed what's on screen without changing what's saved).
        self.theme_signal.changed.emit(self.theme.palette)
        super().reject()
