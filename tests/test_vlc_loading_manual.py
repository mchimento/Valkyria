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
        # On non-Windows platforms, VLC might not be installed.
        # We check if we can create a raw instance first.
        if sys.platform != 'win32':
            try:
                i = vlc.Instance()
                if i is None:
                    self.skipTest("VLC not available on this system")
                i.release()
            except Exception:
                self.skipTest("VLC not available on this system")

        print("Attempting to initialize AudioPlayer...")
        try:
            player = AudioPlayer()
        except AttributeError:
             # This catches the specific error reported: 'NoneType' object has no attribute 'media_player_new'
             # which happens if AudioPlayer gets None from vlc.Instance()
             self.fail("AudioPlayer failed to initialize (vlc.Instance() returned None)")

        self.assertIsNotNone(player.instance, "VLC Instance is None")
        print(f"VLC Version: {vlc.libvlc_get_version().decode()}")

        # Try to create a media player to be sure
        mp = player.instance.media_player_new()
        self.assertIsNotNone(mp, "MediaPlayer could not be created")
        print("SUCCESS: MediaPlayer created.")

if __name__ == '__main__':
    unittest.main()
