"""Tests for ui_qt/waveform_seekbar.py."""
from unittest.mock import MagicMock

import numpy as np
import pytest
import soundfile as sf
from PySide6.QtCore import QPoint, Qt

from ui_qt.waveform_seekbar import WaveformSeekbarQt

PALETTE = {
    "waveform_bg": "#1a1a1a",
    "waveform_played": "#FF6B00",
    "waveform_unplayed": "#404040",
    "waveform_border": "#808080",
}


@pytest.fixture
def mock_player():
    player = MagicMock()
    player.get_time.return_value = 0
    player.get_length.return_value = 3000  # 3s
    return player


@pytest.fixture
def tiny_wav(tmp_path):
    path = tmp_path / "tone.wav"
    sr = 8000
    duration_s = 0.5
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    data = (0.6 * np.sin(2 * np.pi * 440 * t)).astype("float32")
    sf.write(str(path), data, sr)
    return str(path)


def test_paints_without_data(qtbot, mock_player):
    widget = WaveformSeekbarQt(mock_player, PALETTE, width=100, height=40)
    qtbot.addWidget(widget)
    widget.grab()  # forces a paintEvent; must not raise
    assert widget.waveform_data is None


def test_load_waveform_produces_normalized_peaks(qtbot, mock_player, tiny_wav):
    widget = WaveformSeekbarQt(mock_player, PALETTE, width=100, height=40)
    qtbot.addWidget(widget)

    with qtbot.waitSignal(widget.peaks_ready, timeout=5000):
        widget.load_waveform(tiny_wav)

    assert widget.waveform_data is not None
    assert len(widget.waveform_data) == 100
    assert widget.waveform_data.max() == pytest.approx(1.0, abs=1e-6)
    assert widget.waveform_data.min() >= 0.0
    widget.grab()  # painting real bar data must not raise


def test_load_waveform_is_idempotent_for_same_file(qtbot, mock_player, tiny_wav):
    widget = WaveformSeekbarQt(mock_player, PALETTE, width=100, height=40)
    qtbot.addWidget(widget)
    with qtbot.waitSignal(widget.peaks_ready, timeout=5000):
        widget.load_waveform(tiny_wav)
    first = widget.waveform_data
    widget.load_waveform(tiny_wav)  # should no-op, not spawn a second decode
    assert widget.waveform_data is first


def test_seek_calls_player_set_time(qtbot, mock_player):
    widget = WaveformSeekbarQt(mock_player, PALETTE, width=100, height=40)
    qtbot.addWidget(widget)

    qtbot.mousePress(widget, Qt.LeftButton, pos=QPoint(10, 20))
    qtbot.mouseRelease(widget, Qt.LeftButton, pos=QPoint(50, 20))

    assert mock_player.set_time.called
    (target_ms,), _ = mock_player.set_time.call_args
    # 50/100 of the mocked 3000ms length
    assert target_ms == pytest.approx(1500, abs=50)


def test_clear_resets_state(qtbot, mock_player, tiny_wav):
    widget = WaveformSeekbarQt(mock_player, PALETTE, width=100, height=40)
    qtbot.addWidget(widget)
    with qtbot.waitSignal(widget.peaks_ready, timeout=5000):
        widget.load_waveform(tiny_wav)

    widget.clear()

    assert widget.waveform_data is None
    assert widget.current_file is None
    assert widget.playhead_x == 0


def test_apply_palette_updates_colors_and_repaints(qtbot, mock_player):
    widget = WaveformSeekbarQt(mock_player, PALETTE, width=100, height=40)
    qtbot.addWidget(widget)

    new_palette = {
        "waveform_bg": "#111111",
        "waveform_played": "#222222",
        "waveform_unplayed": "#333333",
        "waveform_border": "#444444",
    }
    widget.apply_palette(new_palette)

    assert widget.bg_color == "#111111"
    assert widget.played_color == "#222222"
    assert widget.unplayed_color == "#333333"
    assert widget.border_color == "#444444"
    widget.grab()  # must not raise
