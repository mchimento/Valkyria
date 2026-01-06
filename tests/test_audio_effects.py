import unittest
from unittest.mock import Mock, patch
import tkinter as tk
import os
import numpy as np
from audio.audio_effects import AudioEffects

# Detect whether Tkinter is available and usable (not just present in the environment)
HAS_DISPLAY = os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY') or os.name == 'nt'
if HAS_DISPLAY:
    try:
        _tmp_root = tk.Tk()
        _tmp_root.destroy()
    except Exception:
        HAS_DISPLAY = False


@unittest.skipUnless(HAS_DISPLAY, "Requires display for Tkinter")
class TestAudioEffectsWindow(unittest.TestCase):
    """Unit tests for AudioEffectsWindow audio effects functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        """Clean up test resources."""
        try:
            self.root.destroy()
        except:
            pass

    def _create_mock_player(self):
        """Create a mock player with all necessary methods."""
        mock_player = Mock()
        # Equalizer methods
        mock_player.set_equalizer_enabled = Mock()
        mock_player.set_equalizer_preamp = Mock()
        mock_player.set_equalizer_band = Mock()
        mock_player.get_equalizer_preamp = Mock(return_value=0.0)
        mock_player.get_equalizer_band = Mock(return_value=0.0)
        mock_player.get_equalizer_enabled = Mock(return_value=False)

        # Playback rate methods
        mock_player.get_playback_rate = Mock(return_value=1.0)
        mock_player.set_playback_rate = Mock()

        # Compressor methods
        mock_player.get_compressor_enabled = Mock(return_value=False)
        mock_player.set_compressor = Mock()

        # Spatializer methods
        mock_player.get_spatializer_enabled = Mock(return_value=False)
        mock_player.set_spatializer = Mock()

        # Vocal remover methods
        mock_player.get_channel_mode = Mock(return_value='stereo')
        mock_player.get_vocal_remover_enabled = Mock(return_value=False)
        mock_player.get_vocal_remover_intensity = Mock(return_value=0.5)
        mock_player.set_vocal_remover_enabled = Mock()
        mock_player.set_vocal_remover_intensity = Mock()
        mock_player.set_channel_mode = Mock()

        return mock_player

    def _create_mock_theme(self):
        """Create a mock theme manager with palette."""
        mock_theme = Mock()
        mock_theme.palette = {
            'bg': '#1E1E1E',
            'fg': '#CCCCCB',
            'accent': '#BB86FC',
            'accent_hover': '#985EFF',
            'border': '#3E3E3E',
            'switch_bg': '#4A4A4A',
            'slider_bg': '#404040',
            'slider_fg': '#BB86FC',
            'button_bg_color': '#BB86FC',
            'button_fg_color': '#1E1E1E'
        }
        return mock_theme

    @patch('ui.audio_effects_window.logger')
    def test_equalizer_preset_applied_on_enable(self, mock_logger):
        """Test that when equalizer is enabled, the selected preset is applied."""
        from ui.audio_effects_window import AudioEffectsWindow

        # Create mock player and theme
        mock_player = self._create_mock_player()
        mock_theme = self._create_mock_theme()

        # Create window
        window = AudioEffectsWindow(self.root, mock_player, mock_theme)

        # Select a preset
        preset_name = "Rock"
        window.preset_var.set(preset_name)
        window._on_preset_change(preset_name)

        # Verify preset values were applied to UI
        expected_preamp = -7
        expected_gains = [8, 4.8, -5.6, -8, -3.2, 4, 8.8, 11.2, 11.2, 11.2]

        self.assertEqual(window.preamp_var.get(), expected_preamp)
        for i, expected_gain in enumerate(expected_gains):
            self.assertAlmostEqual(window.slider_vars[i].get(), expected_gain, places=1)

        # Now enable equalizer
        window.enabled_var.set(True)
        window._on_enable_toggle()

        # Verify player methods were called with preset values
        mock_player.set_equalizer_enabled.assert_called_with(True)
        mock_player.set_equalizer_preamp.assert_called_with(expected_preamp)

        # Verify all bands were set with expected values
        window.destroy()

    @patch('ui.audio_effects_window.logger')
    def test_preset_change_applies_new_values(self, mock_logger):
        """Test that changing preset updates all slider values and applies them."""
        from ui.audio_effects_window import AudioEffectsWindow

        # Create mock player and theme
        mock_player = self._create_mock_player()
        mock_theme = self._create_mock_theme()

        # Create window with equalizer enabled
        window = AudioEffectsWindow(self.root, mock_player, mock_theme)
        window.enabled_var.set(True)

        # Apply first preset (Rock)
        preset1 = "Rock"
        window.preset_var.set(preset1)
        window._on_preset_change(preset1)

        rock_preamp = -7
        rock_gains = [8, 4.8, -5.6, -8, -3.2, 4, 8.8, 11.2, 11.2, 11.2]

        # Verify Rock preset is applied to UI
        self.assertEqual(window.preamp_var.get(), rock_preamp)
        for i, expected_gain in enumerate(rock_gains):
            self.assertAlmostEqual(window.slider_vars[i].get(), expected_gain, places=1)

        # Reset mock call counts
        mock_player.set_equalizer_preamp.reset_mock()
        mock_player.set_equalizer_band.reset_mock()

        # Change to different preset (Pop)
        preset2 = "Pop"
        window.preset_var.set(preset2)
        window._on_preset_change(preset2)

        pop_preamp = -6
        pop_gains = [-1.6, 4.8, 7.2, 8, 5.6, 0, -2.4, -2.4, -1.6, -1.6]

        # Verify Pop preset is now applied to UI
        self.assertEqual(window.preamp_var.get(), pop_preamp)
        for i, expected_gain in enumerate(pop_gains):
            self.assertAlmostEqual(window.slider_vars[i].get(), expected_gain, places=1)

        # Verify player methods were called for new preset
        mock_player.set_equalizer_preamp.assert_called_with(pop_preamp)
        expected_calls = [((i, pop_gains[i]),) for i in range(len(pop_gains))]
        mock_player.set_equalizer_band.assert_has_calls(expected_calls)

        window.destroy()

    @patch('ui.audio_effects_window.logger')
    def test_compressor_toggle_and_parameters(self, mock_logger):
        """Test compressor enable/disable and parameter changes."""
        from ui.audio_effects_window import AudioEffectsWindow

        # Create mock player and theme
        mock_player = self._create_mock_player()
        mock_theme = self._create_mock_theme()

        # Create window
        window = AudioEffectsWindow(self.root, mock_player, mock_theme)

        # Test enabling compressor
        window.compressor_enabled_var.set(True)
        window._on_compressor_toggle()

        # Verify set_compressor was called with correct parameters
        mock_player.set_compressor.assert_called_with(
            enabled=True,
            threshold=window.compressor_threshold_var.get(),
            ratio=window.compressor_ratio_var.get(),
            attack=window.compressor_attack_var.get(),
            release=window.compressor_release_var.get(),
            makeup_gain=window.compressor_makeup_var.get(),
            knee=window.compressor_knee_var.get(),
            use_rms=window.compressor_rms_mode_var.get()
        )

        # Test disabling compressor
        mock_player.set_compressor.reset_mock()
        window.compressor_enabled_var.set(False)
        window._on_compressor_toggle()

        mock_player.set_compressor.assert_called_with(
            enabled=False,
            threshold=window.compressor_threshold_var.get(),
            ratio=window.compressor_ratio_var.get(),
            attack=window.compressor_attack_var.get(),
            release=window.compressor_release_var.get(),
            makeup_gain=window.compressor_makeup_var.get(),
            knee=window.compressor_knee_var.get(),
            use_rms=window.compressor_rms_mode_var.get()
        )

        window.destroy()

    @patch('ui.audio_effects_window.logger')
    def test_spatializer_toggle_and_parameters(self, mock_logger):
        """Test spatializer enable/disable and parameter changes."""
        from ui.audio_effects_window import AudioEffectsWindow

        # Create mock player and theme
        mock_player = self._create_mock_player()
        mock_theme = self._create_mock_theme()

        # Create window
        window = AudioEffectsWindow(self.root, mock_player, mock_theme)

        # Test enabling spatializer
        window.spatializer_enabled_var.set(True)
        window._on_spatializer_toggle()

        # Verify set_spatializer was called with correct parameters
        mock_player.set_spatializer.assert_called_with(
            enabled=True,
            size=window.spat_size_var.get(),
            width=window.spat_width_var.get(),
            wet=window.spat_wet_var.get(),
            dry=window.spat_dry_var.get(),
            damp=window.spat_damp_var.get()
        )

        # Test disabling spatializer
        mock_player.set_spatializer.reset_mock()
        window.spatializer_enabled_var.set(False)
        window._on_spatializer_toggle()

        mock_player.set_spatializer.assert_called_with(
            enabled=False,
            size=window.spat_size_var.get(),
            width=window.spat_width_var.get(),
            wet=window.spat_wet_var.get(),
            dry=window.spat_dry_var.get(),
            damp=window.spat_damp_var.get()
        )

        window.destroy()

    @patch('ui.audio_effects_window.logger')
    def test_vocal_remover_toggle_and_intensity(self, mock_logger):
        """Test vocal remover enable/disable and intensity changes."""
        from ui.audio_effects_window import AudioEffectsWindow

        # Create mock player and theme
        mock_player = self._create_mock_player()
        mock_theme = self._create_mock_theme()

        # Create window
        window = AudioEffectsWindow(self.root, mock_player, mock_theme)

        # Test enabling vocal remover
        window.vocal_remover_var.set(True)
        window._on_vocal_remover_toggle()

        mock_player.set_vocal_remover_enabled.assert_called_with(True)

        # Test changing intensity
        test_intensity = 0.8
        window._on_vocal_intensity_change(test_intensity)

        mock_player.set_vocal_remover_intensity.assert_called_with(test_intensity)

        # Test disabling vocal remover
        window.vocal_remover_var.set(False)
        window._on_vocal_remover_toggle()

        mock_player.set_vocal_remover_enabled.assert_called_with(False)

        window.destroy()

    @patch('ui.audio_effects_window.logger')
    def test_playback_speed_changes(self, mock_logger):
        """Test playback speed parameter changes."""
        from ui.audio_effects_window import AudioEffectsWindow

        # Create mock player and theme
        mock_player = self._create_mock_player()
        mock_theme = self._create_mock_theme()

        # Create window
        window = AudioEffectsWindow(self.root, mock_player, mock_theme)

        # Test changing playback rate
        test_rate = 1.25
        window.rate_var.set(test_rate)
        window._on_rate_change(test_rate)

        mock_player.set_playback_rate.assert_called_with(test_rate)

        # Test reset speed
        window._reset_speed()
        mock_player.set_playback_rate.assert_called_with(1.0)

        window.destroy()

    @patch('ui.audio_effects_window.logger')
    def test_channel_mode_changes(self, mock_logger):
        """Test channel mode parameter changes."""
        from ui.audio_effects_window import AudioEffectsWindow

        # Create mock player and theme
        mock_player = self._create_mock_player()
        mock_theme = self._create_mock_theme()

        # Create window
        window = AudioEffectsWindow(self.root, mock_player, mock_theme)

        # Test changing channel mode
        test_mode = "Mono"
        window._on_channel_mode_change(test_mode)

        mock_player.set_channel_mode.assert_called_with(test_mode)

        window.destroy()


class TestAudioEffectsProcessing(unittest.TestCase):

    def setUp(self):
        # Basic config for the test
        config = {
            'spatializer': {
                'enabled': True,
                'size': 0.9,
                'width': 0.8,
                'wet': 0.5,
                'dry': 0.6,
                'damp': 0.4
            }
        }
        defaults = {}
        self.audio_effects = AudioEffects(config, defaults)
        self.samplerate = 44100
        self.channels = 2
        self.audio_effects.prepare(self.samplerate, self.channels)

    def test_spatializer_reset_state_prevents_ghost_noise(self):
        """
        Tests that reset_state() clears the spatializer's internal buffers,
        preventing audio from a previous run from bleeding into the next.
        """
        # 1. Process a distinct audio signal
        # A sine wave at 440Hz for 0.1 seconds
        duration = 0.1
        frequency = 440
        t = np.linspace(0., duration, int(self.samplerate * duration), endpoint=False)
        signal = 0.5 * np.sin(2. * np.pi * frequency * t)

        # Make it stereo
        stereo_signal = np.column_stack([signal, signal])

        # Process this signal. This will populate the spatializer's internal buffers.
        self.audio_effects.set_spatializer(enabled=True)
        processed_signal = self.audio_effects.process(stereo_signal.copy())

        # Check that some processing happened
        self.assertFalse(np.allclose(processed_signal, stereo_signal))

        # 2. Reset the state
        self.audio_effects.reset_state()

        # 3. Process a block of silence
        silence = np.zeros_like(stereo_signal)
        processed_silence = self.audio_effects.process(silence.copy())

        # 4. Assert that the output is silence
        # The output should be very close to zero. We allow a small tolerance
        # for floating point inaccuracies.
        self.assertTrue(np.allclose(processed_silence, 0, atol=1e-9),
                        "Processed silence should be silent after reset_state.")


if __name__ == '__main__':
    unittest.main()