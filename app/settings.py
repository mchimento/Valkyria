"""
Settings (simple JSON)
"""
import logging
from pathlib import Path
import json
from typing import Optional
from app.paths import get_user_data_path

logger = logging.getLogger(__name__)


class Settings:
    def __init__(self) -> None:
        self.theme: str = "light"
        self.window_geometry: Optional[str] = None
        self.volume: int = 80  # Default volume level
        self.mute: bool = False  # Mute state
        self.load()

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
                self.volume = data.get("volume", self.volume)
                self.mute = data.get("mute", self.mute)
        except Exception:
            logger.warning(f"Failed to load settings from {self.config_path}", exc_info=True)

    def save(self) -> None:
        """Save settings to the config file."""
        try:
            data = {
                "theme": self.theme,
                "window_geometry": self.window_geometry,
                "volume": self.volume,
                "mute": self.mute
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            logger.error(f"Failed to save settings to {self.config_path}", exc_info=True)
