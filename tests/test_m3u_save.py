"""
Test for M3U playlist save/load functionality
"""
import unittest
import os
import tempfile
from pathlib import Path
from audio import m3u


class TestM3USaveLoad(unittest.TestCase):
    def test_save_and_load_playlist(self):
        """Test that playlists are saved and loaded correctly."""
        # Test data - simulating what state.playlist should contain.
        # Must be genuinely absolute on whatever platform the test runs on:
        # parse_m3u resolves each entry against the M3U's own directory,
        # which is a no-op for an already-absolute path but silently
        # mangles a path that's only absolute on a *different* OS (e.g. a
        # hardcoded "C:\\..." path isn't absolute per POSIX rules on Linux).
        music_dir = Path(tempfile.mkdtemp())
        test_playlist = [
            str(music_dir / "song1.mp3"),
            str(music_dir / "song2.mp3"),
            str(music_dir / "song3.mp3"),
        ]

        # Use temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.m3u', delete=False) as f:
            temp_path = f.name

        try:
            # Write test playlist
            m3u.write_m3u(temp_path, test_playlist)

            # Read it back
            loaded = m3u.parse_m3u(temp_path)

            # Verify
            self.assertEqual(test_playlist, loaded)
        finally:
            # Cleanup
            if os.path.exists(temp_path):
                os.unlink(temp_path)


if __name__ == '__main__':
    unittest.main()
