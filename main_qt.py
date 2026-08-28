#!/usr/bin/env python3
"""
Entry point for the PySide6 build of Valkyria (migration in progress).
"""
import signal
import sys
import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.logging_config import setup_logging
from app.settings import Settings
from audio.audio_player import AudioPlayer
from themes.theme_manager import ThemeManager
from ui_qt.theme_bridge import ThemeSignal, apply_theme
from ui_qt.main_window import MainWindowQt
from ui_qt.player_bridge import PlayerBridge

logger = logging.getLogger(__name__)

window_instance = None
player_instance = None


def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    if player_instance is not None:
        try:
            player_instance.__del__()
        except Exception:
            logger.error("Error during audio cleanup", exc_info=True)
    if window_instance is not None:
        window_instance.close()
    sys.exit(0)


def main():
    global window_instance, player_instance

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    setup_logging()

    app = QApplication(sys.argv)

    settings = Settings()
    theme = ThemeManager(settings)
    theme_signal = ThemeSignal()
    apply_theme(app, theme.palette)

    bridge = PlayerBridge()
    player = AudioPlayer(on_track_end=bridge.track_ended.emit)
    player_instance = player

    player.set_fade_in_enabled(settings.fade_in_enabled)
    player.set_fade_in_duration(settings.fade_in_duration)
    player.set_fade_out_enabled(settings.fade_out_enabled)
    player.set_fade_out_duration(settings.fade_out_duration)

    window_instance = MainWindowQt(settings, theme, player, theme_signal)
    bridge.track_ended.connect(window_instance._on_track_ended, Qt.QueuedConnection)
    window_instance.show()

    logger.info("Valkyria (PySide6) started")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
