"""
Theme manager: loads JSON palette and exposes apply_to(root).
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any
import tkinter as tk
from ui.styles import apply_base_styles

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
        path = Path(f"themes/{name}.json")

        if not path.is_file():
            logger.warning(f"Theme file not found: {path}, falling back to light theme")
            name = "light"
            path = Path("themes/light.json")

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

    def apply_to(self, root: tk.Tk) -> None:
        """
        Apply the current theme palette to the root window.

        Args:
            root: The Tkinter root window to apply styles to.
        """
        apply_base_styles(root, self.palette)
        try:
            root.configure(bg=self.palette.get("bg"))
        except Exception as e:
            logger.error(f"Failed to apply theme to root window: {e}", exc_info=True)
