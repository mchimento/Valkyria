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


def test_audio_device_menu_drops_alsa_plugin_aliases(window):
    # Regression test: sd.query_devices() also lists ALSA's stock
    # software/plugin routes (sysdefault, front, surroundNN, pipewire,
    # dmix, "default") as separate "devices" purely because alsa.conf
    # names them — on a system with only an ALSA hostapi (no native
    # PipeWire/Pulse hostapi) they all resolve to the same underlying
    # output as "Default Audio Device", so they should be filtered out
    # of the Tools > Audio Device menu rather than padding it with
    # duplicates. Physical hw:CARD,DEV entries and "Default Audio
    # Device" itself (the only way to reach a Bluetooth/dynamically
    # connected output on such a system) must remain.
    window.player.get_audio_devices.return_value = [
        ("__DEFAULT__", "Default Audio Device"),
        ("0", "HDA Intel PCH: Analog (hw:0,0)"),
        ("1", "HDA Intel HDMI: 0 (hw:1,3)"),
        ("2", "sysdefault"),
        ("3", "front"),
        ("4", "surround40"),
        ("5", "pipewire"),
        ("6", "dmix"),
        ("7", "default"),
    ]
    labels = [item["label"] for item in window._build_audio_device_items()]
    assert labels == [
        "Default Audio Device (system default)",
        "HDA Intel PCH: Analog (hw:0,0)",
        "HDA Intel HDMI: 0 (hw:1,3)",
    ]


def test_audio_device_menu_labels_default_with_live_bluetooth_name(window):
    # Regression test: sounddevice/PortAudio can't see what "Default"
    # actually reaches once it's a Bluetooth sink, so the menu used to
    # just say "(system default)" with no indication Bluetooth was even
    # in use. get_default_output_info() resolves this via WirePlumber.
    window.player.get_audio_devices.return_value = [
        ("__DEFAULT__", "Default Audio Device"),
        ("0", "HDA Intel PCH: Analog (hw:0,0)"),
    ]
    window.player.get_default_output_info.return_value = (None, "TWS-D2500")
    labels = [item["label"] for item in window._build_audio_device_items()]
    assert labels[0] == "Default Audio Device (currently: TWS-D2500)"


def test_menu_bar_top_level_labels(window):
    labels = [action.text() for action in window.menubar._menubar.actions()]
    assert labels == ["&Media", "&Playback", "&View", "&Tools", "&Help"]


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


def test_open_folder_menu_action_populates_playlist(qtbot, window, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    (tmp_path / "song.mp3").write_bytes(b"")
    (tmp_path / "notes.txt").write_bytes(b"")

    with patch.object(QFileDialog, "getExistingDirectory", return_value=str(tmp_path)):
        window._on_open_folder()

    assert window.state.playlist == [str(tmp_path / "song.mp3")]
    assert window.state.current_index is None
    # Rows are only created once their metadata batch arrives — see
    # ui_qt/playlist_view.py's refresh() docstring.
    qtbot.waitUntil(lambda: window.playlist_view._tree.topLevelItemCount() == 1, timeout=2000)


def test_play_index_updates_state_and_plays(qtbot, window, mock_player):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3"]
    window.playlist_view.refresh()

    window._play_index(1)

    assert window.state.current_index == 1
    qtbot.waitUntil(lambda: mock_player.play.called, timeout=1000)
    assert mock_player.play.call_args[0][0] == "/tmp/b.mp3"


def test_track_ended_repeat_none_advances_to_next(window):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3"]
    window.state.current_index = 0
    window.state.repeat_mode = "none"

    window._on_track_ended()

    assert window.state.current_index == 1


def test_track_ended_repeat_none_stops_at_end_of_playlist(window):
    window.state.playlist = ["/tmp/a.mp3"]
    window.state.current_index = 0
    window.state.repeat_mode = "none"

    window._on_track_ended()

    assert window.state.current_index == 0  # unchanged — controls.on_track_ended() ran instead


def test_track_ended_repeat_one_replays_and_resets_mode(window):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3"]
    window.state.current_index = 0
    window.state.repeat_mode = "one"

    window._on_track_ended()

    assert window.state.current_index == 0  # replayed the same track
    assert window.state.repeat_mode == "none"


def test_track_ended_repeat_all_wraps_to_start(window):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3"]
    window.state.current_index = 1  # last track
    window.state.repeat_mode = "all"

    window._on_track_ended()

    assert window.state.current_index == 0


def test_track_ended_with_no_current_index_just_stops(window):
    window.state.playlist = []
    window.state.current_index = None

    window._on_track_ended()  # must not raise


def test_prev_moves_back_one(qtbot, window, mock_player):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3", "/tmp/c.mp3"]
    window.state.current_index = 2

    window.controls.btn_prev.click()

    # _on_prev routes through _fade_then_play, which triggers the fade-out
    # and switches tracks on a background thread + queued connection (see
    # main_window.py:385-401) rather than updating state synchronously.
    qtbot.waitUntil(lambda: mock_player.play.called, timeout=1000)
    assert window.state.current_index == 1
    assert mock_player.play.call_args[0][0] == "/tmp/b.mp3"


def test_prev_at_start_of_playlist_does_nothing(window, mock_player):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3"]
    window.state.current_index = 0

    window.controls.btn_prev.click()

    assert window.state.current_index == 0
    mock_player.play.assert_not_called()


def test_next_moves_forward_one(qtbot, window, mock_player):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3", "/tmp/c.mp3"]
    window.state.current_index = 0

    window.controls.btn_next.click()

    # See test_prev_moves_back_one: _on_next also routes through the
    # threaded/queued _fade_then_play sequence, not a synchronous update.
    qtbot.waitUntil(lambda: mock_player.play.called, timeout=1000)
    assert window.state.current_index == 1
    assert mock_player.play.call_args[0][0] == "/tmp/b.mp3"


def test_next_at_end_of_playlist_does_nothing(window, mock_player):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3"]
    window.state.current_index = 1

    window.controls.btn_next.click()

    assert window.state.current_index == 1
    mock_player.play.assert_not_called()


def test_repeat_toggle_cycles_none_one_all_none(window):
    assert window.state.repeat_mode == "none"

    window.controls.btn_repeat.click()
    assert window.state.repeat_mode == "one"

    window.controls.btn_repeat.click()
    assert window.state.repeat_mode == "all"

    window.controls.btn_repeat.click()
    assert window.state.repeat_mode == "none"


def test_repeat_toggle_updates_button_icon(window):
    window.controls.btn_repeat.click()
    assert window.controls.btn_repeat.text() == "🔂"

    window.controls.btn_repeat.click()
    assert window.controls.btn_repeat.text() == "🔁"
    assert "background-color" in window.controls.btn_repeat.styleSheet()


def test_effects_button_does_not_raise(window):
    window.controls.btn_effects.click()  # stub — must not raise


def test_initial_visibility_matches_settings(qtbot, settings, theme, mock_player, theme_signal):
    settings.show_playlist = True
    settings.show_browser = False
    win = MainWindowQt(settings, theme, mock_player, theme_signal)
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    assert win.playlist_view.isVisible()
    assert not win.browser_view.isVisible()


def test_toggle_playlist_visibility(qtbot, window, settings):
    window.show()
    qtbot.waitExposed(window)
    assert window.playlist_view.isVisible()

    window._toggle_playlist_visibility()
    assert not window.playlist_view.isVisible()
    assert settings.show_playlist is False

    window._toggle_playlist_visibility()
    assert window.playlist_view.isVisible()
    assert settings.show_playlist is True


def test_toggle_browser_visibility(qtbot, window, settings):
    window.show()
    qtbot.waitExposed(window)
    assert window.browser_view.isVisible()

    window._toggle_browser_visibility()
    assert not window.browser_view.isVisible()
    assert settings.show_browser is False
