"""
SoundDevice Audio backend wrapper.

Provides a simple, stable API to play/pause/stop and emits callbacks when a track ends.
"""

import logging
import threading
import json
import time
import os
import sys
from pathlib import Path
from contextlib import contextmanager

import sounddevice as sd
import soundfile as sf
import numpy as np

from audio.audio_effects import AudioEffects

logger = logging.getLogger(__name__)

@contextmanager
def suppress_c_stderr():
    """
    Context manager to suppress C-level stderr output.
    Useful for silencing libmpg123 warnings.
    """
    try:
        # Open a null file
        with open(os.devnull, 'w') as fnull:
            # Save the original stderr file descriptor
            original_stderr_fd = sys.stderr.fileno()
            saved_stderr_fd = os.dup(original_stderr_fd)

            try:
                # Redirect stderr to null
                os.dup2(fnull.fileno(), original_stderr_fd)
                yield
            finally:
                # Restore stderr
                os.dup2(saved_stderr_fd, original_stderr_fd)
                os.close(saved_stderr_fd)
    except Exception:
        # If anything goes wrong (e.g. no fileno), just execute code
        yield

class AudioBuffer:
    """
    Thread-safe ring buffer for audio streaming.
    Decouples file I/O from the audio callback to prevent underruns.
    """
    def __init__(self, file_path, capacity_frames=176400): # ~4 seconds at 44.1k
        self.file = sf.SoundFile(file_path)
        self.samplerate = self.file.samplerate
        self.channels = self.file.channels
        self.capacity = capacity_frames

        # Ring buffer
        self.buffer = np.zeros((self.capacity, self.channels), dtype='float32')
        self.write_pos = 0
        self.read_pos = 0
        self.count = 0 # Frames available to read
        self.absolute_read_pos = 0

        self.lock = threading.Lock()
        self.running = True
        self.eof = False

        # Start producer thread
        self.thread = threading.Thread(target=self._producer_loop, daemon=True)
        self.thread.start()

    def _producer_loop(self):
        while self.running:
            # Determine how much space is available
            with self.lock:
                space = self.capacity - self.count

            # If buffer is nearly full, sleep a bit
            if space < 4096:
                time.sleep(0.01)
                continue

            # Read a chunk (without holding lock)
            read_size = min(space, 8192)

            try:
                # Suppress libmpg123 warnings during read
                with suppress_c_stderr():
                    data = self.file.read(read_size, dtype='float32')
            except Exception as e:
                logger.error(f"Error reading audio file: {e}")
                self.eof = True
                break

            if len(data) == 0:
                self.eof = True
                time.sleep(0.05)
                continue

            # Ensure 2D
            if data.ndim == 1:
                data = data[:, np.newaxis]

            n = len(data)

            # Write to buffer (holding lock)
            with self.lock:
                if not self.running:
                    break

                end = self.write_pos + n
                if end <= self.capacity:
                    self.buffer[self.write_pos:end] = data
                else:
                    split = self.capacity - self.write_pos
                    self.buffer[self.write_pos:] = data[:split]
                    self.buffer[:n-split] = data[split:]

                self.write_pos = (self.write_pos + n) % self.capacity
                self.count += n

    def read(self, frames):
        """Read frames from the buffer. Returns None if EOF and empty."""
        with self.lock:
            if self.count == 0:
                if self.eof:
                    return None # Real EOF
                return np.zeros((frames, self.channels), dtype='float32') # Underrun

            n = min(frames, self.count)

            end = self.read_pos + n
            if end <= self.capacity:
                data = self.buffer[self.read_pos:end].copy()
            else:
                split = self.capacity - self.read_pos
                p1 = self.buffer[self.read_pos:]
                p2 = self.buffer[:n-split]
                data = np.concatenate((p1, p2))

            self.read_pos = (self.read_pos + n) % self.capacity
            self.count -= n
            self.absolute_read_pos += n

            # If we requested more than available, pad with zeros (underrun)
            if n < frames:
                padding = np.zeros((frames - n, self.channels), dtype='float32')
                data = np.concatenate((data, padding))

            return data

    def seek(self, frame_pos):
        with self.lock:
            try:
                self.file.seek(frame_pos)
                self.read_pos = 0
                self.write_pos = 0
                self.count = 0
                self.absolute_read_pos = frame_pos
                self.eof = False
            except Exception as e:
                logger.error(f"Error seeking: {e}")

    def close(self):
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=0.5)
        try:
            self.file.close()
        except:
            pass

# Load audio effects configuration
config_path = Path(__file__).parent / 'audio_effects_config.json'
with open(config_path, 'r') as f:
    AUDIO_CONFIG = json.load(f)

# Load audio effects defaults (for structure like bands, labels, presets)
defaults_path = Path(__file__).parent / 'audio_effect_default.json'
with open(defaults_path, 'r') as f:
    AUDIO_DEFAULTS = json.load(f)

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
        self._buffer = None
        self._volume = 100  # 0-100
        self._muted = False
        self._paused = False
        self._stopped_manually = False
        self._device_id = None
        self._playback_rate = AUDIO_CONFIG['playback']['default_rate']
        self._rate_remainder = 0.0

        # Initialize Audio Effects Processor
        self.effects = AudioEffects(AUDIO_CONFIG, AUDIO_DEFAULTS)

        logger.info("AudioPlayer initialized (sounddevice)")

    def _stream_callback(self, outdata, frames, time, status):
        """Callback for sounddevice OutputStream."""
        if status:
            logger.warning(f"Audio callback status: {status}")

        data = []
        frames_to_read = frames

        with self._lock:
            if not self._buffer:
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

            # Read data from buffer
            data = self._buffer.read(frames_to_read)

            if data is None:
                # EOF
                outdata[:] = 0
                raise sd.CallbackStop

        # Resample if needed
        if abs(self._playback_rate - 1.0) < 0.01:
            outdata[:] = data
        else:
            # Resample full block: stretch read data to fit output frames
            # Note: This simple interpolation does not maintain continuity across blocks
            # but is sufficient for basic speed control.
            x_old = np.linspace(0, 1, len(data))
            x_new = np.linspace(0, 1, frames)
            for ch in range(data.shape[1]):
                outdata[:, ch] = np.interp(x_new, x_old, data[:, ch])

        # Apply Audio Effects
        outdata[:] = self.effects.process(outdata)

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
                self._buffer = AudioBuffer(path)
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
                    samplerate=self._buffer.samplerate,
                    channels=self._buffer.channels,
                    device=device,
                    callback=self._stream_callback,
                    finished_callback=self._on_stream_finished
                )

                # Prepare effects for this file
                self.effects.prepare(self._buffer.samplerate, self._buffer.channels)

                self._stream.start()
            except Exception:
                logger.error(f"Failed to play: {path}", exc_info=True)
                # Cleanup manually since we can't call stop() safely inside lock if it blocks
                if self._stream:
                    self._stream.close()
                    self._stream = None
                if self._buffer:
                    self._buffer.close()
                    self._buffer = None

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
        buffer_to_close = None

        with self._lock:
            self._stopped_manually = True
            if self._stream:
                stream_to_close = self._stream
                self._stream = None
            if self._buffer:
                buffer_to_close = self._buffer
                self._buffer = None
            self._paused = False

        # Perform cleanup outside lock to avoid deadlock with callback
        if stream_to_close:
            try:
                stream_to_close.stop()
                stream_to_close.close()
            except Exception:
                logger.error("Failed to stop stream", exc_info=True)

        if buffer_to_close:
            try:
                buffer_to_close.close()
            except Exception:
                logger.error("Failed to close buffer", exc_info=True)

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
                if self._buffer:
                    return int((self._buffer.absolute_read_pos / self._buffer.samplerate) * 1000)
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
                if self._buffer:
                    return int((len(self._buffer.file) / self._buffer.samplerate) * 1000)
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
                if self._buffer:
                    # Convert ms to frames
                    frame_pos = int((time_ms / 1000.0) * self._buffer.samplerate)
                    self._buffer.seek(frame_pos)
                    # Reset filter state on seek to prevent artifacts
                    self.effects.reset_state()
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
                    if isinstance(name, bytes):
                        name = name.decode('utf-8', errors='ignore')
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
                if self._stream and self._buffer:
                    restart_needed = True
                    restart_path = self._buffer.file.name
                    restart_pos = int((self._buffer.absolute_read_pos / self._buffer.samplerate) * 1000)
                    restart_paused = self._paused
            except Exception as e:
                logger.error(f"Failed to set audio device to {device_id}: {e}")

        if restart_needed:
            self.stop()
            self.play(restart_path)
            self.set_time(restart_pos)
            if restart_paused:
                self.pause()

    def set_equalizer_enabled(self, enabled):
        """Enable or disable the equalizer."""
        self.effects.set_equalizer_enabled(enabled)

    def get_equalizer_enabled(self):
        return self.effects.get_equalizer_enabled()

    def set_equalizer_preamp(self, preamp):
        """Set preamp level in dB (-20 to 20)."""
        self.effects.set_equalizer_preamp(preamp)

    def get_equalizer_preamp(self):
        return self.effects.get_equalizer_preamp()

    def set_equalizer_band(self, band_index, value):
        """Set gain for a specific band in dB (-20 to 20)."""
        self.effects.set_equalizer_band(band_index, value)

    def get_equalizer_band(self, band_index):
        return self.effects.get_equalizer_band(band_index)

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

    def set_compressor(self, enabled, threshold=-20.0, ratio=3.0, attack=5.0, release=100.0, makeup_gain=0.0, knee=0.0, use_rms=True):
        """
        Enable/disable and configure dynamic range compressor.

        Args:
            enabled: Enable or disable the compressor
            threshold: Threshold in dB (-60 to 0)
            ratio: Compression ratio (1.0 to 20.0)
            attack: Attack time in ms (0.1 to 500)
            release: Release time in ms (1 to 1000)
            makeup_gain: Makeup gain in dB (-20 to 20)
            knee: Knee width in dB (0 to 10) - 0 for hard knee
            use_rms: Use RMS detection (True) or Peak detection (False)
        """
        with self._lock:
            self.effects.set_compressor(enabled, threshold, ratio, attack, release, makeup_gain, knee, use_rms)

    def get_compressor_enabled(self):
        """Get compressor enabled state."""
        with self._lock:
            return self.effects.get_compressor_enabled()

    def set_spatializer(self, enabled, size=0.85, width=0.5, wet=0.4, dry=0.5, damp=0.5):
        """Configure spatializer."""
        with self._lock:
            self.effects.set_spatializer(enabled, size, width, wet, dry, damp)

    def get_spatializer_enabled(self):
        return self.effects.get_spatializer_enabled()

    def set_channel_mode(self, mode):
        """
        Set the channel processing mode.

        Args:
            mode: One of 'Stereo', 'Mono', 'Left Channel', 'Right Channel', 'Side (Diff)'.
        """
        with self._lock:
            self.effects.set_channel_mode(mode)

    def get_channel_mode(self):
        return self.effects.get_channel_mode()

    def set_vocal_remover_enabled(self, enabled):
        """Enable or disable the vocal remover."""
        with self._lock:
            self.effects.set_vocal_remover_enabled(enabled)

    def get_vocal_remover_enabled(self):
        return self.effects.get_vocal_remover_enabled()

    def set_vocal_remover_intensity(self, intensity):
        """Set the intensity of the vocal remover (0.0 to 1.0)."""
        with self._lock:
            self.effects.set_vocal_remover_intensity(intensity)

    def get_vocal_remover_intensity(self):
        return self.effects.get_vocal_remover_intensity()
