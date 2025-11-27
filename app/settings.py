"""
Settings (simple JSON)
"""
from pathlib import Path
import json

class Settings:
    CONFIG_PATH = Path.home() / ".tango_studio_config.json"

    def __init__(self):
        self.theme = "light"
        self.window_geometry = None
        self.load()

    def load(self):
        try:
            if self.CONFIG_PATH.exists():
                with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.theme = data.get("theme", self.theme)
                self.window_geometry = data.get("window_geometry", self.window_geometry)
        except Exception:
            # ignore malformed config
            pass

    def save(self):
        try:
            data = {"theme": self.theme, "window_geometry": self.window_geometry}
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
