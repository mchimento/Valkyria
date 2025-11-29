"""
Global runtime state
"""
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class AppState:
    playlist: List[str] = field(default_factory=list)
    browser_files: List[str] = field(default_factory=list)
    current_index: Optional[int] = None
    dragged_index: Optional[int] = None
    play_on_double: bool = True
    current_playlist_path: Optional[str] = None
    repeat_mode: str = 'none'  # 'none', 'one', 'all'

    # Track current theme (default to light; will be overridden by apply_theme)
    _current_theme: str = 'light'

    # Support audio extensions
    exts = (".mp3", ".wav", ".flac", ".ogg", ".m4a")