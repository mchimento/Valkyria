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


if __name__ == '__main__':
    unittest.main()
