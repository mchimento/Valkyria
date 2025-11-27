"""
Application coordinator
"""
from app.state import AppState
from app.settings import Settings
from themes.theme_manager import ThemeManager
from audio.audio_player import AudioPlayer
from ui.main_window import MainWindow

class TangoStudioApp:
    def __init__(self):
        # core modules
        self.state = AppState()
        self.settings = Settings()
        self.theme = ThemeManager(self.settings)

        # audio backend: pass callback for track end
        self.player = AudioPlayer(on_track_end=self._on_track_end)

        # main window (UI)
        self.window = MainWindow(self.state, self.theme, self.player, self.settings)

    def _on_track_end(self):
        # called from audio backend thread context via event; schedule UI-safe callback
        try:
            # main window has a thread-safe helper to call on the UI thread
            self.window.on_track_end_from_backend()
        except Exception:
            # fallback: call UI handler directly (MainWindow will handle safe scheduling)
            self.window.handle_track_end()

    def run(self):
        self.window.start()
