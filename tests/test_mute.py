"""Tests for mute functionality."""
import unittest
import logging
from unittest.mock import Mock, MagicMock, patch
from audio.audio_player import AudioPlayer
from app.settings import Settings

# Suppress logging during tests
logging.disable(logging.CRITICAL)


class TestMuteAudio(unittest.TestCase):
    """Unit tests for mute functionality in AudioPlayer."""

    @classmethod
    def setUpClass(cls):
        """Suppress logging for all tests in this class."""
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        """Re-enable logging after tests."""
        logging.disable(logging.NOTSET)

    @patch('audio.audio_player.vlc.Instance')
    def test_get_mute_state_false(self, mock_vlc_instance):
        """Test get_mute_state returns False when not muted."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player
        mock_player.audio_get_mute.return_value = 0  # Not muted

        player = AudioPlayer()
        self.assertFalse(player.get_mute_state())

    @patch('audio.audio_player.vlc.Instance')
    def test_get_mute_state_true(self, mock_vlc_instance):
        """Test get_mute_state returns True when muted."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player
        mock_player.audio_get_mute.return_value = 1  # Muted

        player = AudioPlayer()
        self.assertTrue(player.get_mute_state())

    @patch('audio.audio_player.vlc.Instance')
    def test_set_mute_true(self, mock_vlc_instance):
        """Test set_mute with mute=True."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player

        player = AudioPlayer()
        player.set_mute(True)

        mock_player.audio_set_mute.assert_called_once_with(1)

    @patch('audio.audio_player.vlc.Instance')
    def test_set_mute_false(self, mock_vlc_instance):
        """Test set_mute with mute=False."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player

        player = AudioPlayer()
        player.set_mute(False)

        mock_player.audio_set_mute.assert_called_once_with(0)

    @patch('audio.audio_player.vlc.Instance')
    def test_set_mute_error_handling(self, mock_vlc_instance):
        """Test set_mute handles errors gracefully."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player
        mock_player.audio_set_mute.side_effect = Exception("Mute error")

        player = AudioPlayer()
        # Should not raise, but log error
        player.set_mute(True)

        mock_player.audio_set_mute.assert_called_once()

    @patch('audio.audio_player.vlc.Instance')
    def test_get_mute_state_error_handling(self, mock_vlc_instance):
        """Test get_mute_state handles errors gracefully."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player
        mock_player.audio_get_mute.side_effect = Exception("Get mute error")

        player = AudioPlayer()
        # Should return False on error
        self.assertFalse(player.get_mute_state())


class TestMuteSettings(unittest.TestCase):
    """Unit tests for mute settings persistence."""

    def test_mute_property_default(self):
        """Test mute property defaults to False."""
        settings = Settings()
        self.assertFalse(settings.mute)

    def test_mute_property_set(self):
        """Test mute property can be set."""
        settings = Settings()
        settings.mute = True
        self.assertTrue(settings.mute)

    def test_mute_in_save_data(self):
        """Test mute is included in saved data."""
        import tempfile
        import json
        from pathlib import Path

        # Create temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config.json'

            # Patch the settings path
            with patch('app.settings.get_user_data_path', return_value=Path(tmpdir)):
                settings = Settings()
                settings.mute = True
                settings.save()

                # Verify file exists and contains mute setting
                self.assertTrue(config_path.exists())
                with open(config_path, 'r') as f:
                    data = json.load(f)
                self.assertIn('mute', data)
                self.assertTrue(data['mute'])

    def test_mute_loads_from_file(self):
        """Test mute setting loads from saved file."""
        import tempfile
        import json
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / 'config.json'

            # Write config file with mute=True
            config_data = {
                "theme": "light",
                "window_geometry": None,
                "volume": 80,
                "mute": True
            }
            with open(config_path, 'w') as f:
                json.dump(config_data, f)

            # Patch and load
            with patch('app.settings.get_user_data_path', return_value=Path(tmpdir)):
                settings = Settings()
                self.assertTrue(settings.mute)


if __name__ == '__main__':
    unittest.main()
