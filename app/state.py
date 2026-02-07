"""
Global runtime state
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict

@dataclass
class AppState:
    playlist: List[str] = field(default_factory=list)
    browser_files: List[str] = field(default_factory=list)
    current_index: Optional[int] = None
    dragged_index: Optional[int] = None
    play_on_double: bool = True
    current_playlist_path: Optional[str] = None
    repeat_mode: str = 'none'
    selected_indices: List[int] = field(default_factory=list)

    # Playback time limits per track (filepath -> seconds)
    play_limits: Dict[str, float] = field(default_factory=dict)

    # Playback features runtime state
    crossfade_enabled: bool = False
    crossfade_duration: int = 5
    silence_detection_enabled: bool = False

    _current_theme: str = 'light'
    exts = (".mp3", ".wav", ".flac", ".ogg", ".m4a")