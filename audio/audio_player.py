"""
VLC Audio backend wrapper.

Provides a simple, stable API to play/pause/stop and emits callbacks when a track ends.
"""

import threading
import vlc
from typing import Optional, Callable

class AudioPlayer:
    def __init__(self, on_track_end: Optional[Callable[[], None]] = None):
        # Create a single VLC instance and media_player
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        self.on_track_end = on_track_end

        # Attach VLC event for end-of-media
        events = self.player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end)

        # small lock for thread-safety
        self._lock = threading.RLock()

    def _on_end(self, event):
        # called by vlc in its internal thread
        if callable(self.on_track_end):
            try:
                self.on_track_end()
            except Exception:
                pass

    def play(self, path: str):
        with self._lock:
            media = self.instance.media_new(path)
            self.player.set_media(media)
            self.player.play()

    def pause(self):
        with self._lock:
            try:
                self.player.pause()
            except Exception:
                pass

    def stop(self):
        with self._lock:
            try:
                self.player.stop()
            except Exception:
                pass

    def set_volume(self, val: int):
        with self._lock:
            try:
                self.player.audio_set_volume(int(val))
            except Exception:
                pass

    def is_playing(self) -> bool:
        try:
            return bool(self.player.is_playing())
        except Exception:
            return False

    def get_time(self) -> int:
        try:
            return int(self.player.get_time() or 0)
        except Exception:
            return 0

    def get_length(self) -> int:
        try:
            return int(self.player.get_length() or 0)
        except Exception:
            return 0
