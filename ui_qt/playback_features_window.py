"""
Qt port of ui/playback_features_view.py.

Unlike PreferencesWindowQt, every control here applies LIVE — to
state/player — the moment it's changed, exactly like the original: Tk's
Save button (_save_features_config) only persists the current values to
settings/disk, it is not what makes them take effect. This is a
deliberately different pattern from Preferences' theme "preview until
committed" (see preferences_window.py's docstring) — there is nothing to
preview here, these are direct playback controls, and the original
behaves the same way (flip Fade In on, it fades immediately; only losing
that setting on the next launch if you never hit Save is what's at stake).

Simplified vs. the original: ui/playback_features_view.py additionally
persists fade-in/out to a *second*, separate
`playback_features_config.json` file and reads defaults back from it —
but crossfade/silence-detection/play-on-double were written to that same
file and never actually read back from anywhere, so those three settings
silently reset to AppState's class defaults on every restart regardless of
Save (a real, pre-existing gap in the original, not something intentional
to replicate). This port uses `settings.*` uniformly for *persistence*
(see app/settings.py's play_on_double/crossfade_enabled/crossfade_duration
fields, added alongside this dialog) — one save path, actually correct for
all six values, no separate config file needed.

Persistence is not the same as initial display value, though: matching
ui/playback_features_view.py:22-25/41-46 exactly, every control here is
initialized from the LIVE state/player, not from settings — play_on_double/
crossfade/silence_detection from `state`, fade in/out from `player` (falling
back to `settings` only if unavailable). Reading from settings instead was
tried first and was wrong: since every control applies live immediately,
reopening the dialog after an unsaved toggle would silently revert the
still-in-effect value back to whatever was last saved to disk, because the
fresh dialog's own init sequence re-invokes each toggle handler with
whatever value it was constructed with.
"""

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ui_qt.preferences_window import _DialogTitleBar

logger = logging.getLogger(__name__)


class PlaybackFeaturesWindowQt(QDialog):
    def __init__(self, parent, state, settings, player):
        super().__init__(parent)
        self.state = state
        self.settings = settings
        self.player = player

        self.setObjectName("MainWindow")
        self.setWindowTitle("Playback Features")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setModal(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        outer.addWidget(_DialogTitleBar(self, "Playback Features"))

        body = QWidget(self)
        layout = QVBoxLayout(body)
        outer.addWidget(body, 1)

        # ---------- General ----------
        general_group = QGroupBox("General")
        general_layout = QVBoxLayout(general_group)

        # Sourced from LIVE state/player, not settings — matches
        # ui/playback_features_view.py:22-25 (play_on_double/crossfade/
        # silence_detection always come from app_state) and lines 41-46
        # ("sync with active player state": fade in/out fall back to
        # settings but get unconditionally overridden by the player's own
        # live values whenever a player is passed, which it always is in
        # production). An earlier version sourced all six from `settings`
        # instead — since every control here applies live immediately
        # (see the module docstring), that meant reopening this dialog
        # after toggling something on WITHOUT clicking Save would silently
        # revert the still-in-effect change back to whatever was last
        # saved to disk, because the fresh dialog's own init sequence
        # re-invokes each toggle handler with the (stale) initial value.
        fade_in_enabled_default = bool(getattr(settings, "fade_in_enabled", False))
        fade_in_duration_default = int(getattr(settings, "fade_in_duration", 3))
        fade_out_enabled_default = bool(getattr(settings, "fade_out_enabled", False))
        fade_out_duration_default = int(getattr(settings, "fade_out_duration", 3))
        if player is not None:
            fade_in_enabled_default = bool(getattr(player, "fade_in_enabled", fade_in_enabled_default))
            fade_in_duration_default = int(getattr(player, "fade_in_duration", fade_in_duration_default))
            fade_out_enabled_default = bool(getattr(player, "fade_out_enabled", fade_out_enabled_default))
            fade_out_duration_default = int(getattr(player, "fade_out_duration", fade_out_duration_default))

        self.checkbox_play_on_double = QCheckBox("Play on double-click")
        self.checkbox_play_on_double.setChecked(bool(getattr(state, "play_on_double", True)))
        self.checkbox_play_on_double.toggled.connect(self._on_play_on_double_toggle)
        general_layout.addWidget(self.checkbox_play_on_double)

        self.checkbox_fade_in, self.slider_fade_in, self.label_fade_in = self._add_toggle_slider_row(
            general_layout, "Fade In", fade_in_enabled_default, fade_in_duration_default, minimum=0, maximum=10,
            on_toggle=self._on_fade_in_toggle, on_change=self._on_fade_in_change,
        )
        self.checkbox_fade_out, self.slider_fade_out, self.label_fade_out = self._add_toggle_slider_row(
            general_layout, "Fade Out", fade_out_enabled_default, fade_out_duration_default, minimum=0, maximum=10,
            on_toggle=self._on_fade_out_toggle, on_change=self._on_fade_out_change,
        )
        layout.addWidget(general_group)

        # ---------- Advance ----------
        advance_group = QGroupBox("Advance")
        advance_layout = QVBoxLayout(advance_group)

        self.checkbox_crossfade, self.slider_crossfade, self.label_crossfade = self._add_toggle_slider_row(
            advance_layout, "Crossfade", bool(getattr(state, "crossfade_enabled", False)),
            int(getattr(state, "crossfade_duration", 5)), minimum=1, maximum=12,
            on_toggle=self._on_crossfade_toggle, on_change=self._on_crossfade_change,
        )

        self.checkbox_silence = QCheckBox("Silence Detection")
        self.checkbox_silence.setChecked(bool(getattr(state, "silence_detection_enabled", False)))
        self.checkbox_silence.toggled.connect(self._on_silence_toggle)
        advance_layout.addWidget(self.checkbox_silence)

        layout.addWidget(advance_group)

        # Applying the loaded/saved enabled-state to the slider's disabled
        # look and to the player happens once here — same as Tk calling
        # _on_fade_in_toggle()/_on_fade_out_toggle() right after building
        # the sliders (ui/playback_features_view.py:200-201). Also covers
        # checkbox_silence for the same reason, even though Tk doesn't:
        # setChecked() above runs before .toggled.connect(), so it can't
        # itself fire _on_silence_toggle — if the checkbox's initial value
        # is already True (state.silence_detection_enabled was already on
        # when this dialog was opened/reopened), that True never actually
        # reaches self.player without this explicit call.
        self._on_fade_in_toggle(self.checkbox_fade_in.isChecked())
        self._on_fade_out_toggle(self.checkbox_fade_out.isChecked())
        self._on_crossfade_toggle(self.checkbox_crossfade.isChecked())
        self._on_silence_toggle(self.checkbox_silence.isChecked())

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
        for role in (QDialogButtonBox.Save, QDialogButtonBox.Close):
            btn = buttons.button(role)
            if btn is not None:
                btn.setObjectName("DialogButton")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

        self._center_on_parent()

    # ---------- construction helper ----------

    def _add_toggle_slider_row(self, parent_layout, label, enabled_default, value_default, minimum, maximum, on_toggle, on_change):
        row = QHBoxLayout()
        checkbox = QCheckBox(label)
        checkbox.setChecked(enabled_default)
        row.addWidget(checkbox)

        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(minimum)
        slider.setMaximum(maximum)
        slider.setValue(value_default)
        row.addWidget(slider, 1)

        value_label = QLabel(f"{value_default}s")
        value_label.setFixedWidth(30)
        row.addWidget(value_label)

        parent_layout.addLayout(row)

        checkbox.toggled.connect(on_toggle)
        slider.valueChanged.connect(on_change)
        return checkbox, slider, value_label

    def _center_on_parent(self) -> None:
        self.adjustSize()
        parent = self.parentWidget()
        if parent is None:
            return
        parent_geo = parent.frameGeometry()
        x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
        y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
        self.move(x, y)

    # ---------- live handlers (mirror ui/playback_features_view.py's *_toggle/*_change methods) ----------

    def _on_play_on_double_toggle(self, checked: bool) -> None:
        self.state.play_on_double = checked

    def _on_fade_in_toggle(self, checked: bool) -> None:
        self.slider_fade_in.setEnabled(checked)
        try:
            self.player.set_fade_in_enabled(checked)
        except Exception:
            logger.exception("set_fade_in_enabled() failed")

    def _on_fade_in_change(self, value: int) -> None:
        self.label_fade_in.setText(f"{value}s")
        try:
            self.player.set_fade_in_duration(value)
        except Exception:
            logger.exception("set_fade_in_duration() failed")

    def _on_fade_out_toggle(self, checked: bool) -> None:
        self.slider_fade_out.setEnabled(checked)
        try:
            self.player.set_fade_out_enabled(checked)
        except Exception:
            logger.exception("set_fade_out_enabled() failed")

    def _on_fade_out_change(self, value: int) -> None:
        self.label_fade_out.setText(f"{value}s")
        try:
            self.player.set_fade_out_duration(value)
        except Exception:
            logger.exception("set_fade_out_duration() failed")

    def _on_crossfade_toggle(self, checked: bool) -> None:
        self.slider_crossfade.setEnabled(checked)
        self.state.crossfade_enabled = checked

    def _on_crossfade_change(self, value: int) -> None:
        self.label_crossfade.setText(f"{value}s")
        self.state.crossfade_duration = value

    def _on_silence_toggle(self, checked: bool) -> None:
        self.state.silence_detection_enabled = checked
        # Matches ui/playback_features_view.py:425-426 — a direct attribute
        # assignment, not a setter method (AudioPlayer doesn't have one for
        # this flag).
        self.player.silence_detection_enabled = checked

    # ---------- persistence ----------

    def _on_save(self) -> None:
        self.settings.play_on_double = self.checkbox_play_on_double.isChecked()
        self.settings.fade_in_enabled = self.checkbox_fade_in.isChecked()
        self.settings.fade_in_duration = self.slider_fade_in.value()
        self.settings.fade_out_enabled = self.checkbox_fade_out.isChecked()
        self.settings.fade_out_duration = self.slider_fade_out.value()
        self.settings.crossfade_enabled = self.checkbox_crossfade.isChecked()
        self.settings.crossfade_duration = self.slider_crossfade.value()
        self.settings.silence_detection_enabled = self.checkbox_silence.isChecked()
        try:
            self.settings.save()
        except Exception:
            logger.exception("Failed to save playback feature settings")
        self.accept()
