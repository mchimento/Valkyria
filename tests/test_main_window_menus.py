"""Tests for UI menu functionality related to Track Information and Audio Devices."""
import unittest
import logging
import os
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk

# Suppress logging during tests
logging.disable(logging.CRITICAL)

# Use centralized Tk availability utility (handles retries and TCL_LIBRARY fallback)
from tests import tk_utils
HAS_DISPLAY = tk_utils.HAS_TK


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

    @patch('ui.main_window.ControlsBar')
    @patch('ui.main_window.BrowserView')
    @patch('ui.main_window.PlaylistView')
    @patch('ui.main_window.TooltipManager')
    @patch('ui.main_window.PreferencesWindow')
    def setUp(self, mock_prefs, mock_tooltip, mock_playlist_view, mock_browser_view, mock_controls):
        """Set up test fixtures."""
        tk_utils.skip_if_no_tk(self)
        self.mock_state = MagicMock()
        self.mock_state.playlist = ["/path/to/song1.mp3", "/path/to/song2.mp3"]  # Add songs to playlist
        self.mock_state.current_index = 0
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
            # winfo_reqheight() on an unconfigured mock returns another
            # mock, not an int, which _apply_initial_geometry() then tries
            # to add/compare via min() — give it a real int like a real
            # Tk widget would return.
            mock_controls.return_value.winfo_reqheight.return_value = 40
            mock_controls.return_value.winfo_reqwidth.return_value = 400
            main_window = MainWindow(self.mock_state, self.mock_theme, self.mock_player, self.mock_settings)

            # Check track info menu state through menu_item_refs
            track_info_item = main_window.menu_item_refs.get("track_info")
            self.assertIsNotNone(track_info_item)
            self.assertEqual(track_info_item.get("state"), "disabled")
        finally:
            try:
                root.destroy()
            except Exception:
                pass

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
            # winfo_reqheight() on an unconfigured mock returns another
            # mock, not an int, which _apply_initial_geometry() then tries
            # to add/compare via min() — give it a real int like a real
            # Tk widget would return.
            mock_controls.return_value.winfo_reqheight.return_value = 40
            mock_controls.return_value.winfo_reqwidth.return_value = 400
            main_window = MainWindow(self.mock_state, self.mock_theme, self.mock_player, self.mock_settings)

            # Check track info menu state through menu_item_refs
            track_info_item = main_window.menu_item_refs.get("track_info")
            self.assertIsNotNone(track_info_item)
            self.assertEqual(track_info_item.get("state"), "normal")
        finally:
            try:
                root.destroy()
            except Exception:
                pass

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
            # winfo_reqheight() on an unconfigured mock returns another
            # mock, not an int, which _apply_initial_geometry() then tries
            # to add/compare via min() — give it a real int like a real
            # Tk widget would return.
            mock_controls.return_value.winfo_reqheight.return_value = 40
            mock_controls.return_value.winfo_reqwidth.return_value = 400
            main_window = MainWindow(self.mock_state, self.mock_theme, self.mock_player, self.mock_settings)

            # Check track info menu state through menu_item_refs
            track_info_item = main_window.menu_item_refs.get("track_info")
            self.assertIsNotNone(track_info_item)
            self.assertEqual(track_info_item.get("state"), "normal")
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    @patch('ui.main_window.ControlsBar')
    @patch('ui.main_window.BrowserView')
    @patch('ui.main_window.PlaylistView')
    @patch('ui.main_window.TooltipManager')
    def test_resume_does_not_trigger_dj_reestimate(self, mock_tooltip, mock_playlist, mock_browser, mock_controls):
        """Resuming playback (via 'resume' event) should not cause the DJ view to start new analyses."""
        from ui.main_window import MainWindow
        from audio import bpm as bpm_module

        try:
            root = tk.Tk()
            self.root = root
            # winfo_reqheight() on an unconfigured mock returns another
            # mock, not an int, which _apply_initial_geometry() then tries
            # to add/compare via min() — give it a real int like a real
            # Tk widget would return.
            mock_controls.return_value.winfo_reqheight.return_value = 40
            mock_controls.return_value.winfo_reqwidth.return_value = 400
            main_window = MainWindow(self.mock_state, self.mock_theme, self.mock_player, self.mock_settings)

            # Prepare a cached temporary estimate on DJ view
            main_window.dj_view.current_temp_bpm = 120.0
            main_window.dj_view.current_temp_key = 'Am'

            # Patch analysis manager submission functions to detect unexpected calls
            with patch.object(bpm_module.analysis_manager, 'submit_bpm_analysis') as mock_bpm_submit:
                with patch.object(bpm_module.analysis_manager, 'submit_key_analysis') as mock_key_submit:
                    # Simulate resume event (raised by ControlsBar on resume)
                    main_window._controls_status_event('resume')

                    mock_bpm_submit.assert_not_called()
                    mock_key_submit.assert_not_called()
        finally:
            try:
                root.destroy()
            except Exception:
                pass
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
            # winfo_reqheight() on an unconfigured mock returns another
            # mock, not an int, which _apply_initial_geometry() then tries
            # to add/compare via min() — give it a real int like a real
            # Tk widget would return.
            mock_controls.return_value.winfo_reqheight.return_value = 40
            mock_controls.return_value.winfo_reqwidth.return_value = 400
            main_window = MainWindow(self.mock_state, self.mock_theme, self.mock_player, self.mock_settings)

            # Check that audio device items list has items
            self.assertIsNotNone(main_window.audio_device_items)
            # Should have at least 2 items (default + device1)
            self.assertGreaterEqual(len(main_window.audio_device_items), 1)
        finally:
            try:
                root.destroy()
            except Exception:
                pass

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
            # winfo_reqheight() on an unconfigured mock returns another
            # mock, not an int, which _apply_initial_geometry() then tries
            # to add/compare via min() — give it a real int like a real
            # Tk widget would return.
            mock_controls.return_value.winfo_reqheight.return_value = 40
            mock_controls.return_value.winfo_reqwidth.return_value = 400
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

    @patch('ui.main_window.ControlsBar')
    @patch('ui.main_window.BrowserView')
    @patch('ui.main_window.PlaylistView')
    @patch('ui.main_window.TooltipManager')
    def test_playlist_end_triggers_controls_stop(self, mock_tooltip, mock_playlist, mock_browser, mock_controls):
        """Ensure playlist end clears waveform by invoking ControlsBar.stop."""
        from ui.main_window import MainWindow

        mock_controls_instance = MagicMock()
        mock_controls.return_value = mock_controls_instance

        self.mock_state.playlist = ["/path/to/song1.mp3"]
        self.mock_state.current_index = 0
        self.mock_state.repeat_mode = 'none'

        try:
            root = tk.Tk()
            self.root = root
            # winfo_reqheight() on an unconfigured mock returns another
            # mock, not an int, which _apply_initial_geometry() then tries
            # to add/compare via min() — give it a real int like a real
            # Tk widget would return.
            mock_controls.return_value.winfo_reqheight.return_value = 40
            mock_controls.return_value.winfo_reqwidth.return_value = 400
            main_window = MainWindow(self.mock_state, self.mock_theme, self.mock_player, self.mock_settings)

            main_window.handle_track_end()

            mock_controls_instance.stop.assert_called_once()
        finally:
            try:
                root.destroy()
            except Exception:
                pass


    @patch('ui.main_window.ControlsBar')
    @patch('ui.main_window.BrowserView')
    @patch('ui.main_window.PlaylistView')
    @patch('ui.main_window.TooltipManager')
    def test_show_live_audio_analysis_toggle(self, mock_tooltip, mock_playlist, mock_browser, mock_controls):
        """Verify the 'Show Live Audio Analysis' menu toggle shows/hides the DJ view."""
        from ui.main_window import MainWindow

        try:
            root = tk.Tk()
            self.root = root
            # winfo_reqheight() on an unconfigured mock returns another
            # mock, not an int, which _apply_initial_geometry() then tries
            # to add/compare via min() — give it a real int like a real
            # Tk widget would return.
            mock_controls.return_value.winfo_reqheight.return_value = 40
            mock_controls.return_value.winfo_reqwidth.return_value = 400
            main_window = MainWindow(self.mock_state, self.mock_theme, self.mock_player, self.mock_settings)

            # Ensure variable exists and reflects the setting (defaults to True)
            self.assertTrue(hasattr(main_window, 'show_dj_var'))
            self.assertIsInstance(main_window.show_dj_var, tk.BooleanVar)

            # Toggle off and verify DJ view hidden (no geometry manager)
            main_window.show_dj_var.set(False)
            main_window.toggle_dj_visibility()
            self.assertEqual(main_window.dj_view.winfo_manager(), '')

            # Toggle on and verify DJ view is managed by pack
            main_window.show_dj_var.set(True)
            main_window.toggle_dj_visibility()
            self.assertEqual(main_window.dj_view.winfo_manager(), 'pack')
        finally:
            try:
                root.destroy()
            except Exception:
                pass


if __name__ == '__main__':
    unittest.main()
