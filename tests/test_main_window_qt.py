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
    # Audio Effects dialog init reads these — real numeric/dict values so
    # its sliders' initial formatting (f"{value:.1f}") doesn't choke on a
    # bare MagicMock.
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


def test_audio_effects_reuses_single_instance(window):
    window._on_open_audio_effects()
    first = window._audio_effects_win
    assert first is not None
    window._on_open_audio_effects()
    assert window._audio_effects_win is first
    first.close()


def test_open_folder_menu_action_populates_playlist(qtbot, window, tmp_path):
    from PySide6.QtWidgets import QFileDialog

    (tmp_path / "song.mp3").write_bytes(b"")
    (tmp_path / "notes.txt").write_bytes(b"")

    with patch.object(QFileDialog, "getExistingDirectory", return_value=str(tmp_path)):
        window._on_open_folder()

    assert window.state.playlist == [str(tmp_path / "song.mp3")]
    assert window.state.current_index is None
    # Rows only appear once their metadata batch arrives.
    qtbot.waitUntil(lambda: window.playlist_view._tree.topLevelItemCount() == 1, timeout=2000)


def test_play_index_updates_state_and_plays(qtbot, window, mock_player):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3"]
    window.playlist_view.refresh()

    window._play_index(1)

    assert window.state.current_index == 1
    qtbot.waitUntil(lambda: mock_player.play.called, timeout=1000)
    assert mock_player.play.call_args[0][0] == "/tmp/b.mp3"


def test_double_click_playlist_row_highlights_play_button(qtbot, window, mock_player):
    # play_on_double is on by default; double-clicking a row must reach
    # play_file the same way a Play-button click does, so the button's
    # pressed-highlight isn't tied to only one of the two trigger paths.
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3"]
    window.playlist_view.refresh()

    window.playlist_view.track_activated.emit(1)

    qtbot.waitUntil(lambda: mock_player.play.called, timeout=1000)
    assert window.controls.is_playing is True
    assert window.controls.btn_play.styleSheet() != ""


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

    # _on_prev routes through _fade_then_play (threaded + queued), not synchronous.
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

    # Same as test_prev_moves_back_one: threaded + queued, not synchronous.
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


def test_toggle_dj_visibility_registers_and_unregisters_metrics_callback(qtbot, window, settings, mock_player):
    window.show()
    qtbot.waitExposed(window)
    assert window.dj_view.isVisible()

    window._toggle_dj_visibility()
    assert not window.dj_view.isVisible()
    assert settings.show_dj is False
    mock_player.set_audio_metrics_callback.assert_called_with(None)

    window._toggle_dj_visibility()
    assert window.dj_view.isVisible()
    assert settings.show_dj is True
    mock_player.set_audio_metrics_callback.assert_called_with(window.dj_view._emit_metrics)


def test_track_info_and_booklet_disabled_with_no_target(window):
    assert not window._action_track_info.isEnabled()
    assert not window._action_track_booklet.isEnabled()


def test_track_info_and_booklet_enabled_by_selection(qtbot, window):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3"]
    window.playlist_view.refresh()
    qtbot.waitUntil(lambda: window.playlist_view._tree.topLevelItemCount() == 2, timeout=2000)
    window.playlist_view._select_indices([1])
    assert window._action_track_info.isEnabled()
    assert window._action_track_booklet.isEnabled()


def test_track_info_and_booklet_enabled_by_current_index_fallback(window):
    window.state.playlist = ["/tmp/a.mp3"]
    window.state.current_index = 0
    window._update_menu_state()
    assert window._action_track_info.isEnabled()


def test_open_track_info_with_no_target_shows_message(window):
    with patch("ui_qt.main_window.QMessageBox") as mock_box:
        window._on_open_track_info()
    mock_box.information.assert_called_once()


def test_open_track_info_opens_dialog_for_resolved_file(qtbot, window):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3"]
    window.playlist_view.refresh()
    qtbot.waitUntil(lambda: window.playlist_view._tree.topLevelItemCount() == 2, timeout=2000)
    window.playlist_view._select_indices([1])

    info = {"path": "/tmp/b.mp3", "filename": "b.mp3", "size": 0, "format": "", "duration": 0,
            "bitrate": 0, "sample_rate": 0, "channels": 0, "codec": "", "metadata": {}}
    with patch("ui_qt.media_info_window.get_file_info", return_value=info), \
         patch("ui_qt.media_info_window.metadata_extractor"):
        window._on_open_track_info()

    assert len(window._track_info_windows) == 1
    assert window._track_info_windows[0].file_path == "/tmp/b.mp3"


def test_opening_two_tracks_info_keeps_both_windows(window):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3"]
    window.playlist_view.refresh()

    info = {"path": "/tmp/a.mp3", "filename": "a.mp3", "size": 0, "format": "", "duration": 0,
            "bitrate": 0, "sample_rate": 0, "channels": 0, "codec": "", "metadata": {}}
    with patch("ui_qt.media_info_window.get_file_info", return_value=info), \
         patch("ui_qt.media_info_window.metadata_extractor"):
        window._open_track_info("/tmp/a.mp3")
        window._open_track_info("/tmp/b.mp3")

    assert len(window._track_info_windows) == 2


def test_open_booklet_opens_dialog_for_resolved_file(window):
    window.state.playlist = ["/tmp/a.mp3"]
    window.state.current_index = 0
    window._update_menu_state()

    with patch("ui_qt.booklet_viewer_window.get_booklet_images", return_value=[]):
        window._on_open_booklet()

    assert len(window._track_booklet_windows) == 1
    assert window._track_booklet_windows[0].file_path == "/tmp/a.mp3"


# ---------- mini player ----------

def test_minimize_shows_mini_player_when_enabled(qtbot, window, settings):
    settings.mini_player_enabled = True
    window.show()
    qtbot.waitExposed(window)
    window.showMinimized()
    qtbot.wait(50)
    # MiniPlayerWindowQt is intentionally parentless (a WindowStaysOnTopHint
    # window shouldn't be parented to the window it floats above), so it
    # isn't cleaned up by qtbot.addWidget(window) alone — register it here
    # or its still-running 500ms QTimer leaks into later tests.
    qtbot.addWidget(window.mini_player)
    assert window.mini_player is not None
    assert window.mini_player.isVisible()
    window.mini_player.stop_updates()


def test_minimize_does_not_show_mini_player_when_disabled(qtbot, window, settings):
    settings.mini_player_enabled = False
    window.show()
    qtbot.waitExposed(window)
    window.showMinimized()
    qtbot.wait(50)
    assert window.mini_player is None


def test_restore_from_mini_player_hides_it_and_restores_main(qtbot, window, settings):
    settings.mini_player_enabled = True
    window.show()
    qtbot.waitExposed(window)
    window.showMinimized()
    qtbot.wait(50)

    qtbot.addWidget(window.mini_player)
    with patch.object(window, "showNormal") as mock_show_normal, \
         patch.object(window, "raise_") as mock_raise, \
         patch.object(window, "activateWindow") as mock_activate:
        window.mini_player.restore_requested.emit()
        # raise_()/activateWindow() are deferred via QTimer.singleShot(0, ...)
        # to dodge GNOME/Mutter's focus-stealing prevention — give that tick
        # a chance to fire before asserting.
        qtbot.waitUntil(lambda: mock_raise.called, timeout=1000)

    assert not window.mini_player.isVisible()
    mock_show_normal.assert_called_once()
    mock_raise.assert_called_once()
    mock_activate.assert_called_once()


def test_mini_player_play_pause_when_stopped_calls_play_requested(window):
    window.controls.is_playing = False
    window.controls.is_paused = False
    with patch.object(window, "_on_play_requested") as mock_play_requested:
        window._on_mini_player_play_pause()
    mock_play_requested.assert_called_once()


def test_mini_player_play_pause_when_playing_calls_pause(window):
    window.controls.is_playing = True
    window.controls.is_paused = False
    with patch.object(window.controls, "_on_pause") as mock_pause:
        window._on_mini_player_play_pause()
    mock_pause.assert_called_once()


def test_mini_player_play_pause_when_paused_calls_pause(window):
    window.controls.is_playing = False
    window.controls.is_paused = True
    with patch.object(window.controls, "_on_pause") as mock_pause:
        window._on_mini_player_play_pause()
    mock_pause.assert_called_once()


def test_close_event_stops_mini_player_timer(qtbot, window, settings):
    settings.mini_player_enabled = True
    window.show()
    qtbot.waitExposed(window)
    window.showMinimized()
    qtbot.wait(50)
    mini_player = window.mini_player
    qtbot.addWidget(mini_player)

    window.close()

    assert not mini_player._timer.isActive()


# ---------- Play for time / Clear time limit ----------

def _mock_time_limit_dialog(result):
    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = None
    mock_dialog.result = result
    mock_cls = MagicMock(return_value=mock_dialog)
    return mock_cls, mock_dialog


def test_set_time_limit_writes_value(window):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3"]
    mock_cls, _ = _mock_time_limit_dialog(45.0)
    with patch("ui_qt.main_window.TimeLimitDialogQt", mock_cls):
        window._set_time_limit(1)
    assert window.state.play_limits["/tmp/b.mp3"] == 45.0


def test_set_time_limit_clears_on_none_result(window):
    window.state.playlist = ["/tmp/a.mp3"]
    window.state.play_limits["/tmp/a.mp3"] = 30.0
    mock_cls, _ = _mock_time_limit_dialog(None)
    with patch("ui_qt.main_window.TimeLimitDialogQt", mock_cls):
        window._set_time_limit(0)
    assert "/tmp/a.mp3" not in window.state.play_limits


def test_set_time_limit_noop_on_cancel(window):
    window.state.playlist = ["/tmp/a.mp3"]
    window.state.play_limits["/tmp/a.mp3"] = 30.0
    mock_cls, _ = _mock_time_limit_dialog("CANCEL")
    with patch("ui_qt.main_window.TimeLimitDialogQt", mock_cls):
        window._set_time_limit(0)
    assert window.state.play_limits["/tmp/a.mp3"] == 30.0


def test_set_time_limit_starts_status_timer_for_current_track(window):
    window.state.playlist = ["/tmp/a.mp3"]
    window.state.current_index = 0
    mock_cls, _ = _mock_time_limit_dialog(20.0)
    with patch("ui_qt.main_window.TimeLimitDialogQt", mock_cls), \
         patch.object(window.status_view, "_start_time_limit_updates") as mock_start:
        window._set_time_limit(0)
    mock_start.assert_called_once_with(window.controls)


def test_set_time_limit_does_not_start_timer_for_other_track(window):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3"]
    window.state.current_index = 0
    mock_cls, _ = _mock_time_limit_dialog(20.0)
    with patch("ui_qt.main_window.TimeLimitDialogQt", mock_cls), \
         patch.object(window.status_view, "_start_time_limit_updates") as mock_start:
        window._set_time_limit(1)
    mock_start.assert_not_called()


def test_clear_time_limit_removes_entry_and_stops_timer_if_current(window):
    window.state.playlist = ["/tmp/a.mp3"]
    window.state.current_index = 0
    window.state.play_limits["/tmp/a.mp3"] = 30.0
    with patch.object(window.status_view, "_stop_time_limit_updates") as mock_stop:
        window._clear_time_limit(0)
    assert "/tmp/a.mp3" not in window.state.play_limits
    mock_stop.assert_called_once()


def test_clear_time_limit_noop_when_no_limit_set(window):
    window.state.playlist = ["/tmp/a.mp3"]
    with patch.object(window.status_view, "_stop_time_limit_updates") as mock_stop:
        window._clear_time_limit(0)
    mock_stop.assert_not_called()


def test_play_for_time_menu_no_target_shows_message(window):
    with patch("ui_qt.main_window.QMessageBox") as mock_box:
        window._on_play_for_time_menu()
    mock_box.information.assert_called_once()


def test_play_for_time_menu_resolves_via_selection(qtbot, window):
    window.state.playlist = ["/tmp/a.mp3", "/tmp/b.mp3"]
    window.playlist_view.refresh()
    qtbot.waitUntil(lambda: window.playlist_view._tree.topLevelItemCount() == 2, timeout=2000)
    window.playlist_view._select_indices([1])

    mock_cls, _ = _mock_time_limit_dialog(15.0)
    with patch("ui_qt.main_window.TimeLimitDialogQt", mock_cls):
        window._on_play_for_time_menu()

    assert window.state.play_limits["/tmp/b.mp3"] == 15.0


def test_open_about_shows_dialog(window):
    with patch("ui_qt.main_window.AboutWindowQt") as mock_cls:
        window._on_open_about()
    mock_cls.assert_called_once_with(window, window.theme.palette)
    mock_cls.return_value.show.assert_called_once()
