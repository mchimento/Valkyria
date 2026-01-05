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


class TangoStudioApp:
    def __init__(self) -> None:
        logger.info("Initializing Tango Studio")

        self.state = AppState()
        self.settings = Settings()
        self.theme = ThemeManager(self.settings)
        self.player = AudioPlayer(on_track_end=self._on_track_end)
        self.window = MainWindow(self.state, self.theme, self.player, self.settings)

        # Configure metadata module BPM preference from settings
        try:
            metadata_module.set_bpm_preference(self.settings.bpm_mode)
        except Exception:
            pass

        # Warm up BPM analysis libraries in background to prevent first-time lag
        threading.Thread(target=self._warmup_bpm_analysis, daemon=True).start()

        logger.info("Tango Studio initialized successfully")

    def _warmup_bpm_analysis(self):
        """Preload heavy libraries used for BPM analysis to avoid first-time interruption."""
        try:
            import numpy as np
            import librosa
            # Create a small dummy audio signal to trigger library initialization
            # Use 1 second of audio to avoid FFT warnings
            dummy_audio = np.random.randn(22050).astype(np.float32)
            _ = librosa.onset.onset_strength(y=dummy_audio, sr=22050, hop_length=512, n_fft=2048)
        except Exception:
            # Silently fail - warmup is optional
            pass

    def _on_track_end(self) -> None:
        """Called from audio backend thread context via event; schedule UI-safe callback."""
        try:
            self.window.on_track_end_from_backend()
        except Exception:
            logger.error("Error handling track end event", exc_info=True)
            try:
                self.window.handle_track_end()
            except Exception:
                logger.error("Fallback track end handler also failed", exc_info=True)

    def run(self) -> None:
        """Start the application main loop."""
        logger.info("Starting Tango Studio")
        self.window.start()
