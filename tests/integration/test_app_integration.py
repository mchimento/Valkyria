import unittest
from unittest.mock import MagicMock, patch, ANY
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from app.application import ValkyriaApp
from app.state import AppState

class TestAppIntegration(unittest.TestCase):
    def setUp(self):
        # Patch external dependencies
        self.tk_patcher = patch('tkinter.Tk')
        self.mock_tk = self.tk_patcher.start()

        self.ctk_patcher = patch('customtkinter.CTk')
        self.mock_ctk = self.ctk_patcher.start()

        self.sd_patcher = patch('sounddevice.query_devices')
        self.mock_sd = self.sd_patcher.start()

        # Mock settings - Patch where it is USED in app.application
        self.settings_patcher = patch('app.application.Settings')
        self.mock_settings_cls = self.settings_patcher.start()
        self.mock_settings = self.mock_settings_cls.return_value
        self.mock_settings.theme = "dark"
        self.mock_settings.window_geometry = "800x600"
        self.mock_settings.bpm_mode = "auto"

        # Mock ThemeManager - Patch where it is USED in app.application
        self.theme_patcher = patch('app.application.ThemeManager')
        self.mock_theme_cls = self.theme_patcher.start()
        self.mock_theme = self.mock_theme_cls.return_value
        self.mock_theme.palette = {
            "bg": "#000000", "fg": "#ffffff", "accent": "#0000ff",
            "border": "#333333", "tree_bg": "#111111", "tree_fg": "#eeeeee",
            "button_bg_color": "#222222", "button_fg_color": "#ffffff"
        }

        # Mock AudioPlayer - Patch where it is USED in app.application
        self.player_patcher = patch('app.application.AudioPlayer')
        self.mock_player_cls = self.player_patcher.start()
        self.mock_player = self.mock_player_cls.return_value

        # Mock MainWindow - Patch where it is USED in app.application
        self.mainwindow_patcher = patch('app.application.MainWindow')
        self.mock_mainwindow_cls = self.mainwindow_patcher.start()
        self.mock_mainwindow = self.mock_mainwindow_cls.return_value

        # Patch metadata module in app.application
        self.metadata_patcher = patch('app.application.metadata_module')
        self.mock_metadata = self.metadata_patcher.start()

        # Patch Tkinter variables just in case AppState or others use them
        self.boolean_var_patcher = patch('tkinter.BooleanVar')
        self.mock_boolean_var = self.boolean_var_patcher.start()

        self.string_var_patcher = patch('tkinter.StringVar')
        self.mock_string_var = self.string_var_patcher.start()

        self.int_var_patcher = patch('tkinter.IntVar')
        self.mock_int_var = self.int_var_patcher.start()

        self.double_var_patcher = patch('tkinter.DoubleVar')
        self.mock_double_var = self.double_var_patcher.start()

    def tearDown(self):
        patch.stopall()

    def test_app_initialization(self):
        """Test that the application initializes all components correctly."""
        app = ValkyriaApp()

        self.assertIsInstance(app.state, AppState)
        self.assertEqual(app.settings, self.mock_settings)
        self.assertEqual(app.theme, self.mock_theme)
        self.assertEqual(app.player, self.mock_player)

        # Verify MainWindow was created with correct args
        self.mock_mainwindow_cls.assert_called_with(app.state, self.mock_theme, self.mock_player, self.mock_settings)

        # Verify player callback is registered
        self.mock_player_cls.assert_called_with(on_track_end=app._on_track_end)

    def test_track_end_callback_flow(self):
        """Test the flow from player track end to UI update."""
        app = ValkyriaApp()

        # Simulate track end callback
        app._on_track_end()

        # Verify it calls the window method
        app.window.on_track_end_from_backend.assert_called_once()

    def test_run_starts_window(self):
        """Test that run() starts the main window loop."""
        app = ValkyriaApp()

        app.run()

        app.window.start.assert_called_once()

    def test_bpm_preference_initialization(self):
        """Test that BPM preference is set from settings on initialization."""
        app = ValkyriaApp()

        self.mock_metadata.set_bpm_preference.assert_called_with(self.mock_settings.bpm_mode)

if __name__ == '__main__':
    unittest.main()
