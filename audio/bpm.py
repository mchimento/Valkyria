"""
BPM-related utilities and logic.
"""

import logging
from audio.metadata import analyze_bpm, write_bpm

logger = logging.getLogger(__name__)

def on_bpm_updated(filepath, state):
    """Handle BPM update notifications by refreshing status if current track matches."""
    try:
        idx = state.current_index
        if idx is not None and idx < len(state.playlist):
            current_path = state.playlist[idx]
            if current_path == filepath:
                state.update_meta_with_temp_bpm()
    except Exception:
        # Fail silently - BPM updates are not critical
        pass

def analyze_bpm_worker(filepath, root, on_complete):
    """Worker function to analyze BPM in background."""
    try:
        analyzed_bpm = analyze_bpm(filepath)
        root.after(0, on_complete, filepath, analyzed_bpm)
    except Exception as e:
        logger.error(f"Error in BPM analysis worker: {e}")
        root.after(0, on_complete, filepath, None)

def save_bpm_worker(filepath, bpm_value, root, on_complete):
    """Worker function to save BPM in background."""
    try:
        write_bpm(filepath, bpm_value)
        root.after(0, on_complete, filepath, True)
    except Exception as e:
        logger.error(f"Error in BPM save worker: {e}")
        root.after(0, on_complete, filepath, False)