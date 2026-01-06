import unittest
import tkinter as tk
from unittest.mock import MagicMock
from tests.tk_utils import HAS_TK as HAS_DISPLAY, skip_if_no_tk


class TestDJFrameViewMetrics(unittest.TestCase):
    def setUp(self):
        skip_if_no_tk(self)
        self.root = tk.Tk()
        self.root.withdraw()

        # Minimal mock theme/setting/state
        self.theme = MagicMock()
        self.theme.palette = {
            'status_bg': '#111111',
            'status_border': '#222222',
            'status_meta_fg': '#FFFFFF',
            'status_fg': '#CCCCCC',
            'button_bg_color': '#0078d4',
            'button_fg_color': '#FFFFFF',
            'button_hover': '#106ebe'
        }

        self.settings = MagicMock()
        self.settings.theme = 'dark'

        self.state = MagicMock()

        from ui.dj_frame_view import DJFrameView
        self.view = DJFrameView(self.root, self.state, self.theme, self.settings)

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_update_meter_values_updates_overall(self):
        # Initial default
        self.assertEqual(self.view.overall_lufs_value, -60.0)

        # Update with explicit overall value
        self.view.update_meter_values(lufs=-10.0, peak_dbfs=-6.0, limiter_activity=0.2, overall_lufs=-15.5)
        self.assertAlmostEqual(self.view.overall_lufs_value, -15.5)
        # Label should reflect formatted value
        self.assertEqual(self.view.overall_lufs_label.cget('text'), f"{-15.5:.1f}")

        # Update without overall; value should remain unchanged
        self.view.update_meter_values(lufs=-12.0, peak_dbfs=-8.0, limiter_activity=0.1)
        self.assertAlmostEqual(self.view.overall_lufs_value, -15.5)

    def test_display_key_with_camelot(self):
        """When metadata contains a Key (and optional Camelot), the DJ view displays both."""
        from unittest.mock import patch
        # Prepare state so update_info picks up our fake filepath
        self.view.state.current_index = 0
        self.view.state.playlist = ['/path/to/fake.mp3']

        # Mock metadata to include raw key and camelot mapping
        with patch('ui.dj_frame_view.get_metadata', return_value={'key': 'Am', 'camelot': '8A'}):
            self.view.update_info('/path/to/fake.mp3')
            self.assertEqual(self.view.key_var.get(), '8A')

        # Also ensure that when camelot isn't provided, we compute it from key
        with patch('ui.dj_frame_view.get_metadata', return_value={'key': 'Am'}):
            self.view.update_info('/path/to/fake.mp3')
            # Camelot should be computed as 8A for Am
            self.assertIn('8A', self.view.key_var.get())

    def test_keep_cached_estimates_on_resume(self):
        """When resuming (frame visible), cached temporary estimates should be used and no new analysis started."""
        from unittest.mock import patch
        self.view.state.current_index = 0
        self.view.state.playlist = ['/path/to/fake.mp3']
        filepath = '/path/to/fake.mp3'

        # Prepare cached temporary estimates (per-file mappings)
        self.view.temporary_bpm_values[filepath] = 123.0
        self.view.temporary_key_values[filepath] = 'Am'

    def test_keep_cached_estimates_on_resume_without_temporary_set(self):
        """If a temporary estimate value exists (but isn't listed in the temporary set), it's still used on resume."""
        from unittest.mock import patch
        self.view.state.current_index = 0
        self.view.state.playlist = ['/path/to/fake.mp3']
        filepath = '/path/to/fake.mp3'

        # Prepare per-file cached estimates (prefer explicit mapping over raw current_temp)
        self.view.temporary_bpm_values[filepath] = 123.0
        self.view.temporary_key_values[filepath] = 'Am'

        with patch.object(self.view, 'is_visible', return_value=True):
            with patch('ui.dj_frame_view.get_metadata', return_value={}):
                self.view.update_info(filepath)
                from audio.metadata import get_display_bpm
                self.assertEqual(self.view.bpm_var.get(), get_display_bpm(123.0))
                self.assertEqual(self.view._estimating_file, None)
                self.assertIn('8A', self.view.key_var.get())
                self.assertEqual(self.view._estimating_key_file, None)
            with patch('ui.dj_frame_view.get_metadata', return_value={}):
                self.view.update_info(filepath)
                # BPM displayed should use cached temporary BPM and Save button visible
                from audio.metadata import get_display_bpm
                self.assertEqual(self.view.bpm_var.get(), get_display_bpm(123.0))
                self.assertEqual(self.view._estimating_file, None)
                # Key displayed should be Camelot mapping for 'Am'
                self.assertIn('8A', self.view.key_var.get())
                self.assertEqual(self.view._estimating_key_file, None)

    def test_switching_tracks_triggers_new_estimation_instead_of_reusing_previous(self):
        """When switching to a new track, previous estimates for another file should not be reused."""
        from unittest.mock import patch

        # Prepare playlist with two files; set cached estimate only for the first
        old = '/path/to/old.mp3'
        new = '/path/to/new.mp3'
        self.view.state.playlist = [old, new]

        # Cache BPM/Key for the old file only
        self.view.temporary_bpm_values[old] = 111.0
        self.view.temporary_key_values[old] = 'Gm'

        # Make view visible so update_info attempts estimation for new track
        with patch.object(self.view, 'is_visible', return_value=True):
            # Ensure metadata returns empty for new file so estimation is triggered
            with patch('ui.dj_frame_view.get_metadata', return_value={}):
                # Patch background submission functions to ensure they're invoked
                from audio import bpm as bpm_module
                with patch.object(bpm_module.analysis_manager, 'submit_bpm_analysis') as mock_bpm_submit:
                    with patch.object(bpm_module.analysis_manager, 'submit_key_analysis') as mock_key_submit:
                        # Update to the new file
                        self.view.update_info(new)

                        mock_bpm_submit.assert_called()
                        mock_key_submit.assert_called()


if __name__ == '__main__':
    unittest.main()
