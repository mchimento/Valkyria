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


def test_toggling_theme_previews_live_without_touching_settings(qtbot, dialog, settings, theme_signal):
    """The core fix: preview must broadcast a palette for display without
    ever mutating the shared, persisted settings/theme objects — otherwise
    anything else that calls settings.save() while the dialog is open
    (volume change, mute toggle, even closing the app) would silently bake
    the uncommitted preview into config.json."""
    with qtbot.waitSignal(theme_signal.changed, timeout=1000) as blocker:
        dialog.radio_dark.setChecked(True)
    assert settings.theme == "light"  # unchanged — still the persisted value
    assert blocker.args[0]["bg"] == "#1E1E1E"  # dark.json's bg, shown but not saved


def test_incidental_save_during_preview_does_not_persist_it(dialog, settings):
    """Direct regression test for the reported bug: simulate an unrelated
    settings.save() firing while a preview is live (e.g. the user adjusts
    volume elsewhere) and confirm the previewed theme was never written
    into the settings object that save() would have persisted."""
    dialog.radio_dark.setChecked(True)
    with patch.object(Settings, "save") as mock_save:
        settings.save()
    assert settings.theme == "light"
    assert mock_save.called


def test_reject_without_preview_does_not_reemit_theme(qtbot, dialog, theme_signal):
    # Regression test: closing Preferences without ever touching the
    # theme radios used to unconditionally re-broadcast the (unchanged)
    # committed palette anyway, forcing a full app.setStyleSheet() re-
    # polish of every widget for nothing — expensive enough on the main
    # thread to audibly glitch a track playing via the callback-based
    # sd.OutputStream in audio/audio_player.py. Simply opening and
    # closing the dialog must not touch theme_signal at all.
    received = []
    theme_signal.changed.connect(lambda palette: received.append(palette))

    dialog.reject()
    qtbot.wait(50)

    assert received == []


def test_reject_restores_committed_palette(qtbot, dialog, settings, theme, theme_signal):
    dialog.radio_dark.setChecked(True)  # preview only, settings.theme stays "light"

    with qtbot.waitSignal(theme_signal.changed, timeout=1000) as blocker:
        dialog.reject()

    assert settings.theme == "light"
    assert blocker.args[0]["bg"] == "#FAFAFA"  # light.json's bg — theme.palette, unchanged this whole time


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
