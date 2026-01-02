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

    @patch('sounddevice.query_devices')
    @patch('sounddevice.default')
    def test_get_audio_devices_empty(self, mock_default, mock_query_devices):
        """Test get_audio_devices returns default when no devices found."""
        mock_default.device = [0, 0]
        mock_query_devices.return_value = []

        player = AudioPlayer()
        devices = player.get_audio_devices()

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0][0], '__DEFAULT__')
        self.assertEqual(devices[0][1], 'Default Audio Device')

    @patch('sounddevice.query_devices')
    @patch('sounddevice.default')
    def test_get_audio_devices_with_devices(self, mock_default, mock_query_devices):
        """Test get_audio_devices properly enumerates available devices."""
        mock_default.device = [0, 0]
        mock_query_devices.return_value = [
            {'name': 'Default Device', 'max_output_channels': 2, 'hostapi': 0}
        ]

        player = AudioPlayer()
        devices = player.get_audio_devices()

        self.assertEqual(len(devices), 2)  # Default + one device
        self.assertEqual(devices[0][0], '__DEFAULT__')
        self.assertEqual(devices[0][1], 'Default Audio Device')
        self.assertEqual(devices[1][1], 'Default Device')

    @patch('sounddevice.query_devices')
    @patch('sounddevice.default')
    def test_get_audio_devices_multiple(self, mock_default, mock_query_devices):
        """Test get_audio_devices with multiple devices."""
        mock_default.device = [0, 0]
        mock_query_devices.return_value = [
            {'name': 'Default Device', 'max_output_channels': 2, 'hostapi': 0},
            {'name': 'Speakers', 'max_output_channels': 2, 'hostapi': 0}
        ]

        player = AudioPlayer()
        devices = player.get_audio_devices()

        self.assertEqual(len(devices), 3)  # Default + two devices
        self.assertEqual(devices[0][0], '__DEFAULT__')
        self.assertEqual(devices[0][1], 'Default Audio Device')
        self.assertEqual(devices[1][1], 'Default Device')
        self.assertEqual(devices[2][1], 'Speakers')

    @patch('sounddevice.query_devices')
    @patch('sounddevice.default')
    def test_get_audio_devices_bytes_decoding(self, mock_default, mock_query_devices):
        """Test get_audio_devices properly decodes bytes to strings."""
        mock_default.device = [0, 0]
        mock_query_devices.return_value = [
            {'name': b'Headphones', 'max_output_channels': 2, 'hostapi': 0}
        ]

        player = AudioPlayer()
        devices = player.get_audio_devices()

        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[1][1], 'Headphones')
        self.assertIsInstance(devices[1][1], str)

    def test_set_audio_device_default(self):
        """Test set_audio_device with default device."""
        player = AudioPlayer()
        player.set_audio_device('__DEFAULT__')
        self.assertIsNone(player._device_id)

    def test_set_audio_device_specific(self):
        """Test set_audio_device with specific device GUID."""
        device_guid = '1'
        player = AudioPlayer()
        player.set_audio_device(device_guid)
        self.assertEqual(player._device_id, device_guid)

    def test_set_audio_device_error_handling(self):
        """Test set_audio_device handles errors gracefully."""
        player = AudioPlayer()
        # Should not raise
        player.set_audio_device('invalid-device')
        self.assertEqual(player._device_id, 'invalid-device')

    def test_is_paused(self):
        """Test is_paused method."""
        player = AudioPlayer()
        self.assertFalse(player.is_paused())
        player._paused = True
        self.assertTrue(player.is_paused())


if __name__ == '__main__':
    unittest.main()
