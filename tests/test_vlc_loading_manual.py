import unittest
import sys
import os
from pathlib import Path

# Add project root to sys.path
# tests/ -> project_root
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from audio.audio_player import AudioPlayer
import vlc

class TestVLCLoadingManual(unittest.TestCase):
    def test_vlc_initialization(self):
        print("Attempting to initialize AudioPlayer...")
        player = AudioPlayer()

        self.assertIsNotNone(player.instance, "VLC Instance is None")
        print(f"VLC Version: {vlc.libvlc_get_version().decode()}")

        # Try to create a media player to be sure
        mp = player.instance.media_player_new()
        self.assertIsNotNone(mp, "MediaPlayer could not be created")
        print("SUCCESS: MediaPlayer created.")

if __name__ == '__main__':
    unittest.main()
