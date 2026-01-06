"""Tests for PlaylistView functionality."""
import unittest
import os
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk
from tkinter import ttk

# Skip UI tests if running in headless environment (CI/CD)
HAS_DISPLAY = os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY') or os.name == 'nt'
# Ensure Tk is actually initializable (Windows can report a display but Tk may be broken)
if HAS_DISPLAY:
    try:
        _tmp_root = tk.Tk()
        _tmp_root.destroy()
    except Exception:
        HAS_DISPLAY = False

class TestPlaylistView(unittest.TestCase):
    """Unit tests for PlaylistView class."""

    @classmethod
    def setUpClass(cls):
        """Suppress logging for all tests in this class."""
        pass

    @unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()

        # Mock State
        self.mock_state = MagicMock()
        self.mock_state.playlist = []
        self.mock_state.current_index = None
        self.mock_state.dragged_index = None
        self.mock_state.play_on_double = True

        # Mock Theme
        self.mock_theme = MagicMock()
        self.mock_theme.palette = {
            "bg": "#121212",
            "fg": "#FFFFFF",
            "accent": "#BB86FC",
            "scrollbar_track": "#282828",
            "scrollbar_thumb": "#535353",
            "ui_font": "Segoe UI"
        }

        # Mock Callbacks
        self.mock_select_callback = Mock()
        self.mock_change_callback = Mock()
        self.mock_play_callback = Mock()
        self.mock_metadata_callback = Mock()
        self.mock_remove_callback = Mock()

        # Patch functions in ui.playlist_view namespace
        self.patcher_title = patch('ui.playlist_view.get_display_title')
        self.mock_title = self.patcher_title.start()

        self.patcher_bpm = patch('ui.playlist_view.get_display_bpm')
        self.mock_bpm = self.patcher_bpm.start()

        self.patcher_metadata = patch('ui.playlist_view.get_metadata')
        self.mock_metadata = self.patcher_metadata.start()

        self.patcher_extractor = patch('ui.playlist_view.metadata_extractor')
        self.mock_extractor = self.patcher_extractor.start()

        # Default return values
        self.mock_metadata.return_value = {}
        self.mock_title.return_value = "Unknown Title"
        self.mock_bpm.return_value = ""

        from ui.playlist_view import PlaylistView
        self.PlaylistView = PlaylistView

    def tearDown(self):
        """Clean up after tests."""
        self.patcher_title.stop()
        self.patcher_bpm.stop()
        self.patcher_metadata.stop()
        self.patcher_extractor.stop()

        if hasattr(self, 'root'):
            self.root.destroy()

    def test_initialization(self):
        """Test that PlaylistView initializes correctly."""
        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )
        view.pack()

        self.assertTrue(hasattr(view, 'tree'))
        self.assertTrue(hasattr(view, 'header_label'))
        self.assertTrue(hasattr(view, 'scrollbar_canvas'))

    def test_refresh_populates_tree(self):
        """Test that refresh populates the treeview."""
        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )

        # Setup data
        self.mock_state.playlist = ["/path/song1.mp3", "/path/song2.mp3"]
        self.mock_title.side_effect = ["Song 1", "Song 2"]
        self.mock_bpm.return_value = "120"

        # Configure the global mock for this test
        self.mock_metadata.side_effect = [
            {"title": "Song 1", "bpm": 120},
            {"title": "Song 2", "bpm": 120}
        ]

        # Call refresh
        view.refresh()

        # Verify tree contents
        children = view.tree.get_children()
        self.assertEqual(len(children), 2)

        item1 = view.tree.item(children[0])
        self.assertEqual(item1['values'][0], "Song 1") # Title is in first column

        item2 = view.tree.item(children[1])
        self.assertEqual(item2['values'][0], "Song 2")

    def test_remove_selected_from_playlist(self):
        """Test removing selected items from playlist."""
        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme,
            change_callback=self.mock_change_callback
        )

        # Setup data
        self.mock_state.playlist = ["/path/song1.mp3", "/path/song2.mp3", "/path/song3.mp3"]
        self.mock_state.current_index = 2 # Playing song3
        view.refresh()

        # Select song2 (index 1)
        children = view.tree.get_children()
        view.tree.selection_set(children[1])

        # Call remove
        view.remove_selected_from_playlist()

        # Verify state update
        self.assertEqual(len(self.mock_state.playlist), 2)
        self.assertEqual(self.mock_state.playlist[0], "/path/song1.mp3")
        self.assertEqual(self.mock_state.playlist[1], "/path/song3.mp3")

        # Verify current index shifted down
        self.assertEqual(self.mock_state.current_index, 1)

        # Verify callback
        self.mock_change_callback.assert_called_once()

    def test_remove_playing_song(self):
        """Test removing the currently playing song."""
        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )

        # Setup data
        self.mock_state.playlist = ["/path/song1.mp3"]
        self.mock_state.current_index = 0
        view.refresh()

        # Select song1
        children = view.tree.get_children()
        view.tree.selection_set(children[0])

        # Call remove
        view.remove_selected_from_playlist()

        # Verify state update
        self.assertEqual(len(self.mock_state.playlist), 0)
        self.assertIsNone(self.mock_state.current_index)

    def test_double_click_plays_song(self):
        """Test that double clicking a song updates state and triggers event."""
        # Use real root but mock event_generate
        self.root.event_generate = Mock()

        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme,
            play_callback=self.mock_play_callback
        )

        # Setup data
        self.mock_state.playlist = ["/path/song1.mp3"]
        view.refresh()

        # Simulate double click on first item
        children = view.tree.get_children()
        view.tree.selection_set(children[0])

        # Create a mock event
        mock_event = Mock()
        mock_event.y = 10

        # Call handler directly
        view._on_double(mock_event)

        # Verify state update
        self.assertEqual(self.mock_state.current_index, 0)

        # Verify event generation
        self.root.event_generate.assert_called_with("<<PlaylistDouble>>")

    def test_context_menu_actions(self):
        """Test context menu callbacks."""
        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme,
            play_callback=self.mock_play_callback,
            metadata_callback=self.mock_metadata_callback,
            remove_callback=self.mock_remove_callback
        )

        # Setup context menu index
        view.context_menu_index = 5

        # Test Play
        view._on_context_play()
        self.mock_play_callback.assert_called_with(5)

        # Test Metadata
        view._on_context_metadata()
        self.mock_metadata_callback.assert_called_with(5)

        # Test Remove
        view._on_context_remove()
        self.mock_remove_callback.assert_called_with(5)

if __name__ == '__main__':
    unittest.main()
