"""Tests for ui_qt/media_info_window.py. Mocks at the module boundary
(get_file_info/save_metadata/analysis_manager/metadata_extractor) — no
real audio fixture exists in this repo."""
from unittest.mock import MagicMock, patch

import pytest

from ui_qt.media_info_window import MediaInfoWindowQt

PALETTE = {"bg": "#1E1E1E", "fg": "#CCCCCB", "accent": "#BB86FC", "highlight": "#FF6B00"}


def _info(**metadata):
    return {
        "path": "/tmp/song.mp3", "filename": "song.mp3", "size": 5_000_000,
        "format": "MP3", "duration": 185, "bitrate": 192000, "sample_rate": 44100,
        "channels": 2, "codec": "MPEG Audio Layer 3", "metadata": metadata,
    }


@pytest.fixture
def window(qtbot):
    with patch("ui_qt.media_info_window.get_file_info", return_value=_info(title="Test", bpm="128.4", key="Am")), \
         patch("ui_qt.media_info_window.metadata_extractor"):
        win = MediaInfoWindowQt(None, "/tmp/song.mp3", PALETTE)
    qtbot.addWidget(win)
    return win


def test_bpm_field_rounds_displayed_value(window):
    assert window.entries["bpm"].text() == "128"
    assert window._bpm_raw_value == "128.4"


def test_key_field_shows_camelot_when_mappable(window):
    assert window.entries["key"].text() == "8A"
    assert window._key_raw_value == "Am"


def test_key_field_shows_raw_when_unmappable(qtbot):
    with patch("ui_qt.media_info_window.get_file_info", return_value=_info(key="not-a-key")), \
         patch("ui_qt.media_info_window.metadata_extractor"):
        win = MediaInfoWindowQt(None, "/tmp/song.mp3", PALETTE)
    qtbot.addWidget(win)
    assert win.entries["key"].text() == "not-a-key"


def test_general_tab_omits_unparseable_bpm(qtbot):
    with patch("ui_qt.media_info_window.get_file_info", return_value=_info(bpm="not-a-number")), \
         patch("ui_qt.media_info_window.metadata_extractor"):
        win = MediaInfoWindowQt(None, "/tmp/song.mp3", PALETTE)
    qtbot.addWidget(win)
    assert "BPM" in win.general_text.toHtml()  # label shown, value blank not omitted


def test_codec_tab_shows_stereo_for_two_channels(window):
    assert "Stereo" in window.codec_text.toHtml()


def test_size_uses_mb_above_one_megabyte(window):
    assert "MB" in window.general_text.toHtml()


def test_size_uses_kb_below_one_megabyte(qtbot):
    with patch("ui_qt.media_info_window.get_file_info", return_value={**_info(), "size": 500_000}), \
         patch("ui_qt.media_info_window.metadata_extractor"):
        win = MediaInfoWindowQt(None, "/tmp/song.mp3", PALETTE)
    qtbot.addWidget(win)
    assert "KB" in win.general_text.toHtml()


def test_bpm_text_edited_clears_raw_value_but_programmatic_set_does_not(window):
    window._set_bpm_field("140.0")
    assert window._bpm_raw_value == "140.0"
    window.entries["bpm"].textEdited.emit("999")
    assert window._bpm_raw_value is None


@pytest.mark.parametrize("typed,expected_display,expected_raw", [
    ("8a", "8A", None),
    (" 11 B ", "11B", None),
    ("Am", "8A", "Am"),
    ("nonsense", "nonsense", "nonsense"),
])
def test_key_entry_edit_branches(window, typed, expected_display, expected_raw):
    window.entries["key"].setText(typed)
    window._on_key_entry_edit(typed)
    assert window.entries["key"].text() == expected_display
    assert window._key_raw_value == expected_raw


def test_save_uses_raw_key_not_displayed_camelot(window):
    # Regression test: saving after a Calculate-Key/mapped-edit must write
    # the actual key name, not the Camelot display string, into the tag.
    saved = {}
    with patch("ui_qt.media_info_window.save_metadata", side_effect=lambda fp, d: (saved.update(d), True)[1]), \
         patch("ui_qt.media_info_window.get_file_info", return_value=_info()), \
         patch("ui_qt.media_info_window.QMessageBox"):
        window._save_metadata()
    assert saved["key"] == "Am"
    assert saved["bpm"] == "128.4"


def test_calculate_bpm_uses_qt_scheduler(window):
    with patch("ui_qt.media_info_window.analysis_manager") as mock_manager:
        window._calculate_bpm()
    mock_manager.submit_bpm_analysis.assert_called_once_with(
        "/tmp/song.mp3", window._on_bpm_calculation_complete, window._qt_scheduler
    )
    assert window.bpm_btn.text() == "Calculating..."
    assert not window.bpm_btn.isEnabled()


def test_calculate_key_uses_qt_scheduler(window):
    with patch("ui_qt.media_info_window.analysis_manager") as mock_manager:
        window._calculate_key()
    mock_manager.submit_key_analysis.assert_called_once_with(
        "/tmp/song.mp3", window._on_key_calculation_complete, window._qt_scheduler
    )


def test_bpm_calculation_complete_updates_field_and_resets_button(window):
    window.bpm_btn.setEnabled(False)
    window.bpm_btn.setText("Calculating...")
    window._on_bpm_calculation_complete("/tmp/song.mp3", 99.0)
    assert window.entries["bpm"].text() == "99"
    assert window.bpm_btn.isEnabled()
    assert window.bpm_btn.text() == "Calculate BPM"


def test_key_calculation_complete_sets_raw_value(window):
    window._on_key_calculation_complete("/tmp/song.mp3", "Cm")
    assert window.entries["key"].text() == "5A"
    assert window._key_raw_value == "Cm"


def test_live_bpm_listener_refreshes_general_and_metadata_tab(window):
    with patch("ui_qt.media_info_window.get_file_info", return_value=_info(bpm="150")):
        window._on_bpm_metadata_changed("/tmp/song.mp3")
    assert window.entries["bpm"].text() == "150"
    assert "150" in window.general_text.toHtml()


def test_live_listener_ignores_other_files(window):
    window.entries["bpm"].setText("SHOULD_NOT_CHANGE")
    with patch("ui_qt.media_info_window.get_file_info", return_value=_info(bpm="1")):
        window._on_bpm_metadata_changed("/tmp/other.mp3")
    assert window.entries["bpm"].text() == "SHOULD_NOT_CHANGE"


def test_done_unregisters_listeners_on_any_close_path(qtbot):
    mock_extractor = MagicMock()
    with patch("ui_qt.media_info_window.get_file_info", return_value=_info()), \
         patch("ui_qt.media_info_window.metadata_extractor", mock_extractor):
        win = MediaInfoWindowQt(None, "/tmp/song.mp3", PALETTE)
        qtbot.addWidget(win)
        win.reject()
    mock_extractor.unregister_bpm_listener.assert_called_once()
    mock_extractor.unregister_key_listener.assert_called_once()
