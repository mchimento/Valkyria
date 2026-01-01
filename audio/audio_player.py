"""
SoundDevice Audio backend wrapper.

Provides a simple, stable API to play/pause/stop and emits callbacks when a track ends.
"""

import logging
import threading
import os
import sys
from pathlib import Path

import sounddevice as sd
import soundfile as sf
import numpy as np
import scipy.signal
import audio.metadata as metadata_module

logger = logging.getLogger(__name__)

class AudioPlayer:
    def __init__(self, on_track_end=None):
        """
        Initialize the audio player.

        Args:
            on_track_end: Optional callback function to be called when a track ends.
        """
        self.on_track_end = on_track_end
        self._lock = threading.RLock()

        self._stream = None
        self._file = None
        self._volume = 100  # 0-100
        self._muted = False
        self._paused = False
        self._stopped_manually = False
        self._device_id = None
        self._playback_rate = 1.0
        self._rate_remainder = 0.0

        # Equalizer
        self.equalizer_enabled = False
        self._eq_bands = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000]
        self._eq_gains = [0.0] * len(self._eq_bands)
        self._eq_preamp = 0.0
        self._eq_sos = None
        self._eq_zi = None

        logger.info("AudioPlayer initialized (sounddevice)")

    def _stream_callback(self, outdata, frames, time, status):
        """Callback for sounddevice OutputStream."""
        if status:
            logger.warning(f"Audio callback status: {status}")

        data = []
        frames_to_read = frames

        with self._lock:
            if not self._file:
                outdata[:] = 0
                raise sd.CallbackStop

            # Calculate frames to read based on rate
            if abs(self._playback_rate - 1.0) < 0.01:
                frames_to_read = frames
                self._rate_remainder = 0.0
            else:
                # Accumulate fractional frames to keep sync over time
                target_read = frames * self._playback_rate + self._rate_remainder
                frames_to_read = int(target_read)
                self._rate_remainder = target_read - frames_to_read

            # Read data from file
            data = self._file.read(frames_to_read)
            # Ensure data is 2D for consistent processing (N, C)
            if data.ndim == 1:
                data = data[:, np.newaxis]

        # Handle End of File
        if len(data) < frames_to_read:
            # End of file reached, handle partial data
            if abs(self._playback_rate - 1.0) < 0.01:
                outdata[:len(data)] = data
                outdata[len(data):] = 0
            else:
                # Resample partial data
                valid_frames = int(len(data) / self._playback_rate)
                valid_frames = min(valid_frames, frames)
                if valid_frames > 0:
                    x_old = np.linspace(0, 1, len(data))
                    x_new = np.linspace(0, 1, valid_frames)
                    for ch in range(data.shape[1]):
                        outdata[:valid_frames, ch] = np.interp(x_new, x_old, data[:, ch])
                outdata[valid_frames:] = 0
            raise sd.CallbackStop
        else:
            if abs(self._playback_rate - 1.0) < 0.01:
                outdata[:] = data
            else:
                # Resample full block: stretch read data to fit output frames
                x_old = np.linspace(0, 1, len(data))
                x_new = np.linspace(0, 1, frames)
                for ch in range(data.shape[1]):
                    outdata[:, ch] = np.interp(x_new, x_old, data[:, ch])

        # Apply Equalizer
        if self.equalizer_enabled and self._eq_sos is not None:
            # Apply Preamp
            if self._eq_preamp != 0.0:
                outdata[:] *= (10 ** (self._eq_preamp / 20.0))

            # Apply SOS filters
            # Check if ZI shape matches current channels (file channels)
            if self._eq_zi is not None and self._eq_zi.shape[1] == outdata.shape[1]:
                outdata[:], self._eq_zi = scipy.signal.sosfilt(self._eq_sos, outdata, axis=0, zi=self._eq_zi)

        # Apply Volume
        if self._muted:
            outdata[:] = 0
        else:
            # Normalize 0-100 to 0.0-1.0
            vol = self._volume / 100.0
            outdata[:] *= vol

    def _on_stream_finished(self):
        """Called when stream finishes (stops or ends)."""
        # Only trigger track end if it wasn't stopped manually or paused
        if not self._stopped_manually and not self._paused:
            if callable(self.on_track_end):
                try:
                    self.on_track_end()
                except Exception:
                    logger.error("Error in track end callback", exc_info=True)

    def play(self, path):
        """
        Play an audio file.

        Args:
            path: Path to the audio file to play.
        """
        self.stop()

        with self._lock:
            try:
                self._file = sf.SoundFile(path)
                self._paused = False
                self._stopped_manually = False

                # Determine device index if set
                device = None
                if self._device_id is not None:
                    try:
                        device = int(self._device_id)
                    except (ValueError, TypeError):
                        device = None

                self._stream = sd.OutputStream(
                    samplerate=self._file.samplerate,
                    channels=self._file.channels,
                    device=device,
                    callback=self._stream_callback,
                    finished_callback=self._on_stream_finished
                )
                self._stream.start()
                self._update_equalizer()
            except Exception:
                logger.error(f"Failed to play: {path}", exc_info=True)
                # Cleanup manually since we can't call stop() safely inside lock if it blocks
                if self._stream:
                    self._stream.close()
                    self._stream = None
                if self._file:
                    self._file.close()
                    self._file = None

    def pause(self):
        """Pause or resume playback."""
        stream_to_toggle = None
        should_start = False

        with self._lock:
            if self._stream:
                stream_to_toggle = self._stream
                if self._paused:
                    should_start = True
                    self._paused = False
                else:
                    should_start = False
                    self._paused = True

        if stream_to_toggle:
            try:
                if should_start:
                    stream_to_toggle.start()
                else:
                    stream_to_toggle.stop()
            except Exception:
                logger.error("Failed to pause playback", exc_info=True)

    def stop(self):
        """Stop playback."""
        stream_to_close = None
        file_to_close = None

        with self._lock:
            self._stopped_manually = True
            if self._stream:
                stream_to_close = self._stream
                self._stream = None
            if self._file:
                file_to_close = self._file
                self._file = None
            self._paused = False

        # Perform cleanup outside lock to avoid deadlock with callback
        if stream_to_close:
            try:
                stream_to_close.stop()
                stream_to_close.close()
            except Exception:
                logger.error("Failed to stop stream", exc_info=True)

        if file_to_close:
            try:
                file_to_close.close()
            except Exception:
                logger.error("Failed to close file", exc_info=True)

    def set_volume(self, val):
        """
        Set the playback volume.

        Args:
            val: Volume level (0-100).
        """
        with self._lock:
            self._volume = max(0, min(100, float(val)))

    def get_mute_state(self):
        """
        Check if audio is currently muted.

        Returns:
            True if muted, False otherwise.
        """
        return self._muted

    def set_mute(self, mute):
        """
        Set mute state.

        Args:
            mute: True to mute, False to unmute.
        """
        with self._lock:
            self._muted = bool(mute)
            logger.info(f"Mute set to: {mute}")

    def is_playing(self):
        """
        Check if audio is currently playing.

        Returns:
            True if playing, False otherwise.
        """
        return self._stream is not None and self._stream.active and not self._paused

    def is_paused(self):
        """
        Check if audio is currently paused.

        Returns:
            True if paused, False otherwise.
        """
        return self._paused

    def get_time(self):
        """
        Get current playback position in milliseconds.

        Returns:
            Current position in milliseconds, or 0 if unavailable.
        """
        with self._lock:
            try:
                if self._file:
                    # tell() returns frames, convert to ms
                    return int((self._file.tell() / self._file.samplerate) * 1000)
                return 0
            except Exception:
                logger.error("Failed to get playback time", exc_info=True)
                return 0

    def get_length(self):
        """
        Get total track length in milliseconds.

        Returns:
            Track length in milliseconds, or 0 if unavailable.
        """
        with self._lock:
            try:
                if self._file:
                    return int((len(self._file) / self._file.samplerate) * 1000)
                return 0
            except Exception:
                logger.error("Failed to get track length", exc_info=True)
                return 0

    def set_time(self, time_ms):
        """
        Set the playback position.

        Args:
            time_ms: Position in milliseconds.
        """
        with self._lock:
            try:
                if self._file:
                    # Convert ms to frames
                    frame_pos = int((time_ms / 1000.0) * self._file.samplerate)
                    self._file.seek(frame_pos)
                    # Reset filter state on seek to prevent artifacts
                    if self._eq_zi is not None:
                        self._eq_zi.fill(0)
            except Exception:
                logger.error(f"Failed to set time to {time_ms}", exc_info=True)

    def get_audio_devices(self) -> list:
        """
        Get available audio output devices.

        Returns:
            List of tuples (device_id, device_name). device_id is the identifier used by sounddevice.
            The default device has device_id = '__DEFAULT__'.
        """
        try:
            devices = []

            # Query sounddevice
            sd_devices = sd.query_devices()

            # Add default option
            devices.append(('__DEFAULT__', 'Default Audio Device'))

            # Filter duplicates by using the host API of the system default output device
            target_hostapi = None
            default_out_idx = sd.default.device[1]

            if default_out_idx >= 0 and default_out_idx < len(sd_devices):
                target_hostapi = sd_devices[default_out_idx]['hostapi']

            # Fallback: if no default device, pick the API of the first available output device
            if target_hostapi is None:
                for dev in sd_devices:
                    if dev['max_output_channels'] > 0:
                        target_hostapi = dev['hostapi']
                        break

            for idx, dev in enumerate(sd_devices):
                # Filter for output devices
                if dev['max_output_channels'] > 0:
                    # If we have a target API, skip devices from other APIs to avoid duplicates
                    if target_hostapi is not None and dev['hostapi'] != target_hostapi:
                        continue

                    name = dev['name']
                    # Use index as ID
                    devices.append((str(idx), name))

            return devices
        except Exception as e:
            logger.error(f"Failed to get audio devices: {e}")
            return [('__DEFAULT__', 'Default Audio Device')]

    def set_audio_device(self, device_id):
        """
        Set the audio output device.

        Args:
            device_id: Device ID or '__DEFAULT__' for system default.
        """
        restart_needed = False
        restart_path = None
        restart_pos = 0
        restart_paused = False

        with self._lock:
            try:
                if device_id == '__DEFAULT__':
                    self._device_id = None
                else:
                    self._device_id = device_id

                logger.info(f"Audio device set to: {device_id}")

                # If currently playing or paused, restart stream to apply new device
                if self._stream and self._file:
                    restart_needed = True
                    restart_path = self._file.name
                    restart_pos = int((self._file.tell() / self._file.samplerate) * 1000)
                    restart_paused = self._paused
            except Exception as e:
                logger.error(f"Failed to set audio device to {device_id}: {e}")

        if restart_needed:
            self.stop()
            self.play(restart_path)
            self.set_time(restart_pos)
            if restart_paused:
                self.pause()

    def _design_peaking_filter(self, f0, gain_db, Q, fs):
        """Design coefficients for a peaking EQ filter."""
        A = 10 ** (gain_db / 40.0)
        w0 = 2 * np.pi * f0 / fs
        alpha = np.sin(w0) / (2 * Q)

        b0 = 1 + alpha * A
        b1 = -2 * np.cos(w0)
        b2 = 1 - alpha * A
        a0 = 1 + alpha / A
        a1 = -2 * np.cos(w0)
        a2 = 1 - alpha / A

        return np.array([b0, b1, b2, a0, a1, a2]) / a0

    def _update_equalizer(self):
        """Recalculate equalizer filter coefficients."""
        with self._lock:
            if not self._file or not self.equalizer_enabled:
                self._eq_sos = None
                self._eq_zi = None
                return

            fs = self._file.samplerate
            sos_list = []
            for i, freq in enumerate(self._eq_bands):
                sos = self._design_peaking_filter(freq, self._eq_gains[i], 1.414, fs)
                sos_list.append(sos)

            self._eq_sos = np.vstack(sos_list)

            # Initialize state if needed
            if self._eq_zi is None or self._eq_zi.shape != (len(self._eq_bands), self._file.channels, 2):
                self._eq_zi = np.zeros((len(self._eq_bands), self._file.channels, 2))

    def set_equalizer_enabled(self, enabled):
        """Enable or disable the equalizer."""
        self.equalizer_enabled = enabled
        self._update_equalizer()

    def get_equalizer_enabled(self):
        return self.equalizer_enabled

    def set_equalizer_preamp(self, preamp):
        """Set preamp level in dB (-20 to 20)."""
        self._eq_preamp = max(-20.0, min(20.0, float(preamp)))

    def get_equalizer_preamp(self):
        return self._eq_preamp

    def set_equalizer_band(self, band_index, value):
        """Set gain for a specific band in dB (-20 to 20)."""
        if 0 <= band_index < len(self._eq_bands):
            self._eq_gains[band_index] = max(-20.0, min(20.0, float(value)))
            self._update_equalizer()

    def get_equalizer_band(self, band_index):
        if 0 <= band_index < len(self._eq_bands):
            return self._eq_gains[band_index]
        return 0.0

    def set_playback_rate(self, rate):
        """
        Set playback speed.
        Args:
            rate: Speed factor (e.g. 1.0 is normal, 0.5 is half speed, 2.0 is double).
        """
        # Clamp rate to reasonable limits
        self._playback_rate = max(0.1, min(4.0, float(rate)))

    def get_playback_rate(self):
        """Get current playback rate."""
        return self._playback_rate
