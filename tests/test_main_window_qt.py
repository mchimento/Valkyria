"""
Tests for the PySide6 foundation (ui_qt/). Additive to the existing
tkinter-based test suite — not a replacement, until final cutover.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.settings import Settings
from themes.theme_manager import ThemeManager
from ui_qt.main_window import MainWindowQt
from ui_qt.theme_bridge import ThemeSignal


@pytest.fixture
def settings():
    with patch.object(Settings, "load"):
        s = Settings()
    s.window_geometry_qt = None
    return s


@pytest.fixture
def theme(settings):
    return ThemeManager(settings)


@pytest.fixture
def theme_signal():
    return ThemeSignal()


@pytest.fixture
def mock_player():
    player = MagicMock()
    player.get_time.return_value = 0
    player.get_length.return_value = 0
    player.get_mute_state.return_value = False
    player.trigger_fade_out.return_value = 0
    return player


@pytest.fixture
def window(qtbot, settings, theme, mock_player, theme_signal):
    win = MainWindowQt(settings, theme, mock_player, theme_signal)
    qtbot.addWidget(win)
    return win


def test_shows_without_error(qtbot, window):
    window.show()
    qtbot.waitExposed(window)
    assert window.isVisible()


def test_is_frameless(window):
    from PySide6.QtCore import Qt

    assert window.windowFlags() & Qt.FramelessWindowHint


def test_menu_bar_top_level_labels(window):
    labels = [action.text() for action in window.menubar._menubar.actions()]
    assert labels == ["Media", "Playback", "View", "Tools", "Help"]


def test_window_controls_wired(window):
    assert window.menubar._btn_min is not None
    assert window.menubar._btn_max is not None
    assert window.menubar._btn_close is not None


def test_close_button_closes_window(qtbot, window):
    window.show()
    qtbot.waitExposed(window)
    window.menubar._btn_close.click()
    assert not window.isVisible()


def test_geometry_persisted_on_close(qtbot, window, settings):
    window.setGeometry(50, 60, 900, 700)
    window.close()
    assert settings.window_geometry_qt == "900x700+50+60"


def test_restores_saved_geometry(qtbot, settings, theme, mock_player, theme_signal):
    settings.window_geometry_qt = "800x600+10+20"
    win = MainWindowQt(settings, theme, mock_player, theme_signal)
    qtbot.addWidget(win)
    g = win.geometry()
    assert (g.width(), g.height(), g.x(), g.y()) == (800, 600, 10, 20)


def test_maximize_toggle_updates_button_text(qtbot, window):
    window.show()
    qtbot.waitExposed(window)
    initial = window.menubar._btn_max.text()
    window.menubar._toggle_maximize()
    qtbot.wait(50)
    assert window.menubar._btn_max.text() != initial


def test_theme_signal_updates_waveform_colors(window, theme_signal):
    new_palette = {"waveform_bg": "#123456", "waveform_played": "#abcdef"}
    theme_signal.changed.emit(new_palette)
    assert window.controls.waveform.bg_color == "#123456"
    assert window.controls.waveform.played_color == "#abcdef"


def test_preferences_reuses_single_instance(window):
    window._on_open_preferences()
    first = window._preferences_win
    assert first is not None
    window._on_open_preferences()
    assert window._preferences_win is first
    first.close()
