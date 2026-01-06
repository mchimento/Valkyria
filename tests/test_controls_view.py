"""Tests for ControlsBar view."""
import unittest
import logging
import os
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch
from tkinter import ttk

# Suppress logging during tests
logging.disable(logging.CRITICAL)

from tests.tk_utils import HAS_TK as HAS_DISPLAY

class TestControlsTheme(unittest.TestCase):
    """Unit tests for ControlsBar theme functionality."""

    @classmethod
    def setUpClass(cls):
        """Suppress logging for all tests in this class."""
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        """Re-enable logging after tests."""
        logging.disable(logging.NOTSET)

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def setUp(self):
        """Set up test fixtures."""
        try:
            self.root = tk.Tk()
        except Exception:
            self.skipTest("Tkinter not available in this environment")

        self.mock_player = MagicMock()
        self.mock_state = MagicMock()
        self.mock_state.play_on_double = False

        self.mock_theme = MagicMock()
        self.mock_theme.palette = {
            "button_bg_color": "#123456",
            "button_fg_color": "#ffffff",
            "button_hover": "#654321",
            "accent": "#0078d4",
            "accent_hover": "#106ebe",
            "slider_fg": "#0078d4",
            "slider_bg": "#E0E0E0",
            "slider_hover": "#106ebe",
            "slider_progress": "#0078d4",
            "bg": "#FAFAFA",
            "fg": "#202020"
        }

        self.mock_settings = MagicMock()
        self.mock_settings.volume = 80
        self.mock_settings.mute = False
        self.mock_settings.theme = "light"

        self.mock_tooltip = MagicMock()

    def tearDown(self):
        """Clean up after tests."""
        try:
            if hasattr(self, 'root'):
                self.root.destroy()
        except Exception:
            pass

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_update_theme_no_crash(self):
        """Test that update_theme does not raise TclError."""
        from ui.controls import ControlsBar

        # Initialize ControlsBar
        controls = ControlsBar(
            self.root,
            self.mock_player,
            self.mock_state,
            self.mock_theme,
            playlist=None,
            tooltip_manager=self.mock_tooltip,
            settings=self.mock_settings
        )

        # Verify initial state
        self.assertIsInstance(controls, ttk.Frame)

        # Change theme palette values to simulate a theme switch
        self.mock_theme.palette = {
            "button_bg_color": "#ABCDEF",
            "button_fg_color": "#000000",
            "button_hover": "#FEDCBA",
            "accent": "#0078d4",
            "accent_hover": "#106ebe",
            "slider_fg": "#005a9e",
            "slider_bg": "#2D2D2D",
            "slider_hover": "#0078d4",
            "slider_progress": "#005a9e",
            "bg": "#1E1E1E",
            "fg": "#FFFFFF"
        }

        # Call update_theme - this should NOT raise TclError
        try:
            controls.update_theme()
        except tk.TclError as e:
            self.fail(f"update_theme raised TclError: {e}")
        except Exception as e:
            self.fail(f"update_theme raised unexpected exception: {e}")

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_theme_switch_light_to_dark(self):
        """Test switching from light to dark theme."""
        from ui.controls import ControlsBar

        # Light theme palette
        light_palette = {
            "button_bg_color": "#0078d4",
            "button_fg_color": "#ffffff",
            "button_hover": "#106ebe",
            "accent": "#0078d4",
            "accent_hover": "#106ebe",
            "slider_fg": "#0078d4",
            "slider_bg": "#E0E0E0",
            "slider_hover": "#106ebe",
            "slider_progress": "#0078d4",
            "bg": "#FAFAFA",
            "fg": "#202020"
        }

        self.mock_theme.palette = light_palette.copy()

        # Initialize ControlsBar with light theme
        controls = ControlsBar(
            self.root,
            self.mock_player,
            self.mock_state,
            self.mock_theme,
            playlist=None,
            tooltip_manager=self.mock_tooltip,
            settings=self.mock_settings
        )

        # Verify initial light theme colors
        self.assertEqual(controls.btn_mute.cget('fg_color'), "#0078d4")
        self.assertEqual(controls.btn_mute.cget('text_color'), "#ffffff")
        self.assertEqual(controls.volume.cget('bg_color'), "#FAFAFA")

        # Switch to dark theme
        dark_palette = {
            "button_bg_color": "#404040",
            "button_fg_color": "#ffffff",
            "button_hover": "#505050",
            "accent": "#0078d4",
            "accent_hover": "#106ebe",
            "slider_fg": "#0078d4",
            "slider_bg": "#2D2D2D",
            "slider_hover": "#106ebe",
            "slider_progress": "#0078d4",
            "bg": "#1E1E1E",
            "fg": "#FFFFFF"
        }

        self.mock_theme.palette = dark_palette.copy()
        controls.update_theme()

        # Verify dark theme colors are applied
        self.assertEqual(controls.btn_mute.cget('fg_color'), "#404040")
        self.assertEqual(controls.btn_mute.cget('text_color'), "#ffffff")
        self.assertEqual(controls.volume.cget('bg_color'), "#1E1E1E")
        self.assertEqual(controls.volume_percent_label.cget('text_color'), "#FFFFFF")

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_theme_switch_dark_to_light(self):
        """Test switching from dark to light theme."""
        from ui.controls import ControlsBar

        # Dark theme palette
        dark_palette = {
            "button_bg_color": "#404040",
            "button_fg_color": "#ffffff",
            "button_hover": "#505050",
            "accent": "#0078d4",
            "accent_hover": "#106ebe",
            "slider_fg": "#0078d4",
            "slider_bg": "#2D2D2D",
            "slider_hover": "#106ebe",
            "slider_progress": "#0078d4",
            "bg": "#1E1E1E",
            "fg": "#FFFFFF"
        }

        self.mock_theme.palette = dark_palette.copy()

        # Initialize ControlsBar with dark theme
        controls = ControlsBar(
            self.root,
            self.mock_player,
            self.mock_state,
            self.mock_theme,
            playlist=None,
            tooltip_manager=self.mock_tooltip,
            settings=self.mock_settings
        )

        # Verify initial dark theme colors
        self.assertEqual(controls.btn_mute.cget('fg_color'), "#404040")
        self.assertEqual(controls.volume.cget('bg_color'), "#1E1E1E")

        # Switch to light theme
        light_palette = {
            "button_bg_color": "#0078d4",
            "button_fg_color": "#ffffff",
            "button_hover": "#106ebe",
            "accent": "#0078d4",
            "accent_hover": "#106ebe",
            "slider_fg": "#0078d4",
            "slider_bg": "#E0E0E0",
            "slider_hover": "#106ebe",
            "slider_progress": "#0078d4",
            "bg": "#FAFAFA",
            "fg": "#202020"
        }

        self.mock_theme.palette = light_palette.copy()
        controls.update_theme()

        # Verify light theme colors are applied
        self.assertEqual(controls.btn_mute.cget('fg_color'), "#0078d4")
        self.assertEqual(controls.volume.cget('bg_color'), "#FAFAFA")
        self.assertEqual(controls.volume_percent_label.cget('text_color'), "#202020")

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_volume_slider_theme_update(self):
        """Test that volume slider colors update correctly on theme switch."""
        from ui.controls import ControlsBar

        controls = ControlsBar(
            self.root,
            self.mock_player,
            self.mock_state,
            self.mock_theme,
            playlist=None,
            tooltip_manager=self.mock_tooltip,
            settings=self.mock_settings
        )

        # Initial slider colors
        self.assertEqual(controls.volume.cget('fg_color'), "#E0E0E0")
        self.assertEqual(controls.volume.cget('progress_color'), "#0078d4")
        self.assertEqual(controls.volume.cget('button_color'), "#0078d4")

        # Switch to theme with different slider colors
        new_palette = self.mock_theme.palette.copy()
        new_palette.update({
            "slider_bg": "#CCCCCC",
            "slider_progress": "#FF5722",
            "slider_fg": "#FF5722",
            "slider_hover": "#E64A19"
        })
        self.mock_theme.palette = new_palette

        controls.update_theme()

        # Verify slider colors updated
        self.assertEqual(controls.volume.cget('fg_color'), "#CCCCCC")
        self.assertEqual(controls.volume.cget('progress_color'), "#FF5722")
        self.assertEqual(controls.volume.cget('button_color'), "#FF5722")

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_volume_label_theme_update(self):
        """Test that volume percentage label colors update correctly on theme switch."""
        from ui.controls import ControlsBar

        controls = ControlsBar(
            self.root,
            self.mock_player,
            self.mock_state,
            self.mock_theme,
            playlist=None,
            tooltip_manager=self.mock_tooltip,
            settings=self.mock_settings
        )

        # Initial label colors
        self.assertEqual(controls.volume_percent_label.cget('text_color'), "#202020")

        # Switch to theme with different label colors
        new_palette = self.mock_theme.palette.copy()
        new_palette.update({
            "fg": "#FFFFFF",
            "bg": "#1E1E1E"
        })
        self.mock_theme.palette = new_palette

        controls.update_theme()

        # Verify label colors updated
        self.assertEqual(controls.volume_percent_label.cget('text_color'), "#FFFFFF")

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_theme_switch_with_missing_palette_keys(self):
        """Test theme switching when some palette keys are missing."""
        from ui.controls import ControlsBar

        controls = ControlsBar(
            self.root,
            self.mock_player,
            self.mock_state,
            self.mock_theme,
            playlist=None,
            tooltip_manager=self.mock_tooltip,
            settings=self.mock_settings
        )

        # Switch to incomplete palette (missing some keys)
        incomplete_palette = {
            "button_bg_color": "#FF0000",
            "bg": "#000000"
            # Missing other keys
        }
        self.mock_theme.palette = incomplete_palette

        # Should not crash and should use fallbacks
        try:
            controls.update_theme()
        except Exception as e:
            self.fail(f"update_theme with incomplete palette raised exception: {e}")

        # Should use provided values and fallbacks for missing ones
        self.assertEqual(controls.btn_mute.cget('fg_color'), "#FF0000")
        self.assertEqual(controls.volume.cget('bg_color'), "#000000")

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def test_multiple_theme_switches(self):
        """Test multiple rapid theme switches."""
        from ui.controls import ControlsBar

        controls = ControlsBar(
            self.root,
            self.mock_player,
            self.mock_state,
            self.mock_theme,
            playlist=None,
            tooltip_manager=self.mock_tooltip,
            settings=self.mock_settings
        )

        # Define multiple theme palettes
        themes = [
            {
                "button_bg_color": "#FF0000",
                "bg": "#FFFFFF",
                "fg": "#000000"
            },
            {
                "button_bg_color": "#00FF00",
                "bg": "#000000",
                "fg": "#FFFFFF"
            },
            {
                "button_bg_color": "#0000FF",
                "bg": "#FAFAFA",
                "fg": "#202020"
            }
        ]

        # Apply multiple theme switches
        for theme in themes:
            self.mock_theme.palette = theme
            try:
                controls.update_theme()
            except Exception as e:
                self.fail(f"Multiple theme switches raised exception: {e}")

        # Verify final theme is applied
        self.assertEqual(controls.btn_mute.cget('fg_color'), "#0000FF")
        self.assertEqual(controls.volume.cget('bg_color'), "#FAFAFA")


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
            from audio.audio_player import AudioPlayer
            player = AudioPlayer()
            self.assertFalse(player.get_mute_state())

    def test_get_mute_state_true(self):
        """Test get_mute_state returns True when muted."""
        with patch('sounddevice.play') as mock_play:
            from audio.audio_player import AudioPlayer
            player = AudioPlayer()
            # Manually set muted state
            player._muted = True
            self.assertTrue(player.get_mute_state())

    def test_set_mute_true(self):
        """Test set_mute with mute=True."""
        with patch('sounddevice.play') as mock_play:
            from audio.audio_player import AudioPlayer
            player = AudioPlayer()
            player.set_mute(True)
            self.assertTrue(player.get_mute_state())

    def test_set_mute_false(self):
        """Test set_mute with mute=False."""
        with patch('sounddevice.play') as mock_play:
            from audio.audio_player import AudioPlayer
            player = AudioPlayer()
            player.set_mute(False)
            self.assertFalse(player.get_mute_state())

    def test_set_mute_error_handling(self):
        """Test set_mute handles errors gracefully."""
        with patch('sounddevice.play') as mock_play:
            from audio.audio_player import AudioPlayer
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
            from audio.audio_player import AudioPlayer
            player = AudioPlayer()
            # Should return False on error
            self.assertFalse(player.get_mute_state())


class TestMuteSettings(unittest.TestCase):
    """Unit tests for mute settings persistence."""

    def test_mute_property_default(self):
        """Test mute property defaults to False."""
        with patch('app.settings.Settings.load'):
            from app.settings import Settings
            settings = Settings()
            self.assertFalse(settings.mute)

    def test_mute_property_set(self):
        """Test mute property can be set."""
        from app.settings import Settings
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
                from app.settings import Settings
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
                from app.settings import Settings
                settings = Settings()
                self.assertTrue(settings.mute)


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

        from audio.audio_player import AudioPlayer
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

        from audio.audio_player import AudioPlayer
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

        from audio.audio_player import AudioPlayer
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

        from audio.audio_player import AudioPlayer
        player = AudioPlayer()
        devices = player.get_audio_devices()

        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[1][1], 'Headphones')
        self.assertIsInstance(devices[1][1], str)

    def test_set_audio_device_default(self):
        """Test set_audio_device with default device."""
        from audio.audio_player import AudioPlayer
        player = AudioPlayer()
        player.set_audio_device('__DEFAULT__')
        self.assertIsNone(player._device_id)

    def test_set_audio_device_specific(self):
        """Test set_audio_device with specific device GUID."""
        from audio.audio_player import AudioPlayer
        device_guid = '1'
        player = AudioPlayer()
        player.set_audio_device(device_guid)
        self.assertEqual(player._device_id, device_guid)

    def test_set_audio_device_error_handling(self):
        """Test set_audio_device handles errors gracefully."""
        from audio.audio_player import AudioPlayer
        player = AudioPlayer()
        # Should not raise
        player.set_audio_device('invalid-device')
        self.assertEqual(player._device_id, 'invalid-device')

    def test_is_paused(self):
        """Test is_paused method."""
        from audio.audio_player import AudioPlayer
        player = AudioPlayer()
        self.assertFalse(player.is_paused())
        player._paused = True
        self.assertTrue(player.is_paused())


if __name__ == '__main__':
    unittest.main()