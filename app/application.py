"""
Application coordinator
"""
import logging
from app.state import AppState
from app.settings import Settings
from themes.theme_manager import ThemeManager
from audio.audio_player import AudioPlayer
from ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class TangoStudioApp:
    def __init__(self) -> None:
        logger.info("Initializing Tango Studio")

        # core modules
        self.state = AppState()
        self.settings = Settings()
        self.theme = ThemeManager(self.settings)

        # audio backend: pass callback for track end
        self.player = AudioPlayer(on_track_end=self._on_track_end)

        # main window (UI)
        self.window = MainWindow(self.state, self.theme, self.player, self.settings)

        logger.info("Tango Studio initialized successfully")

    def _on_track_end(self) -> None:
        """Called from audio backend thread context via event; schedule UI-safe callback."""
        try:
            # main window has a thread-safe helper to call on the UI thread
            self.window.on_track_end_from_backend()
        except Exception:
            logger.error("Error handling track end event", exc_info=True)
            # fallback: call UI handler directly (MainWindow will handle safe scheduling)
            try:
                self.window.handle_track_end()
            except Exception:
                logger.error("Fallback track end handler also failed", exc_info=True)

    def run(self) -> None:
        """Start the application main loop."""
        logger.info("Starting Tango Studio")
        self.window.start()
