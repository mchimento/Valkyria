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


if __name__ == '__main__':
    unittest.main()
