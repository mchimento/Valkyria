"""Tests for ui_qt/status_view.py."""
from unittest.mock import MagicMock, patch

import pytest

from app.state import AppState
from ui_qt.status_view import StatusViewQt

PALETTE = {"status_fg": "#202020", "status_meta_fg": "#505050", "accent": "#0078D4"}


@pytest.fixture
def state():
    return AppState(playlist=["/tmp/a.mp3", "/tmp/b.mp3"], current_index=0)


@pytest.fixture
def theme():
    t = MagicMock()
    t.palette = PALETTE
    return t


@pytest.fixture
def settings():
    return MagicMock()


@pytest.fixture
def view(qtbot, state, theme, settings):
    with patch("ui_qt.status_view.get_metadata", return_value={}), \
         patch("ui_qt.status_view.get_best_artwork", return_value=None):
        v = StatusViewQt(state, theme, settings)
    qtbot.addWidget(v)
    return v


def test_restore_status_falls_back_to_basename(view, state):
    with patch("ui_qt.status_view.get_metadata", return_value={}):
        view.restore_status()
    assert view.title_label.text() == "a.mp3"


def test_restore_status_populates_from_metadata(view):
    meta = {"title": "Real Title", "artist": "Real Artist", "duration_s": 125, "bitrate": 192}
    with patch("ui_qt.status_view.get_metadata", return_value=meta):
        view.restore_status()
    assert view.title_label.text() == "Real Title"
    assert view.artist_label.text() == "Real Artist"
    assert view.meta_label.text() == "02:05 • 192 kbps"


def test_no_current_track_clears_status(view, state):
    state.current_index = None
    view.restore_status()
    assert view.title_label.text() == ""
    assert view.artist_label.text() == ""


def test_schedule_restore_restores_after_delay(qtbot, view):
    with patch("ui_qt.status_view.get_metadata", return_value={"title": "Restored"}):
        view.title_label.setText("Temporary")
        view.schedule_restore(delay=50)
        qtbot.waitUntil(lambda: view.title_label.text() == "Restored", timeout=1000)


def test_handle_stop_clears_and_stops_ticker(view):
    view._time_limit_timer.start()
    view.handle_stop()
    assert view.title_label.text() == ""
    assert not view._time_limit_timer.isActive()


def test_time_limit_ticker_shows_remaining_and_self_stops(view, state):
    state.play_limits = {"/tmp/a.mp3": 30}
    controls = MagicMock()
    controls.player.get_time.return_value = 5000
    view._base_meta_text = "02:05 • 192 kbps"
    view._start_time_limit_updates(controls)
    assert view.time_limit_label.text() == "⏱ Time limit: 25s remaining"

    # Limit entry removed -> ticker stops itself and restores base text.
    state.play_limits = {}
    view._update_time_limit()
    assert not view._time_limit_timer.isActive()
    assert view.meta_label.text() == "02:05 • 192 kbps"


def test_artwork_uses_real_bytes_when_available(view):
    import struct
    import zlib

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    # Minimal valid 1x1 PNG.
    raw = zlib.compress(b"\x00\x00\x00\x00")
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", raw)
        + chunk(b"IEND", b"")
    )
    with patch("ui_qt.status_view.get_best_artwork", return_value=png):
        view._update_artwork("/tmp/a.mp3")
    assert not view.artwork_label.pixmap().isNull()


def test_artwork_placeholder_when_missing(view):
    with patch("ui_qt.status_view.get_best_artwork", return_value=None):
        view._update_artwork("/tmp/a.mp3")
    assert not view.artwork_label.pixmap().isNull()
