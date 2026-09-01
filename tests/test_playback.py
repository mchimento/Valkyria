"""Tests for audio/playback.py's pure playlist-manipulation functions."""
import unittest

from audio import playback


class TestPlayAfterCurrent(unittest.TestCase):
    """Test the play_after_current function."""

    def test_play_after_current_single_track(self):
        """Test moving a single track after current."""
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


if __name__ == '__main__':
    unittest.main()
