import unittest
from unittest.mock import Mock, MagicMock, patch
from audio.audio_player import AudioPlayer


class TestAudioPlayer(unittest.TestCase):
    """Unit tests for the AudioPlayer class."""

    @patch('audio.audio_player.vlc.Instance')
    def test_initialization(self, mock_vlc_instance):
        """Test that AudioPlayer initializes correctly."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player

        player = AudioPlayer()

        self.assertIsNotNone(player.instance)
        self.assertIsNotNone(player.player)
        mock_vlc_instance.assert_called_once()
        mock_instance.media_player_new.assert_called_once()

    @patch('audio.audio_player.vlc.Instance')
    def test_play(self, mock_vlc_instance):
        """Test that play method creates media and starts playback."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_media = MagicMock()

        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player
        mock_instance.media_new.return_value = mock_media

        player = AudioPlayer()
        player.play("/path/to/song.mp3")

        mock_instance.media_new.assert_called_once_with("/path/to/song.mp3")
        mock_player.set_media.assert_called_once_with(mock_media)
        mock_player.play.assert_called_once()

    @patch('audio.audio_player.vlc.Instance')
    def test_pause(self, mock_vlc_instance):
        """Test that pause method calls VLC pause."""
        mock_instance = MagicMock()
        mock_player = MagicMock()

        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player

        player = AudioPlayer()
        player.pause()

        mock_player.pause.assert_called_once()

    @patch('audio.audio_player.vlc.Instance')
    def test_stop(self, mock_vlc_instance):
        """Test that stop method calls VLC stop."""
        mock_instance = MagicMock()
        mock_player = MagicMock()

        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player

        player = AudioPlayer()
        player.stop()

        mock_player.stop.assert_called_once()

    @patch('audio.audio_player.vlc.Instance')
    def test_set_volume(self, mock_vlc_instance):
        """Test that set_volume method sets VLC volume."""
        mock_instance = MagicMock()
        mock_player = MagicMock()

        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player

        player = AudioPlayer()
        player.set_volume(75)

        mock_player.audio_set_volume.assert_called_once_with(75)

    @patch('audio.audio_player.vlc.Instance')
    def test_track_end_callback(self, mock_vlc_instance):
        """Test that track end callback is invoked."""
        mock_instance = MagicMock()
        mock_player = MagicMock()

        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player

        callback = Mock()
        player = AudioPlayer(on_track_end=callback)

        # Simulate track end event
        player._on_end(None)

        callback.assert_called_once()

    @patch('audio.audio_player.vlc.Instance')
    def test_get_time(self, mock_vlc_instance):
        """Test that get_time method returns current playback position."""
        mock_instance = MagicMock()
        mock_player = MagicMock()

        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player
        mock_player.get_time.return_value = 5000  # 5 seconds in milliseconds

        player = AudioPlayer()
        time = player.get_time()

        self.assertEqual(time, 5000)
        mock_player.get_time.assert_called_once()

    @patch('audio.audio_player.vlc.Instance')
    def test_get_time_with_none(self, mock_vlc_instance):
        """Test that get_time handles None return value."""
        mock_instance = MagicMock()
        mock_player = MagicMock()

        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player
        mock_player.get_time.return_value = None

        player = AudioPlayer()
        time = player.get_time()

        self.assertEqual(time, 0)

    @patch('audio.audio_player.vlc.Instance')
    def test_get_length(self, mock_vlc_instance):
        """Test that get_length method returns track length."""
        mock_instance = MagicMock()
        mock_player = MagicMock()

        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player
        mock_player.get_length.return_value = 180000  # 3 minutes in milliseconds

        player = AudioPlayer()
        length = player.get_length()

        self.assertEqual(length, 180000)
        mock_player.get_length.assert_called_once()

    @patch('audio.audio_player.vlc.Instance')
    def test_get_length_with_none(self, mock_vlc_instance):
        """Test that get_length handles None return value."""
        mock_instance = MagicMock()
        mock_player = MagicMock()

        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player
        mock_player.get_length.return_value = None

        player = AudioPlayer()
        length = player.get_length()

        self.assertEqual(length, 0)

    @patch('audio.audio_player.vlc.Instance')
    def test_is_playing_true(self, mock_vlc_instance):
        """Test that is_playing returns True when playing."""
        mock_instance = MagicMock()
        mock_player = MagicMock()

        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player
        mock_player.is_playing.return_value = 1  # VLC returns 1 for True

        player = AudioPlayer()
        is_playing = player.is_playing()

        self.assertTrue(is_playing)
        mock_player.is_playing.assert_called_once()

    @patch('audio.audio_player.vlc.Instance')
    def test_is_playing_false(self, mock_vlc_instance):
        """Test that is_playing returns False when not playing."""
        mock_instance = MagicMock()
        mock_player = MagicMock()

        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player
        mock_player.is_playing.return_value = 0  # VLC returns 0 for False

        player = AudioPlayer()
        is_playing = player.is_playing()

        self.assertFalse(is_playing)


if __name__ == '__main__':
    unittest.main()
