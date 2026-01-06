"""Tests for BrowserView functionality."""
import unittest
import os
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk
from tkinter import ttk

from tests.tk_utils import HAS_TK as HAS_DISPLAY

class TestBrowserView(unittest.TestCase):
    """Unit tests for BrowserView class."""

    @classmethod
    def setUpClass(cls):
        """Suppress logging for all tests in this class."""
        pass

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def setUp(self):
        """Set up test fixtures."""
        try:
            self.root = tk.Tk()
        except Exception:
            self.skipTest("Tkinter not available in this environment")

        # Mock State
        self.mock_state = MagicMock()
        self.mock_state.browser_files = []
        self.mock_state.playlist = []
        self.mock_state.exts = ('.mp3', '.wav', '.flac', '.ogg', '.m4a')
        self.mock_state.current_index = 0

        # Mock Theme
        self.mock_theme = MagicMock()
        self.mock_theme.palette = {
            "bg": "#121212",
            "fg": "#FFFFFF",
            "button_bg_color": "#333333",
            "button_fg_color": "#FFFFFF",
            "button_hover": "#444444",
            "accent": "#0078d4",
            "accent_hover": "#106ebe",
            "scrollbar_track": "#282828",
            "scrollbar_thumb": "#535353"
        }

        # Mock TooltipManager
        self.mock_tooltip_manager = MagicMock()

        # Mock Status Callback
        self.mock_status_callback = Mock()

        # Import BrowserView here to avoid import errors if display is missing
        from ui.browser_view import BrowserView
        self.BrowserView = BrowserView

    def tearDown(self):
        """Clean up after tests."""
        if hasattr(self, 'root'):
            self.root.destroy()

    def test_initialization(self):
        """Test that BrowserView initializes correctly."""
        browser = self.BrowserView(
            self.root,
            self.mock_state,
            self.mock_theme,
            self.mock_tooltip_manager,
            self.mock_status_callback
        )
        browser.pack()

        # Check if buttons exist
        # We can't easily check CTkButton existence by name, but we can check if the frame was created
        self.assertTrue(hasattr(browser, 'button_frame'))
        self.assertTrue(hasattr(browser, 'tree'))
        self.assertTrue(hasattr(browser, 'header_label'))

    @patch('tkinter.filedialog.askdirectory')
    @patch('os.walk')
    def test_browse_folder(self, mock_walk, mock_askdirectory):
        """Test browsing a folder."""
        browser = self.BrowserView(
            self.root,
            self.mock_state,
            self.mock_theme,
            status_callback=self.mock_status_callback
        )

        # Setup mocks
        mock_askdirectory.return_value = "/fake/path"
        mock_walk.return_value = [
            ("/fake/path", [], ["song1.mp3", "image.jpg", "song2.wav"])
        ]

        # Call method
        browser.browse_folder()

        # Verify state update
        self.assertEqual(len(self.mock_state.browser_files), 2)
        self.assertIn(os.path.join("/fake/path", "song1.mp3"), self.mock_state.browser_files)
        self.assertIn(os.path.join("/fake/path", "song2.wav"), self.mock_state.browser_files)

        # Verify callback
        self.mock_status_callback.assert_called_with("browsed_folder", 2)

    @patch('tkinter.filedialog.askopenfilenames')
    def test_browse_files(self, mock_askopenfilenames):
        """Test browsing specific files."""
        browser = self.BrowserView(
            self.root,
            self.mock_state,
            self.mock_theme,
            status_callback=self.mock_status_callback
        )

        # Setup mocks
        mock_askopenfilenames.return_value = ["/path/song1.mp3", "/path/song2.mp3"]

        # Call method
        browser.browse_files()

        # Verify state update
        self.assertEqual(len(self.mock_state.browser_files), 2)
        self.mock_status_callback.assert_called_with("browsed_files", 2)

    def test_add_selected_to_playlist(self):
        """Test adding selected items to playlist."""
        browser = self.BrowserView(
            self.root,
            self.mock_state,
            self.mock_theme,
            status_callback=self.mock_status_callback
        )

        # Setup browser files
        self.mock_state.browser_files = ["/path/song1.mp3", "/path/song2.mp3", "/path/song3.mp3"]
        browser.refresh()

        # Select items (song1 and song3)
        children = browser.tree.get_children()
        browser.tree.selection_set(children[0], children[2])

        # Call method
        browser.add_selected_to_playlist()

        # Verify playlist update
        self.assertEqual(len(self.mock_state.playlist), 2)
        self.assertEqual(self.mock_state.playlist[0], "/path/song1.mp3")
        self.assertEqual(self.mock_state.playlist[1], "/path/song3.mp3")

        # Verify callback
        self.mock_status_callback.assert_called_with("added_to_playlist", 2)

    def test_add_selected_below_playlist(self):
        """Test adding selected items below current playing item."""
        browser = self.BrowserView(
            self.root,
            self.mock_state,
            self.mock_theme,
            status_callback=self.mock_status_callback
        )

        # Setup initial playlist and browser files
        self.mock_state.playlist = ["/existing/song1.mp3", "/existing/song2.mp3"]
        self.mock_state.current_index = 0 # Playing song1
        self.mock_state.browser_files = ["/new/songA.mp3", "/new/songB.mp3"]
        browser.refresh()

        # Select new songA
        children = browser.tree.get_children()
        browser.tree.selection_set(children[0])

        # Call method
        browser.add_selected_below_playlist()

        # Verify playlist update (should be inserted at index 1)
        self.assertEqual(len(self.mock_state.playlist), 3)
        self.assertEqual(self.mock_state.playlist[0], "/existing/song1.mp3")
        self.assertEqual(self.mock_state.playlist[1], "/new/songA.mp3")
        self.assertEqual(self.mock_state.playlist[2], "/existing/song2.mp3")

        # Verify callback
        self.mock_status_callback.assert_called_with("added_to_playlist_below", 1)

if __name__ == '__main__':
    unittest.main()
