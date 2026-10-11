"""
Theme manager: loads a JSON palette (see themes/*.json). Qt applies it via
ui_qt/theme_bridge.py's QSS stylesheet.
"""

import json
import logging
from typing import Dict, Any

from app.paths import get_resource_path

logger = logging.getLogger(__name__)

class ThemeManager:
    def __init__(self, settings) -> None:
        """
        Initialize the theme manager.

        Args:
            settings: Settings object containing theme preference.
        """
        self.settings = settings
        self.palette: Dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        """
        Load theme from JSON file based on settings.

        Falls back to light theme if the specified theme doesn't exist.
        Uses hardcoded defaults if theme file cannot be loaded.
        """
        name = self.settings.theme or "light"

        path = get_resource_path(f"themes/{name}.json")

        if not path.exists():
            path = get_resource_path("themes/light.json")

        try:
            with open(path, "r", encoding="utf-8") as f:
                self.palette = json.load(f)
            logger.info(f"Loaded theme: {name}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in theme file {path}: {e}", exc_info=True)
            self._load_default_palette()
        except Exception as e:
            logger.error(f"Failed to load theme file {path}: {e}", exc_info=True)
            self._load_default_palette()

    def _load_default_palette(self) -> None:
        """Load hardcoded default palette as fallback."""
        self.palette = {
            "bg": "#f0f0f0", "fg": "#000", "accent": "#0078d4",
            "accent_hover": "#106ebe", "tree_bg": "#ffffff",
            "tree_header": "#e0e0e0", "tooltip_bg": "#ffffe0",
            "highlight": "#FFF59D", "ui_font": "Segoe UI"
        }
        logger.info("Loaded default fallback palette")
