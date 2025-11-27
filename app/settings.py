"""
Settings (simple JSON)
"""
import logging
from pathlib import Path
import json
from typing import Optional

logger = logging.getLogger(__name__)


class Settings:
    CONFIG_PATH = ath('.config.json')

    def __init__(self) -> None:
        self.theme: str = "light"
        self.window_geometry: Optional[str] = None
        self.load()

    def load(self) -> None:
        """Load settings from the config file."""
        try:
            if self.CONFIG_PATH.exists():
                with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.theme = data.get("theme", self.theme)
                self.window_geometry = data.get("window_geometry", self.window_geometry)
        except Exception:
            logger.warning(f"Failed to load settings from {self.CONFIG_PATH}", exc_info=True)

    def save(self) -> None:
        """Save settings to the config file."""
        try:
            data = {"theme": self.theme, "window_geometry": self.window_geometry}
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            logger.error(f"Failed to save settings to {self.CONFIG_PATH}", exc_info=True)
