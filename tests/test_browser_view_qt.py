"""Tests for ui_qt/browser_view.py."""
import logging
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QLabel

from app.state import AppState
import ui_qt.browser_view as browser_view_module
from ui_qt.browser_view import BrowserViewQt
from ui_qt.playlist_view import PlaylistViewQt

logging.disable(logging.CRITICAL)  # get_metadata logs errors for the fake paths used below


@pytest.fixture
def mock_preview_player(monkeypatch):
    player = MagicMock()
    monkeypatch.setattr(browser_view_module, "AudioPlayer", MagicMock(return_value=player))
    return player


@pytest.fixture
def state():
    return AppState(browser_files=["/tmp/a.mp3", "/tmp/b.mp3"])


@pytest.fixture
def settings():
    s = MagicMock()
    s.supported_extensions = (".mp3", ".wav")
    return s


@pytest.fixture
def main_player():
    # Two distinct sound cards, so tests can exercise more than "nothing available".
    player = MagicMock()
    player.get_audio_devices.return_value = [
        ("__DEFAULT__", "Default Audio Device"),
        ("0", "HDA Intel PCH: Analog (hw:0,0)"),
        ("1", "HDA Intel HDMI: 0 (hw:1,3)"),
        ("2", "sysdefault"),
    ]
    player._device_id = None  # main player using the system default (card 0)
    return player


@pytest.fixture
def view(qtbot, state, settings, mock_preview_player, main_player):
    v = BrowserViewQt(state, settings, player=main_player)
    qtbot.addWidget(v)
    return v


def test_header_label_text(view):
    header = view.findChild(QLabel, "PanelHeader")
    assert header is not None
    assert header.text() == "Browser"


def test_refresh_populates_rows(view, state):
    assert view._tree.topLevelItemCount() == len(state.browser_files)
    assert view._tree.topLevelItem(0).data(0, Qt.UserRole) == "/tmp/a.mp3"
    assert view._tree.topLevelItem(0).text(0) == "a.mp3"


def test_open_folder_walks_and_filters_extensions(view, state, settings, tmp_path):
    (tmp_path / "song.mp3").write_bytes(b"")
    (tmp_path / "notes.txt").write_bytes(b"")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "track.wav").write_bytes(b"")

    with patch.object(QFileDialog, "getExistingDirectory", return_value=str(tmp_path)):
        view._on_open_folder()

    assert sorted(state.browser_files) == sorted([str(tmp_path / "song.mp3"), str(sub / "track.wav")])
    assert view._tree.topLevelItemCount() == 2


def test_open_folder_cancelled_leaves_state_unchanged(view, state):
    original = list(state.browser_files)
    with patch.object(QFileDialog, "getExistingDirectory", return_value=""):
        view._on_open_folder()
    assert state.browser_files == original


def test_open_files_sets_browser_files(view, state):
    with patch.object(QFileDialog, "getOpenFileNames", return_value=(["/x/one.mp3", "/x/two.mp3"], "")):
        view._on_open_files()
    assert state.browser_files == ["/x/one.mp3", "/x/two.mp3"]
    assert view._tree.topLevelItemCount() == 2


def test_preview_play_dispatches_to_player(qtbot, view, mock_preview_player):
    item = view._tree.topLevelItem(0)
    view._tree.setCurrentItem(item)
    view._on_preview_play_clicked()

    qtbot.waitUntil(lambda: mock_preview_player.play.called, timeout=1000)
    assert mock_preview_player.play.call_args[0][0] == "/tmp/a.mp3"
    assert view._current_preview_path == "/tmp/a.mp3"


def test_preview_stop_dispatches_to_player(qtbot, view, mock_preview_player):
    view._preview_play("/tmp/a.mp3")
    view._preview_stop()

    qtbot.waitUntil(lambda: mock_preview_player.stop.called, timeout=1000)
    assert view._current_preview_path is None


def test_double_click_toggles_preview(qtbot, view, mock_preview_player):
    item = view._tree.topLevelItem(0)

    view._on_double_clicked(item, 0)
    qtbot.waitUntil(lambda: mock_preview_player.play.called, timeout=1000)
    assert view._current_preview_path == "/tmp/a.mp3"

    view._on_double_clicked(item, 0)  # same path again -> stop
    qtbot.waitUntil(lambda: mock_preview_player.stop.called, timeout=1000)
    assert view._current_preview_path is None


def test_preview_ended_clears_current_path(view):
    view._current_preview_path = "/tmp/a.mp3"
    view._on_preview_ended()
    assert view._current_preview_path is None


def test_shutdown_stops_preview_player(view, mock_preview_player):
    view.shutdown()
    assert mock_preview_player.stop.called


def test_tree_mimedata_carries_selected_file_urls(view):
    view._tree.topLevelItem(0).setSelected(True)
    view._tree.topLevelItem(1).setSelected(True)
    mime = view._tree.mimeData(view._tree.selectedItems())
    urls = [url.toLocalFile() for url in mime.urls()]
    assert sorted(urls) == ["/tmp/a.mp3", "/tmp/b.mp3"]


def test_tree_mimedata_also_carries_internal_move_format(view):
    """Regression test: an earlier version built mimeData from scratch
    (just text/uri-list), which meant dragging within the browser to
    reorder did nothing at all — QAbstractItemView's default drop handling
    needs application/x-qabstractitemmodeldatalist to recognize an
    internal row move. Confirmed via mime.formats() before/after the fix."""
    item = view._tree.topLevelItem(0)
    mime = view._tree.mimeData([item])
    assert "application/x-qabstractitemmodeldatalist" in mime.formats()
    assert "text/uri-list" in mime.formats()


def test_items_are_not_drop_enabled_to_prevent_accidental_nesting(view):
    for i in range(view._tree.topLevelItemCount()):
        item = view._tree.topLevelItem(i)
        assert not (item.flags() & Qt.ItemIsDropEnabled)


def test_internal_reorder_resyncs_browser_files(view, state):
    # Simulates the visual move Qt's real drag-drop would perform.
    item_b = view._tree.takeTopLevelItem(1)
    view._tree.insertTopLevelItem(0, item_b)

    view._resync_from_internal_move()

    assert state.browser_files == ["/tmp/b.mp3", "/tmp/a.mp3"]


# ---------- Add / Add Below (need a real PlaylistViewQt to insert into) ----------

PALETTE = {"highlight": "#FFF59D"}


@pytest.fixture
def playlist_state():
    return AppState(playlist=["/tmp/x.mp3", "/tmp/y.mp3"])


@pytest.fixture
def playlist_view(qtbot, playlist_state):
    pv = PlaylistViewQt(playlist_state, PALETTE)
    qtbot.addWidget(pv)
    return pv


@pytest.fixture
def linked_view(qtbot, settings, mock_preview_player, playlist_state, playlist_view):
    # Deliberately reuse playlist_state as the browser's own state too,
    # matching how MainWindowQt wires both views to the same AppState.
    playlist_state.browser_files = ["/tmp/a.mp3", "/tmp/b.mp3"]
    v = BrowserViewQt(playlist_state, settings, playlist_view=playlist_view)
    qtbot.addWidget(v)
    return v


def test_add_appends_selected_to_end_of_playlist(linked_view, playlist_state):
    linked_view._tree.topLevelItem(1).setSelected(True)  # b.mp3
    linked_view._on_add_to_playlist()
    assert playlist_state.playlist == ["/tmp/x.mp3", "/tmp/y.mp3", "/tmp/b.mp3"]


def test_add_below_inserts_after_playlist_selection(linked_view, playlist_state, playlist_view):
    playlist_view._select_indices([0])  # x.mp3 selected in the playlist
    linked_view._tree.topLevelItem(0).setSelected(True)  # a.mp3 in browser
    linked_view._on_add_below_to_playlist()
    assert playlist_state.playlist == ["/tmp/x.mp3", "/tmp/a.mp3", "/tmp/y.mp3"]


def test_add_below_falls_back_to_after_current_track(linked_view, playlist_state):
    playlist_state.current_index = 0  # x.mp3 playing, nothing selected in playlist
    linked_view._tree.topLevelItem(0).setSelected(True)  # a.mp3
    linked_view._on_add_below_to_playlist()
    assert playlist_state.playlist == ["/tmp/x.mp3", "/tmp/a.mp3", "/tmp/y.mp3"]


def test_add_with_no_selection_does_nothing(linked_view, playlist_state):
    linked_view._on_add_to_playlist()
    assert playlist_state.playlist == ["/tmp/x.mp3", "/tmp/y.mp3"]


def test_add_without_playlist_view_does_not_raise(qtbot, settings, mock_preview_player):
    state = AppState(browser_files=["/tmp/a.mp3"])
    v = BrowserViewQt(state, settings)  # no playlist_view
    qtbot.addWidget(v)
    v._tree.topLevelItem(0).setSelected(True)
    v._on_add_to_playlist()  # must not raise


# ---------- preview output device ----------

def test_no_main_player_has_no_preview_devices(state, settings, mock_preview_player):
    v = BrowserViewQt(state, settings)  # no player
    assert v.preview_device_combo.count() == 1
    assert v.preview_device_combo.currentText() == "No device available"
    assert not v.preview_device_combo.isEnabled()
    assert not v.btn_preview_play.isEnabled()


def test_main_player_device_excluded_from_preview_list(qtbot, state, settings, mock_preview_player):
    main_player = MagicMock()
    main_player.get_audio_devices.return_value = [
        ("__DEFAULT__", "Default"),
        ("0", "HDA Intel PCH: Analog (hw:0,0)"),
        ("1", "HDA Intel HDMI: 0 (hw:1,3)"),
        ("2", "sysdefault"),
    ]
    main_player._device_id = "0"  # main player pinned directly to card 0

    v = BrowserViewQt(state, settings, player=main_player)
    qtbot.addWidget(v)

    names = [v.preview_device_combo.itemText(i) for i in range(v.preview_device_combo.count())]
    assert "HDA Intel PCH: Analog (hw:0,0)" not in names
    assert "Default" not in names
    assert "sysdefault" not in names
    assert "HDA Intel HDMI: 0 (hw:1,3)" in names


def test_main_player_on_secondary_card_reoffers_default(qtbot, state, settings, mock_preview_player):
    # Default resolves to the primary card, so it's real separation when main is on a secondary card.
    main_player = MagicMock()
    main_player.get_audio_devices.return_value = [
        ("__DEFAULT__", "Default"),
        ("0", "HDA Intel PCH: Analog (hw:0,0)"),
        ("1", "HDA Intel HDMI: 0 (hw:1,3)"),
        ("2", "sysdefault"),
    ]
    main_player._device_id = "1"  # main player pinned to the secondary card (1)

    v = BrowserViewQt(state, settings, player=main_player)
    qtbot.addWidget(v)

    names = [v.preview_device_combo.itemText(i) for i in range(v.preview_device_combo.count())]
    assert "Default" in names
    assert "HDA Intel PCH: Analog (hw:0,0)" in names
    assert "sysdefault" not in names
    assert "HDA Intel HDMI: 0 (hw:1,3)" not in names


def test_main_player_on_bluetooth_default_reoffers_laptop_speakers(qtbot, state, settings, mock_preview_player):
    # Regression test: a non-ALSA default (Bluetooth) must not wrongly exclude real hw: devices.
    main_player = MagicMock()
    main_player.get_audio_devices.return_value = [
        ("__DEFAULT__", "Default Audio Device"),
        ("0", "HDA Intel PCH: Analog (hw:0,0)"),
        ("1", "HDA Intel HDMI: 0 (hw:1,3)"),
        ("2", "sysdefault"),
    ]
    main_player._device_id = None  # main uses Default, which is now Bluetooth
    main_player.get_default_output_info.return_value = (None, "TWS-D2500")

    v = BrowserViewQt(state, settings, player=main_player)
    qtbot.addWidget(v)

    names = [v.preview_device_combo.itemText(i) for i in range(v.preview_device_combo.count())]
    assert "HDA Intel PCH: Analog (hw:0,0)" in names
    assert "HDA Intel HDMI: 0 (hw:1,3)" in names
    assert "Default Audio Device" not in names


def test_default_entry_shows_live_bluetooth_name_when_offered(qtbot, state, settings, mock_preview_player):
    # Label should show what Default currently resolves to, same as the Tools menu.
    main_player = MagicMock()
    main_player.get_audio_devices.return_value = [
        ("__DEFAULT__", "Default Audio Device"),
        ("0", "HDA Intel PCH: Analog (hw:0,0)"),
        ("1", "HDA Intel HDMI: 0 (hw:1,3)"),
    ]
    main_player._device_id = "1"  # main pinned to HDMI, not Default
    main_player.get_default_output_info.return_value = (None, "TWS-D2500")

    v = BrowserViewQt(state, settings, player=main_player)
    qtbot.addWidget(v)

    names = [v.preview_device_combo.itemText(i) for i in range(v.preview_device_combo.count())]
    assert "Default Audio Device (currently: TWS-D2500)" in names
    assert "sysdefault" not in names


def test_preview_play_sets_resolved_device_before_playing(qtbot, state, settings, mock_preview_player):
    main_player = MagicMock()
    main_player.get_audio_devices.return_value = [
        ("__DEFAULT__", "Default"),
        ("0", "HDA Intel PCH: Analog (hw:0,0)"),
        ("1", "HDA Intel HDMI: 0 (hw:1,3)"),
    ]
    main_player._device_id = None  # main player using the system default (card 0)

    v = BrowserViewQt(state, settings, player=main_player)
    qtbot.addWidget(v)
    v.preview_device_combo.setCurrentText("HDA Intel HDMI: 0 (hw:1,3)")

    v._tree.setCurrentItem(v._tree.topLevelItem(0))
    v._on_preview_play_clicked()

    qtbot.waitUntil(lambda: mock_preview_player.play.called, timeout=1000)
    assert mock_preview_player.set_audio_device.call_args[0][0] == "1"


def test_changing_device_while_previewing_stops_it(qtbot, view, mock_preview_player):
    view._preview_play("/tmp/a.mp3")
    assert view._current_preview_path == "/tmp/a.mp3"

    view._on_preview_device_changed("Default")

    qtbot.waitUntil(lambda: mock_preview_player.stop.called, timeout=1000)
    assert view._current_preview_path is None


def test_refresh_preview_devices_public_entry_point(view, mock_preview_player):
    view.refresh_preview_devices()  # must not raise
    assert view.preview_device_combo.count() >= 1
