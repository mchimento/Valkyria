"""Tests for audio device enumeration and switching functionality."""
import unittest
import logging
from unittest.mock import Mock, MagicMock, patch
from audio.audio_player import AudioPlayer

# Suppress logging during tests
logging.disable(logging.CRITICAL)


class TestAudioDevices(unittest.TestCase):
    """Unit tests for audio device management in AudioPlayer."""

    @classmethod
    def setUpClass(cls):
        """Suppress logging for all tests in this class."""
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        """Re-enable logging after tests."""
        logging.disable(logging.NOTSET)

    @patch('audio.audio_player.vlc.Instance')
    def test_get_audio_devices_empty(self, mock_vlc_instance):
        """Test get_audio_devices returns default when no devices found."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player
        mock_player.audio_output_device_enum.return_value = None

        player = AudioPlayer()
        devices = player.get_audio_devices()

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0][0], '__DEFAULT__')
        self.assertEqual(devices[0][1], 'Default Audio Device')

    @patch('audio.audio_player.vlc.Instance')
    def test_get_audio_devices_with_devices(self, mock_vlc_instance):
        """Test get_audio_devices properly enumerates available devices."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player

        # Create mock device list
        device1_content = MagicMock()
        device1_content.description = 'Default'
        device1_content.device = ''
        device1_content.next = None

        device1 = MagicMock()
        device1.contents = device1_content

        mock_player.audio_output_device_enum.return_value = device1

        player = AudioPlayer()
        devices = player.get_audio_devices()

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0][0], '__DEFAULT__')
        self.assertEqual(devices[0][1], 'Default')

    @patch('audio.audio_player.vlc.Instance')
    def test_get_audio_devices_multiple(self, mock_vlc_instance):
        """Test get_audio_devices with multiple devices."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player

        # Create mock device chain
        device2_content = MagicMock()
        device2_content.description = 'Speakers'
        device2_content.device = '{0.0.0}.{speaker-guid}'
        device2_content.next = None

        device2 = MagicMock()
        device2.contents = device2_content

        device1_content = MagicMock()
        device1_content.description = 'Default'
        device1_content.device = ''
        device1_content.next = device2

        device1 = MagicMock()
        device1.contents = device1_content

        mock_player.audio_output_device_enum.return_value = device1

        player = AudioPlayer()
        devices = player.get_audio_devices()

        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[0][0], '__DEFAULT__')
        self.assertEqual(devices[0][1], 'Default')
        self.assertEqual(devices[1][0], '{0.0.0}.{speaker-guid}')
        self.assertEqual(devices[1][1], 'Speakers')

    @patch('audio.audio_player.vlc.Instance')
    def test_get_audio_devices_bytes_decoding(self, mock_vlc_instance):
        """Test get_audio_devices properly decodes bytes to strings."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player

        device_content = MagicMock()
        device_content.description = b'Headphones'
        device_content.device = b'{0.0.0}.{headphone-guid}'
        device_content.next = None

        device = MagicMock()
        device.contents = device_content

        mock_player.audio_output_device_enum.return_value = device

        player = AudioPlayer()
        devices = player.get_audio_devices()

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0][0], '{0.0.0}.{headphone-guid}')
        self.assertEqual(devices[0][1], 'Headphones')
        self.assertIsInstance(devices[0][0], str)
        self.assertIsInstance(devices[0][1], str)

    @patch('audio.audio_player.vlc.Instance')
    def test_set_audio_device_default(self, mock_vlc_instance):
        """Test set_audio_device with default device."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player

        player = AudioPlayer()
        player.set_audio_device('__DEFAULT__')

        mock_player.audio_output_device_set.assert_called_once_with(None, '')

    @patch('audio.audio_player.vlc.Instance')
    def test_set_audio_device_specific(self, mock_vlc_instance):
        """Test set_audio_device with specific device GUID."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player

        device_guid = '{0.0.0}.{specific-device-guid}'
        player = AudioPlayer()
        player.set_audio_device(device_guid)

        mock_player.audio_output_device_set.assert_called_once_with(None, device_guid)

    @patch('audio.audio_player.vlc.Instance')
    def test_set_audio_device_error_handling(self, mock_vlc_instance):
        """Test set_audio_device handles errors gracefully."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player
        mock_player.audio_output_device_set.side_effect = Exception("Device error")

        player = AudioPlayer()
        # Should not raise, but log error
        player.set_audio_device('{0.0.0}.{invalid-guid}')

        mock_player.audio_output_device_set.assert_called_once()

    @patch('audio.audio_player.vlc.Instance')
    def test_is_paused(self, mock_vlc_instance):
        """Test is_paused method."""
        mock_instance = MagicMock()
        mock_player = MagicMock()
        mock_vlc_instance.return_value = mock_instance
        mock_instance.media_player_new.return_value = mock_player

        import vlc
        mock_player.get_state.return_value = vlc.State.Paused

        player = AudioPlayer()
        self.assertTrue(player.is_paused())

        mock_player.get_state.return_value = vlc.State.Playing
        self.assertFalse(player.is_paused())


if __name__ == '__main__':
    unittest.main()
