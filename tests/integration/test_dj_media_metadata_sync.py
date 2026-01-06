import os
import tempfile
import threading
import time
import unittest
import tkinter as tk
import numpy as np
import soundfile as sf
from unittest.mock import MagicMock, patch

from audio.metadata import write_bpm, save_metadata, metadata_extractor
from ui.dj_frame_view import DJFrameView

from tests.tk_utils import HAS_TK as HAS_DISPLAY, skip_if_no_tk


class TestDJMediaIntegration(unittest.TestCase):
    def setUp(self):
        # Note: do not skip automatically if Tk isn't available. We will attempt
        # to use a lightweight dummy GUI if necessary so integration logic is
        # still testable in headless environments.
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception:
            # Defer to later when we decide whether to use a DummyMaster
            self.root = None

        # Create temp FLAC file (supports metadata reliably)
        fd, path = tempfile.mkstemp(suffix='.flac')
        os.close(fd)
        self.filepath = path
        # write 0.5s of silence (mono)
        data = np.zeros((22050, 1), dtype='float32')
        sf.write(self.filepath, data, 44100, format='FLAC')

        # Simple theme/settings/state mocks
        self.theme = MagicMock()
        self.theme.palette = {}
        self.settings = MagicMock()
        self.settings.theme = 'dark'
        self.state = MagicMock()
        self.state.playlist = [self.filepath]
        self.state.current_index = 0

        # If real Tk is available this test will use it; otherwise create a
        # lightweight fake GUI environment so we can exercise DJFrameView logic
        # without requiring a full Tk install.
        try:
            # Try to create real root window once
            tmp_root = tk.Tk()
            tmp_root.withdraw()
            tmp_root.destroy()
            using_real_tk = True
        except Exception:
            using_real_tk = False

        if using_real_tk:
            # Ensure self.root references a real root (first attempt may have failed earlier)
            if self.root is None:
                try:
                    self.root = tk.Tk()
                    self.root.withdraw()
                except Exception:
                    # If creating a real root now fails, fall back to dummy mode
                    using_real_tk = False

        if not using_real_tk:
            # Monkeypatch top-level customtkinter classes to simple dummies that don't
            # require a running Tk event loop. Patch the library namespace so other
            # modules that import customtkinter also see the dummy classes.
            class DummyRoot:
                def after(self, delay, func, *args, **kwargs):
                    func(*args, **kwargs)
                def withdraw(self): pass
                def destroy(self): pass
                def update(self): pass

            class DummyMaster:
                def __init__(self):
                    self._root = DummyRoot()
                    self.tk = None
                def winfo_toplevel(self):
                    return self._root

            class DummyFrame:
                def __init__(self, master=None, **kwargs):
                    self.master = master
                    self._children = []
                def pack(self, *args, **kwargs): self._packed = True
                def pack_propagate(self, val): pass
                def pack_forget(self): self._packed = False
                def pack_configure(self, *a, **kw): pass

            class DummyLabel(DummyFrame):
                def __init__(self, master=None, **kwargs):
                    super().__init__(master, **kwargs)
                    self._text = kwargs.get('text', '')
                    self._textvar = kwargs.get('textvariable', None)
                def configure(self, **kwargs):
                    if 'text' in kwargs:
                        self._text = kwargs['text']
                def cget(self, key):
                    if key == 'text':
                        return self._text
                    return ''

            class DummyButton(DummyLabel):
                def __init__(self, master=None, **kwargs):
                    super().__init__(master, **kwargs)
                    self._state = kwargs.get('state', 'normal')
                def pack_forget(self):
                    self._state = ''
                def pack(self, *a, **kw):
                    self._state = 'normal'
                def cget(self, key):
                    if key == 'text':
                        return self._text
                    if key == 'state':
                        return self._state
                    return ''

            class DummyCanvas(DummyFrame):
                def __init__(self, master=None, **kwargs):
                    super().__init__(master, **kwargs)
                def delete(self, *args, **kwargs): pass
                def create_rectangle(self, *args, **kwargs): pass

            class DummyOptionMenu(DummyFrame):
                def __init__(self, master=None, **kwargs):
                    super().__init__(master, **kwargs)

            # Patch the top-level customtkinter names so other modules use them
            import customtkinter as ctk
            self._patches = []
            self._patches.append(patch('customtkinter.CTkFrame', DummyFrame))
            self._patches.append(patch('customtkinter.CTkLabel', DummyLabel))
            self._patches.append(patch('customtkinter.CTkButton', DummyButton))
            self._patches.append(patch('customtkinter.CTkCanvas', DummyCanvas))
            self._patches.append(patch('customtkinter.CTkFont', lambda *a, **k: None))
            self._patches.append(patch('customtkinter.CTkOptionMenu', DummyOptionMenu))
            for p in self._patches:
                p.start()

            self.root = DummyMaster()

        # Create DJ view
        self.dj = DJFrameView(self.root, self.state, self.theme, self.settings)
        # Pack the frame so widgets can be mapped and manipulated during test
        try:
            self.dj.pack()
        except Exception:
            pass

        # If we are using dummy GUI, ensure the save button is in a known default state
        if not using_real_tk:
            try:
                # Ensure the button is considered hidden initially
                if hasattr(self.dj.save_btn, 'pack_forget'):
                    self.dj.save_btn.pack_forget()
            except Exception:
                pass

        # Register listener so DJ view is notified on metadata changes
        metadata_extractor.register_bpm_listener(self.dj._on_bpm_metadata_changed)

    def tearDown(self):
        try:
            metadata_extractor.unregister_bpm_listener(self.dj._on_bpm_metadata_changed)
        except Exception:
            pass
        # Stop any started patchers
        if hasattr(self, '_patches'):
            for p in self._patches:
                try:
                    p.stop()
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

    def test_save_then_remove_bpm_shows_save_button(self):
        # 1) Estimation complete -> save button appears
        # Emulate the state set by update_info where _estimating_file is set
        self.dj._estimating_file = self.filepath
        self.dj._finish_estimation(self.filepath, 123.4)
        self.root.update()
        # Some test environments don't map widgets; check configuration instead
        self.assertEqual(self.dj.save_btn.cget('text'), 'Save BPM')
        self.assertEqual(self.dj.save_btn.cget('state'), 'normal')

        # 2) Simulate saving to disk (write bpm), then call save completion handler
        # Ensure we have a cached estimate
        self.assertIsNotNone(self.dj.current_temp_bpm, "Estimated BPM should be cached before save")
        write_bpm(self.filepath, 123.4)
        # Simulate worker completion
        self.dj._on_bpm_save_complete(self.filepath, True)
        self.root.update()
        # After save we keep cached estimate, but the button should be hidden
        self.assertEqual(self.dj.save_btn.winfo_manager(), "", "Save button should be hidden after successful save")
        self.assertIsNotNone(self.dj.current_temp_bpm, "Estimated BPM should remain cached after successful save")

        # 3) Remove BPM via save_metadata
        success = save_metadata(self.filepath, {'bpm': ''})
        self.assertTrue(success, "save_metadata should succeed when removing BPM")

        # Allow notification to propagate and UI to update
        # Use small wait loop to process any scheduled callbacks
        for _ in range(10):
            self.root.update()
            time.sleep(0.02)

        # Since we had a cached estimate, Save button should reappear immediately
        self.assertEqual(self.dj.save_btn.cget('text'), 'Save BPM')
        self.assertEqual(self.dj.save_btn.cget('state'), 'normal')
        # And our cached estimate should still be available
        self.assertIsNotNone(self.dj.current_temp_bpm)

    def test_remove_bpm_triggers_reestimate_and_shows_save_on_completion(self):
        # Ensure DJ has no cached estimate
        self.dj.current_temp_bpm = None

        # Put a BPM on disk (simulate existing metadata) - use write_bpm for better format support
        success = write_bpm(self.filepath, 120)
        self.assertTrue(success, "Initial write_bpm should succeed")

        # Now remove the BPM
        success = save_metadata(self.filepath, {'bpm': ''})
        self.assertTrue(success, "save_metadata should succeed when removing BPM")

        # Allow notification to propagate and UI to update
        for _ in range(10):
            self.root.update()
            time.sleep(0.02)

        # DJ should have started a re-estimation (estimating_file set and UI updated)
        self.assertEqual(self.dj._estimating_file, self.filepath)
        self.assertEqual(self.dj.bpm_var.get(), "Estimating...")

        # Simulate analysis completion with a new estimate
        self.dj._on_bpm_analysis_complete(self.filepath, 111.5)
        self.root.update()

        # After completion, Save button should be visible and estimate cached
        self.assertEqual(self.dj.save_btn.cget('text'), 'Save BPM')
        self.assertEqual(self.dj.save_btn.cget('state'), 'normal')
        self.assertAlmostEqual(self.dj.current_temp_bpm, 111.5)

if __name__ == '__main__':
    unittest.main()
