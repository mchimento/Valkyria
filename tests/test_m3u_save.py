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
        # Test data - simulating what state.playlist should contain
        test_playlist = [
            "C:\\Music\\song1.mp3",
            "C:\\Music\\song2.mp3",
            "C:\\Music\\song3.mp3"
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
