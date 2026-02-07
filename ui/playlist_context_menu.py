"""
Context menu for playlist items.
Provides quick access to common operations on playlist songs.
"""
import tkinter as tk
from ui.booklet_viewer import BookletViewer


class PlaylistContextMenu:
    def __init__(self, parent, play_callback=None, metadata_callback=None, remove_callback=None, get_current_file_callback=None, play_after_current_callback=None, set_time_limit_callback=None, clear_time_limit_callback=None):
        """
        Initialize the playlist context menu.

        Args:
            parent: Parent widget (typically the playlist tree)
            play_callback: Function to call when "Play Song" is selected
            metadata_callback: Function to call when "Show Metadata" is selected
            remove_callback: Function to call when "Remove from Playlist" is selected
            get_current_file_callback: Function to get the current selected file path
            play_after_current_callback: Function to call when "Play After Current Song" is selected
            set_time_limit_callback: Function to call when "Play for time..." is selected
            clear_time_limit_callback: Function to call when "Clear time limit" is selected
        """
        self.parent = parent
        self.play_callback = play_callback
        self.metadata_callback = metadata_callback
        self.remove_callback = remove_callback
        self.get_current_file_callback = get_current_file_callback
        self.play_after_current_callback = play_after_current_callback
        self.set_time_limit_callback = set_time_limit_callback
        self.clear_time_limit_callback = clear_time_limit_callback

        # Create the menu
        self.menu = tk.Menu(parent, tearoff=0)
        self.menu.add_command(label="▶ Play", command=self._on_play)
        self.menu.add_command(label="Play After Current Song", command=self._on_play_after_current)
        self.menu.add_separator()
        self.menu.add_command(label="⏱ Play for time...", command=self._on_set_time_limit)
        self.menu.add_command(label="✖ Clear time limit", command=self._on_clear_time_limit)
        self.menu.add_separator()
        self.menu.add_command(label="Show Metadata", command=self._on_metadata)
        self.menu.add_command(label="Show Album Booklet", command=self._on_booklet)
        self.menu.add_separator()
        self.menu.add_command(label="Remove from Playlist", command=self._on_remove)

    def _on_play(self):
        """Handle Play Song menu item."""
        if callable(self.play_callback):
            self.play_callback()

    def _on_play_after_current(self):
        """Handle Play After Current Song menu item."""
        if callable(self.play_after_current_callback):
            self.play_after_current_callback()
    
    def _on_set_time_limit(self):
        """Handle Play for time... menu item."""
        if callable(self.set_time_limit_callback):
            self.set_time_limit_callback()
    
    def _on_clear_time_limit(self):
        """Handle Clear time limit menu item."""
        if callable(self.clear_time_limit_callback):
            self.clear_time_limit_callback()

    def _on_metadata(self):
        """Handle Show Metadata menu item."""
        if callable(self.metadata_callback):
            self.metadata_callback()

    def _on_booklet(self):
        """Handle Show Album Booklet menu item."""
        if callable(self.get_current_file_callback):
            filepath = self.get_current_file_callback()
            if filepath:
                BookletViewer(self.parent, filepath).show()

    def _on_remove(self):
        """Handle Remove from Playlist menu item."""
        if callable(self.remove_callback):
            self.remove_callback()

    def show(self, event):
        """
        Display the context menu at the cursor position.

        Args:
            event: The event object containing cursor coordinates
        """
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()
