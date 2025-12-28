"""
This module handles playback-related functionality for the audio player.
"""

import random
from mutagen import File as MutagenFile


def get_artist(file_path):
    """Get artist from metadata or return empty string."""
    try:
        audio = MutagenFile(file_path, easy=True)
        if audio and audio.tags:
            artist = audio.get('artist', [''])[0]
            return artist.lower() if artist else ''
    except Exception:
        pass
    return ''


def sort_playlist_by_artist(playlist, current_index=None):
    """Sort playlist by artist (from metadata) or filename."""
    if not playlist:
        return playlist, current_index

    current_path = playlist[current_index] if current_index is not None else None
    playlist_sorted = sorted(playlist, key=get_artist)

    if current_path and current_path in playlist_sorted:
        try:
            new_index = playlist_sorted.index(current_path)
        except ValueError:
            new_index = None
    else:
        new_index = None

    return playlist_sorted, new_index


def sort_playlist_by_title(playlist, current_index=None):
    """Sort playlist by title (from metadata) or filename."""
    if not playlist:
        return playlist, current_index

    from .metadata import get_display_title

    current_path = playlist[current_index] if current_index is not None else None
    playlist_sorted = sorted(playlist, key=lambda x: get_display_title(x).lower())

    if current_path and current_path in playlist_sorted:
        try:
            new_index = playlist_sorted.index(current_path)
        except ValueError:
            new_index = None
    else:
        new_index = None

    return playlist_sorted, new_index


def shuffle_playlist(playlist, current_index=None):
    """Shuffle the playlist while maintaining the currently playing track if any."""
    if not playlist:
        return [], None

    if current_index is not None and 0 <= current_index < len(playlist):
        # Remove current track temporarily
        current_track = playlist.pop(current_index)
        # Shuffle the rest
        random.shuffle(playlist)
        # Reinsert current track at the beginning
        playlist.insert(0, current_track)
        return playlist, 0
    else:
        # No current track or invalid index, just shuffle everything
        shuffled = playlist.copy()
        random.shuffle(shuffled)
        return shuffled, None


def clear_playlist():
    """Return an empty playlist and reset current index."""
    return [], None


def move_selected_up(playlist, selected_indices):
    """Move selected items up in the playlist."""
    if not selected_indices or min(selected_indices) <= 0:
        return playlist.copy()

    new_playlist = playlist.copy()
    for i in sorted(selected_indices):
        if i > 0:  # Can't move first item up
            new_playlist[i-1], new_playlist[i] = new_playlist[i], new_playlist[i-1]
    return new_playlist


def move_selected_down(playlist, selected_indices):
    """Move selected items down in the playlist."""
    if not selected_indices or max(selected_indices) >= len(playlist) - 1:
        return playlist.copy()

    new_playlist = playlist.copy()
    for i in sorted(selected_indices, reverse=True):
        if i < len(new_playlist) - 1:  # Can't move last item down
            new_playlist[i], new_playlist[i+1] = new_playlist[i+1], new_playlist[i]
    return new_playlist


def remove_selected_from_playlist(playlist, selected_indices, current_index):
    """Remove selected items from the playlist and adjust current index if needed."""
    if not selected_indices:
        return playlist.copy(), current_index

    new_playlist = [track for i, track in enumerate(playlist) if i not in selected_indices]

    # Adjust current index if needed
    if current_index is not None:
        # Count how many items before current_index were removed
        removed_before = sum(1 for i in selected_indices if i < current_index)
        new_index = current_index - removed_before

        # If current track was removed, set to None
        if current_index in selected_indices:
            new_index = None
        # If the new index is out of bounds, set to last item
        elif new_index >= len(new_playlist):
            new_index = len(new_playlist) - 1 if new_playlist else None
    else:
        new_index = None

    return new_playlist, new_index
