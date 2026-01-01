"""
VLC Audio backend wrapper.

Provides a simple, stable API to play/pause/stop and emits callbacks when a track ends.
"""

import logging
import threading
import os
import sys
from pathlib import Path

import vlc
import threading
import audio.metadata as metadata_module

logger = logging.getLogger(__name__)

# Add project root to DLL search path for libvlc.dll
# This allows VLC to find libvlc.dll in the project root directory
if sys.platform == 'win32':
    # Get the project root (parent of audio/ directory)
    if getattr(sys, 'frozen', False):
        project_root = Path(sys._MEIPASS)
    else:
        project_root = Path(__file__).parent.parent
    # Path to the bundled plugins directory
    plugins_dir = project_root / 'plugins'

    # Add to DLL search path (Python 3.8+)
    if hasattr(os, 'add_dll_directory'):
        try:
            # We need to add the plugins directory itself where libvlc.dll resides
            os.add_dll_directory(str(plugins_dir))
        except (OSError, FileNotFoundError):
            pass

    # Also add to PATH as fallback for older Python versions and for other dependencies
    os.environ['PATH'] = str(plugins_dir) + os.pathsep + os.environ.get('PATH', '')

    # Explicitly set the library path for python-vlc
    os.environ['PYTHON_VLC_LIB_PATH'] = str(plugins_dir / 'libvlc.dll')

    # Set VLC_PLUGIN_PATH to plugins_dir, where libvlc will find the 'plugins' subdirectory
    os.environ['VLC_PLUGIN_PATH'] = str(plugins_dir)

class AudioPlayer:
    def __init__(self, on_track_end=None):
        """
        Initialize the audio player.

        Args:
            on_track_end: Optional callback function to be called when a track ends.
        """
        # Create a single VLC instance and media_player
        # Use --quiet to suppress VLC's startup sound and messages
        self.instance = vlc.Instance('--quiet', '--no-video')
        self.player = self.instance.media_player_new()
        self.on_track_end = on_track_end

        # Attach VLC event for end-of-media
        events = self.player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end)

        # small lock for thread-safety
        self._lock = threading.RLock()

        # Initialize equalizer
        try:
            self.equalizer = vlc.AudioEqualizer()
        except Exception as e:
            logger.warning(f"Failed to initialize equalizer: {e}")
            self.equalizer = None

        self.equalizer_enabled = False

        logger.info("AudioPlayer initialized")

    def _on_end(self, event):
        """Called by VLC in its internal thread when media ends."""
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
        with self._lock:
            try:
                # Stop current playback to prevent audio overlap noise
                if self.player.is_playing():
                    self.player.stop()

                media = self.instance.media_new(path)
                self.player.set_media(media)
                self.player.play()

            except Exception:
                logger.error(f"Failed to play: {path}", exc_info=True)

    def pause(self):
        """Pause or resume playback."""
        with self._lock:
            try:
                self.player.pause()
            except Exception:
                logger.error("Failed to pause playback", exc_info=True)

    def stop(self):
        """Stop playback."""
        with self._lock:
            try:
                self.player.stop()
            except Exception:
                logger.error("Failed to stop playback", exc_info=True)

    def set_volume(self, val):
        """
        Set the playback volume.

        Args:
            val: Volume level (0-100).
        """
        with self._lock:
            try:
                self.player.audio_set_volume(int(val))
            except Exception:
                logger.error(f"Failed to set volume to {val}", exc_info=True)

    def get_mute_state(self):
        """
        Check if audio is currently muted.

        Returns:
            True if muted, False otherwise.
        """
        try:
            return bool(self.player.audio_get_mute())
        except Exception:
            logger.error("Failed to check mute status", exc_info=True)
            return False

    def set_mute(self, mute):
        """
        Set mute state.

        Args:
            mute: True to mute, False to unmute.
        """
        with self._lock:
            try:
                self.player.audio_set_mute(int(mute))
                logger.info(f"Mute set to: {mute}")
            except Exception:
                logger.error(f"Failed to set mute to {mute}", exc_info=True)

    def is_playing(self):
        """
        Check if audio is currently playing.

        Returns:
            True if playing, False otherwise.
        """
        try:
            return bool(self.player.is_playing())
        except Exception:
            logger.error("Failed to check playback status", exc_info=True)
            return False

    def is_paused(self):
        """
        Check if audio is currently paused.

        Returns:
            True if paused, False otherwise.
        """
        try:
            return self.player.get_state() == vlc.State.Paused
        except Exception:
            logger.error("Failed to check pause status", exc_info=True)
            return False

    def get_time(self):
        """
        Get current playback position in milliseconds.

        Returns:
            Current position in milliseconds, or 0 if unavailable.
        """
        try:
            return int(self.player.get_time() or 0)
        except Exception:
            logger.error("Failed to get playback time", exc_info=True)
            return 0

    def get_length(self):
        """
        Get total track length in milliseconds.

        Returns:
            Track length in milliseconds, or 0 if unavailable.
        """
        try:
            return int(self.player.get_length() or 0)
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
                self.player.set_time(time_ms)
            except Exception:
                logger.error(f"Failed to set time to {time_ms}", exc_info=True)

    def get_audio_devices(self) -> list:
        """
        Get available audio output devices.

        Returns:
            List of tuples (device_id, device_name). device_id is the actual VLC device identifier (GUID or similar).
            The default device has device_id = '__DEFAULT__'.
        """
        try:
            devices = []

            # Get audio output devices from VLC
            aout = self.player.audio_output_device_enum()

            if aout:
                device = aout
                is_first = True
                while device:
                    try:
                        content = device.contents
                        # Get device description (friendly name)
                        desc = getattr(content, 'description', None)
                        # Get device ID (GUID or identifier)
                        dev_id = getattr(content, 'device', None)

                        if desc:
                            if isinstance(desc, bytes):
                                desc = desc.decode('utf-8', errors='ignore')

                            if isinstance(dev_id, bytes):
                                dev_id = dev_id.decode('utf-8', errors='ignore')

                            # First device with empty ID is the default
                            if is_first and not dev_id:
                                device_key = '__DEFAULT__'
                                is_first = False
                            else:
                                device_key = dev_id if dev_id else desc

                            devices.append((device_key, str(desc)))

                        # Move to next device
                        device = getattr(content, 'next', None)
                    except Exception:
                        break

            # If no devices found, return default option
            if not devices:
                devices.append(('__DEFAULT__', 'Default Audio Device'))

            return devices
        except Exception as e:
            logger.error(f"Failed to get audio devices: {e}")
            return [('__DEFAULT__', 'Default Audio Device')]

    def set_audio_device(self, device_id):
        """
        Set the audio output device.

        Args:
            device_id: Device ID (GUID or identifier from VLC) or '__DEFAULT__' for system default.
        """
        try:
            if device_id == '__DEFAULT__':
                # Reset to default by setting empty device ID
                self.player.audio_output_device_set(None, '')
            else:
                # Set using the actual device ID (GUID)
                self.player.audio_output_device_set(None, device_id)

            logger.info(f"Audio device set to: {device_id}")
        except Exception as e:
            logger.error(f"Failed to set audio device to {device_id}: {e}")

    def set_equalizer_enabled(self, enabled):
        """Enable or disable the equalizer."""
        if not self.equalizer:
            return

        with self._lock:
            self.equalizer_enabled = enabled
            if enabled:
                self.player.set_equalizer(self.equalizer)
            else:
                self.player.set_equalizer(None)

    def get_equalizer_enabled(self):
        return self.equalizer_enabled

    def set_equalizer_preamp(self, preamp):
        """Set preamp level in dB (-20 to 20)."""
        if not self.equalizer:
            return

        with self._lock:
            try:
                self.equalizer.set_preamp(preamp)
                # Re-apply if enabled to ensure update takes effect immediately
                if self.equalizer_enabled:
                    self.player.set_equalizer(self.equalizer)
            except Exception as e:
                logger.error(f"Failed to set equalizer preamp: {e}")

    def get_equalizer_preamp(self):
        if not self.equalizer:
            return 0.0
        return self.equalizer.get_preamp()

    def set_equalizer_band(self, band_index, value):
        """Set gain for a specific band in dB (-20 to 20)."""
        if not self.equalizer:
            return

        with self._lock:
            try:
                self.equalizer.set_amp_at_index(value, band_index)
                # Re-apply if enabled to ensure update takes effect immediately
                if self.equalizer_enabled:
                    self.player.set_equalizer(self.equalizer)
            except Exception as e:
                logger.error(f"Failed to set equalizer band {band_index}: {e}")

    def get_equalizer_band(self, band_index):
        if not self.equalizer:
            return 0.0
        return self.equalizer.get_amp_at_index(band_index)

    def set_playback_rate(self, rate):
        """
        Set playback speed.
        Args:
            rate: Speed factor (e.g. 1.0 is normal, 0.5 is half speed, 2.0 is double).
        """
        try:
            self.player.set_rate(rate)
        except Exception as e:
            logger.error(f"Failed to set playback rate: {e}")

    def get_playback_rate(self):
        """Get current playback rate."""
        try:
            return self.player.get_rate()
        except Exception:
            return 1.0

    def set_stereo_mode(self, mode):
        """
        Set stereo output mode.
        Args:
            mode: One of 'stereo', 'reverse', 'left', 'right'.
        """
        mode_map = {
            'stereo': vlc.AudioOutputChannel.Stereo,
            'reverse': vlc.AudioOutputChannel.RStereo,
            'left': vlc.AudioOutputChannel.Left,
            'right': vlc.AudioOutputChannel.Right
        }
        if mode in mode_map:
            try:
                self.player.audio_output_set_channel(mode_map[mode])
            except Exception as e:
                logger.error(f"Failed to set stereo mode: {e}")
