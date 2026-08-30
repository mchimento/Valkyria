"""Tests for ui_qt/playback_features_window.py, focused on Fade In/Out.

Mirrors tests/test_audio_effects.py's TestPlaybackFeaturesView (the Tk
PlaybackFeaturesView fade in/out coverage) for intent — every control here
applies live to the player immediately, settings aren't touched until Save,
and the dialog initializes from the player's live state rather than disk
settings (see ui_qt/playback_features_window.py's module docstring for why:
these controls apply live, so initializing from settings would silently
revert an unsaved-but-still-in-effect change every time the dialog reopens).
Uses qtbot instead of Tk fixtures, per this project's testing conventions.
"""
from unittest.mock import MagicMock

import pytest

from ui_qt.playback_features_window import PlaybackFeaturesWindowQt

PALETTE = {"switch_bg": "#4a4a4a", "button_bg_color": "#BB86FC"}


def _mock_player():
    player = MagicMock()
    player.fade_in_enabled = False
    player.fade_in_duration = 3
    player.fade_out_enabled = False
    player.fade_out_duration = 3
    player.silence_detection_enabled = False
    return player


def _mock_state():
    state = MagicMock()
    state.play_on_double = True
    state.crossfade_enabled = False
    state.crossfade_duration = 5
    state.silence_detection_enabled = False
    return state


def _mock_settings():
    settings = MagicMock()
    settings.fade_in_enabled = False
    settings.fade_in_duration = 3
    settings.fade_out_enabled = False
    settings.fade_out_duration = 3
    settings.crossfade_enabled = False
    settings.crossfade_duration = 5
    settings.silence_detection_enabled = False
    return settings


@pytest.fixture
def player():
    return _mock_player()


@pytest.fixture
def state():
    return _mock_state()


@pytest.fixture
def settings():
    return _mock_settings()


@pytest.fixture
def dialog(qtbot, state, settings, player):
    win = PlaybackFeaturesWindowQt(None, state, settings, player, PALETTE)
    qtbot.addWidget(win)
    return win


def test_fade_in_updates_player_immediately(dialog, settings, player):
    # Construction itself calls set_fade_in_enabled(False) once (see
    # playback_features_window.py:157) -- reset so the assertions below
    # only see the effect of the actual toggle/slider interactions.
    player.set_fade_in_enabled.reset_mock()
    player.set_fade_in_duration.reset_mock()

    dialog.checkbox_fade_in.setChecked(True)
    player.set_fade_in_enabled.assert_called_with(True)
    assert settings.fade_in_enabled is False, "Settings should not be updated before Save"

    dialog.slider_fade_in.setValue(5)
    player.set_fade_in_duration.assert_called_with(5)
    assert settings.fade_in_duration == 3, "Settings should not be updated before Save"


def test_fade_out_updates_player_immediately(dialog, settings, player):
    player.set_fade_out_enabled.reset_mock()
    player.set_fade_out_duration.reset_mock()

    dialog.checkbox_fade_out.setChecked(True)
    player.set_fade_out_enabled.assert_called_with(True)
    assert settings.fade_out_enabled is False, "Settings should not be updated before Save"

    dialog.slider_fade_out.setValue(4)
    player.set_fade_out_duration.assert_called_with(4)
    assert settings.fade_out_duration == 3, "Settings should not be updated before Save"


def test_fade_in_slider_disabled_state_follows_toggle(dialog):
    # Matches ui/playback_features_view.py's slider enable/disable pairing
    # (playback_features_window.py:237/251) -- the duration slider should
    # never be interactable while its fade is switched off.
    assert not dialog.slider_fade_in.isEnabled()
    dialog.checkbox_fade_in.setChecked(True)
    assert dialog.slider_fade_in.isEnabled()
    dialog.checkbox_fade_in.setChecked(False)
    assert not dialog.slider_fade_in.isEnabled()


def test_save_persists_fade_settings(dialog, settings):
    dialog.checkbox_fade_in.setChecked(True)
    dialog.slider_fade_in.setValue(8)
    dialog.checkbox_fade_out.setChecked(True)
    dialog.slider_fade_out.setValue(7)

    # Still defaults right up until Save is actually triggered.
    assert settings.fade_in_duration == 3

    dialog._on_save()

    assert settings.fade_in_enabled is True
    assert settings.fade_in_duration == 8
    assert settings.fade_out_enabled is True
    assert settings.fade_out_duration == 7
    settings.save.assert_called_once()


def test_initialization_uses_live_player_state_over_settings(qtbot, state, settings):
    # Session (player) state differs from disk settings -- the dialog must
    # reflect whatever the player is actually doing right now, not what
    # was last saved, since every control here applies live (see the
    # module docstring's rationale for why sourcing from settings instead
    # was tried first and was wrong).
    player = _mock_player()
    player.fade_in_enabled = True
    player.fade_in_duration = 9
    player.fade_out_enabled = True
    player.fade_out_duration = 6
    # settings stay at their defaults (False, 3) from the settings fixture.

    win = PlaybackFeaturesWindowQt(None, state, settings, player, PALETTE)
    qtbot.addWidget(win)

    assert win.checkbox_fade_in.isChecked() is True
    assert win.slider_fade_in.value() == 9
    assert win.checkbox_fade_out.isChecked() is True
    assert win.slider_fade_out.value() == 6


def test_initialization_falls_back_to_settings_without_a_player(qtbot, state, settings):
    settings.fade_in_enabled = True
    settings.fade_in_duration = 6

    win = PlaybackFeaturesWindowQt(None, state, settings, None, PALETTE)
    qtbot.addWidget(win)

    assert win.checkbox_fade_in.isChecked() is True
    assert win.slider_fade_in.value() == 6
