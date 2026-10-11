"""Tests for ui_qt/audio_effects_window.py."""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

import ui_qt.audio_effects_window as aew
from ui_qt.audio_effects_window import AUDIO_DEFAULTS, AudioEffectsWindowQt

PALETTE = {"switch_bg": "#4a4a4a", "button_bg_color": "#BB86FC"}


def _mock_player():
    player = MagicMock()
    player.get_equalizer_enabled.return_value = False
    player.get_equalizer_preamp.return_value = 0.0
    player.get_equalizer_band.return_value = 0.0
    player.get_compressor_enabled.return_value = False
    player.get_compressor_settings.return_value = {
        "threshold": -11.0, "ratio": 3.0, "attack": 25.0, "release": 100.0,
        "makeup_gain": 6.0, "knee": 5.0, "use_rms": True,
    }
    player.get_spatializer_enabled.return_value = False
    player.get_spatializer_settings.return_value = {
        "size": 0.85, "width": 0.5, "wet": 0.4, "dry": 0.5, "damp": 0.5,
    }
    player.get_playback_rate.return_value = 1.0
    player.get_channel_mode.return_value = "stereo"
    player.get_vocal_remover_enabled.return_value = False
    player.get_vocal_remover_intensity.return_value = 0.5
    return player


@pytest.fixture
def player():
    return _mock_player()


@pytest.fixture
def dialog(qtbot, player):
    win = AudioEffectsWindowQt(None, player, PALETTE)
    qtbot.addWidget(win)
    return win


# ---------- initialization reads live player state ----------

def test_init_reads_compressor_from_live_player_not_config_file(qtbot, player):
    # Regression for the deliberate improvement over ui/audio_effects_window.py:
    # compressor numerics must come from get_compressor_settings(), not the
    # saved JSON config, so a value changed-but-not-Saved still shows
    # correctly on reopen.
    player.get_compressor_settings.return_value = {
        "threshold": -25.0, "ratio": 7.0, "attack": 99.0, "release": 321.0,
        "makeup_gain": 12.0, "knee": 4.0, "use_rms": False,
    }
    win = AudioEffectsWindowQt(None, player, PALETTE)
    qtbot.addWidget(win)
    assert win.comp_threshold.value() / win.comp_threshold._scale == -25.0
    assert win.comp_ratio.value() / win.comp_ratio._scale == 7.0
    assert win.comp_rms_mode.isChecked() is False


def test_init_reads_spatializer_from_live_player_not_config_file(qtbot, player):
    player.get_spatializer_settings.return_value = {
        "size": 0.11, "width": 0.22, "wet": 0.33, "dry": 0.44, "damp": 0.55,
    }
    win = AudioEffectsWindowQt(None, player, PALETTE)
    qtbot.addWidget(win)
    assert win.spat_size.value() / win.spat_size._scale == 0.11
    assert win.spat_wet.value() / win.spat_wet._scale == 0.33


def test_init_channel_mode_checks_matching_radio_case_insensitively(qtbot, player):
    player.get_channel_mode.return_value = "mono"
    win = AudioEffectsWindowQt(None, player, PALETTE)
    qtbot.addWidget(win)
    checked = win.channel_mode_group.checkedButton()
    assert checked is not None
    assert checked.text() == "Mono"


# ---------- Equalizer ----------

def test_eq_enable_toggle_calls_player_and_gates_sliders(dialog, player):
    dialog.eq_enable.setChecked(True)
    player.set_equalizer_enabled.assert_called_with(True)
    assert dialog.preamp_slider.isEnabled() is True
    assert dialog.band_sliders[0].isEnabled() is True


def test_preamp_change_calls_player(dialog, player):
    dialog.preamp_slider.setValue(50)  # 5.0 dB at 1-decimal scale
    player.set_equalizer_preamp.assert_called_with(5.0)


def test_band_change_calls_player_with_index(dialog, player):
    dialog.band_sliders[3].setValue(-20)  # -2.0 dB
    player.set_equalizer_band.assert_called_with(3, -2.0)


def test_preset_selection_moves_and_applies_all_sliders(dialog, player):
    # "Flat" is all-zero, matching the sliders' already-zero starting
    # position — QSlider only emits valueChanged on an actual delta, so a
    # preset picked here must differ from the default to exercise the
    # apply path at all.
    dialog.preset_combo.setCurrentText("Rock")
    preamp, gains = dialog.presets["Rock"]
    assert dialog.preamp_slider.value() / dialog.preamp_slider._scale == preamp
    for slider, gain in zip(dialog.band_sliders, gains):
        assert slider.value() / slider._scale == gain
    player.set_equalizer_preamp.assert_called_with(preamp)


def test_blank_preset_resets_to_flat(dialog, player):
    # Regression: ui/audio_effects_window.py's _on_preset_change treats the
    # blank entry as "Flat" (reset everything to 0), not a no-op that
    # leaves whatever was previously applied in place.
    dialog.preset_combo.setCurrentText("Rock")
    assert dialog.preamp_slider.value() != 0

    dialog.preset_combo.setCurrentText("")

    assert dialog.preamp_slider.value() == 0
    for slider in dialog.band_sliders:
        assert slider.value() == 0
    player.set_equalizer_preamp.assert_called_with(0)


# ---------- Compressor ----------

def test_compressor_enable_toggle_calls_player_and_gates_sliders(dialog, player):
    dialog.comp_enable.setChecked(True)
    assert player.set_compressor.called
    call_kwargs = player.set_compressor.call_args.kwargs
    assert call_kwargs["enabled"] is True
    assert dialog.comp_threshold.isEnabled() is True


def test_compressor_slider_change_resends_full_state(dialog, player):
    dialog.comp_enable.setChecked(True)
    player.set_compressor.reset_mock()
    dialog.comp_threshold.setValue(-150)  # -15.0 dB
    call_kwargs = player.set_compressor.call_args.kwargs
    assert call_kwargs["threshold"] == -15.0
    assert call_kwargs["ratio"] == 3.0  # unrelated fields still resent, unchanged


def test_compressor_reset_restores_defaults_and_applies(dialog, player):
    dialog.comp_threshold.setValue(-1)
    dialog._reset_compressor()
    defaults = AUDIO_DEFAULTS["compressor"]
    assert dialog.comp_threshold.value() / dialog.comp_threshold._scale == defaults["threshold"]
    call_kwargs = player.set_compressor.call_args.kwargs
    assert call_kwargs["threshold"] == defaults["threshold"]


# ---------- Spatializer ----------

def test_spatializer_enable_toggle_calls_player_and_gates_sliders(dialog, player):
    dialog.spat_enable.setChecked(True)
    assert player.set_spatializer.called
    assert dialog.spat_size.isEnabled() is True


def test_spatializer_slider_change_resends_full_state(dialog, player):
    dialog.spat_enable.setChecked(True)
    player.set_spatializer.reset_mock()
    dialog.spat_size.setValue(50)  # 0.50
    call_kwargs = player.set_spatializer.call_args.kwargs
    assert call_kwargs["size"] == 0.5


def test_spatializer_reset_restores_defaults(dialog, player):
    dialog.spat_size.setValue(0)
    dialog._reset_spatializer()
    defaults = AUDIO_DEFAULTS["spatializer"]
    assert dialog.spat_size.value() / dialog.spat_size._scale == defaults["size"]


# ---------- Advanced ----------

def test_rate_change_calls_player(dialog, player):
    dialog.rate_slider.setValue(150)  # 1.5x
    player.set_playback_rate.assert_called_with(1.5)


def test_rate_reset_restores_default(dialog):
    dialog.rate_slider.setValue(300)
    dialog._reset_speed()
    assert dialog.rate_slider.value() / dialog.rate_slider._scale == AUDIO_DEFAULTS["playback"]["default_rate"]


def test_channel_mode_change_calls_player(dialog, player):
    for btn in dialog.channel_mode_group.buttons():
        if btn.text() == "Mono":
            btn.setChecked(True)
    player.set_channel_mode.assert_called_with("Mono")


def test_vocal_remover_toggle_calls_player_and_gates_slider(dialog, player):
    dialog.vocal_remover_enable.setChecked(True)
    player.set_vocal_remover_enabled.assert_called_with(True)
    assert dialog.vocal_remover_intensity.isEnabled() is True


def test_vocal_remover_intensity_change_calls_player(dialog, player):
    dialog.vocal_remover_intensity.setValue(80)  # 0.8
    player.set_vocal_remover_intensity.assert_called_with(0.8)


def test_vocal_remover_reset(dialog, player):
    dialog.vocal_remover_enable.setChecked(True)
    dialog.vocal_remover_intensity.setValue(10)
    dialog._reset_vocal_remover()
    assert dialog.vocal_remover_intensity.value() / dialog.vocal_remover_intensity._scale == 0.5
    assert dialog.vocal_remover_enable.isChecked() is False


# ---------- Save ----------

def test_save_writes_expected_config_shape(dialog, tmp_path):
    fake_path = tmp_path / "audio_effects_config.json"
    with patch.object(aew, "_CONFIG_PATH", fake_path):
        dialog._save_to_config()
    saved = json.loads(fake_path.read_text())
    assert set(saved.keys()) == {"equalizer", "compressor", "spatializer", "playback", "channel_mode", "vocal_remover"}
    assert saved["compressor"]["rms_buffer_size"] == 512
    assert saved["playback"]["min_rate"] == 0.25
    assert saved["playback"]["max_rate"] == 4.0
    assert saved["channel_mode"]["mode"] == "Stereo"


def test_save_preserves_rms_buffer_size_from_disk(qtbot, player, tmp_path):
    on_disk = tmp_path / "audio_effects_config.json"
    on_disk.write_text(json.dumps({"compressor": {"rms_buffer_size": 1024}, "playback": {"min_rate": 0.1, "max_rate": 8.0}}))
    with patch.object(aew, "_CONFIG_PATH", on_disk):
        win = AudioEffectsWindowQt(None, player, PALETTE)
        qtbot.addWidget(win)
        win._save_to_config()
    saved = json.loads(on_disk.read_text())
    assert saved["compressor"]["rms_buffer_size"] == 1024
    assert saved["playback"]["min_rate"] == 0.1
    assert saved["playback"]["max_rate"] == 8.0


# ---------- click-to-seek sliders ----------

def test_clicking_track_jumps_to_position_not_page_step(dialog):
    # Regression: plain QSlider only page-steps toward a click on the
    # track — this must jump straight to the clicked position instead.
    slider = dialog.preamp_slider
    assert slider.value() == 0

    click_pos = QPointF(int(slider.width() * 0.9), slider.height() // 2)
    event = QMouseEvent(QMouseEvent.MouseButtonPress, click_pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    slider.mousePressEvent(event)

    # A page-step nudge would move it by a few units; a real jump lands
    # much closer to the slider's maximum (200 at this slider's 1-decimal
    # scale of -20..20 dB).
    assert slider.value() > 100


def test_clicking_near_left_edge_jumps_toward_minimum(dialog):
    slider = dialog.preamp_slider
    slider.setValue(150)

    click_pos = QPointF(int(slider.width() * 0.1), slider.height() // 2)
    event = QMouseEvent(QMouseEvent.MouseButtonPress, click_pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    slider.mousePressEvent(event)

    assert slider.value() < -100


def test_theme_signal_updates_toggle_switch_colors(qtbot, player):
    from ui_qt.theme_bridge import ThemeSignal

    theme_signal = ThemeSignal()
    win = AudioEffectsWindowQt(None, player, PALETTE, theme_signal)
    qtbot.addWidget(win)

    new_palette = {"switch_bg": "#C0C0C0", "button_bg_color": "#1682D4"}
    theme_signal.changed.emit(new_palette)

    assert win.eq_enable._palette == new_palette
    assert win.comp_enable._palette == new_palette
    assert win.spat_enable._palette == new_palette
    assert win.vocal_remover_enable._palette == new_palette
