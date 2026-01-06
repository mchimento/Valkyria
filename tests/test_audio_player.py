import unittest
from unittest.mock import Mock, MagicMock, patch
import numpy as np
from audio.audio_player import AudioPlayer

class TestAudioPlayer(unittest.TestCase):
    """Unit tests for AudioPlayer class."""

    def test_initialization(self):
        """Test that AudioPlayer initializes correctly."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()  # Don't pass path to avoid file opening
            self.assertIsNone(player._buffer)  # _buffer is None until play() is called
            self.assertFalse(player._muted)
            self.assertFalse(player._paused)
            self.assertFalse(player._stopped_manually)

    def test_track_end_callback(self):
        """Test that track end callback is invoked."""
        callback = Mock()
        player = AudioPlayer(on_track_end=callback)

        # Simulate track end event by calling the callback method directly
        player._on_stream_finished()

        callback.assert_called_once()

    def test_pause(self):
        """Test that pause method pauses playback."""
        with patch('sounddevice.play') as mock_play, \
             patch('sounddevice.OutputStream') as mock_stream:
            player = AudioPlayer()
            # Mock the stream
            mock_stream_instance = MagicMock()
            mock_stream.return_value = mock_stream_instance
            player._stream = mock_stream_instance
            player.pause()
            self.assertTrue(player._paused)

    def test_stop(self):
        """Test that stop method stops playback."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()
            player.stop()
            self.assertTrue(player._stopped_manually)
            self.assertIsNone(player._buffer)

    def test_set_volume(self):
        """Test that set_volume method sets volume."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()
            player.set_volume(75)
            self.assertEqual(player._volume, 75)

    def test_get_mute_state(self):
        """Test get_mute_state returns correct state."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()
            # Default should be False
            self.assertFalse(player.get_mute_state())

            # Manually set to True
            player._muted = True
            self.assertTrue(player.get_mute_state())

    def test_set_mute(self):
        """Test set_mute updates state correctly."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()

            player.set_mute(True)
            self.assertTrue(player.get_mute_state())

            player.set_mute(False)
            self.assertFalse(player.get_mute_state())

    def test_cleanup(self):
        """Test that cleanup method properly cleans up audio resources."""
        with patch('sounddevice.play') as mock_play, \
             patch('sounddevice.stop') as mock_sd_stop, \
             patch('sounddevice.OutputStream') as mock_stream_class:

            player = AudioPlayer()

            # Create mock stream and buffer
            mock_stream = MagicMock()
            mock_buffer = MagicMock()

            player._stream = mock_stream
            player._buffer = mock_buffer

            # Call cleanup
            player._cleanup()

            # Verify stream was stopped and closed
            mock_stream.stop.assert_called_once()
            mock_stream.close.assert_called_once()

            # Verify buffer was closed
            mock_buffer.close.assert_called_once()

            # Verify sounddevice.stop was called
            mock_sd_stop.assert_called_once()

            # Verify references were cleared
            self.assertIsNone(player._stream)
            self.assertIsNone(player._buffer)

    def test_cleanup_with_exceptions(self):
        """Test that cleanup handles exceptions gracefully."""
        with patch('sounddevice.play') as mock_play, \
             patch('sounddevice.stop') as mock_sd_stop, \
             patch('sounddevice.OutputStream') as mock_stream_class:

            player = AudioPlayer()

            # Create mock stream and buffer that raise exceptions
            mock_stream = MagicMock()
            mock_stream.stop.side_effect = Exception("Stop failed")
            # Note: close() won't be called if stop() fails due to same try block

            mock_buffer = MagicMock()
            mock_buffer.close.side_effect = Exception("Buffer close failed")

            mock_sd_stop.side_effect = Exception("SD stop failed")

            player._stream = mock_stream
            player._buffer = mock_buffer

            # Call cleanup - should not raise exceptions
            player._cleanup()

            # Verify methods were attempted despite exceptions
            mock_stream.stop.assert_called_once()
            # close() is not called if stop() fails (same try block)
            mock_buffer.close.assert_called_once()
            mock_sd_stop.assert_called_once()

            # Verify references were still cleared
            self.assertIsNone(player._stream)
            self.assertIsNone(player._buffer)


class TestAudioPlayerResample(unittest.TestCase):
    """Tests for the stateful resampler in AudioPlayer."""

    class DummyBuffer:
        def __init__(self, channels=2):
            self.channels = channels
            self.samplerate = 44100
            self.absolute_read_pos = 0
            self.eof = False
            self._offset = 0

        def read(self, frames):
            # Simulate read returning more frames than requested (e.g., due to rate changes)
            # Return 1704 frames of stereo audio (float32) with a slight offset per read
            n = 1704
            data = np.zeros((n, self.channels), dtype="float32")
            # Fill with a simple ramp so values are deterministic and different per read
            for ch in range(self.channels):
                start = -0.5 + (self._offset * 1e-3)
                end = 0.5 + (self._offset * 1e-3)
                data[:, ch] = np.linspace(start, end, n, dtype="float32")
            self._offset += 1
            return data

    def test_stream_callback_resample_does_not_broadcast_error(self):
        player = AudioPlayer()

        # Replace real effects with identity to avoid side-effects or state requirements
        player.effects.process = lambda x: x

        # Attach dummy buffer and set a playback rate that triggers resampling
        player._buffer = self.DummyBuffer(channels=2)
        player._playback_rate = 1.5

        # Create outdata buffer matching a smaller frame request (e.g., 1136 frames)
        frames = 1136
        outdata = np.zeros((frames, 2), dtype="float32")

        # Call the callback - it should not raise
        player._stream_callback(outdata, frames, None, None)

        # Ensure outdata contains non-zero data after processing (resampled/interpolated)
        self.assertFalse(np.allclose(outdata, 0), "outdata appears to be silent after callback")

    def test_resampler_stateful_continuity(self):
        player = AudioPlayer()
        player.effects.process = lambda x: x
        player._buffer = self.DummyBuffer(channels=2)
        player._playback_rate = 1.5

        frames = 1136
        out1 = np.zeros((frames, 2), dtype="float32")
        player._stream_callback(out1, frames, None, None)

        # Capture resampler position after first callback
        pos_after_first = getattr(player, '_resample_pos', None)

        out2 = np.zeros((frames, 2), dtype="float32")
        player._stream_callback(out2, frames, None, None)

        # Ensure both outputs are non-silent and the resampler state is reasonable
        self.assertFalse(np.allclose(out1, 0))
        self.assertFalse(np.allclose(out2, 0))
        self.assertIsNotNone(pos_after_first)
        self.assertGreaterEqual(pos_after_first, 0.0)

        # Resample buffer should not grow unbounded for this use-case
        buf_len = getattr(player, '_resample_buffer', np.zeros((0,))).shape[0]
        self.assertLess(buf_len, 5000)


if __name__ == '__main__':
    unittest.main()
