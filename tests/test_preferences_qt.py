"""Tests for ui_qt/preferences_window.py, especially the theme rollback path."""
from unittest.mock import patch

import pytest

from app.settings import Settings
from themes.theme_manager import ThemeManager
from ui_qt.preferences_window import PreferencesWindowQt
from ui_qt.theme_bridge import ThemeSignal


@pytest.fixture
def settings():
    with patch.object(Settings, "load"):
        s = Settings()
    s.theme = "light"
    s.mini_player_enabled = True
    s.bpm_mode = "raw"
    return s


@pytest.fixture
def theme(settings):
    return ThemeManager(settings)


@pytest.fixture
def theme_signal():
    return ThemeSignal()


@pytest.fixture
def dialog(qtbot, settings, theme, theme_signal):
    win = PreferencesWindowQt(None, settings, theme, theme_signal)
    qtbot.addWidget(win)
    return win


def test_initial_state_matches_settings(dialog):
    assert dialog.radio_light.isChecked()
    assert not dialog.radio_dark.isChecked()
    assert dialog.checkbox_mini_player.isChecked()
    assert dialog.radio_bpm_raw.isChecked()


def test_toggling_theme_previews_live(qtbot, dialog, settings, theme_signal):
    with qtbot.waitSignal(theme_signal.changed, timeout=1000) as blocker:
        dialog.radio_dark.setChecked(True)
    assert settings.theme == "dark"
    assert blocker.args[0]["bg"] == "#1E1E1E"  # dark.json's bg


def test_reject_rolls_back_preview(qtbot, dialog, settings, theme_signal):
    dialog.radio_dark.setChecked(True)
    assert settings.theme == "dark"

    with qtbot.waitSignal(theme_signal.changed, timeout=1000) as blocker:
        dialog.reject()

    assert settings.theme == "light"
    assert blocker.args[0]["bg"] == "#FAFAFA"  # light.json's bg


def test_reject_without_preview_does_not_emit(qtbot, dialog, theme_signal):
    received = []
    theme_signal.changed.connect(lambda p: received.append(p))
    dialog.reject()
    assert received == []


def test_save_commits_all_fields(dialog, settings):
    dialog.radio_dark.setChecked(True)
    dialog.checkbox_mini_player.setChecked(False)
    dialog.radio_bpm_perceived.setChecked(True)

    with patch.object(Settings, "save") as mock_save:
        dialog._on_save()

    assert settings.theme == "dark"
    assert settings.mini_player_enabled is False
    assert settings.bpm_mode == "perceived"
    assert mock_save.called
