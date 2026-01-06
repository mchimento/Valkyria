import os
import tempfile
import time
import unittest
import tkinter as tk
from unittest.mock import MagicMock

import soundfile as sf
from mutagen import File as MutagenFile

from audio.metadata import save_metadata, write_key, metadata_extractor, get_file_info
from ui.media_info_window import MediaInfoWindow
from tests.tk_utils import skip_if_no_tk


class TestMediaInfoIntegration(unittest.TestCase):
    def setUp(self):
        # Require a working Tk for these integration tests
        skip_if_no_tk(self)

        # Create a real root window for UI tests
        self.root = tk.Tk()
        self.root.withdraw()

        # Create temp FLAC file (supports metadata reliably)
        fd, path = tempfile.mkstemp(suffix='.flac')
        os.close(fd)
        self.filepath = path
        # write 0.5s of silence (mono)
        import numpy as np
        data = np.zeros((22050, 1), dtype='float32')
        sf.write(self.filepath, data, 44100, format='FLAC')

        # Minimal theme manager mock expected by window
        self.theme = MagicMock()
        self.theme.palette = {}

        # Create MediaInfoWindow
        self.win = MediaInfoWindow(self.root, self.filepath, theme_manager=self.theme)

        # Let Tk process initial events
        self.root.update()

    def tearDown(self):
        try:
            self.win._on_close()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        try:
            os.remove(self.filepath)
        except Exception:
            pass

    def _get_general_text(self):
        try:
            txt = self.win.general_text.get('1.0', tk.END)
            return txt
        except Exception:
            return ''

    def test_save_key_updates_media_info_display(self):
        # Initially no key should be shown
        initial = self._get_general_text()
        self.assertNotIn('Key', initial)

        # Save a key to the file (should notify listeners)
        success = save_metadata(self.filepath, {'key': 'Am'})
        self.assertTrue(success)

        # Allow notification and UI update to propagate
        for _ in range(20):
            self.root.update()
            time.sleep(0.01)

        txt = self._get_general_text()
        # Should show 'Key' and the raw key 'Am'
        self.assertIn('Key', txt)
        self.assertIn('Am', txt)
        # Camelot notation may be shown separately for display; ensure raw key is shown in UI
        # (Camelot mapping is validated in a separate test below.)
        self.assertIn('Key', txt)

    def test_write_key_persists_raw_tag_in_file(self):
        # Use write_key to write tag directly (lower-level)
        result = write_key(self.filepath, 'Gm')
        self.assertTrue(result)

        # Reload tags using mutagen to inspect what's written
        mf = MutagenFile(self.filepath)
        # FLAC uses Vorbis comments; check for 'KEY' or 'key'
        tags = {}
        if hasattr(mf, 'tags') and mf.tags is not None:
            for k in mf.tags.keys():
                tags[k] = mf.tags[k]

        # Ensure raw key value (or a variant) exists; we accept lowercase or uppercase keys
        found_key = False
        for v in tags.values():
            try:
                s = str(v)
                if 'Gm' in s or 'Gm' in s:
                    found_key = True
                    break
            except Exception:
                pass

        self.assertTrue(found_key, 'Raw key tag should be present in file tags')

    def test_get_file_info_includes_camelot_mapping(self):
        # After saving a key, get_file_info should include a 'camelot' mapping for display
        success = save_metadata(self.filepath, {'key': 'Am'})
        self.assertTrue(success)

        # Give the metadata extractor a moment to update
        time.sleep(0.05)

        info = get_file_info(self.filepath)
        meta = info.get('metadata', {})
        self.assertIn('camelot', meta)
        self.assertEqual(meta.get('camelot'), '8A')


if __name__ == '__main__':
    unittest.main()
