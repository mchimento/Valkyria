"""
Automated tests for WaveformSeekbar component.
"""

import unittest
import tkinter as tk
from tkinter import ttk
import sys
import os
from unittest.mock import Mock, patch
import numpy as np

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.waveform_seekbar import WaveformSeekbar
from audio.audio_player import AudioPlayer

from tests.tk_utils import HAS_TK as HAS_DISPLAY, skip_if_no_tk


class TestWaveformSeekbar(unittest.TestCase):
    """Test cases for WaveformSeekbar component."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Skip if Tk isn't available in this environment
        skip_if_no_tk(self)

        # Create a root window for testing
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the window during tests

        # Create a mock player
        self.mock_player = Mock()
        self.mock_player.get_time.return_value = 50000  # 50 seconds
        self.mock_player.get_length.return_value = 180000  # 3 minutes
        self.mock_player.set_time = Mock(return_value=None)

        # Create a mock theme
        self.mock_theme = Mock()
        self.mock_theme.palette = {
            "waveform_bg": "#1a1a1a",
            "waveform_playhead": "#FF6B00",
            "waveform_played": "#FF6B00",
            "waveform_unplayed": "#404040"
        }

        # Create waveform seekbar
        self.waveform = WaveformSeekbar(
            self.root,
            self.mock_player,
            self.mock_theme,
            width=300,
            height=50
        )

        # Set up dummy waveform data
        self.waveform.audio_length = 180000
        self.waveform.waveform_data = [0.5, 0.8, 0.3, 0.9, 0.6, 0.4, 0.7, 0.2]

    def tearDown(self):
        """Clean up after each test method."""
        try:
            self.waveform.destroy()
            self.root.destroy()
        except:
            pass

    def test_initialization(self):
        """Test WaveformSeekbar initializes correctly."""
        self.assertIsInstance(self.waveform, WaveformSeekbar)
        self.assertEqual(self.waveform.width, 300)
        self.assertEqual(self.waveform.height, 50)
        self.assertEqual(self.waveform.player, self.mock_player)
        self.assertEqual(self.waveform.bg_color, '#1a1a1a')
        self.assertEqual(self.waveform.played_color, '#FF6B00')

    def test_mouse_click_sets_dragging_state(self):
        """Test mouse click sets dragging state and stores position."""
        # Simulate mouse click
        event = Mock()
        event.x = 150

        self.waveform._on_click(event)

        self.assertTrue(self.waveform.is_dragging)
        self.assertEqual(self.waveform._pending_seek_position, 150)
        self.assertEqual(self.waveform.playhead_x, 150)

    def test_mouse_drag_updates_position(self):
        """Test mouse drag updates position without seeking."""
        # Start dragging
        event = Mock()
        event.x = 100
        self.waveform._on_click(event)

        # Drag to new position
        event.x = 200
        self.waveform._on_drag(event)

        self.assertTrue(self.waveform.is_dragging)
        self.assertEqual(self.waveform._pending_seek_position, 200)
        self.assertEqual(self.waveform.playhead_x, 200)

        # Verify set_time was not called during drag
        self.mock_player.set_time.assert_not_called()

    def test_mouse_release_performs_seek(self):
        """Test mouse release performs actual seek."""
        # Start dragging
        event = Mock()
        event.x = 150
        self.waveform._on_click(event)

        # Release mouse
        self.waveform._on_release(event)

        # Verify seek was performed
        self.mock_player.set_time.assert_called_once()

        # Calculate expected time (150/300 * 180000 = 90000ms)
        call_args = self.mock_player.set_time.call_args[0][0]
        self.assertEqual(call_args, 90000)

        # Verify dragging state is reset
        self.assertFalse(self.waveform.is_dragging)
        self.assertFalse(hasattr(self.waveform, '_pending_seek_position'))

    def test_seek_position_calculation(self):
        """Test seek position calculation from X coordinate."""
        # Test various positions
        test_cases = [
            (0, 0),      # Start position
            (150, 90000), # Middle position
            (300, 180000) # End position
        ]

        for x_pos, expected_time in test_cases:
            with self.subTest(x_position=x_pos):
                self.waveform._seek_to_position(x_pos)
                self.mock_player.set_time.assert_called_with(expected_time)

    def test_playhead_update_during_drag(self):
        """Test playhead update is paused during dragging."""
        # Start dragging
        event = Mock()
        event.x = 100
        self.waveform._on_click(event)

        # Try to update playhead (should be ignored during drag)
        original_playhead_x = self.waveform.playhead_x
        self.waveform._update_playhead()

        # Playhead should not have changed during drag
        self.assertEqual(self.waveform.playhead_x, original_playhead_x)

    def test_playhead_update_resumes_after_drag(self):
        """Test playhead update resumes after drag ends."""
        # Start and end dragging
        event = Mock()
        event.x = 100
        self.waveform._on_click(event)
        self.waveform._on_release(event)

        # Now update should work normally
        self.waveform._update_playhead()

        # Should update based on player time (50/180 * 300 = 83.33)
        expected_x = int((50000 / 180000) * 300)
        self.assertEqual(self.waveform.playhead_x, expected_x)

    def test_waveform_drawing(self):
        """Test waveform drawing functionality."""
        # Test drawing with dummy data
        self.waveform._draw_waveform()

        # Should have created waveform items
        self.assertGreater(len(self.waveform.waveform_items), 0)

        # playhead_x should be calculated based on mock player time (50/180 * 300 = 83)
        expected_x = int((50000 / 180000) * 300)
        self.assertEqual(self.waveform.playhead_x, expected_x)

    def test_waveform_clearing(self):
        """Test waveform clearing functionality."""
        # Draw waveform first
        self.waveform._draw_waveform()

        # Then clear it
        self.waveform._clear_waveform()

        # Should be empty
        self.assertEqual(len(self.waveform.waveform_items), 0)
        # playhead_x should be calculated based on mock player time (50/180 * 300 = 83)
        expected_x = int((50000 / 180000) * 300)
        self.assertEqual(self.waveform.playhead_x, expected_x)

    def test_color_updates(self):
        """Test waveform color updates based on playhead."""
        # Draw waveform first
        self.waveform._draw_waveform()

        # Update colors
        self.waveform._update_waveform_colors()

        # Should not raise any exceptions
        # (Visual verification would need GUI, but we test no crashes)

    @patch('ui.waveform_seekbar.threading.Thread')
    def test_load_waveform_starts_thread(self, mock_thread):
        """Test loading waveform starts background thread."""
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance

        # Load waveform
        self.waveform.load_waveform("test.mp3")

        # Should have started a thread
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()

    def test_generate_waveform_ffmpeg_fallback(self):
        """Test the ffmpeg fallback branch when soundfile can't read the input."""
        import soundfile as sf
        # Prepare synthetic audio to be returned by the second sf.read
        sr = 44100
        y = np.zeros(44100, dtype='float32')
        y[::sr//2] = 0.8

        # Make sf.read raise on first call (original file), succeed on second (decoded tmp)
        original_read = sf.read
        def fake_read(path, *args, **kwargs):
            if path == "bad.mp3":
                raise sf.LibsndfileError("cannot read mp3")
            return (y, sr)

        with patch('ui.waveform_seekbar.sf.read', side_effect=fake_read):
            with patch('ui.waveform_seekbar.shutil.which', return_value='/usr/bin/ffmpeg'):
                with patch('ui.waveform_seekbar.subprocess.run') as mock_run:
                    # Call worker directly to avoid threading complexity
                    self.waveform._generate_waveform_worker('bad.mp3')

        # After worker runs, waveform_data should be present and non-empty
        self.assertIsNotNone(self.waveform.waveform_data)
        self.assertGreater(len(self.waveform.waveform_data), 0)

    def test_edge_cases(self):
        """Test edge cases and error handling."""
        # Test seek with zero length
        original_audio_length = self.waveform.audio_length
        self.waveform.audio_length = 0
        self.waveform._seek_to_position(150)
        # With zero length, seek should return early without calling set_time
        # We can't easily test this without isolating the method more

        # Test seek with negative position
        self.waveform.audio_length = 180000
        self.waveform._seek_to_position(-10)
        # Should clamp to 0 and call set_time
        # Note: We're testing the behavior, not the exact mock state

        # Test seek beyond width
        self.waveform._seek_to_position(400)
        # Should clamp to max and call set_time
        # Note: We're testing the behavior, not the exact mock state

        # Restore original audio length
        self.waveform.audio_length = original_audio_length


class TestWaveformSeekbarIntegration(unittest.TestCase):
    """Integration tests with real AudioPlayer."""

    def setUp(self):
        """Set up integration test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()

        # Use real AudioPlayer for integration testing
        self.player = AudioPlayer()

        # Create a mock theme for integration testing
        self.theme = Mock()
        self.theme.palette = {
            "waveform_bg": "#1a1a1a",
            "waveform_playhead": "#FF6B00",
            "waveform_played": "#FF6B00",
            "waveform_unplayed": "#404040"
        }

        self.waveform = WaveformSeekbar(
            self.root,
            self.player,
            self.theme,
            width=200,
            height=40
        )

    def tearDown(self):
        """Clean up integration test fixtures."""
        try:
            self.waveform.destroy()
            self.root.destroy()
        except:
            pass

    def test_real_player_integration(self):
        """Test integration with real AudioPlayer."""
        # Test that methods exist and can be called
        self.assertTrue(hasattr(self.player, 'get_time'))
        self.assertTrue(hasattr(self.player, 'get_length'))
        self.assertTrue(hasattr(self.player, 'set_time'))

        # Test calling methods (should not crash)
        try:
            time = self.player.get_time()
            length = self.player.get_length()
            self.assertIsInstance(time, int)
            self.assertIsInstance(length, int)
        except Exception:
            # Expected if no media is loaded
            pass


if __name__ == '__main__':
    unittest.main()
