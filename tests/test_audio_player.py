import time
import unittest
from unittest.mock import Mock, MagicMock, patch
import numpy as np
from audio.audio_player import AudioPlayer

class TestAudioPlayer(unittest.TestCase):
    """Unit tests for AudioPlayer class."""

    def test_initialization(self):
        """Test that AudioPlayer initializes correctly."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()  # Don't pass path to avoid file opening
            self.assertIsNone(player._buffer)  # _buffer is None until play() is called
            self.assertFalse(player._muted)
            self.assertFalse(player._paused)
            self.assertFalse(player._stopped_manually)

    def test_track_end_callback(self):
        """Test that track end callback is invoked."""
        callback = Mock()
        player = AudioPlayer(on_track_end=callback)

        # Simulate track end event by calling the callback method directly
        player._on_stream_finished()

        callback.assert_called_once()

    def test_pause(self):
        """Test that pause method pauses playback."""
        with patch('sounddevice.play') as mock_play, \
             patch('sounddevice.OutputStream') as mock_stream:
            player = AudioPlayer()
            # Mock the stream
            mock_stream_instance = MagicMock()
            mock_stream.return_value = mock_stream_instance
            player._stream = mock_stream_instance
            player.pause()
            self.assertTrue(player._paused)

    def test_stop(self):
        """Test that stop method stops playback."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()
            player.stop()
            self.assertTrue(player._stopped_manually)
            self.assertIsNone(player._buffer)

    def test_set_volume(self):
        """Test that set_volume method sets volume."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()
            player.set_volume(75)
            self.assertEqual(player._volume, 75)

    def test_get_mute_state(self):
        """Test get_mute_state returns correct state."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()
            # Default should be False
            self.assertFalse(player.get_mute_state())

            # Manually set to True
            player._muted = True
            self.assertTrue(player.get_mute_state())

    def test_set_mute(self):
        """Test set_mute updates state correctly."""
        with patch('sounddevice.play') as mock_play:
            player = AudioPlayer()

            player.set_mute(True)
            self.assertTrue(player.get_mute_state())

            player.set_mute(False)
            self.assertFalse(player.get_mute_state())

    def test_cleanup(self):
        """Test that cleanup method properly cleans up audio resources."""
        with patch('sounddevice.play') as mock_play, \
             patch('sounddevice.stop') as mock_sd_stop, \
             patch('sounddevice.OutputStream') as mock_stream_class:

            player = AudioPlayer()

            # Create mock stream and buffer
            mock_stream = MagicMock()
            mock_buffer = MagicMock()

            player._stream = mock_stream
            player._buffer = mock_buffer

            # Call cleanup
            player.__del__()

            # Verify stream was stopped and closed
            mock_stream.stop.assert_called_once()
            mock_stream.close.assert_called_once()

            # Verify buffer was closed
            mock_buffer.close.assert_called_once()

            # Verify sounddevice.stop was called
            mock_sd_stop.assert_called_once()

            # Verify references were cleared
            self.assertIsNone(player._stream)
            self.assertIsNone(player._buffer)

    def test_cleanup_with_exceptions(self):
        """Test that cleanup handles exceptions gracefully."""
        with patch('sounddevice.play') as mock_play, \
             patch('sounddevice.stop') as mock_sd_stop, \
             patch('sounddevice.OutputStream') as mock_stream_class:

            player = AudioPlayer()

            # Create mock stream and buffer that raise exceptions
            mock_stream = MagicMock()
            mock_stream.stop.side_effect = Exception("Stop failed")
            # Note: close() won't be called if stop() fails due to same try block

            mock_buffer = MagicMock()
            mock_buffer.close.side_effect = Exception("Buffer close failed")

            mock_sd_stop.side_effect = Exception("SD stop failed")

            player._stream = mock_stream
            player._buffer = mock_buffer

            # Call cleanup - should not raise exceptions
            player.__del__()

            # Verify methods were attempted despite exceptions
            mock_stream.stop.assert_called_once()
            # close() is not called if stop() fails (same try block)
            mock_buffer.close.assert_called_once()
            mock_sd_stop.assert_called_once()

            # Verify references were still cleared
            self.assertIsNone(player._stream)
            self.assertIsNone(player._buffer)


class TestAudioPlayerResample(unittest.TestCase):
    """Tests for the stateful resampler in AudioPlayer."""

    class DummyBuffer:
        def __init__(self, channels=2):
            self.channels = channels
            self.samplerate = 44100
            self.absolute_read_pos = 0
            self.eof = False
            self._offset = 0

        def read(self, frames):
            # Simulate read returning more frames than requested (e.g., due to rate changes)
            # Return 1704 frames of stereo audio (float32) with a slight offset per read
            n = 1704
            data = np.zeros((n, self.channels), dtype="float32")
            # Fill with a simple ramp so values are deterministic and different per read
            for ch in range(self.channels):
                start = -0.5 + (self._offset * 1e-3)
                end = 0.5 + (self._offset * 1e-3)
                data[:, ch] = np.linspace(start, end, n, dtype="float32")
            self._offset += 1
            return data

    def test_stream_callback_resample_does_not_broadcast_error(self):
        player = AudioPlayer()

        # Replace real effects with identity to avoid side-effects or state requirements
        player.effects.process = lambda x: x

        # Attach dummy buffer and set a playback rate that triggers resampling
        player._buffer = self.DummyBuffer(channels=2)
        player._playback_rate = 1.5

        # Create outdata buffer matching a smaller frame request (e.g., 1136 frames)
        frames = 1136
        outdata = np.zeros((frames, 2), dtype="float32")

        # Call the callback - it should not raise
        player._stream_callback(outdata, frames, None, None)

        # Ensure outdata contains non-zero data after processing (resampled/interpolated)
        self.assertFalse(np.allclose(outdata, 0), "outdata appears to be silent after callback")

    def test_resampler_stateful_continuity(self):
        player = AudioPlayer()
        player.effects.process = lambda x: x
        player._buffer = self.DummyBuffer(channels=2)
        player._playback_rate = 1.5

        frames = 1136
        out1 = np.zeros((frames, 2), dtype="float32")
        player._stream_callback(out1, frames, None, None)

        # Capture resampler position after first callback
        pos_after_first = getattr(player, '_resample_pos', None)

        out2 = np.zeros((frames, 2), dtype="float32")
        player._stream_callback(out2, frames, None, None)

        # Ensure both outputs are non-silent and the resampler state is reasonable
        self.assertFalse(np.allclose(out1, 0))
        self.assertFalse(np.allclose(out2, 0))
        self.assertIsNotNone(pos_after_first)
        self.assertGreaterEqual(pos_after_first, 0.0)

        # Resample buffer should not grow unbounded for this use-case
        buf_len = getattr(player, '_resample_buffer', np.zeros((0,))).shape[0]
        self.assertLess(buf_len, 5000)


class TestAudioPlayerSilenceDetection(unittest.TestCase):
    """Regression tests for silence-detection auto-skip in _stream_callback."""

    class ConstantLevelBuffer:
        """Fake AudioBuffer returning a constant amplitude on every read."""

        def __init__(self, amplitude, channels=2, samplerate=44100):
            self.channels = channels
            self.samplerate = samplerate
            self.absolute_read_pos = 0
            self.eof = False
            self._amplitude = amplitude

        def read(self, frames):
            return np.full((frames, self.channels), self._amplitude, dtype="float32")

        def seek(self, frame_pos):
            self.absolute_read_pos = frame_pos

    def _make_player(self, amplitude, total_frames, frames_played, volume=100):
        player = AudioPlayer()
        player.effects.process = lambda x: x
        player.silence_detection_enabled = True
        player._buffer = self.ConstantLevelBuffer(amplitude=amplitude)
        player._total_frames = total_frames
        player._frames_played = frames_played
        player._volume = volume
        return player

    def _run_quiet_callbacks(self, player, seconds=4.5, frames=4410):
        # Stops as soon as _silence_detected flips.
        outdata = np.zeros((frames, 2), dtype="float32")
        for _ in range(int(seconds * 44100 / frames) + 1):
            player._stream_callback(outdata, frames, None, None)
            if player._silence_detected:
                break

    def test_quiet_intro_does_not_trigger_near_start_of_track(self):
        player = self._make_player(
            amplitude=1e-4, total_frames=44100 * 300, frames_played=0,
        )
        self._run_quiet_callbacks(player)
        self.assertFalse(player._silence_detected)

    def test_quiet_stretch_near_end_of_track_triggers(self):
        total_frames = 44100 * 100
        player = self._make_player(
            amplitude=1e-4, total_frames=total_frames,
            frames_played=total_frames - 44100 * 5,
        )
        self._run_quiet_callbacks(player)
        self.assertTrue(player._silence_detected)

    def test_long_trailing_silence_far_from_reported_end_still_triggers(self):
        # Regression: detection used to gate on proximity to total_frames
        # (remaining time <= 30s), so a file whose trailing silence is
        # itself much longer than 30s never got close enough to that
        # window to trigger — confirmed via real playback logs showing
        # 16+ continuous seconds of true digital silence with minutes still
        # "remaining" per total_frames. Gating on elapsed time since start
        # instead means this triggers as soon as real silence is detected,
        # regardless of how much of the file's reported length is left.
        total_frames = 44100 * 600  # a file with several minutes of tail silence
        player = self._make_player(
            amplitude=1e-4, total_frames=total_frames, frames_played=44100 * 40,
        )
        self._run_quiet_callbacks(player)
        self.assertTrue(player._silence_detected)

    def test_manual_seek_into_silence_soon_after_start_still_triggers(self):
        # Regression: set_time() (the waveform drag-to-seek handler) updated
        # the underlying buffer's read position but never updated
        # _frames_played to match — so seeking forward into real silence
        # shortly after starting a track left _frames_played stuck near its
        # pre-seek (near-zero) value, blocking the "30s of playback already
        # elapsed" gate for up to 30 more real seconds after the seek, even
        # though the audio being read was already genuinely silent.
        player = self._make_player(
            amplitude=1e-4, total_frames=44100 * 300, frames_played=44100 * 2,
        )
        player.set_time(200_000)  # seek to 200s, well past the elapsed-gate
        self.assertEqual(player._frames_played, 44100 * 200)
        self._run_quiet_callbacks(player)
        self.assertTrue(player._silence_detected)

    def test_measured_on_raw_source_not_volume_scaled_output(self):
        # Loud raw source + near-zero volume: must not read as silent post-volume.
        total_frames = 44100 * 100
        player = self._make_player(
            amplitude=0.5, total_frames=total_frames,
            frames_played=total_frames - 44100 * 5, volume=0.1,
        )
        self._run_quiet_callbacks(player)
        self.assertFalse(player._silence_detected)


class TestAudioPlayerMetricsVolumeIndependence(unittest.TestCase):
    """Regression tests for LUFS/peak/limiter/energy metrics being measured
    on the track's own content, not the volume/mute-scaled output — like a
    real DJ mixer's meters, which don't move just because you turn down
    the monitor."""

    class ConstantLevelBuffer:
        def __init__(self, amplitude, channels=2, samplerate=44100):
            self.channels = channels
            self.samplerate = samplerate
            self.absolute_read_pos = 0
            self.eof = False
            self._amplitude = amplitude

        def read(self, frames):
            return np.full((frames, self.channels), self._amplitude, dtype="float32")

    def _make_player(self):
        player = AudioPlayer()
        player.effects.process = lambda x: x
        player._buffer = self.ConstantLevelBuffer(amplitude=0.5)
        return player

    def _capture_one_update(self, player, frames=4410):
        received = []
        player.set_audio_metrics_callback(lambda *args: received.append(args))
        player._metrics_last_update = 0  # force the next callback to fire
        outdata = np.zeros((frames, 2), dtype="float32")
        player._stream_callback(outdata, frames, None, None)
        deadline = time.time() + 2.0
        while not received and time.time() < deadline:
            time.sleep(0.01)
        self.assertTrue(received, "metrics callback never fired")
        _lufs, _overall, peak_dbfs, _limiter, energy = received[-1]
        return peak_dbfs, energy

    def test_metrics_unaffected_by_volume(self):
        player = self._make_player()
        player._volume = 100
        full_volume_peak, full_volume_energy = self._capture_one_update(player)

        player._volume = 10
        low_volume_peak, low_volume_energy = self._capture_one_update(player)

        self.assertAlmostEqual(full_volume_peak, low_volume_peak, places=3)
        self.assertAlmostEqual(full_volume_energy, low_volume_energy, places=3)

    def test_metrics_unaffected_by_mute(self):
        player = self._make_player()
        player._volume = 100
        player._muted = False
        unmuted_peak, unmuted_energy = self._capture_one_update(player)

        player._muted = True
        muted_peak, muted_energy = self._capture_one_update(player)

        self.assertAlmostEqual(unmuted_peak, muted_peak, places=3)
        self.assertAlmostEqual(unmuted_energy, muted_energy, places=3)


class TestAudioPlayerEffectsGetters(unittest.TestCase):
    """Regression tests for the getters added so ui_qt/audio_effects_window.py
    can initialize its Compressor/Spatializer sliders from live player state
    instead of only the saved config file (ui/audio_effects_window.py has no
    such live override for these two sections' numeric values)."""

    def test_get_compressor_settings_reflects_live_values(self):
        player = AudioPlayer()
        player.set_compressor(enabled=True, threshold=-15.0, ratio=4.0, attack=10.0,
                               release=200.0, makeup_gain=3.0, knee=2.0, use_rms=False)
        settings = player.get_compressor_settings()
        self.assertEqual(settings, {
            "threshold": -15.0, "ratio": 4.0, "attack": 10.0, "release": 200.0,
            "makeup_gain": 3.0, "knee": 2.0, "use_rms": False,
        })

    def test_get_spatializer_settings_reflects_live_values(self):
        player = AudioPlayer()
        player.set_spatializer(enabled=True, size=0.5, width=0.3, wet=0.2, dry=0.9, damp=0.1)
        settings = player.get_spatializer_settings()
        self.assertEqual(settings, {
            "size": 0.5, "width": 0.3, "wet": 0.2, "dry": 0.9, "damp": 0.1,
        })

    def test_equalizer_and_rate_setters_still_work_under_lock(self):
        # Regression: set_equalizer_enabled/preamp/band and set_playback_rate
        # were unlocked while every sibling effects setter already used
        # self._lock — wrapping them must not change their actual behavior.
        player = AudioPlayer()
        player.set_equalizer_enabled(True)
        player.set_equalizer_preamp(5.0)
        player.set_equalizer_band(0, -3.0)
        player.set_playback_rate(1.5)
        self.assertTrue(player.get_equalizer_enabled())
        self.assertEqual(player.get_equalizer_preamp(), 5.0)
        self.assertEqual(player.get_equalizer_band(0), -3.0)
        self.assertEqual(player.get_playback_rate(), 1.5)


class TestAudioPlayerDevices(unittest.TestCase):
    """Unit tests for audio device management in AudioPlayer."""

    @patch('sounddevice.query_devices')
    @patch('sounddevice.default')
    def test_get_audio_devices_empty(self, mock_default, mock_query_devices):
        """Test get_audio_devices returns default when no devices found."""
        mock_default.device = [0, 0]
        mock_query_devices.return_value = []

        player = AudioPlayer()
        devices = player.get_audio_devices()

        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0][0], '__DEFAULT__')
        self.assertEqual(devices[0][1], 'Default Audio Device')

    @patch('sounddevice.query_devices')
    @patch('sounddevice.default')
    def test_get_audio_devices_with_devices(self, mock_default, mock_query_devices):
        """Test get_audio_devices properly enumerates available devices."""
        mock_default.device = [0, 0]
        mock_query_devices.return_value = [
            {'name': 'Default Device', 'max_output_channels': 2, 'hostapi': 0}
        ]

        player = AudioPlayer()
        devices = player.get_audio_devices()

        self.assertEqual(len(devices), 2)  # Default + one device
        self.assertEqual(devices[0][0], '__DEFAULT__')
        self.assertEqual(devices[0][1], 'Default Audio Device')
        self.assertEqual(devices[1][1], 'Default Device')

    @patch('sounddevice.query_devices')
    @patch('sounddevice.default')
    def test_get_audio_devices_multiple(self, mock_default, mock_query_devices):
        """Test get_audio_devices with multiple devices."""
        mock_default.device = [0, 0]
        mock_query_devices.return_value = [
            {'name': 'Default Device', 'max_output_channels': 2, 'hostapi': 0},
            {'name': 'Speakers', 'max_output_channels': 2, 'hostapi': 0}
        ]

        player = AudioPlayer()
        devices = player.get_audio_devices()

        self.assertEqual(len(devices), 3)  # Default + two devices
        self.assertEqual(devices[0][0], '__DEFAULT__')
        self.assertEqual(devices[0][1], 'Default Audio Device')
        self.assertEqual(devices[1][1], 'Default Device')
        self.assertEqual(devices[2][1], 'Speakers')

    @patch('sounddevice.query_devices')
    @patch('sounddevice.default')
    def test_get_audio_devices_bytes_decoding(self, mock_default, mock_query_devices):
        """Test get_audio_devices properly decodes bytes to strings."""
        mock_default.device = [0, 0]
        mock_query_devices.return_value = [
            {'name': b'Headphones', 'max_output_channels': 2, 'hostapi': 0}
        ]

        player = AudioPlayer()
        devices = player.get_audio_devices()

        self.assertEqual(len(devices), 2)
        self.assertEqual(devices[1][1], 'Headphones')
        self.assertIsInstance(devices[1][1], str)

    def test_set_audio_device_default(self):
        """Test set_audio_device with default device."""
        player = AudioPlayer()
        player.set_audio_device('__DEFAULT__')
        self.assertIsNone(player._device_id)

    def test_set_audio_device_specific(self):
        """Test set_audio_device with specific device GUID."""
        device_guid = '1'
        player = AudioPlayer()
        player.set_audio_device(device_guid)
        self.assertEqual(player._device_id, device_guid)

    def test_set_audio_device_error_handling(self):
        """Test set_audio_device handles errors gracefully."""
        player = AudioPlayer()
        # Should not raise
        player.set_audio_device('invalid-device')
        self.assertEqual(player._device_id, 'invalid-device')

    def test_is_paused(self):
        """Test is_paused method."""
        player = AudioPlayer()
        self.assertFalse(player.is_paused())
        player._paused = True
        self.assertTrue(player.is_paused())


if __name__ == '__main__':
    unittest.main()
