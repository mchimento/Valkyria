import unittest
from unittest.mock import Mock, MagicMock, patch
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


if __name__ == '__main__':
    unittest.main()
