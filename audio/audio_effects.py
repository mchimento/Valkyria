import numpy as np
import scipy.signal
import logging

logger = logging.getLogger(__name__)

class AudioEffects:
    def __init__(self, config, defaults):
        self.config = config
        self.defaults = defaults
        self.samplerate = 44100
        self.channels = 2

        # Equalizer State
        eq_config = config.get('equalizer', {})
        eq_defaults = defaults.get('equalizer', {})
        self.equalizer_enabled = eq_config.get('enabled', False)
        self._eq_bands = eq_defaults.get('bands', [])
        self._eq_gains = eq_config.get('gains', []).copy()
        self._eq_preamp = eq_config.get('preamp', 0.0)
        self._eq_sos = None
        self._eq_zi = None

        # Compressor State
        comp_config = config.get('compressor', {})
        self._compressor_enabled = comp_config.get('enabled', False)
        self._compressor_threshold = comp_config.get('threshold', -20.0)
        self._compressor_ratio = comp_config.get('ratio', 3.0)
        self._compressor_attack = comp_config.get('attack', 5.0)
        self._compressor_release = comp_config.get('release', 100.0)
        self._compressor_makeup = comp_config.get('makeup_gain', 0.0)
        self._compressor_knee = comp_config.get('knee', 0.0)
        self._compressor_use_rms = comp_config.get('use_rms', True)
        self._compressor_envelope = 0.0
        self._compressor_rms_buffer = np.zeros(comp_config.get('rms_buffer_size', 512))
        self._compressor_rms_index = 0

        # Spatializer State
        spat_config = config.get('spatializer', {})
        self._spatializer_enabled = spat_config.get('enabled', False)
        self._spat_size = spat_config.get('size', 0.85)
        self._spat_width = spat_config.get('width', 0.5)
        self._spat_wet = spat_config.get('wet', 0.4)
        self._spat_dry = spat_config.get('dry', 0.5)
        self._spat_damp = spat_config.get('damp', 0.5)
        self._spat_initialized = False
        self._spat_buffer = None
        self._spat_write_pos = 0

        # Vocal Remover State
        vr_config = config.get('vocal_remover', {})
        self._vocal_remover_enabled = vr_config.get('enabled', False)
        self._vocal_remover_intensity = vr_config.get('intensity', 0.5)
        self._vocal_remover_sos = None
        self._vocal_remover_zi = None

        # Channel Mode State
        cm_config = config.get('channel_mode', {})
        self._channel_mode = cm_config.get('mode', 'stereo').lower()

    def prepare(self, samplerate, channels):
        """Prepare effects for a specific samplerate and channel count."""
        self.samplerate = samplerate
        self.channels = channels

        # Reset filters that depend on samplerate
        self._update_equalizer()
        self._update_vocal_remover()

        # Reset spatializer
        self._spat_initialized = False

        # Reset compressor envelope
        self._compressor_envelope = 0.0
        self._compressor_rms_buffer.fill(0)

    def reset_state(self):
        """Reset internal state buffers (e.g. for seeking)."""
        # Reset EQ state
        if self._eq_zi is not None:
            self._eq_zi.fill(0)

        # Reset Vocal Remover state
        if self._vocal_remover_zi is not None:
            self._vocal_remover_zi.fill(0)

        # Reset Compressor state
        self._compressor_envelope = 0.0
        self._compressor_rms_buffer.fill(0)

        # Reset Spatializer state
        if self._spat_buffer is not None:
            self._spat_buffer.fill(0)

    def process(self, data):
        """Apply all enabled effects to the audio data."""
        # Apply Equalizer
        if self.equalizer_enabled and self._eq_sos is not None:
            # Apply Preamp
            if self._eq_preamp != 0.0:
                data[:] *= (10 ** (self._eq_preamp / 20.0))

            # Apply SOS filters
            # Check if ZI shape matches current channels (zi shape is (n_sections, 2, channels))
            if self._eq_zi is not None and self._eq_zi.shape[2] == data.shape[1]:
                data[:], self._eq_zi = scipy.signal.sosfilt(self._eq_sos, data, axis=0, zi=self._eq_zi)

        # Apply Compressor
        if self._compressor_enabled:
            data[:] = self._apply_compressor(data)

        # Apply Spatializer
        if self._spatializer_enabled:
            data[:] = self._apply_spatializer(data)

        # Apply Channel Mode
        data[:] = self._apply_channel_mode(data)

        # Apply Vocal Remover
        if self._vocal_remover_enabled:
            data[:] = self._apply_vocal_remover(data)

        return data

    # --- Equalizer Methods ---

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

    def _design_low_shelf(self, f0, gain_db, Q, fs):
        """Design coefficients for a low shelf filter."""
        A = 10 ** (gain_db / 40.0)
        w0 = 2 * np.pi * f0 / fs
        alpha = np.sin(w0) / (2 * Q)

        b0 = A * ((A + 1) - (A - 1) * np.cos(w0) + 2 * np.sqrt(A) * alpha)
        b1 = 2 * A * ((A - 1) - (A + 1) * np.cos(w0))
        b2 = A * ((A + 1) - (A - 1) * np.cos(w0) - 2 * np.sqrt(A) * alpha)
        a0 = (A + 1) + (A - 1) * np.cos(w0) + 2 * np.sqrt(A) * alpha
        a1 = -2 * ((A - 1) + (A + 1) * np.cos(w0))
        a2 = (A + 1) + (A - 1) * np.cos(w0) - 2 * np.sqrt(A) * alpha

        return np.array([b0, b1, b2, a0, a1, a2]) / a0

    def _design_high_shelf(self, f0, gain_db, Q, fs):
        """Design coefficients for a high shelf filter."""
        A = 10 ** (gain_db / 40.0)
        w0 = 2 * np.pi * f0 / fs
        alpha = np.sin(w0) / (2 * Q)

        b0 = A * ((A + 1) + (A - 1) * np.cos(w0) + 2 * np.sqrt(A) * alpha)
        b1 = -2 * A * ((A - 1) + (A + 1) * np.cos(w0))
        b2 = A * ((A + 1) + (A - 1) * np.cos(w0) - 2 * np.sqrt(A) * alpha)
        a0 = (A + 1) - (A - 1) * np.cos(w0) + 2 * np.sqrt(A) * alpha
        a1 = 2 * ((A - 1) - (A + 1) * np.cos(w0))
        a2 = (A + 1) - (A - 1) * np.cos(w0) - 2 * np.sqrt(A) * alpha

        return np.array([b0, b1, b2, a0, a1, a2]) / a0

    def _update_equalizer(self):
        """Recalculate equalizer filter coefficients."""
        if not self.equalizer_enabled:
            self._eq_sos = None
            self._eq_zi = None
            return

        fs = self.samplerate
        nyquist = fs / 2.0
        sos_list = []
        for i, freq in enumerate(self._eq_bands):
            # Ensure frequency is below Nyquist to prevent instability
            safe_freq = min(freq, nyquist - 10.0)

            if i == 0:
                # Low Shelf for the first band (60Hz)
                sos = self._design_low_shelf(safe_freq, self._eq_gains[i], 0.707, fs)
            elif i == len(self._eq_bands) - 1:
                # High Shelf for the last band (16kHz)
                sos = self._design_high_shelf(safe_freq, self._eq_gains[i], 0.707, fs)
            else:
                # Peaking filter for middle bands
                sos = self._design_peaking_filter(safe_freq, self._eq_gains[i], 1.414, fs)
            sos_list.append(sos)

        self._eq_sos = np.vstack(sos_list)

        # Initialize state if needed
        # Shape must be (n_sections, 2, channels) for scipy.signal.sosfilt with axis=0
        if self._eq_zi is None or self._eq_zi.shape != (len(self._eq_bands), 2, self.channels):
            self._eq_zi = np.zeros((len(self._eq_bands), 2, self.channels))

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

    # --- Compressor Methods ---

    def _apply_compressor(self, data):
        """Apply dynamic range compression to audio data."""
        # Convert parameters
        threshold_linear = 10 ** (self._compressor_threshold / 20.0)
        attack_coef = np.exp(-1.0 / (self._compressor_attack * self.samplerate / 1000.0))
        release_coef = np.exp(-1.0 / (self._compressor_release * self.samplerate / 1000.0))
        makeup_linear = 10 ** (self._compressor_makeup / 20.0)
        knee_db = self._compressor_knee

        # Process each sample
        compressed = np.zeros_like(data)

        # Pre-calculate RMS alpha if needed (approximate window average)
        rms_window = len(self._compressor_rms_buffer)
        rms_alpha = 1.0 - np.exp(-1.0 / rms_window)

        for i in range(len(data)):
            # Get input level based on detection mode
            if self._compressor_use_rms:
                # RMS detection using Exponential Moving Average (EMA)
                sample_power = np.mean(data[i] ** 2)
                current_ms = self._compressor_rms_buffer[0]
                new_ms = rms_alpha * sample_power + (1 - rms_alpha) * current_ms
                self._compressor_rms_buffer[0] = new_ms
                input_level = np.sqrt(new_ms)
            else:
                # Peak detection
                input_level = np.max(np.abs(data[i]))

            # Envelope follower
            if input_level > self._compressor_envelope:
                self._compressor_envelope = attack_coef * self._compressor_envelope + (1 - attack_coef) * input_level
            else:
                self._compressor_envelope = release_coef * self._compressor_envelope + (1 - release_coef) * input_level

            # Calculate gain reduction with knee
            envelope_db = 20 * np.log10(self._compressor_envelope + 1e-10)
            threshold_db = self._compressor_threshold

            if knee_db > 0:
                # Soft knee
                knee_lower = threshold_db - knee_db / 2
                knee_upper = threshold_db + knee_db / 2

                if envelope_db < knee_lower:
                    gain_reduction_db = 0.0
                elif envelope_db > knee_upper:
                    over_db = envelope_db - threshold_db
                    gain_reduction_db = over_db * (1.0 - 1.0 / self._compressor_ratio)
                else:
                    over_db = envelope_db - knee_lower
                    knee_ratio = over_db / knee_db
                    gain_reduction_db = knee_ratio * knee_ratio * knee_db * (1.0 - 1.0 / self._compressor_ratio) / 2
            else:
                # Hard knee
                if envelope_db > threshold_db:
                    over_db = envelope_db - threshold_db
                    gain_reduction_db = over_db * (1.0 - 1.0 / self._compressor_ratio)
                else:
                    gain_reduction_db = 0.0

            gain_reduction_linear = 10 ** (-gain_reduction_db / 20.0)

            # Apply gain reduction and makeup gain
            compressed[i] = data[i] * gain_reduction_linear * makeup_linear

        return compressed

    def set_compressor(self, enabled, threshold=-20.0, ratio=3.0, attack=5.0, release=100.0, makeup_gain=0.0, knee=0.0, use_rms=True):
        """Enable/disable and configure dynamic range compressor."""
        self._compressor_enabled = enabled
        self._compressor_threshold = max(-60.0, min(0.0, float(threshold)))
        self._compressor_ratio = max(1.0, min(20.0, float(ratio)))
        self._compressor_attack = max(0.1, min(500.0, float(attack)))
        self._compressor_release = max(1.0, min(1000.0, float(release)))
        self._compressor_makeup = max(-20.0, min(30.0, float(makeup_gain)))
        self._compressor_knee = max(0.0, min(10.0, float(knee)))
        self._compressor_use_rms = bool(use_rms)

        if enabled:
            mode = "RMS" if use_rms else "Peak"
            logger.info(f"Compressor enabled: threshold={threshold}dB, ratio={ratio}:1, attack={attack}ms, release={release}ms, makeup={makeup_gain}dB, knee={knee}dB, mode={mode}")
        else:
            logger.info("Compressor disabled")

    def get_compressor_enabled(self):
        return self._compressor_enabled

    # --- Spatializer Methods ---

    def set_spatializer(self, enabled, size=0.85, width=0.5, wet=0.4, dry=0.5, damp=0.5):
        """Configure spatializer."""
        self._spatializer_enabled = enabled
        self._spat_size = max(0.0, min(1.1, float(size)))
        self._spat_width = max(0.0, min(1.0, float(width)))
        self._spat_wet = max(0.0, min(1.0, float(wet)))
        self._spat_dry = max(0.0, min(1.0, float(dry)))
        self._spat_damp = max(0.0, min(1.0, float(damp)))

        if enabled:
            logger.info(f"Spatializer enabled: size={size}, width={width}, wet={wet}, dry={dry}, damp={damp}")
        else:
            logger.info("Spatializer disabled")

    def get_spatializer_enabled(self):
        return self._spatializer_enabled

    def _apply_spatializer(self, data):
        """Apply spatializer effect (Width + Simple Cross-Delay)."""
        if not self._spat_initialized:
            # Init simple buffers
            # 100ms max delay
            size = int(0.1 * self.samplerate)
            self._spat_buffer = np.zeros((size, 2))
            self._spat_write_pos = 0
            self._spat_initialized = True

        # 1. Width
        width_factor = self._spat_width * 2.0
        mid = (data[:, 0] + data[:, 1]) * 0.5
        side = (data[:, 0] - data[:, 1]) * 0.5
        side *= width_factor

        dry_signal = np.column_stack((mid + side, mid - side))

        # 2. Simple Reverb/Ambience (Cross-Delay)
        # Delay time based on 'size' (0-100ms)
        delay_samples = int(self._spat_size * 0.1 * self.samplerate)
        if delay_samples == 0: delay_samples = 1

        # Read from buffer (circular)
        num_frames = len(data)
        buffer_len = len(self._spat_buffer)

        # Create indices
        read_indices = (np.arange(num_frames) + self._spat_write_pos - delay_samples) % buffer_len
        write_indices = (np.arange(num_frames) + self._spat_write_pos) % buffer_len

        # Read delayed signal
        delayed = self._spat_buffer[read_indices]

        # Cross-feed: L gets delayed R, R gets delayed L
        reverb_signal = np.column_stack((delayed[:, 1], delayed[:, 0]))

        # Write current input to buffer (with some feedback for tail)
        # Use damp as feedback control
        feedback = self._spat_damp * 0.6
        self._spat_buffer[write_indices] = data + reverb_signal * feedback

        self._spat_write_pos = (self._spat_write_pos + num_frames) % buffer_len

        # Mix
        return dry_signal * self._spat_dry + reverb_signal * self._spat_wet

    # --- Channel Mode Methods ---

    def set_channel_mode(self, mode):
        """Set the channel processing mode."""
        self._channel_mode = mode.lower()
        logger.info(f"Channel mode set to: {self._channel_mode}")

    def get_channel_mode(self):
        return self._channel_mode

    def _apply_channel_mode(self, data):
        """Apply channel mode processing (Stereo, Mono, Left, Right, Side)."""
        if self._channel_mode == 'stereo' or data.shape[1] < 2:
            return data

        left = data[:, 0]
        right = data[:, 1]

        if self._channel_mode == 'mono':
            # (L+R) / 2
            mono = (left + right) * 0.5
            data[:, 0] = mono
            data[:, 1] = mono
        elif self._channel_mode == 'left channel':
            # L to both
            data[:, 1] = left
            data[:, 0] = left
        elif self._channel_mode == 'right channel':
            # R to both
            data[:, 0] = right
            data[:, 1] = right
        elif self._channel_mode == 'side (diff)':
            # (L-R) / 2
            side = (left - right) * 0.5
            data[:, 0] = side
            data[:, 1] = side

        return data

    # --- Vocal Remover Methods ---

    def set_vocal_remover_enabled(self, enabled):
        self._vocal_remover_enabled = enabled
        self._update_vocal_remover()

    def set_vocal_remover_intensity(self, intensity):
        self._vocal_remover_intensity = intensity
        self._update_vocal_remover()

    def get_vocal_remover_enabled(self):
        return self._vocal_remover_enabled

    def get_vocal_remover_intensity(self):
        return self._vocal_remover_intensity

    def _update_vocal_remover(self):
        """Update vocal remover filter coefficients."""
        if self._vocal_remover_enabled and self._vocal_remover_intensity > 0:
            # Vocals typically span from 200Hz to 8kHz
            low_cut = 200
            high_cut = 8000

            nyq = self.samplerate / 2
            low = max(20, low_cut) / nyq
            high = min(nyq - 100, high_cut) / nyq

            # Use Chebyshev Type II filter for very high stopband attenuation (60dB)
            self._vocal_remover_sos = scipy.signal.cheby2(
                8, 60, [low, high],
                btype='bandstop',
                output='sos'
            )

            if self._vocal_remover_zi is None or self._vocal_remover_zi.ndim != 2 or self._vocal_remover_zi.shape[0] != len(self._vocal_remover_sos):
                self._vocal_remover_zi = np.zeros((len(self._vocal_remover_sos), 2))
        else:
            self._vocal_remover_sos = None
            self._vocal_remover_zi = None

    def _apply_vocal_remover(self, data):
        """Apply vocal remover using center channel band-stop."""
        if self._vocal_remover_sos is not None and self._vocal_remover_zi is not None and data.shape[1] >= 2:
            left = data[:, 0]
            right = data[:, 1]

            # Calculate center (L+R) and side (L-R) channels
            center = (left + right) * 0.5
            side = (left - right) * 0.5

            # Apply band-stop filter to center channel only
            # This removes the vocal range from the center channel while preserving bass and highs
            center_filtered, self._vocal_remover_zi = scipy.signal.sosfilt(
                self._vocal_remover_sos, center, zi=self._vocal_remover_zi
            )

            # Blend based on intensity
            intensity = self._vocal_remover_intensity
            center_processed = (center_filtered * intensity) + (center * (1.0 - intensity))

            # Reconstruct stereo
            data[:, 0] = center_processed + side
            data[:, 1] = center_processed - side

            return data
        return data
