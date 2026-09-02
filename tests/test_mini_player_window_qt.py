"""Tests for ui_qt/mini_player_window.py."""
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt

from app.state import AppState
from ui_qt.mini_player_window import MiniPlayerWindowQt

PALETTE = {"highlight": "#EB5B00", "accent": "#BB86FC"}


@pytest.fixture
def state():
    return AppState(playlist=["/tmp/alpha.mp3", "/tmp/bravo.mp3"], current_index=0)


@pytest.fixture
def controls():
    c = MagicMock()
    c.is_playing = False
    c.is_paused = False
    c.player = MagicMock()
    c.player.get_length.return_value = 0
    c.player.get_time.return_value = 0
    return c


@pytest.fixture
def win(qtbot, state, controls):
    with patch("ui_qt.mini_player_window.get_metadata", return_value={}):
        w = MiniPlayerWindowQt(state, controls, PALETTE)
    qtbot.addWidget(w)
    return w


def test_play_pause_click_emits_signal(qtbot, win):
    with qtbot.waitSignal(win.play_pause_requested, timeout=1000):
        win.btn_play_pause.click()


def test_prev_click_emits_signal(qtbot, win):
    with qtbot.waitSignal(win.prev_requested, timeout=1000):
        win.btn_prev.click()


def test_next_click_emits_signal(qtbot, win):
    with qtbot.waitSignal(win.next_requested, timeout=1000):
        win.btn_next.click()


def test_close_button_emits_restore_requested(qtbot, win):
    with qtbot.waitSignal(win.restore_requested, timeout=1000):
        win.close_btn.click()


def test_maximize_button_emits_restore_requested(qtbot, win):
    with qtbot.waitSignal(win.restore_requested, timeout=1000):
        win.maximize_btn.click()


def test_double_click_emits_restore_requested(qtbot, win):
    # Headless sanity check only — synthetic mouse events aren't guaranteed
    # to match a real interactive session (see CLAUDE.md's Qt gotchas).
    with qtbot.waitSignal(win.restore_requested, timeout=1000):
        qtbot.mouseDClick(win, Qt.LeftButton)


def test_play_pause_icon_reflects_playing(win, controls):
    controls.is_playing = True
    controls.is_paused = False
    win._update_ui()
    assert win.btn_play_pause.text() == "⏸"


def test_play_pause_icon_reflects_paused(win, controls):
    controls.is_playing = False
    controls.is_paused = True
    win._update_ui()
    assert win.btn_play_pause.text() == "▶"


def test_play_pause_icon_reflects_stopped(win, controls):
    controls.is_playing = False
    controls.is_paused = False
    win._update_ui()
    assert win.btn_play_pause.text() == "▶"


def test_time_limit_label_hidden_without_limit(win):
    win._update_ui()
    assert win.time_limit_label.text() == ""


def test_time_limit_label_shows_remaining_seconds(win, state, controls):
    state.play_limits["/tmp/alpha.mp3"] = 60
    controls.player.get_length.return_value = 200000
    controls.player.get_time.return_value = 10000
    win._update_ui()
    assert win.time_limit_label.text() == "Time limit: 50s remaining"


def test_title_falls_back_to_basename_without_metadata(win):
    with patch("ui_qt.mini_player_window.get_metadata", return_value={}):
        win._update_ui()
    assert win.title_label.text() == "alpha.mp3"


def test_title_uses_metadata_title(win):
    with patch("ui_qt.mini_player_window.get_metadata", return_value={"title": "Real Title"}):
        win._update_ui()
    assert win.title_label.text() == "Real Title"


def test_title_truncated_when_long():
    long_title = "A" * 80
    state = AppState(playlist=["/tmp/x.mp3"], current_index=0)
    controls = MagicMock()
    controls.is_playing = False
    controls.is_paused = False
    controls.player.get_length.return_value = 0
    controls.player.get_time.return_value = 0
    with patch("ui_qt.mini_player_window.get_metadata", return_value={"title": long_title}):
        w = MiniPlayerWindowQt(state, controls, PALETTE)
        w._update_ui()
    assert w.title_label.text() == "A" * 47 + "..."


def test_no_track_loaded_shows_placeholder(win, state):
    state.current_index = None
    win._update_ui()
    assert win.title_label.text() == "No track loaded"


def test_start_updates_starts_timer(win):
    win.start_updates()
    assert win._timer.isActive()
    win.stop_updates()


def test_stop_updates_stops_timer(win):
    win.start_updates()
    win.stop_updates()
    assert not win._timer.isActive()


def test_position_bottom_right_uses_available_geometry(win):
    from PySide6.QtWidgets import QApplication

    screen = QApplication.primaryScreen()
    win._position_bottom_right()
    if screen is not None:
        avail = screen.availableGeometry()
        expected_x = avail.x() + avail.width() - win.width() - 20
        expected_y = avail.y() + avail.height() - win.height() - 40
        assert win.pos().x() == expected_x
        assert win.pos().y() == expected_y
