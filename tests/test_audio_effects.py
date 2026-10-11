import unittest
import numpy as np
from audio.audio_effects import AudioEffects


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
