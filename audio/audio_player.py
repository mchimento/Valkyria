"""
VLC Audio backend wrapper.

Provides a simple, stable API to play/pause/stop and emits callbacks when a track ends.
"""

import logging
import threading
import os
import sys
from pathlib import Path

# Add project root to DLL search path for libvlc.dll
# This allows VLC to find libvlc.dll in the project root directory
if sys.platform == 'win32':
    # Get the project root (parent of audio/ directory)
    project_root = Path(__file__).parent.parent
    # Add to DLL search path (Python 3.8+)
    if hasattr(os, 'add_dll_directory'):
        try:
            os.add_dll_directory(str(project_root))
        except (OSError, FileNotFoundError):
            pass
    # Also add to PATH as fallback for older Python versions
    os.environ['PATH'] = str(project_root) + os.pathsep + os.environ.get('PATH', '')

import vlc
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class AudioPlayer:
    def __init__(self, on_track_end: Optional[Callable[[], None]] = None) -> None:
        """
        Initialize the audio player.

        Args:
            on_track_end: Optional callback function to be called when a track ends.
        """
        # Create a single VLC instance and media_player
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.on_track_end = on_track_end

        # Attach VLC event for end-of-media
        events = self.player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end)

        # small lock for thread-safety
        self._lock = threading.RLock()

        logger.info("AudioPlayer initialized")

    def _on_end(self, event) -> None:
        """Called by VLC in its internal thread when media ends."""
        if callable(self.on_track_end):
            try:
                self.on_track_end()
            except Exception:
                logger.error("Error in track end callback", exc_info=True)

    def play(self, path: str) -> None:
        """
        Play an audio file.

        Args:
            path: Path to the audio file to play.
        """
        with self._lock:
            try:
                media = self.instance.media_new(path)
                self.player.set_media(media)
                self.player.play()
            except Exception:
                logger.error(f"Failed to play: {path}", exc_info=True)

    def pause(self) -> None:
        """Pause or resume playback."""
        with self._lock:
            try:
                self.player.pause()
            except Exception:
                logger.error("Failed to pause playback", exc_info=True)

    def stop(self) -> None:
        """Stop playback."""
        with self._lock:
            try:
                self.player.stop()
            except Exception:
                logger.error("Failed to stop playback", exc_info=True)

    def set_volume(self, val: int) -> None:
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

    def is_playing(self) -> bool:
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

    def get_time(self) -> int:
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

    def get_length(self) -> int:
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
