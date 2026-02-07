"""Tests for PlaylistView functionality."""
import unittest
import os
from unittest.mock import Mock, MagicMock, patch
import tkinter as tk
from tkinter import ttk

from tests.tk_utils import HAS_TK as HAS_DISPLAY

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

        self.patcher_metadata = patch('ui.playlist_view.get_metadata')
        self.mock_metadata = self.patcher_metadata.start()

        self.patcher_extractor = patch('ui.playlist_view.metadata_extractor')
        self.mock_extractor = self.patcher_extractor.start()

        # Default return values
        self.mock_metadata.return_value = {}
        self.mock_title.return_value = "Unknown Title"

        from ui.playlist_view import PlaylistView
        self.PlaylistView = PlaylistView

    def tearDown(self):
        """Clean up after tests."""
        self.patcher_title.stop()
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

        # Configure the global mock for this test
        self.mock_metadata.side_effect = [
            {"title": "Song 1"},
            {"title": "Song 2"}
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


class TestPlayAfterCurrent(unittest.TestCase):
    """Test the play_after_current function."""

    def test_play_after_current_single_track(self):
        """Test moving a single track after current."""
        from audio import playback
        playlist = ["track1.mp3", "track2.mp3", "track3.mp3", "track4.mp3"]
        current_index = 1  # track2 is playing
        selected_indices = [3]  # track4 selected

        new_playlist, new_current_index = playback.play_after_current(
            playlist, selected_indices, current_index
        )

        # track4 should now be after track2
        expected = ["track1.mp3", "track2.mp3", "track4.mp3", "track3.mp3"]
        self.assertEqual(new_playlist, expected)
        self.assertEqual(new_current_index, 1)  # current_index stays at track2

    def test_play_after_current_multiple_tracks(self):
        """Test moving multiple tracks after current."""
        from audio import playback
        playlist = ["track1.mp3", "track2.mp3", "track3.mp3", "track4.mp3", "track5.mp3"]
        current_index = 1  # track2 is playing
        selected_indices = [3, 4]  # track4 and track5 selected

        new_playlist, new_current_index = playback.play_after_current(
            playlist, selected_indices, current_index
        )

        # track4 and track5 should be after track2, in order
        expected = ["track1.mp3", "track2.mp3", "track4.mp3", "track5.mp3", "track3.mp3"]
        self.assertEqual(new_playlist, expected)
        self.assertEqual(new_current_index, 1)

    def test_play_after_current_from_before(self):
        """Test moving a track from before current position."""
        from audio import playback
        playlist = ["track1.mp3", "track2.mp3", "track3.mp3", "track4.mp3"]
        current_index = 2  # track3 is playing
        selected_indices = [0]  # track1 selected

        new_playlist, new_current_index = playback.play_after_current(
            playlist, selected_indices, current_index
        )

        # track1 should be after track3
        expected = ["track2.mp3", "track3.mp3", "track1.mp3", "track4.mp3"]
        self.assertEqual(new_playlist, expected)
        # current_index adjusted because track before it was removed
        self.assertEqual(new_current_index, 1)

    def test_play_after_current_preserves_order(self):
        """Test that moved tracks preserve their relative order."""
        from audio import playback
        playlist = ["track1.mp3", "track2.mp3", "track3.mp3", "track4.mp3", "track5.mp3"]
        current_index = 0  # track1 is playing
        selected_indices = [2, 4]  # track3 and track5 selected (non-contiguous)

        new_playlist, new_current_index = playback.play_after_current(
            playlist, selected_indices, current_index
        )

        # track3 and track5 should be after track1, in original order
        expected = ["track1.mp3", "track3.mp3", "track5.mp3", "track2.mp3", "track4.mp3"]
        self.assertEqual(new_playlist, expected)
        self.assertEqual(new_current_index, 0)

    def test_play_after_current_no_current_track(self):
        """Test when no track is currently playing."""
        from audio import playback
        playlist = ["track1.mp3", "track2.mp3", "track3.mp3"]
        current_index = None
        selected_indices = [1]

        new_playlist, new_current_index = playback.play_after_current(
            playlist, selected_indices, current_index
        )

        # Should return unchanged playlist
        self.assertEqual(new_playlist, playlist)
        self.assertIsNone(new_current_index)

    def test_play_after_current_current_track_selected(self):
        """Test when current track is in selection (should be ignored)."""
        from audio import playback
        playlist = ["track1.mp3", "track2.mp3", "track3.mp3", "track4.mp3"]
        current_index = 1  # track2 is playing
        selected_indices = [1, 3]  # track2 (current) and track4 selected

        new_playlist, new_current_index = playback.play_after_current(
            playlist, selected_indices, current_index
        )

        # Only track4 should move (track2 ignored because it's current)
        expected = ["track1.mp3", "track2.mp3", "track4.mp3", "track3.mp3"]
        self.assertEqual(new_playlist, expected)
        self.assertEqual(new_current_index, 1)

    def test_play_after_current_empty_selection(self):
        """Test with empty selection."""
        from audio import playback
        playlist = ["track1.mp3", "track2.mp3", "track3.mp3"]
        current_index = 1
        selected_indices = []

        new_playlist, new_current_index = playback.play_after_current(
            playlist, selected_indices, current_index
        )

        # Should return unchanged playlist
        self.assertEqual(new_playlist, playlist)
        self.assertEqual(new_current_index, current_index)

    def test_play_after_current_only_current_selected(self):
        """Test when only the current track is selected."""
        from audio import playback
        playlist = ["track1.mp3", "track2.mp3", "track3.mp3"]
        current_index = 1
        selected_indices = [1]  # Only current track selected

        new_playlist, new_current_index = playback.play_after_current(
            playlist, selected_indices, current_index
        )

        # Should return unchanged playlist (current track ignored)
        self.assertEqual(new_playlist, playlist)
        self.assertEqual(new_current_index, current_index)

    def test_play_after_current_at_end(self):
        """Test moving track to after last track."""
        from audio import playback
        playlist = ["track1.mp3", "track2.mp3", "track3.mp3"]
        current_index = 2  # track3 (last) is playing
        selected_indices = [0]  # track1 selected

        new_playlist, new_current_index = playback.play_after_current(
            playlist, selected_indices, current_index
        )

        # track1 should move to end
        expected = ["track2.mp3", "track3.mp3", "track1.mp3"]
        self.assertEqual(new_playlist, expected)
        self.assertEqual(new_current_index, 1)


class TestPlaylistViewSearchBar(unittest.TestCase):
    """Unit tests for PlaylistView search bar functionality."""

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

        # Mock Theme with all required palette entries
        self.mock_theme = MagicMock()
        self.mock_theme.palette = {
            "bg": "#121212",
            "fg": "#FFFFFF",
            "fg_dim": "#888888",
            "entry_bg": "#2A2A2A",
            "accent": "#BB86FC",
            "scrollbar_track": "#282828",
            "scrollbar_thumb": "#535353",
            "ui_font": "Segoe UI"
        }

        # Patch functions in ui.playlist_view namespace
        self.patcher_title = patch('ui.playlist_view.get_display_title')
        self.mock_title = self.patcher_title.start()

        self.patcher_metadata = patch('ui.playlist_view.get_metadata')
        self.mock_metadata = self.patcher_metadata.start()

        self.patcher_extractor = patch('ui.playlist_view.metadata_extractor')
        self.mock_extractor = self.patcher_extractor.start()

        # Default return values
        self.mock_metadata.return_value = {}
        self.mock_title.return_value = "Unknown Title"

        from ui.playlist_view import PlaylistView
        self.PlaylistView = PlaylistView

    def tearDown(self):
        """Clean up after tests."""
        self.patcher_title.stop()
        self.patcher_metadata.stop()
        self.patcher_extractor.stop()

        if hasattr(self, 'root'):
            self.root.destroy()

    def test_search_bar_initialization(self):
        """Test that search bar components are initialized correctly."""
        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )

        self.assertTrue(hasattr(view, 'search_frame'))
        self.assertTrue(hasattr(view, 'search_entry'))
        self.assertTrue(hasattr(view, 'search_var'))
        self.assertTrue(hasattr(view, 'search_label'))
        self.assertTrue(hasattr(view, 'clear_button'))
        self.assertTrue(hasattr(view, '_search_text'))
        self.assertTrue(hasattr(view, '_filtered_indices'))
        self.assertTrue(hasattr(view, '_placeholder_active'))

    def test_search_bar_placeholder_active_on_init(self):
        """Test that placeholder is active on initialization."""
        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )

        self.assertTrue(view._placeholder_active)
        self.assertEqual(view.search_var.get(), "Search")

    def test_search_bar_hidden_when_playlist_empty(self):
        """Test that search bar is hidden when playlist is empty."""
        self.mock_state.playlist = []
        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )

        view.refresh()
        self.assertFalse(view.search_frame.winfo_ismapped())

    def test_search_bar_visible_when_playlist_has_songs(self):
        """Test that search bar becomes visible after adding songs to playlist."""
        # Start with empty playlist
        self.mock_state.playlist = []

        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )
        view.refresh()

        # Search bar should be hidden with empty playlist
        self.assertFalse(view.search_frame.winfo_ismapped())

        # Add songs to playlist
        self.mock_state.playlist = ["song1.mp3", "song2.mp3"]
        self.mock_metadata.side_effect = lambda path: {
            "title": os.path.basename(path),
            "artist": "Artist",
            "album": "Album"
        }

        # Refresh to show songs
        view.refresh()

        # Check that search_frame is in the packing list (has been packed)
        # winfo_ismapped might not work reliably in tests, check if widget is managed
        pack_info = view.search_frame.pack_info()
        self.assertIsNotNone(pack_info)
        self.assertIn('anchor', pack_info)

    def test_search_filter_by_title(self):
        """Test filtering playlist by song title."""
        self.mock_state.playlist = ["rock_song.mp3", "jazz_song.mp3", "blues_song.mp3"]
        self.mock_metadata.side_effect = lambda path: {
            "title": os.path.basename(path).replace(".mp3", "").replace("_", " "),
            "artist": "Artist",
            "album": "Album"
        }

        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )
        view.refresh()

        # Simulate search for "rock"
        view._placeholder_active = False
        view.search_var.set("rock")
        view._on_search_changed()

        # Should only show 1 matching track
        self.assertEqual(len(view._filtered_indices), 1)
        self.assertIn(0, view._filtered_indices)  # rock_song.mp3
        self.assertEqual(len(view.tree.get_children()), 1)

    def test_search_filter_by_artist(self):
        """Test filtering playlist by artist name."""
        self.mock_state.playlist = ["song1.mp3", "song2.mp3", "song3.mp3"]
        self.mock_metadata.side_effect = lambda path: {
            "title": os.path.basename(path),
            "artist": "Beatles" if "song1" in path else "Rolling Stones",
            "album": "Album"
        }

        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )
        view.refresh()

        # Simulate search for "beatles"
        view._placeholder_active = False
        view.search_var.set("beatles")
        view._on_search_changed()

        # Should only show 1 matching track
        self.assertEqual(len(view._filtered_indices), 1)
        self.assertIn(0, view._filtered_indices)

    def test_search_filter_by_album(self):
        """Test filtering playlist by album name."""
        self.mock_state.playlist = ["song1.mp3", "song2.mp3", "song3.mp3"]
        self.mock_metadata.side_effect = lambda path: {
            "title": os.path.basename(path),
            "artist": "Artist",
            "album": "Greatest Hits" if "song2" in path else "Other Album"
        }

        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )
        view.refresh()

        # Simulate search for "greatest"
        view._placeholder_active = False
        view.search_var.set("greatest")
        view._on_search_changed()

        # Should only show 1 matching track
        self.assertEqual(len(view._filtered_indices), 1)
        self.assertIn(1, view._filtered_indices)

    def test_search_case_insensitive(self):
        """Test that search is case-insensitive."""
        self.mock_state.playlist = ["ROCK_SONG.mp3", "jazz_song.mp3"]
        self.mock_metadata.side_effect = lambda path: {
            "title": os.path.basename(path).replace(".mp3", "").replace("_", " "),
            "artist": "Artist",
            "album": "Album"
        }

        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )
        view.refresh()

        # Search with lowercase
        view._placeholder_active = False
        view.search_var.set("rock")
        view._on_search_changed()

        self.assertEqual(len(view._filtered_indices), 1)
        self.assertIn(0, view._filtered_indices)

    def test_search_multiple_matches(self):
        """Test search returning multiple matches."""
        self.mock_state.playlist = ["rock1.mp3", "rock2.mp3", "jazz.mp3", "rock3.mp3"]
        self.mock_metadata.side_effect = lambda path: {
            "title": os.path.basename(path).replace(".mp3", ""),
            "artist": "Artist",
            "album": "Album"
        }

        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )
        view.refresh()

        # Search for "rock"
        view._placeholder_active = False
        view.search_var.set("rock")
        view._on_search_changed()

        # Should show 3 matching tracks
        self.assertEqual(len(view._filtered_indices), 3)
        self.assertEqual(view._filtered_indices, [0, 1, 3])
        self.assertEqual(len(view.tree.get_children()), 3)

    def test_search_clear_shows_all(self):
        """Test that clearing search shows all tracks."""
        self.mock_state.playlist = ["song1.mp3", "song2.mp3", "song3.mp3"]
        self.mock_metadata.side_effect = lambda path: {
            "title": os.path.basename(path),
            "artist": "Artist",
            "album": "Album"
        }

        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )
        view.refresh()

        # Apply search filter
        view._placeholder_active = False
        view.search_var.set("song1")
        view._on_search_changed()
        self.assertEqual(len(view.tree.get_children()), 1)

        # Clear search
        view.search_var.set("")
        view._on_search_changed()

        # Should show all tracks
        self.assertEqual(len(view._filtered_indices), 0)
        self.assertEqual(len(view.tree.get_children()), 3)

    def test_search_focus_in_removes_placeholder(self):
        """Test that focusing on search entry removes placeholder."""
        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )

        self.assertTrue(view._placeholder_active)
        self.assertEqual(view.search_var.get(), "Search")

        # Simulate focus in
        event = MagicMock()
        view._on_search_focus_in(event)

        self.assertFalse(view._placeholder_active)
        self.assertEqual(view.search_var.get(), "")

    def test_search_focus_out_restores_placeholder_if_empty(self):
        """Test that losing focus restores placeholder if search is empty."""
        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )

        # Remove placeholder
        view._placeholder_active = False
        view.search_var.set("")

        # Simulate focus out with empty search
        event = MagicMock()
        view._on_search_focus_out(event)

        self.assertTrue(view._placeholder_active)
        self.assertEqual(view.search_var.get(), "Search")

    def test_search_focus_out_keeps_text_if_not_empty(self):
        """Test that losing focus keeps search text if not empty."""
        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )

        # Set search text
        view._placeholder_active = False
        view.search_var.set("rock")

        # Simulate focus out with search text
        event = MagicMock()
        view._on_search_focus_out(event)

        self.assertFalse(view._placeholder_active)
        self.assertEqual(view.search_var.get(), "rock")

    def test_search_no_filter_when_placeholder_active(self):
        """Test that search doesn't filter when placeholder is active."""
        self.mock_state.playlist = ["song1.mp3", "song2.mp3"]
        self.mock_metadata.side_effect = lambda path: {
            "title": os.path.basename(path),
            "artist": "Artist",
            "album": "Album"
        }

        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )
        view.refresh()

        # Placeholder is active, set search text (shouldn't trigger filter)
        view._placeholder_active = True
        view.search_var.set("Search")
        view._on_search_changed()

        # Should show all tracks (no filtering)
        self.assertEqual(len(view._filtered_indices), 0)
        self.assertEqual(len(view.tree.get_children()), 2)

    def test_search_recalculates_after_playlist_modification(self):
        """Test that search filter is recalculated when playlist is modified."""
        self.mock_state.playlist = ["rock1.mp3", "jazz.mp3", "rock2.mp3"]
        self.mock_metadata.side_effect = lambda path: {
            "title": os.path.basename(path).replace(".mp3", ""),
            "artist": "Artist",
            "album": "Album"
        }

        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )
        view.refresh()

        # Apply search filter
        view._placeholder_active = False
        view.search_var.set("rock")
        view._on_search_changed()

        # Initial filter: 2 matches
        self.assertEqual(len(view._filtered_indices), 2)

        # Modify playlist (remove middle item)
        self.mock_state.playlist = ["rock1.mp3", "rock2.mp3"]

        # Refresh should recalculate filter
        view.refresh()

        # Should still find 2 rock songs, but indices updated
        self.assertEqual(len(view._filtered_indices), 2)
        self.assertEqual(view._filtered_indices, [0, 1])

    def test_get_actual_index_from_filtered_tree_item(self):
        """Test getting actual playlist index from filtered tree view."""
        self.mock_state.playlist = ["song1.mp3", "rock.mp3", "song3.mp3", "rock2.mp3"]
        self.mock_metadata.side_effect = lambda path: {
            "title": os.path.basename(path).replace(".mp3", ""),
            "artist": "Artist",
            "album": "Album"
        }

        view = self.PlaylistView(
            self.root,
            self.mock_state,
            self.mock_theme
        )
        view.refresh()

        # Apply filter for "rock"
        view._placeholder_active = False
        view.search_var.set("rock")
        view._on_search_changed()

        # Tree should have 2 items, but they map to playlist indices 1 and 3
        children = view.tree.get_children()
        self.assertEqual(len(children), 2)

        # First tree item should map to playlist index 1
        actual_index_0 = view._get_actual_index_from_tree_item(children[0])
        self.assertEqual(actual_index_0, 1)

        # Second tree item should map to playlist index 3
        actual_index_1 = view._get_actual_index_from_tree_item(children[1])
        self.assertEqual(actual_index_1, 3)


if __name__ == '__main__':
    unittest.main()
