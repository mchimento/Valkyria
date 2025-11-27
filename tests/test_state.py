import unittest
from app.state import AppState


class TestAppState(unittest.TestCase):
    """Unit tests for the AppState dataclass."""

    def test_initialization(self):
        """Test that AppState initializes with correct default values."""
        state = AppState()

        self.assertEqual(state.playlist, [])
        self.assertEqual(state.browser_files, [])
        self.assertIsNone(state.current_index)
        self.assertIsNone(state.dragged_index)
        self.assertTrue(state.play_on_double)
        self.assertIsNone(state.current_playlist_path)
        self.assertEqual(state._current_theme, 'light')
        self.assertEqual(state.exts, (".mp3", ".wav", ".flac", ".ogg", ".m4a"))

    def test_playlist_modification(self):
        """Test that playlist can be modified."""
        state = AppState()

        state.playlist.append("/path/to/song1.mp3")
        state.playlist.append("/path/to/song2.mp3")

        self.assertEqual(len(state.playlist), 2)
        self.assertEqual(state.playlist[0], "/path/to/song1.mp3")
        self.assertEqual(state.playlist[1], "/path/to/song2.mp3")

    def test_current_index_tracking(self):
        """Test that current_index can be set and retrieved."""
        state = AppState()
        state.playlist = ["/song1.mp3", "/song2.mp3", "/song3.mp3"]

        state.current_index = 1
        self.assertEqual(state.current_index, 1)

        state.current_index = None
        self.assertIsNone(state.current_index)


if __name__ == '__main__':
    unittest.main()
