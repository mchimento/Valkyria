"""
Application coordinator
"""
import logging
import threading
from app.state import AppState
from app.settings import Settings
from themes.theme_manager import ThemeManager
from audio.audio_player import AudioPlayer
from ui.main_window import MainWindow
import audio.metadata as metadata_module

logger = logging.getLogger(__name__)


class ValkyriaApp:
    def __init__(self):
        logger.info("Initializing Valkyria")

        self.state = AppState()
        self.settings = Settings()
        self.theme = ThemeManager(self.settings)
        self.player = AudioPlayer(on_track_end=self._on_track_end)

        # Initialize fade settings
        self.player.set_fade_in_enabled(self.settings.fade_in_enabled)
        self.player.set_fade_in_duration(self.settings.fade_in_duration)
        self.player.set_fade_out_enabled(self.settings.fade_out_enabled)
        self.player.set_fade_out_duration(self.settings.fade_out_duration)

        # Initialize playback state from settings
        self.state.crossfade_enabled = getattr(self.settings, "crossfade_enabled", False)
        self.state.crossfade_duration = getattr(self.settings, "crossfade_duration", 5)
        self.state.silence_detection_enabled = getattr(self.settings, "silence_detection_enabled", False)

        self.window = MainWindow(self.state, self.theme, self.player, self.settings)

        # Configure metadata module BPM preference from settings
        try:
            metadata_module.set_bpm_preference(self.settings.bpm_mode)
        except Exception:
            pass

        logger.info("Valkyria initialized successfully")

    def _on_track_end(self):
        """Called from audio backend thread context via event; schedule UI-safe callback."""
        try:
            self.window.on_track_end_from_backend()
        except Exception:
            logger.error("Error handling track end event", exc_info=True)
            try:
                self.window.handle_track_end()
            except Exception:
                logger.error("Fallback track end handler also failed", exc_info=True)

    def run(self):
        """Start the application main loop."""
        logger.info("Starting Valkyria")
        self.window.start()
