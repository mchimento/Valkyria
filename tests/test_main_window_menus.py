"""Tests for UI menu functionality related to Track Information and Audio Devices."""
import unittest
import logging
import os
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk

# Suppress logging during tests
logging.disable(logging.CRITICAL)

# Skip UI tests if running in headless environment (CI/CD)
HAS_DISPLAY = os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY') or os.name == 'nt'


class TestMainWindowMenus(unittest.TestCase):
    """Unit tests for MainWindow menu functionality."""

    @classmethod
    def setUpClass(cls):
        """Suppress logging for all tests in this class."""
        logging.disable(logging.CRITICAL)

    @classmethod
    def tearDownClass(cls):
        """Re-enable logging after tests."""
        logging.disable(logging.NOTSET)

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    @patch('ui.main_window.ControlsBar')
    @patch('ui.main_window.BrowserView')
    @patch('ui.main_window.PlaylistView')
    @patch('ui.main_window.TooltipManager')
    @patch('ui.main_window.PreferencesWindow')
    def setUp(self, mock_prefs, mock_tooltip, mock_playlist_view, mock_browser_view, mock_controls):
        """Set up test fixtures."""
        self.mock_state = MagicMock()
        self.mock_state.playlist = []
        self.mock_state.current_index = None
        self.mock_state.play_on_double = False

        self.mock_theme = MagicMock()
        self.mock_theme.palette = {}

        self.mock_player = MagicMock()
        self.mock_player.is_playing.return_value = False
        self.mock_player.is_paused.return_value = False
        self.mock_player.get_audio_devices.return_value = [
            ('__DEFAULT__', 'Default'),
            ('{0.0.0}.{device1}', 'Device 1'),
        ]

        self.mock_settings = MagicMock()
        self.mock_settings.window_geometry = None
        self.mock_settings.theme = 'light'

    def tearDown(self):
        """Clean up after tests."""
        try:
            if hasattr(self, 'root'):
                self.root.destroy()
        except Exception:
            pass

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    @patch('ui.main_window.ControlsBar')
    @patch('ui.main_window.BrowserView')
    @patch('ui.main_window.PlaylistView')
    @patch('ui.main_window.TooltipManager')
    def test_track_info_disabled_when_not_playing(self, mock_tooltip, mock_playlist, mock_browser, mock_controls):
        """Test Track Information menu item is disabled when not playing or paused."""
        from ui.main_window import MainWindow

        self.mock_player.is_playing.return_value = False
        self.mock_player.is_paused.return_value = False

        try:
            root = tk.Tk()
            self.root = root
            main_window = MainWindow(self.mock_state, self.mock_theme, self.mock_player, self.mock_settings)

            # Check track info menu state
            state = main_window.toolsmenu.entryconfig(main_window.track_info_index)['state']
            self.assertEqual(state[4], tk.DISABLED)
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    @patch('ui.main_window.ControlsBar')
    @patch('ui.main_window.BrowserView')
    @patch('ui.main_window.PlaylistView')
    @patch('ui.main_window.TooltipManager')
    def test_track_info_enabled_when_playing(self, mock_tooltip, mock_playlist, mock_browser, mock_controls):
        """Test Track Information menu item is enabled when playing."""
        from ui.main_window import MainWindow

        self.mock_player.is_playing.return_value = True
        self.mock_player.is_paused.return_value = False

        try:
            root = tk.Tk()
            self.root = root
            main_window = MainWindow(self.mock_state, self.mock_theme, self.mock_player, self.mock_settings)

            # Check track info menu state
            state = main_window.toolsmenu.entryconfig(main_window.track_info_index)['state']
            self.assertEqual(state[4], tk.NORMAL)
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    @patch('ui.main_window.ControlsBar')
    @patch('ui.main_window.BrowserView')
    @patch('ui.main_window.PlaylistView')
    @patch('ui.main_window.TooltipManager')
    def test_track_info_enabled_when_paused(self, mock_tooltip, mock_playlist, mock_browser, mock_controls):
        """Test Track Information menu item is enabled when paused."""
        from ui.main_window import MainWindow

        self.mock_player.is_playing.return_value = False
        self.mock_player.is_paused.return_value = True

        try:
            root = tk.Tk()
            self.root = root
            main_window = MainWindow(self.mock_state, self.mock_theme, self.mock_player, self.mock_settings)

            # Check track info menu state
            state = main_window.toolsmenu.entryconfig(main_window.track_info_index)['state']
            self.assertEqual(state[4], tk.NORMAL)
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    @patch('ui.main_window.ControlsBar')
    @patch('ui.main_window.BrowserView')
    @patch('ui.main_window.PlaylistView')
    @patch('ui.main_window.TooltipManager')
    def test_audio_device_menu_populated(self, mock_tooltip, mock_playlist, mock_browser, mock_controls):
        """Test Audio Device submenu is properly populated with devices."""
        from ui.main_window import MainWindow

        try:
            root = tk.Tk()
            self.root = root
            main_window = MainWindow(self.mock_state, self.mock_theme, self.mock_player, self.mock_settings)

            # Check that audio device menu has items
            menu_items = main_window.audio_device_menu.index('end')
            self.assertIsNotNone(menu_items)
            # Should have at least 2 items (default + device1)
            self.assertGreaterEqual(menu_items, 1)
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    @patch('ui.main_window.ControlsBar')
    @patch('ui.main_window.BrowserView')
    @patch('ui.main_window.PlaylistView')
    @patch('ui.main_window.TooltipManager')
    def test_audio_device_selection(self, mock_tooltip, mock_playlist, mock_browser, mock_controls):
        """Test setting audio device updates player."""
        from ui.main_window import MainWindow

        try:
            root = tk.Tk()
            self.root = root
            main_window = MainWindow(self.mock_state, self.mock_theme, self.mock_player, self.mock_settings)

            device_id = '{0.0.0}.{device1}'
            main_window.set_audio_device(device_id)

            # Verify player's set_audio_device was called
            self.mock_player.set_audio_device.assert_called_with(device_id)
        finally:
            try:
                root.destroy()
            except Exception:
                pass


if __name__ == '__main__':
    unittest.main()
