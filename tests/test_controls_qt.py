"""Tests for ui_qt/controls.py."""
import threading
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf
from PySide6.QtCore import Qt

from app.settings import Settings
from ui_qt.controls import ControlsBarQt, _format_ms

PALETTE = {
    "waveform_bg": "#1a1a1a",
    "waveform_played": "#FF6B00",
    "waveform_unplayed": "#404040",
    "waveform_border": "#808080",
    "button_fg_color": "#1E1E1E",
    "button_bg_color": "#BB86FC",
    "button_hover": "#985EFF",
    "button_pressed": "#6023CB",
}


@pytest.fixture
def settings():
    with patch.object(Settings, "load"):
        s = Settings()
    s.volume = 80
    s.mute = False
    return s


@pytest.fixture
def mock_player():
    player = MagicMock()
    player.get_time.return_value = 0
    player.get_length.return_value = 0
    player.get_mute_state.return_value = False
    player.trigger_fade_out.return_value = 0
    return player


@pytest.fixture
def controls(qtbot, mock_player, settings):
    bar = ControlsBarQt(mock_player, settings, PALETTE)
    qtbot.addWidget(bar)
    settings.save = MagicMock()  # reset call history from construction-time init
    mock_player.reset_mock()  # clears call history only; return_values set above are preserved
    return bar


@pytest.fixture
def mock_state():
    state = MagicMock()
    state.current_index = 0
    state.playlist = ["/tmp/a.mp3"]
    state.play_limits = {}
    return state


@pytest.fixture
def controls_with_state(qtbot, mock_player, settings, mock_state):
    bar = ControlsBarQt(mock_player, settings, PALETTE, state=mock_state)
    qtbot.addWidget(bar)
    mock_player.reset_mock()
    mock_player.is_playing.return_value = True
    mock_player.is_paused.return_value = False
    return bar


@pytest.fixture
def tiny_wav(tmp_path):
    path = tmp_path / "tone.wav"
    sr = 8000
    t = np.linspace(0, 0.3, int(sr * 0.3), endpoint=False)
    data = (0.5 * np.sin(2 * np.pi * 440 * t)).astype("float32")
    sf.write(str(path), data, sr)
    return str(path)


def test_init_mute_does_not_reset_saved_preference(qtbot, settings):
    """Regression test: a freshly-constructed AudioPlayer's get_mute_state()
    always returns its constructor default (False), never None — a prior
    version of _init_mute() treated that default as authoritative and
    silently reset a saved "muted" preference back to unmuted on every
    launch, then re-persisted the wrong value to disk."""
    settings.mute = True
    player = MagicMock()
    player.get_time.return_value = 0
    player.get_length.return_value = 0
    player.get_mute_state.return_value = False  # fresh player's real default
    player.trigger_fade_out.return_value = 0

    bar = ControlsBarQt(player, settings, PALETTE)
    qtbot.addWidget(bar)

    assert settings.mute is True
    assert bar._is_muted is True
    assert bar.btn_mute.text() == "🔇"
    assert player.set_mute.call_args[0][0] is True


def test_format_ms():
    assert _format_ms(0) == "--:--"
    assert _format_ms(None) == "--:--"
    assert _format_ms(65_000) == "01:05"


def test_play_file_calls_player_play_and_loads_waveform(qtbot, controls, mock_player, tiny_wav):
    controls.play_file(tiny_wav)
    qtbot.waitUntil(lambda: mock_player.play.called, timeout=2000)
    assert mock_player.play.call_args[0][0] == tiny_wav
    qtbot.waitUntil(lambda: controls.waveform.current_file == tiny_wav, timeout=2000)


def test_pause_calls_player_pause(controls, mock_player):
    controls.btn_pause.click()
    assert mock_player.pause.called


def test_pause_with_nothing_loaded_does_not_change_button_state(controls, mock_player):
    # Matches ui/controls.py's _on_pause guard: with nothing playing or
    # paused, pressing Pause must be a no-op, not flip is_playing/is_paused
    # and highlight a button for playback that isn't actually happening.
    mock_player.is_playing.return_value = False
    mock_player.is_paused.return_value = False

    controls.btn_pause.click()

    assert not mock_player.pause.called
    assert controls.is_playing is False
    assert controls.is_paused is False
    assert controls.btn_play.styleSheet() == ""
    assert controls.btn_pause.styleSheet() == ""


def test_stop_dispatches_and_resets_ui(qtbot, controls, mock_player):
    controls.btn_stop.click()
    qtbot.waitUntil(lambda: mock_player.stop.called, timeout=2000)
    qtbot.waitUntil(lambda: controls.current_time_label.text() == "--:--", timeout=2000)


def test_play_file_highlights_play_button(controls, tiny_wav):
    assert controls.btn_play.styleSheet() == ""
    controls.play_file(tiny_wav)
    assert controls.is_playing is True
    assert controls.is_paused is False
    assert "button_pressed" not in controls.btn_play.styleSheet()  # sanity: real color, not the key name
    assert controls.btn_play.styleSheet() == f"background-color: {PALETTE['button_pressed']};"
    assert controls.btn_pause.styleSheet() == ""


def test_pause_then_resume_toggles_button_highlight(controls, mock_player, tiny_wav):
    controls.play_file(tiny_wav)

    mock_player.is_paused.return_value = True
    controls.btn_pause.click()
    assert controls.is_paused is True
    assert controls.is_playing is False
    assert controls.btn_pause.styleSheet() == f"background-color: {PALETTE['button_pressed']};"
    assert controls.btn_play.styleSheet() == ""

    mock_player.is_paused.return_value = False
    controls.btn_pause.click()
    assert controls.is_playing is True
    assert controls.is_paused is False
    assert controls.btn_play.styleSheet() == f"background-color: {PALETTE['button_pressed']};"
    assert controls.btn_pause.styleSheet() == ""


def test_stop_clears_play_pause_highlight(qtbot, controls, mock_player, tiny_wav):
    controls.play_file(tiny_wav)
    controls.btn_stop.click()
    qtbot.waitUntil(lambda: mock_player.stop.called, timeout=2000)
    qtbot.waitUntil(lambda: controls.btn_play.styleSheet() == "", timeout=2000)
    assert controls.is_playing is False
    assert controls.is_paused is False
    assert controls.btn_pause.styleSheet() == ""


def test_track_ended_clears_play_pause_highlight(controls, tiny_wav):
    controls.play_file(tiny_wav)
    controls.on_track_ended()
    assert controls.is_playing is False
    assert controls.btn_play.styleSheet() == ""


def test_volume_change_persists_and_calls_player(controls, mock_player, settings):
    controls.volume_slider.setValue(42)
    assert settings.volume == 42
    assert settings.save.called
    assert mock_player.set_volume.call_args[0][0] == 42
    assert controls.volume_label.text() == "42%"


def test_mute_toggle_persists_and_saves(controls, mock_player, settings):
    controls.btn_mute.click()
    assert mock_player.set_mute.call_args[0][0] is True
    assert settings.mute is True
    assert settings.save.called
    assert controls.btn_mute.text() == "🔇"


def test_track_ended_resets_ui(controls):
    controls.current_time_label.setText("01:23")
    controls.on_track_ended()
    assert controls.current_time_label.text() == "--:--"
    assert controls.total_time_label.text() == "--:--"


def test_real_player_track_end_bridges_across_thread(qtbot, settings):
    """End-to-end regression net for the cross-thread bridge: a REAL
    AudioPlayer (not a mock) firing on_track_end from a background thread,
    same as the sounddevice callback-finished thread would, must reach
    ControlsBarQt.on_track_ended() on the Qt main thread."""
    from audio.audio_player import AudioPlayer
    from ui_qt.player_bridge import PlayerBridge

    bridge = PlayerBridge()
    player = AudioPlayer(on_track_end=bridge.track_ended.emit)
    bar = ControlsBarQt(player, settings, PALETTE)
    qtbot.addWidget(bar)
    bridge.track_ended.connect(bar.on_track_ended, Qt.QueuedConnection)
    bar.current_time_label.setText("01:23")

    worker = threading.Thread(target=player._on_stream_finished, daemon=True)
    with qtbot.waitSignal(bridge.track_ended, timeout=2000):
        worker.start()
    worker.join()

    qtbot.waitUntil(lambda: bar.current_time_label.text() == "--:--", timeout=2000)


def test_time_limit_reached_fires_when_elapsed_exceeds_limit(controls_with_state, mock_state):
    mock_state.play_limits["/tmp/a.mp3"] = 30  # seconds
    received = []
    controls_with_state.time_limit_reached.connect(lambda: received.append(True))

    controls_with_state._check_time_limit(30_000)  # exactly at the limit, in ms

    assert received == [True]
    assert controls_with_state._time_limit_fired is True


def test_time_limit_does_not_fire_before_limit_reached(controls_with_state, mock_state):
    mock_state.play_limits["/tmp/a.mp3"] = 30
    received = []
    controls_with_state.time_limit_reached.connect(lambda: received.append(True))

    controls_with_state._check_time_limit(29_000)

    assert received == []
    assert controls_with_state._time_limit_fired is False


def test_time_limit_does_not_fire_without_a_limit_set(controls_with_state):
    received = []
    controls_with_state.time_limit_reached.connect(lambda: received.append(True))

    controls_with_state._check_time_limit(999_000)

    assert received == []


def test_time_limit_does_not_fire_while_paused(controls_with_state, mock_player, mock_state):
    mock_state.play_limits["/tmp/a.mp3"] = 10
    mock_player.is_paused.return_value = True
    received = []
    controls_with_state.time_limit_reached.connect(lambda: received.append(True))

    controls_with_state._check_time_limit(20_000)

    assert received == []


def test_time_limit_does_not_fire_when_not_playing(controls_with_state, mock_player, mock_state):
    mock_state.play_limits["/tmp/a.mp3"] = 10
    mock_player.is_playing.return_value = False
    received = []
    controls_with_state.time_limit_reached.connect(lambda: received.append(True))

    controls_with_state._check_time_limit(20_000)

    assert received == []


def test_time_limit_only_fires_once(controls_with_state, mock_state):
    mock_state.play_limits["/tmp/a.mp3"] = 10
    received = []
    controls_with_state.time_limit_reached.connect(lambda: received.append(True))

    controls_with_state._check_time_limit(20_000)
    controls_with_state._check_time_limit(21_000)

    assert received == [True]


def test_time_limit_fired_flag_resets_on_play_file(controls_with_state, tiny_wav):
    controls_with_state._time_limit_fired = True
    controls_with_state.play_file(tiny_wav)
    assert controls_with_state._time_limit_fired is False
