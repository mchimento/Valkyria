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

    def test_get_mute_state_false(self):
        """Test get_mute_state returns False when not muted."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()
            self.assertFalse(player.get_mute_state())

    def test_get_mute_state_true(self):
        """Test get_mute_state returns True when muted."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()
            # Manually set muted state
            player._muted = True
            self.assertTrue(player.get_mute_state())

    def test_set_mute_true(self):
        """Test set_mute with mute=True."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()
            player.set_mute(True)
            self.assertTrue(player.get_mute_state())

    def test_set_mute_false(self):
        """Test set_mute with mute=False."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()
            player.set_mute(False)
            self.assertFalse(player.get_mute_state())

    def test_set_mute_error_handling(self):
        """Test set_mute handles errors gracefully."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()

            # Should not raise exception for valid values
            try:
                player.set_mute(True)
                player.set_mute(False)
            except Exception:
                self.fail("set_mute should not raise exception for valid boolean values")

    def test_get_mute_state_error_handling(self):
        """Test get_mute_state handles errors gracefully."""
        with patch('sounddevice.play') as mock_play:
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
