"""Equalizer, Compressor, Spatializer, and Advanced (speed/channel-mode/
vocal-remover) controls for the shared audio/audio_effects.py DSP chain.

Every control applies LIVE to the player the moment it changes — there is
no pending/Apply state."""

import json
import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QSlider,
    QStyle,
    QStyleOptionSlider,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui_qt.preferences_window import _DialogTitleBar
from ui_qt.toggle_switch import ToggleSwitch

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "audio" / "audio_effects_config.json"
_DEFAULTS_PATH = Path(__file__).parent.parent / "audio" / "audio_effect_default.json"

with open(_DEFAULTS_PATH, "r") as f:
    AUDIO_DEFAULTS = json.load(f)

_CHANNEL_MODES = ["Stereo", "Mono", "Left Channel", "Right Channel", "Side (Diff)"]


class _ClickToSeekSlider(QSlider):

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            handle_rect = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            if not handle_rect.contains(pos):
                value = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), pos.x(), self.width())
                self.setValue(value)
        super().mousePressEvent(event)


class AudioEffectsWindowQt(QDialog):
    def __init__(self, parent, player, palette: dict, theme_signal=None):
        super().__init__(parent)
        self.player = player
        self.palette = palette
        if theme_signal is not None:
            theme_signal.changed.connect(self._on_theme_changed)
        try:
            with open(_CONFIG_PATH, "r") as f:
                self._config_on_disk = json.load(f)
        except Exception:
            self._config_on_disk = {}

        self.setObjectName("MainWindow")
        self.setWindowTitle("Audio Effects")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setModal(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        outer.addWidget(_DialogTitleBar(self, "Audio Effects"))

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 12, 12, 12)
        body_layout.setSpacing(10)
        outer.addWidget(body, 1)

        self.tabs = QTabWidget(body)
        self.tabs.addTab(self._build_equalizer_tab(), "Equalizer")
        self.tabs.addTab(self._build_compressor_tab(), "Compressor")
        self.tabs.addTab(self._build_spatializer_tab(), "Spatializer")
        self.tabs.addTab(self._build_advanced_tab(), "Advanced")
        body_layout.addWidget(self.tabs, 1)

        button_row = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.setObjectName("CompactButton")
        self.save_btn.clicked.connect(self._save_to_config)
        button_row.addWidget(self.save_btn)
        button_row.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        close_btn = buttons.button(QDialogButtonBox.Close)
        close_btn.setObjectName("CompactButton")
        close_btn.setIcon(QIcon())
        buttons.rejected.connect(self.reject)
        button_row.addWidget(buttons)
        body_layout.addLayout(button_row)

        self.resize(800, self._measure_ideal_height())
        self._center_on_parent()

    def _measure_ideal_height(self) -> int:
        advanced_height = self.tabs.widget(3).sizeHint().height()
        chrome = 30 + self.save_btn.sizeHint().height() + 40  # titlebar + button row + margins
        return advanced_height + self.tabs.tabBar().sizeHint().height() + chrome

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        parent_geo = parent.frameGeometry()
        x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
        y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
        self.move(x, y)

    def _on_theme_changed(self, palette: dict) -> None:
        self.palette = palette
        for switch in (self.eq_enable, self.comp_enable, self.comp_rms_mode,
                       self.spat_enable, self.vocal_remover_enable):
            switch.apply_palette(palette)

    # ---------- construction helpers ----------

    def _add_toggle_row(self, parent_layout, label, enabled_default, on_toggle):
        row = QHBoxLayout()
        row.setSpacing(8)
        switch = ToggleSwitch(self.palette)
        switch.setChecked(enabled_default)
        row.addWidget(switch)
        row.addWidget(QLabel(label))
        row.addStretch(1)
        parent_layout.addLayout(row)
        switch.toggled.connect(on_toggle)
        return switch

    def _add_labeled_slider(self, parent_layout, label, minimum, maximum, initial, decimals, on_change, suffix=""):
        """A label + horizontal slider (scaled by 10**decimals so QSlider's
        integer-only range can represent float values) + a live value
        label."""
        scale = 10 ** decimals
        row = QHBoxLayout()
        row.setSpacing(8)
        text_label = QLabel(label)
        text_label.setFixedWidth(120)
        row.addWidget(text_label)
        slider = _ClickToSeekSlider(Qt.Horizontal)
        slider.setMinimum(round(minimum * scale))
        slider.setMaximum(round(maximum * scale))
        slider.setValue(round(initial * scale))
        row.addWidget(slider, 1)
        value_label = QLabel(f"{initial:.{decimals}f}{suffix}")
        value_label.setFixedWidth(60)
        row.addWidget(value_label)
        parent_layout.addLayout(row)

        def _on_slider_value_changed(v):
            real = v / scale
            value_label.setText(f"{real:.{decimals}f}{suffix}")
            on_change(real)

        slider.valueChanged.connect(_on_slider_value_changed)
        slider._scale = scale
        return slider

    def _set_slider_value(self, slider, value: float) -> None:
        slider.setValue(round(value * slider._scale))

    # ---------- Equalizer tab ----------

    def _build_equalizer_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        self.eq_enable = ToggleSwitch(self.palette)
        eq_enabled = bool(self.player.get_equalizer_enabled())
        self.eq_enable.setChecked(eq_enabled)
        top_row.addWidget(self.eq_enable)
        top_row.addWidget(QLabel("Equalizer"))
        top_row.addSpacing(16)
        top_row.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.presets = {
            name: (data["preamp"], data["gains"])
            for name, data in AUDIO_DEFAULTS["equalizer"]["presets"].items()
        }
        self.preset_combo.addItem("")
        self.preset_combo.addItems(sorted(self.presets.keys()))
        self.preset_combo.currentTextChanged.connect(self._on_preset_change)
        top_row.addWidget(self.preset_combo, 1)
        layout.addLayout(top_row)
        self.eq_enable.toggled.connect(self._on_eq_enable_toggle)
        layout.addSpacing(8)

        preamp_default = float(self.player.get_equalizer_preamp())
        self.preamp_slider = self._add_labeled_slider(
            layout, "Preamp", -20.0, 20.0, preamp_default, 1, self._on_preamp_change, suffix=" dB",
        )
        layout.addSpacing(8)

        bands = AUDIO_DEFAULTS["equalizer"]["bands"]
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)
        self.band_sliders = []
        for i, freq in enumerate(bands):
            band_default = float(self.player.get_equalizer_band(i))
            label = f"{freq}Hz" if freq < 1000 else f"{freq / 1000:g}kHz"
            row_widget = QWidget()
            row_layout = QVBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            slider = self._add_labeled_slider(
                row_layout, label, -20.0, 20.0, band_default, 1,
                lambda val, idx=i: self._on_band_change(idx, val), suffix=" dB",
            )
            self.band_sliders.append(slider)
            grid.addWidget(row_widget, i // 2, i % 2)
        layout.addLayout(grid)
        layout.addStretch(1)

        self._update_eq_controls_enabled(eq_enabled)
        return tab

    def _on_eq_enable_toggle(self, checked: bool) -> None:
        self.player.set_equalizer_enabled(checked)
        self._update_eq_controls_enabled(checked)

    def _update_eq_controls_enabled(self, enabled: bool) -> None:
        self.preamp_slider.setEnabled(enabled)
        for slider in self.band_sliders:
            slider.setEnabled(enabled)

    def _on_preamp_change(self, value: float) -> None:
        self.player.set_equalizer_preamp(value)

    def _on_band_change(self, index: int, value: float) -> None:
        self.player.set_equalizer_band(index, value)

    def _on_preset_change(self, name: str) -> None:
        if not name:
            name = "Flat"
        if name not in self.presets:
            return
        preamp, gains = self.presets[name]
        self._set_slider_value(self.preamp_slider, preamp)
        for slider, gain in zip(self.band_sliders, gains):
            self._set_slider_value(slider, gain)

    # ---------- Compressor tab ----------

    def _build_compressor_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        settings = self.player.get_compressor_settings()
        comp_enabled = bool(self.player.get_compressor_enabled())

        top_row = QHBoxLayout()
        self.comp_enable = ToggleSwitch(self.palette)
        self.comp_enable.setChecked(comp_enabled)
        top_row.addWidget(self.comp_enable)
        top_row.addWidget(QLabel("Compressor"))
        top_row.addStretch(1)
        layout.addLayout(top_row)
        self.comp_enable.toggled.connect(self._on_compressor_toggle)
        layout.addSpacing(8)

        self.comp_threshold = self._add_labeled_slider(
            layout, "Threshold", -30.0, 0.0, settings["threshold"], 1, lambda v: self._apply_compressor(), suffix=" dB",
        )
        self.comp_ratio = self._add_labeled_slider(
            layout, "Ratio", 1.0, 20.0, settings["ratio"], 1, lambda v: self._apply_compressor(), suffix=":1",
        )
        self.comp_attack = self._add_labeled_slider(
            layout, "Attack", 1.0, 400.0, settings["attack"], 0, lambda v: self._apply_compressor(), suffix=" ms",
        )
        self.comp_release = self._add_labeled_slider(
            layout, "Release", 1.0, 800.0, settings["release"], 0, lambda v: self._apply_compressor(), suffix=" ms",
        )
        self.comp_knee = self._add_labeled_slider(
            layout, "Knee", 0.0, 10.0, settings["knee"], 1, lambda v: self._apply_compressor(), suffix=" dB",
        )
        self.comp_makeup = self._add_labeled_slider(
            layout, "Makeup", 0.0, 24.0, settings["makeup_gain"], 1, lambda v: self._apply_compressor(), suffix=" dB",
        )

        rms_row = QHBoxLayout()
        self.comp_rms_mode = ToggleSwitch(self.palette)
        self.comp_rms_mode.setChecked(bool(settings["use_rms"]))
        self.comp_rms_mode.toggled.connect(lambda checked: self._apply_compressor())
        rms_row.addWidget(self.comp_rms_mode)
        rms_row.addWidget(QLabel("RMS Detection (off = Peak)"))
        rms_row.addStretch(1)
        layout.addLayout(rms_row)
        layout.addSpacing(8)

        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setObjectName("CompactButton")
        reset_btn.clicked.connect(self._reset_compressor)
        reset_row.addWidget(reset_btn)
        layout.addLayout(reset_row)
        layout.addStretch(1)

        self._update_compressor_controls_enabled(comp_enabled)
        return tab

    def _on_compressor_toggle(self, checked: bool) -> None:
        self._update_compressor_controls_enabled(checked)
        self._apply_compressor()

    def _update_compressor_controls_enabled(self, enabled: bool) -> None:
        for widget in (self.comp_threshold, self.comp_ratio, self.comp_attack,
                       self.comp_release, self.comp_knee, self.comp_makeup, self.comp_rms_mode):
            widget.setEnabled(enabled)

    def _apply_compressor(self) -> None:
        self.player.set_compressor(
            enabled=self.comp_enable.isChecked(),
            threshold=self.comp_threshold.value() / self.comp_threshold._scale,
            ratio=self.comp_ratio.value() / self.comp_ratio._scale,
            attack=self.comp_attack.value() / self.comp_attack._scale,
            release=self.comp_release.value() / self.comp_release._scale,
            makeup_gain=self.comp_makeup.value() / self.comp_makeup._scale,
            knee=self.comp_knee.value() / self.comp_knee._scale,
            use_rms=self.comp_rms_mode.isChecked(),
        )

    def _reset_compressor(self) -> None:
        defaults = AUDIO_DEFAULTS["compressor"]
        self._set_slider_value(self.comp_threshold, defaults["threshold"])
        self._set_slider_value(self.comp_ratio, defaults["ratio"])
        self._set_slider_value(self.comp_attack, defaults["attack"])
        self._set_slider_value(self.comp_release, defaults["release"])
        self._set_slider_value(self.comp_knee, defaults["knee"])
        self._set_slider_value(self.comp_makeup, defaults["makeup_gain"])
        self.comp_rms_mode.setChecked(defaults["use_rms"])
        self._apply_compressor()

    # ---------- Spatializer tab ----------

    def _build_spatializer_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        settings = self.player.get_spatializer_settings()
        spat_enabled = bool(self.player.get_spatializer_enabled())

        top_row = QHBoxLayout()
        self.spat_enable = ToggleSwitch(self.palette)
        self.spat_enable.setChecked(spat_enabled)
        top_row.addWidget(self.spat_enable)
        top_row.addWidget(QLabel("Spatializer"))
        top_row.addStretch(1)
        layout.addLayout(top_row)
        self.spat_enable.toggled.connect(self._on_spatializer_toggle)
        layout.addSpacing(8)

        self.spat_size = self._add_labeled_slider(
            layout, "Size", 0.0, 1.1, settings["size"], 2, lambda v: self._apply_spatializer(),
        )
        self.spat_width = self._add_labeled_slider(
            layout, "Width", 0.0, 1.0, settings["width"], 2, lambda v: self._apply_spatializer(),
        )
        self.spat_wet = self._add_labeled_slider(
            layout, "Wet", 0.0, 1.0, settings["wet"], 2, lambda v: self._apply_spatializer(),
        )
        self.spat_dry = self._add_labeled_slider(
            layout, "Dry", 0.0, 1.0, settings["dry"], 2, lambda v: self._apply_spatializer(),
        )
        self.spat_damp = self._add_labeled_slider(
            layout, "Damp", 0.0, 1.0, settings["damp"], 2, lambda v: self._apply_spatializer(),
        )

        layout.addSpacing(8)
        reset_row = QHBoxLayout()
        reset_row.addStretch(1)
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setObjectName("CompactButton")
        reset_btn.clicked.connect(self._reset_spatializer)
        reset_row.addWidget(reset_btn)
        layout.addLayout(reset_row)
        layout.addStretch(1)

        self._update_spatializer_controls_enabled(spat_enabled)
        return tab

    def _on_spatializer_toggle(self, checked: bool) -> None:
        self._update_spatializer_controls_enabled(checked)
        self._apply_spatializer()

    def _update_spatializer_controls_enabled(self, enabled: bool) -> None:
        for widget in (self.spat_size, self.spat_width, self.spat_wet, self.spat_dry, self.spat_damp):
            widget.setEnabled(enabled)

    def _apply_spatializer(self) -> None:
        self.player.set_spatializer(
            enabled=self.spat_enable.isChecked(),
            size=self.spat_size.value() / self.spat_size._scale,
            width=self.spat_width.value() / self.spat_width._scale,
            wet=self.spat_wet.value() / self.spat_wet._scale,
            dry=self.spat_dry.value() / self.spat_dry._scale,
            damp=self.spat_damp.value() / self.spat_damp._scale,
        )

    def _reset_spatializer(self) -> None:
        defaults = AUDIO_DEFAULTS["spatializer"]
        self._set_slider_value(self.spat_size, defaults["size"])
        self._set_slider_value(self.spat_width, defaults["width"])
        self._set_slider_value(self.spat_wet, defaults["wet"])
        self._set_slider_value(self.spat_dry, defaults["dry"])
        self._set_slider_value(self.spat_damp, defaults["damp"])
        self._apply_spatializer()

    # ---------- Advanced tab ----------

    def _build_advanced_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        speed_group = QGroupBox("Playback Speed")
        speed_layout = QVBoxLayout(speed_group)
        rate_default = float(self.player.get_playback_rate())
        self.rate_slider = self._add_labeled_slider(
            speed_layout, "Speed", 0.25, 4.0, rate_default, 2, self._on_rate_change, suffix="x",
        )
        rate_reset_row = QHBoxLayout()
        rate_reset_row.addStretch(1)
        rate_reset_btn = QPushButton("Reset (1.0x)")
        rate_reset_btn.setObjectName("CompactButton")
        rate_reset_btn.clicked.connect(self._reset_speed)
        rate_reset_row.addWidget(rate_reset_btn)
        speed_layout.addLayout(rate_reset_row)
        layout.addWidget(speed_group)

        channel_group = QGroupBox("Channel Mode")
        channel_layout = QVBoxLayout(channel_group)
        channel_row = QHBoxLayout()
        self.channel_mode_group = QButtonGroup(self)
        # get_channel_mode() returns lowercase (AudioEffects._channel_mode
        # is always .lower()'d), unlike _CHANNEL_MODES' display casing.
        current_mode = str(self.player.get_channel_mode() or "").lower()
        for mode in _CHANNEL_MODES:
            radio = QRadioButton(mode)
            if mode.lower() == current_mode:
                radio.setChecked(True)
            radio.toggled.connect(lambda checked, m=mode: checked and self._on_channel_mode_change(m))
            self.channel_mode_group.addButton(radio)
            channel_row.addWidget(radio)
        channel_layout.addLayout(channel_row)
        layout.addWidget(channel_group)

        vocal_group = QGroupBox("Vocal Remover")
        vocal_layout = QVBoxLayout(vocal_group)
        vr_top_row = QHBoxLayout()
        self.vocal_remover_enable = ToggleSwitch(self.palette)
        vr_enabled = bool(self.player.get_vocal_remover_enabled())
        self.vocal_remover_enable.setChecked(vr_enabled)
        self.vocal_remover_enable.toggled.connect(self._on_vocal_remover_toggle)
        vr_top_row.addWidget(self.vocal_remover_enable)
        vr_top_row.addWidget(QLabel("Enabled"))
        vr_top_row.addStretch(1)
        vocal_layout.addLayout(vr_top_row)

        intensity_default = float(self.player.get_vocal_remover_intensity())
        self.vocal_remover_intensity = self._add_labeled_slider(
            vocal_layout, "Intensity", 0.0, 1.0, intensity_default, 2, self._on_vocal_intensity_change,
        )
        vr_reset_row = QHBoxLayout()
        vr_reset_row.addStretch(1)
        vr_reset_btn = QPushButton("Reset")
        vr_reset_btn.setObjectName("CompactButton")
        vr_reset_btn.clicked.connect(self._reset_vocal_remover)
        vr_reset_row.addWidget(vr_reset_btn)
        vocal_layout.addLayout(vr_reset_row)
        self.vocal_remover_intensity.setEnabled(vr_enabled)
        layout.addWidget(vocal_group)

        layout.addStretch(1)
        return tab

    def _on_rate_change(self, value: float) -> None:
        self.player.set_playback_rate(value)

    def _reset_speed(self) -> None:
        self._set_slider_value(self.rate_slider, AUDIO_DEFAULTS["playback"]["default_rate"])

    def _on_channel_mode_change(self, mode: str) -> None:
        self.player.set_channel_mode(mode)

    def _on_vocal_remover_toggle(self, checked: bool) -> None:
        self.player.set_vocal_remover_enabled(checked)
        self.vocal_remover_intensity.setEnabled(checked)

    def _on_vocal_intensity_change(self, value: float) -> None:
        self.player.set_vocal_remover_intensity(value)

    def _reset_vocal_remover(self) -> None:
        self._set_slider_value(self.vocal_remover_intensity, 0.5)
        self.vocal_remover_enable.setChecked(False)

    # ---------- persistence ----------

    def _save_to_config(self) -> None:
        config = {
            "equalizer": {
                "enabled": self.eq_enable.isChecked(),
                "preamp": self.preamp_slider.value() / self.preamp_slider._scale,
                "gains": [s.value() / s._scale for s in self.band_sliders],
                "selected_preset": self.preset_combo.currentText(),
            },
            "compressor": {
                "enabled": self.comp_enable.isChecked(),
                "threshold": self.comp_threshold.value() / self.comp_threshold._scale,
                "ratio": self.comp_ratio.value() / self.comp_ratio._scale,
                "attack": self.comp_attack.value() / self.comp_attack._scale,
                "release": self.comp_release.value() / self.comp_release._scale,
                "makeup_gain": self.comp_makeup.value() / self.comp_makeup._scale,
                "knee": self.comp_knee.value() / self.comp_knee._scale,
                "use_rms": self.comp_rms_mode.isChecked(),
                "rms_buffer_size": self._config_on_disk.get("compressor", {}).get("rms_buffer_size", 512),
            },
            "spatializer": {
                "enabled": self.spat_enable.isChecked(),
                "size": self.spat_size.value() / self.spat_size._scale,
                "width": self.spat_width.value() / self.spat_width._scale,
                "wet": self.spat_wet.value() / self.spat_wet._scale,
                "dry": self.spat_dry.value() / self.spat_dry._scale,
                "damp": self.spat_damp.value() / self.spat_damp._scale,
            },
            "playback": {
                "default_rate": self.rate_slider.value() / self.rate_slider._scale,
                "min_rate": self._config_on_disk.get("playback", {}).get("min_rate", 0.25),
                "max_rate": self._config_on_disk.get("playback", {}).get("max_rate", 4.0),
            },
            "channel_mode": {
                "mode": (self.channel_mode_group.checkedButton().text()
                         if self.channel_mode_group.checkedButton() else "Stereo"),
            },
            "vocal_remover": {
                "enabled": self.vocal_remover_enable.isChecked(),
                "intensity": self.vocal_remover_intensity.value() / self.vocal_remover_intensity._scale,
            },
        }
        try:
            with open(_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=2)
        except Exception:
            logger.exception("Failed to save audio effects config")
