"""
Settings (simple JSON)
"""
import logging
from pathlib import Path
import json
from typing import Optional, Tuple
from app.paths import get_user_data_path, get_resource_path

logger = logging.getLogger(__name__)


class Settings:
    def __init__(self) -> None:
        self.theme: str = "light"
        self.window_geometry: Optional[str] = None
        # Separate from window_geometry: Tk's "WxH+X+Y" string format and Qt's
        # QRect aren't interchangeable, and both UIs can coexist during the
        # PySide6 migration.
        self.window_geometry_qt: Optional[str] = None
        self.volume: int = 80
        self.mute: bool = False
        self.show_playlist: bool = True
        self.show_browser: bool = True
        self.show_dj: bool = True
        # BPM preference: 'perceived' maps tempo into 50-100, 'raw' returns detected tempo
        self.bpm_mode: str = 'raw'

        # Supported audio extensions — loaded from config.json
        self.supported_extensions: Tuple[str, ...] = (".mp3", ".wav", ".flac", ".ogg", ".m4a")
        self._load_app_config()

        # Mini player (enabled by default)
        self.mini_player_enabled: bool = True

        # Fade settings
        self.fade_in_enabled: bool = False
        self.fade_in_duration: int = 3
        self.fade_out_enabled: bool = False
        self.fade_out_duration: int = 3

        # Silence detection
        self.silence_detection_enabled: bool = False

        self.load()

    def _load_app_config(self) -> None:
        """Load static app defaults from the bundled config.json."""
        try:
            path = get_resource_path("config.json")
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                exts = data.get("audio", {}).get("supported_extensions")
                if exts:
                    self.supported_extensions = tuple(exts)
        except Exception:
            logger.warning("Failed to load app config from config.json", exc_info=True)

    @property
    def config_path(self) -> Path:
        return get_user_data_path() / 'config.json'

    def load(self) -> None:
        """Load settings from the config file."""
        try:
            path = self.config_path
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.theme = data.get("theme", self.theme)
                self.window_geometry = data.get("window_geometry", self.window_geometry)
                self.window_geometry_qt = data.get("window_geometry_qt", self.window_geometry_qt)
                self.volume = data.get("volume", self.volume)
                self.mute = data.get("mute", self.mute)
                self.show_playlist = data.get("show_playlist", self.show_playlist)
                self.show_browser = data.get("show_browser", self.show_browser)
                self.show_dj = data.get("show_dj", self.show_dj)
                self.bpm_mode = data.get("bpm_mode", self.bpm_mode)
                self.mini_player_enabled = data.get("mini_player_enabled", self.mini_player_enabled)

                self.fade_in_enabled = data.get("fade_in_enabled", self.fade_in_enabled)
                self.fade_in_duration = data.get("fade_in_duration", self.fade_in_duration)
                self.fade_out_enabled = data.get("fade_out_enabled", self.fade_out_enabled)
                self.fade_out_duration = data.get("fade_out_duration", self.fade_out_duration)
                self.silence_detection_enabled = data.get("silence_detection_enabled", self.silence_detection_enabled)

        except Exception:
            logger.warning(f"Failed to load settings from {self.config_path}", exc_info=True)

    def save(self) -> None:
        """Save settings to the config file."""
        try:
            data = {
                "theme": self.theme,
                "window_geometry": self.window_geometry,
                "window_geometry_qt": self.window_geometry_qt,
                "volume": self.volume,
                "mute": self.mute,
                "show_playlist": self.show_playlist,
                "show_browser": self.show_browser,
                "show_dj": self.show_dj,
                "bpm_mode": self.bpm_mode,
                "mini_player_enabled": self.mini_player_enabled,
                "fade_in_enabled": self.fade_in_enabled,
                "fade_in_duration": self.fade_in_duration,
                "fade_out_enabled": self.fade_out_enabled,
                "fade_out_duration": self.fade_out_duration,
                "silence_detection_enabled": self.silence_detection_enabled
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            logger.error(f"Failed to save settings to {self.config_path}", exc_info=True)
