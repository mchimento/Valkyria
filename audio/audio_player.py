"""
SoundDevice Audio backend wrapper.

Provides a simple, stable API to play/pause/stop and emits callbacks when a track ends.
"""

import logging
import threading
import json
import re
import subprocess
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


def filter_selectable_audio_devices(devices: list) -> list:
    """Drop ALSA's stock plugin aliases (sysdefault, front, pipewire, dmix,
    ...), keeping only 'Default Audio Device' and real hw:CARD,DEV entries."""
    def is_selectable(device_id: str, name: str) -> bool:
        if device_id == "__DEFAULT__":
            return True
        return re.search(r"\(hw:\d+,\d+\)", name) is not None

    return [(did, name) for did, name in devices if is_selectable(did, name)]


class AudioBuffer:
    """
    Thread-safe ring buffer for audio streaming.
    Decouples file I/O from the audio callback to prevent underruns.
    """
    def __init__(self, file_path, capacity_frames=176400): # ~4 seconds at 44.1k
        # Suppress libmpg123 warnings during file opening
        with suppress_c_stderr():
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
        # Stateful resampler buffer (keeps continuity between callbacks)
        self._resample_buffer = None
        self._resample_pos = 0.0

        # Audio metrics calculation (LUFS, Peak dBFS, Energy)
        self._audio_metrics_callback = None
        self._audio_metrics_accumulator = []
        self._overall_lufs = -60.0  # Pre-computed overall track LUFS
        self._metrics_last_update = 0
        self._metrics_update_interval = 0.05  # Update every 50ms

        # Initialize Audio Effects Processor
        self.effects = AudioEffects(AUDIO_CONFIG, AUDIO_DEFAULTS)

        # Fade settings
        self.fade_in_enabled = False
        self.fade_in_duration = 3
        self.fade_out_enabled = False
        self.fade_out_duration = 3

        # Silence detection
        self.silence_detection_enabled = False
        self._silence_threshold = -50.0  # dB
        self._silence_duration = 1.5  # seconds
        self._silence_frames_count = 0
        self._silence_detected = False

        self._fade_in_frames = 0
        self._fade_out_frames = 0
        self._frames_played = 0
        self._total_frames = 0
        self._is_stopping = False
        self._stopping_start_frame = 0

        logger.info("AudioPlayer initialized (sounddevice)")

    def __del__(self):
        """Ensure cleanup when AudioPlayer is destroyed."""
        try:
            # Stop any active playback
            if hasattr(self, '_stream') and self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None

            # Close buffer
            if hasattr(self, '_buffer') and self._buffer:
                try:
                    self._buffer.close()
                except Exception:
                    pass
                self._buffer = None

            # Reset audio metrics for UI as part of cleanup (ensure UI is reset)
            try:
                if self._audio_metrics_callback:
                    threading.Thread(
                        target=lambda: self._audio_metrics_callback(-60.0, -60.0, -60.0, 0.0, 0.0),
                        daemon=True
                    ).start()
            except Exception:
                pass

            # Stop all sounddevice operations
            import sounddevice as sd
            try:
                sd.stop()
            except Exception:
                pass

        except Exception:
            # Ensure cleanup doesn't raise exceptions
            logger.error("Error cleaning up audio player")
            pass

    def _stream_callback(self, outdata, frames, time, status):
        """Callback for sounddevice OutputStream."""
        if status:
            logger.warning(f"Audio callback status: {status}")

        # Clear output buffer first to prevent residual audio
        outdata.fill(0)

        # If stop was requested, abort immediately — don't process any more old audio
        if self._stopped_manually:
            raise sd.CallbackAbort

        data = []
        frames_to_read = frames

        with self._lock:
            # Check for silence-triggered stop first
            if self._silence_detected:
                outdata[:] = 0
                raise sd.CallbackStop

            if not self._buffer:
                outdata[:] = 0
                raise sd.CallbackAbort

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

        # Resample if needed (stateful resampler for smoother speed changes)
        rate = self._playback_rate
        if abs(rate - 1.0) < 0.01:
            # Direct copy with padding/truncation to match frames
            n = data.shape[0]
            if n >= frames:
                outdata[:] = data[:frames]
            else:
                if n > 0:
                    outdata[:n] = data
                if frames > n:
                    outdata[n:frames] = 0
        else:
            # Initialize resample state if missing
            if not hasattr(self, '_resample_buffer') or self._resample_buffer is None:
                # Create empty buffer with proper channels
                self._resample_buffer = np.zeros((0, data.shape[1]), dtype='float32')
                self._resample_pos = 0.0

            # Append new samples to the resample buffer
            if data.shape[0] > 0:
                self._resample_buffer = np.concatenate((self._resample_buffer, data), axis=0)

            # Use a high-quality sinc (windowed) resampler
            out, consumed = self._sinc_resample(frames, rate)
            outdata[:] = out

            # Drop consumed frames from buffer and update position
            if consumed > 0:
                buf_len = self._resample_buffer.shape[0]
                channels = self._resample_buffer.shape[1] if buf_len > 0 else data.shape[1]
                if consumed >= buf_len:
                    self._resample_buffer = np.zeros((0, channels), dtype='float32')
                else:
                    self._resample_buffer = self._resample_buffer[consumed:]

                self._resample_pos = (self._resample_pos + frames * rate) - consumed

            # Trim buffer if it grows too large
            max_buf = 44100 * 5  # 5 seconds guard
            if self._resample_buffer.shape[0] > max_buf:
                drop = self._resample_buffer.shape[0] - max_buf
                self._resample_buffer = self._resample_buffer[drop:]
                self._resample_pos = max(0.0, self._resample_pos - drop)

        # Apply Audio Effects (use outdata as the source for processing)
        outdata[:] = self.effects.process(outdata)

        # Apply fade in/out logic
        # Copy values locally to minimize locking
        current_frames_played = 0
        current_total_frames = 0
        fade_in_len = 0
        fade_out_len = 0
        do_fade_in = False
        do_fade_out = False
        is_manual_stopping = False
        manual_stop_start = 0

        with self._lock:
            current_frames_played = self._frames_played
            current_total_frames = self._total_frames
            do_fade_in = self.fade_in_enabled
            do_fade_out = self.fade_out_enabled
            fade_in_len = self._fade_in_frames
            fade_out_len = self._fade_out_frames
            is_manual_stopping = self._is_stopping
            manual_stop_start = self._stopping_start_frame

            # Update position for next callback
            self._frames_played += frames

        # Apply Fade In
        if do_fade_in and fade_in_len > 0 and current_frames_played < fade_in_len:
            # We are in the fade-in zone
            start_idx = current_frames_played
            end_idx = min(current_frames_played + frames, fade_in_len)
            length = end_idx - start_idx

            if length > 0:
                # Generate linear ramp 0..1
                # The segment corresponds to [start_idx, end_idx)
                ramp = np.linspace(start_idx / fade_in_len, end_idx / fade_in_len, length, dtype='float32')

                # Apply to first 'length' frames
                if outdata.ndim == 2:
                    outdata[:length] *= ramp[:, np.newaxis]
                else:
                    outdata[:length] *= ramp

        # Apply Fade Out
        if do_fade_out and fade_out_len > 0:
            # 1. Natural end of track fade out
            frames_remaining = current_total_frames - current_frames_played

            if frames_remaining < fade_out_len + frames and current_total_frames > 0:
                # Calculate start frame relative to fade out start
                # Fade starts at (total - fade_out_len)
                fade_start_pos = max(0, current_total_frames - fade_out_len)

                # Current chunk start/end absolute positions
                chunk_start = current_frames_played
                chunk_end = current_frames_played + frames

                # Intersect chunk with fade region [fade_start_pos, total_frames]
                # We only fade the part that is >= fade_start_pos

                f_start = max(chunk_start, fade_start_pos)
                f_end = min(chunk_end, current_total_frames + fade_out_len) # Allow fading slightly past end if needed or clamp

                if f_end > f_start:
                    # Relative indices in outdata
                    out_start = f_start - chunk_start
                    out_end = f_end - chunk_start

                    vol_s = 1.0 - (f_start - fade_start_pos) / fade_out_len
                    vol_e = 1.0 - (f_end - fade_start_pos) / fade_out_len

                    vol_s = max(0.0, min(1.0, vol_s))
                    vol_e = max(0.0, min(1.0, vol_e))

                    ramp = np.linspace(vol_s, vol_e, f_end - f_start, dtype='float32')

                    if outdata.ndim == 2:
                        outdata[out_start:out_end] *= ramp[:, np.newaxis]
                    else:
                        outdata[out_start:out_end] *= ramp

            # 2. Manual stop fade out
            if is_manual_stopping:
                # Fade out from manual_stop_start over fade_out_len
                # frames_played has progressed since manual_stop_start
                # The manual stop creates a virtual "zero point" at manual_stop_start + fade_out_len

                chunk_start = current_frames_played
                chunk_end = current_frames_played + frames
                rel_start = chunk_start - manual_stop_start
                rel_end = chunk_end - manual_stop_start

                vol_s = 1.0 - rel_start / fade_out_len
                vol_e = 1.0 - rel_end / fade_out_len

                # Clamp
                vol_s = max(0.0, min(1.0, vol_s))
                vol_e = max(0.0, min(1.0, vol_e))

                # Only apply if we have something to fade
                # If vol_s and vol_e are both 0, we can just zero out
                if vol_s <= 0 and vol_e <= 0:
                    outdata[:] = 0
                else:
                    ramp = np.linspace(vol_s, vol_e, frames, dtype='float32')
                    if outdata.ndim == 2:
                        outdata[:] *= ramp[:, np.newaxis]
                    else:
                        outdata[:] *= ramp

        # LUFS/peak/limiter/energy metrics reflect the track's own content,
        # like a real DJ mixer's meters — snapshot before mute/volume (the
        # monitor level) are applied, not after. Only copy when something's
        # actually listening — this runs on every real-time audio callback.
        metrics_source = outdata.copy() if self._audio_metrics_callback is not None else None

        if self._muted:
            outdata[:] = 0
        else:
            # Normalize 0-100 to 0.0-1.0
            vol = self._volume / 100.0
            outdata[:] *= vol

        # Silence Detection — measured on raw `data`, not volume-scaled
        # `outdata`, so it isn't affected by the volume/mute/fade settings.
        with self._lock:
            if self.silence_detection_enabled and not self._silence_detected and self._buffer and len(data) > 0:
                rms = np.sqrt(np.mean(data ** 2))
                level_db = 20 * np.log10(rms + 1e-10)  # Add small value to avoid log(0)

                if level_db < self._silence_threshold:
                    self._silence_frames_count += len(data)
                    sr = self._buffer.samplerate
                    silence_duration = self._silence_frames_count / sr

                    # Requires 30s of playback already elapsed (not proximity
                    # to the file's reported end) before allowing a trigger —
                    # avoids mistaking a quiet intro for dead air without
                    # capping how much trailing silence it can skip. Gating
                    # on remaining-time-to-end instead let files with long
                    # silent tails play out nearly the whole tail before ever
                    # reaching that window, defeating the feature for exactly
                    # the files it's meant to help with (confirmed via real
                    # playback logs).
                    if silence_duration >= self._silence_duration and self._frames_played >= sr * 30:
                        self._silence_detected = True
                else:
                    self._silence_frames_count = 0

        # Calculate audio metrics if callback is registered
        if metrics_source is not None:
            self._update_audio_metrics(metrics_source)

    def _on_stream_finished(self):
        """Called when stream finishes (stops or ends)."""
        # Only trigger track end if it wasn't stopped manually or paused
        if not self._stopped_manually and not self._paused:
            if callable(self.on_track_end):
                try:
                    self.on_track_end()
                except Exception:
                    logger.error("Error in track end callback", exc_info=True)

    def _sinc_resample(self, frames, rate, kernel_size=64):
        """High-quality stateful sinc resampler.

        Uses a windowed sinc kernel (Hann window) and linear convolution across a
        kernel of size `kernel_size` to interpolate arbitrary fractional positions.
        This keeps state in `self._resample_buffer` and `self._resample_pos`.
        Returns (out, consumed_frames) where `out` is (frames, channels).
        """
        buf = self._resample_buffer
        if buf is None or buf.shape[0] == 0:
            # Nothing available; return silence
            channels = self._buffer.channels if self._buffer else 2
            return np.zeros((frames, channels), dtype='float32'), 0

        buf_len = buf.shape[0]
        channels = buf.shape[1]

        # Kernel parameters
        if kernel_size % 2 != 0:
            kernel_size += 1
        half = kernel_size // 2

        # Positions in source frames for each output frame
        positions = self._resample_pos + np.arange(frames) * rate
        centers = np.floor(positions).astype(np.int64)

        # Prepare index grid and offsets
        n_range = np.arange(-half + 1, half + 1)  # length kernel_size
        indices = centers[:, None] + n_range[None, :]

        # Clip indices to buffer range for safe gathering and mark validity
        valid_mask = (indices >= 0) & (indices < buf_len)
        clipped = np.clip(indices, 0, buf_len - 1)

        # Gather samples: shape (frames, kernel_size, channels)
        samples = buf[clipped]

        # Offsets for sinc: how far each tap is from the source position
        offsets = positions[:, None] - indices  # shape (frames, kernel_size)

        # Hann window applied to the sinc kernel
        win = 0.5 * (1.0 + np.cos(np.pi * offsets / half))
        win[np.abs(offsets) > half] = 0.0

        # Sinc function: np.sinc uses sin(pi x)/(pi x)
        kernel = np.sinc(offsets) * win
        kernel *= valid_mask.astype('float32')

        # Perform convolution for each channel using einsum for clarity
        out = np.einsum('ij,ijk->ik', kernel, samples)

        # Compute how many source frames we can drop: max floor index used + 1
        row_valid = valid_mask.any(axis=1)
        if np.any(row_valid):
            consumed = int(np.max(centers[row_valid])) + 1
        else:
            consumed = 0

        return out.astype('float32'), consumed

    def set_audio_metrics_callback(self, callback):
        """Set callback for audio metrics updates. Callback receives (lufs_value, overall_lufs, peak_dbfs, limiter_activity, energy_level)."""
        with self._lock:
            self._audio_metrics_callback = callback
            logger.info("Audio metrics callback registered")

    def _compute_and_notify_overall_lufs(self, path):
        """Background worker to compute overall LUFS without blocking playback start.

        Once computed, updates internal state and notifies any audio metrics callback so UI can refresh.
        """
        try:
            val = self._calculate_overall_lufs(path)
            with self._lock:
                self._overall_lufs = val
            logger.info(f"Overall LUFS for track (async): {self._overall_lufs:.1f}")

            # If a UI callback is registered, send an update with conservative realtime metrics
            try:
                if self._audio_metrics_callback:
                    # Provide placeholder current metrics (they will be updated by the regular audio metrics path)
                    self._audio_metrics_callback(-60.0, self._overall_lufs, -60.0, 0.0, 0.0)
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"Async LUFS calculation failed for {path}: {e}")

    def _update_audio_metrics(self, audio_data):
        """Calculate and update LUFS, Peak dBFS, limiter activity, and energy from audio data without affecting playback."""
        try:
            if self._audio_metrics_callback is None:
                return

            # Calculate RMS of the audio block
            rms = np.sqrt(np.mean(audio_data ** 2))

            # Calculate peak level (maximum absolute sample value)
            peak = np.max(np.abs(audio_data))
            if peak > 0:
                peak_dbfs = 20 * np.log10(peak)
            else:
                peak_dbfs = -60.0
            peak_dbfs = max(-60.0, min(0.0, peak_dbfs))

            # Accumulate samples for averaging (current LUFS)
            self._audio_metrics_accumulator.append(rms)
            # Store peak values for periodic update
            if not hasattr(self, '_peak_accumulator'):
                self._peak_accumulator = []
            self._peak_accumulator.append(peak_dbfs)

            # Calculate metrics periodically
            current_time = time.time()
            if current_time - self._metrics_last_update >= self._metrics_update_interval:
                if self._audio_metrics_accumulator:
                    # Average RMS over accumulated samples (current LUFS)
                    avg_rms = np.mean(self._audio_metrics_accumulator)

                    # Convert to dBFS (approximate LUFS)
                    if avg_rms > 0:
                        lufs = 20 * np.log10(avg_rms)
                    else:
                        lufs = -60.0

                    # Clamp to reasonable range
                    lufs = max(-60.0, min(0.0, lufs))

                    # Get maximum peak from accumulated values
                    if self._peak_accumulator:
                        max_peak_dbfs = max(self._peak_accumulator)
                    else:
                        max_peak_dbfs = -60.0

                    # Calculate limiter activity based on how close the peak is to clipping
                    # -12 dBFS = 0.0 activity (safe)
                    # 0 dBFS = 1.0 activity (clipping risk)
                    # This represents how "hot" the signal is
                    limiter_activity = 0.0
                    if max_peak_dbfs > -12.0:
                        # Normalize from -12..0 to 0..1
                        limiter_activity = (max_peak_dbfs + 12.0) / 12.0
                        limiter_activity = max(0.0, min(1.0, limiter_activity))

                    # Calculate energy level (normalized 0.0 to 1.0)
                    # Map RMS to energy: 0.0 = silence, 1.0 = maximum
                    # Use exponential scaling for better visual representation
                    energy = min(1.0, avg_rms * 3.0)  # Scale factor to make typical music reach good levels
                    energy = max(0.0, energy)

                    # Call the callback asynchronously to avoid blocking audio thread
                    # Use threading to prevent UI blocking from affecting audio
                    if self._audio_metrics_callback:
                        callback = self._audio_metrics_callback
                        threading.Thread(
                            target=lambda: callback(lufs, self._overall_lufs, max_peak_dbfs, limiter_activity, energy),
                            daemon=True
                        ).start()

                    # Reset accumulators
                    self._audio_metrics_accumulator = []
                    self._peak_accumulator = []
                    self._metrics_last_update = current_time
        except Exception as e:
            logger.error(f"Error calculating audio metrics: {e}")

    def _calculate_overall_lufs(self, path):
        """Pre-calculate overall LUFS for entire track."""
        try:
            # Open file separately for analysis
            with suppress_c_stderr():
                with sf.SoundFile(path) as audio_file:
                    samplerate = audio_file.samplerate
                    channels = audio_file.channels

                    # Read and analyze in chunks to avoid memory issues
                    chunk_size = 44100  # 1 second at 44.1kHz
                    rms_values = []

                    while True:
                        data = audio_file.read(chunk_size, dtype='float32')
                        if len(data) == 0:
                            break

                        # Ensure 2D
                        if data.ndim == 1:
                            data = data[:, np.newaxis]

                        # Calculate RMS for this chunk
                        rms = np.sqrt(np.mean(data ** 2))
                        rms_values.append(rms)

                    # Calculate overall LUFS from all chunks
                    if rms_values:
                        overall_rms = np.mean(rms_values)
                        if overall_rms > 0:
                            overall_lufs = 20 * np.log10(overall_rms)
                        else:
                            overall_lufs = -60.0
                        return max(-60.0, min(0.0, overall_lufs))

            return -60.0
        except Exception as e:
            logger.error(f"Error calculating overall LUFS: {e}")
            return -60.0

    def play(self, path):
        """
        Play an audio file.

        Args:
            path: Path to the audio file to play.
        """
        self.stop()

        # Delay to ensure stop() completes and hardware buffers are fully cleared
        # This prevents ghost sounds from previous track
        time.sleep(0.06)

        with self._lock:
            try:
                # Reset audio metrics tracking for new track
                self._audio_metrics_accumulator = []
                self._metrics_last_update = 0
                self._rate_remainder = 0.0

                # Start playback immediately; calculate overall LUFS in background to avoid blocking
                self._buffer = AudioBuffer(path)
                self._paused = False
                self._stopped_manually = False
                self._is_stopping = False
                self._stopping_start_frame = 0

                # Setup fade frames based on samplerate
                sr = self._buffer.samplerate
                self._fade_in_frames = int(self.fade_in_duration * sr)
                self._fade_out_frames = int(self.fade_out_duration * sr)
                self._frames_played = 0

                # Reset silence detection for new track
                self._silence_frames_count = 0
                self._silence_detected = False

                # Try to get total frames for natural fade out
                try:
                    self._total_frames = self._buffer.file.frames
                except:
                    self._total_frames = 0

                # Compute overall LUFS asynchronously and notify listeners/UI when ready
                # Only compute if an audio metrics callback is registered (i.e., UI is listening)
                if self._audio_metrics_callback:
                    threading.Thread(target=self._compute_and_notify_overall_lufs, args=(path,), daemon=True).start()

                # Determine device index if set
                device = None
                if self._device_id is not None:
                    try:
                        device = int(self._device_id)
                    except (ValueError, TypeError):
                        device = None

                # Prepare effects for this file BEFORE creating stream
                self.effects.prepare(self._buffer.samplerate, self._buffer.channels)

                # Reset effects state to prevent ghost sounds from previous tracks
                self.effects.reset_state()

                # Reset resampler state for new track
                self._resample_buffer = None
                self._resample_pos = 0.0

                self._stream = sd.OutputStream(
                    samplerate=self._buffer.samplerate,
                    channels=self._buffer.channels,
                    device=device,
                    latency='low',
                    callback=self._stream_callback,
                    finished_callback=self._on_stream_finished
                )

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

            # Clear resampler state to prevent ghost sounds
            self._resample_buffer = None
            self._resample_pos = 0.0

            # Reset effects state on stop to ensure no residual audio in buffers
            if hasattr(self, 'effects'):
                self.effects.reset_state()

        # Perform cleanup outside lock to avoid deadlock with callback
        if stream_to_close:
            try:
                # Use abort() instead of stop() to immediately discard buffered audio
                # This prevents "ghost sounds" from previous track when changing songs
                stream_to_close.abort()
                # Delay to ensure hardware buffer is completely flushed
                time.sleep(0.07)
                stream_to_close.close()
            except Exception:
                logger.error("Failed to stop stream", exc_info=True)

        if buffer_to_close:
            try:
                buffer_to_close.close()
            except Exception:
                logger.error("Failed to close buffer", exc_info=True)

        # Reset audio metrics for UI (ensure overall LUFS resets when playback stops)
        try:
            if self._audio_metrics_callback:
                # Use a thread to avoid blocking
                threading.Thread(
                    target=lambda: self._audio_metrics_callback(-60.0, -60.0, -60.0, 0.0, 0.0),
                    daemon=True
                ).start()
        except Exception:
            # Don't let metrics reset failures interrupt stop
            pass

    def set_fade_in_enabled(self, enabled):
        with self._lock:
            self.fade_in_enabled = bool(enabled)

    def set_fade_out_enabled(self, enabled):
        with self._lock:
            self.fade_out_enabled = bool(enabled)

    def set_fade_in_duration(self, duration):
        with self._lock:
            self.fade_in_duration = max(0, min(10, duration))
            if self._buffer:
                self._fade_in_frames = int(self.fade_in_duration * self._buffer.samplerate)

    def set_fade_out_duration(self, duration):
        with self._lock:
            self.fade_out_duration = max(0, min(10, duration))
            if self._buffer:
                self._fade_out_frames = int(self.fade_out_duration * self._buffer.samplerate)

    def trigger_fade_out(self):
        """
        Triggers a manual fade out starting immediately.
        Returns the duration in seconds the caller should wait.
        """
        with self._lock:
            if not self._stream or self._paused or not self.fade_out_enabled or self.fade_out_duration <= 0:
                return 0.0

            if not self._is_stopping:
                self._is_stopping = True
                self._stopping_start_frame = self._frames_played
                return float(self.fade_out_duration)

            return 0.0
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
                    # frames_played must track the seeked-to position, not
                    # just keep counting from wherever it was — otherwise the
                    # "has enough playback elapsed to allow a silence-skip"
                    # check reads a stale value and can block a genuine skip
                    # for up to 30s after the seek, even while sitting in
                    # real silence the whole time. Also clear the in-progress
                    # silence run, since it was measuring audio from the old
                    # position.
                    self._frames_played = frame_pos
                    self._silence_frames_count = 0
                    self._silence_detected = False
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

    def get_default_output_info(self):
        """Resolve what '__DEFAULT__' actually reaches via WirePlumber
        (sounddevice's ALSA hostapi can't see this). Returns (alsa_card, description)."""
        try:
            result = subprocess.run(
                ["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"],
                capture_output=True, text=True, timeout=2,
            )
            if result.returncode != 0:
                return None, None
            output = result.stdout
            desc_match = re.search(r'node\.description = "([^"]+)"', output)
            description = desc_match.group(1) if desc_match else None
            api_match = re.search(r'device\.api = "([^"]+)"', output)
            if api_match is None or api_match.group(1) != "alsa":
                return None, description
            card_match = re.search(r'alsa\.card = "(\d+)"', output)
            return (card_match.group(1) if card_match else None), description
        except Exception:
            return None, None

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
        with self._lock:
            self.effects.set_equalizer_enabled(enabled)

    def get_equalizer_enabled(self):
        return self.effects.get_equalizer_enabled()

    def set_equalizer_preamp(self, preamp):
        """Set preamp level in dB (-20 to 20)."""
        with self._lock:
            self.effects.set_equalizer_preamp(preamp)

    def get_equalizer_preamp(self):
        return self.effects.get_equalizer_preamp()

    def set_equalizer_band(self, band_index, value):
        """Set gain for a specific band in dB (-20 to 20)."""
        with self._lock:
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
        with self._lock:
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

    def get_compressor_settings(self):
        with self._lock:
            return self.effects.get_compressor_settings()

    def set_spatializer(self, enabled, size=0.85, width=0.5, wet=0.4, dry=0.5, damp=0.5):
        """Configure spatializer."""
        with self._lock:
            self.effects.set_spatializer(enabled, size, width, wet, dry, damp)

    def get_spatializer_enabled(self):
        return self.effects.get_spatializer_enabled()

    def get_spatializer_settings(self):
        with self._lock:
            return self.effects.get_spatializer_settings()

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
