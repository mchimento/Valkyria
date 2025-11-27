"""
Theme manager: loads JSON palette and exposes apply_to(root).
"""

import json
from pathlib import Path
from ui.styles import apply_base_styles

class ThemeManager:
    def __init__(self, settings):
        self.settings = settings
        self.palette = {}
        self.reload()

    def reload(self):
        name = self.settings.theme or "light"
        base = Path(__file__).parent
        path = base / f"{name}.json"
        if not path.exists():
            path = base / "light.json"
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.palette = json.load(f)
        except Exception:
            self.palette = {
                "bg": "#f0f0f0", "fg": "#000", "accent": "#0078d4",
                "accent_hover": "#106ebe", "tree_bg": "#ffffff",
                "tree_header": "#e0e0e0", "tooltip_bg": "#ffffe0", "highlight": "#FFF59D"
            }

    def apply_to(self, root):
        apply_base_styles(root, self.palette)
        try:
            root.configure(bg=self.palette.get("bg"))
        except Exception:
            pass
