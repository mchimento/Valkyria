"""Tests for ControlsBar theme update functionality."""
import unittest
import logging
import os
import tkinter as tk
from unittest.mock import Mock, MagicMock, patch
from tkinter import ttk

# Suppress logging during tests
logging.disable(logging.CRITICAL)

# Skip UI tests if running in headless environment (CI/CD)
HAS_DISPLAY = os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY') or os.name == 'nt'

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
        self.root = tk.Tk()

        self.mock_player = MagicMock()
        self.mock_state = MagicMock()
        self.mock_state.play_on_double = False

        self.mock_theme = MagicMock()
        self.mock_theme.palette = {
            "button_bg_color": "#123456",
            "button_fg_color": "#ffffff",
            "button_hover": "#654321",
            "accent": "#0078d4",
            "accent_hover": "#106ebe"
        }

        self.mock_settings = MagicMock()
        self.mock_settings.volume = 80
        self.mock_settings.mute = False

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
            "accent_hover": "#106ebe"
        }

        # Call update_theme - this should NOT raise TclError
        try:
            controls.update_theme()
        except tk.TclError as e:
            self.fail(f"update_theme raised TclError: {e}")
        except Exception as e:
            self.fail(f"update_theme raised unexpected exception: {e}")

if __name__ == '__main__':
    unittest.main()
