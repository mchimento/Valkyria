
import tkinter as tk
from tkinter import ttk
import os


from ui.utils import get_display_title
from ui.playlist_context_menu import PlaylistContextMenu

class PlaylistView(ttk.Frame):
    def __init__(self, master, state, theme, tooltip_manager=None, select_callback=None, change_callback=None,
                 play_callback=None, metadata_callback=None, remove_callback=None):
        super().__init__(master)
        self.state = state
        self.theme = theme
        self.select_callback = select_callback
        self.change_callback = change_callback
        self.tooltip_manager = tooltip_manager
        self.play_callback = play_callback
        self.metadata_callback = metadata_callback
        self.remove_callback = remove_callback

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True)

        # Vertical scrollbar
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        vsb.pack(side="right", fill="y")

        # Treeview
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("Playlist",),
            show="headings",
            selectmode="browse",
            yscrollcommand=vsb.set
        )
        self.tree.heading("Playlist", text="Playlist")
        self.tree.column('Playlist', width=350, minwidth=100, stretch=True)
        self.update_theme()
        self.tree.pack(fill="both", expand=True)

        # Connect scrollbars to Treeview
        vsb.config(command=self.tree.yview)

        # ---------- Context Menu ----------
        self.context_menu = PlaylistContextMenu(
            self.tree,
            play_callback=self._on_context_play,
            metadata_callback=self._on_context_metadata,
            remove_callback=self._on_context_remove
        )

        # ---------- Bindings ----------
        self.tree.bind("<Double-1>", self._on_double)
        self.tree.bind("<ButtonPress-1>", self._on_button_press)
        self.tree.bind("<B1-Motion>", self._on_mouse_motion)
        self.tree.bind("<ButtonRelease-1>", self._on_button_release)
        self.tree.bind('<Delete>', self.remove_selected_from_playlist)
        self.tree.bind("<Button-3>", self._on_right_click)  # Right-click for context menu

        # Drop Indicator
        self.drop_indicator = tk.Frame(self.tree, background="red", height=2)
        self.drop_target_index = None

    def update_theme(self):
        """Update theme-dependent styles."""
        highlight_color = self.theme.palette.get("highlight", "#FFF59D")
        self.tree.tag_configure('current', background=highlight_color)

    # ---------- Refresh ----------
    def refresh(self, preserve_selection=False):


        selected_indices = []
        if preserve_selection:
            selected_indices = [self.tree.index(item) for item in self.tree.selection()]

        self.tree.delete(*self.tree.get_children())
        for f in self.state.playlist:
            self.tree.insert('', tk.END, values=(get_display_title(f), f))

        # Restore selection
        if preserve_selection:
            children = self.tree.get_children()
            for i in selected_indices:
                if i < len(children):
                    self.tree.selection_add(children[i])

        # Restore the yellow highlight for the currently playing song
        if self.state.current_index is not None:
            self._highlight_current()

    def _highlight_current(self):
        for iid in self.tree.get_children():
            self.tree.item(iid, tags=())
        idx = self.state.current_index
        if idx is not None and 0 <= idx < len(self.state.playlist):
            child = self.tree.get_children()[idx]
            self.tree.item(child, tags=("current",))

    # ---------- Events ----------
    def _on_double(self, event):
        if not self.state.play_on_double:
            return

        sels = self.tree.selection()
        if not sels:
            return
        self.state.current_index = self.tree.index(sels[0])
        self.master.event_generate("<<PlaylistDouble>>", when="tail")
        self._highlight_current()

    def remove_selected_from_playlist(self, event=None):
        selections = self.tree.selection()
        if not selections:
            return

        removed_indices = sorted([self.tree.index(sel) for sel in selections], reverse=True)

        for idx in removed_indices:
            self.state.playlist.pop(idx)

        if self.state.current_index is not None:
            # If the current song itself was removed, reset highlight
            if self.state.current_index in removed_indices:
                self.state.current_index = None
            else:
                # Count how many removed indices were before current
                shift = sum(1 for i in removed_indices if i < self.state.current_index)
                self.state.current_index -= shift

        self.refresh()

        # Notify main window that playlist changed
        if callable(self.change_callback):
            self.change_callback()

    # ---------- Context Menu ----------
    def _on_right_click(self, event):
        """Handle right-click to show context menu."""
        # Identify which row was clicked
        item = self.tree.identify_row(event.y)
        if not item:
            return

        # Select the clicked item visually
        self.tree.selection_set(item)

        # Store the index for context menu operations (don't change current_index)
        self.context_menu_index = self.tree.index(item)

        # Show the context menu
        self.context_menu.show(event)

    def _on_context_play(self):
        """Handle Play Song from context menu."""
        if callable(self.play_callback):
            # Pass the index of the song to play
            self.play_callback(self.context_menu_index)

    def _on_context_metadata(self):
        """Handle Show Metadata from context menu."""
        if callable(self.metadata_callback):
            # Pass the index of the song to show metadata for
            self.metadata_callback(self.context_menu_index)

    def _on_context_remove(self):
        """Handle Remove from Playlist from context menu."""
        if callable(self.remove_callback):
            # Pass the index of the song to remove
            self.remove_callback(self.context_menu_index)

    # ---------- Drag & Drop ----------
    def _on_button_press(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.state.dragged_index = self.tree.index(item)

    def _on_mouse_motion(self, event):
        if self.state.dragged_index is None:
            return

        target_row = self.tree.identify_row(event.y)
        if not target_row:
            return

        target_index = self.tree.index(target_row)
        if target_index == self.state.dragged_index:
            return

        # Swap playlist entries
        self.state.playlist.insert(target_index, self.state.playlist.pop(self.state.dragged_index))

        # Adjust current index if a song is playing and dragged song is current
        if self.state.current_index is not None:
            if self.state.dragged_index == self.state.current_index:
                self.state.current_index = target_index
            elif self.state.dragged_index < self.state.current_index <= target_index:
                self.state.current_index -= 1
            elif target_index <= self.state.current_index < self.state.dragged_index:
                self.state.current_index += 1

        # Update tree and preserve selection
        self.refresh(preserve_selection=True)

        # Move selection highlight to follow dragged item
        children = self.tree.get_children()
        if target_index < len(children):
            self.tree.selection_set(children[target_index])
            self.tree.see(children[target_index])

        # Highlight current song if there is one playing
        if self.state.current_index is not None:
            self._highlight_current()

        self.state.dragged_index = target_index

    def _on_button_release(self, event):
        self.state.dragged_index = None
        if self.state.current_index is not None:
            self._highlight_current()

    # ---------- External Drag & Drop (Browser -> Playlist) ----------
    def handle_external_drag_motion(self, x_root, y_root, data):
        """
        Called by BrowserView when dragging over the playlist.
        """
        try:
            # Check if mouse is actually inside the tree widget
            tree_x = self.tree.winfo_rootx()
            tree_y = self.tree.winfo_rooty()
            tree_w = self.tree.winfo_width()
            tree_h = self.tree.winfo_height()

            if not (tree_x <= x_root <= tree_x + tree_w and tree_y <= y_root <= tree_y + tree_h):
                self.handle_external_drag_leave()
                return

            local_y = y_root - tree_y

            # Identify row under mouse
            item = self.tree.identify_row(local_y)

            if item:
                bbox = self.tree.bbox(item)
                # bbox is (x, y, width, height)
                item_y, item_h = bbox[1], bbox[3]

                # Determine if we are in the top or bottom half
                if local_y < item_y + item_h / 2:
                    # Insert before
                    self.drop_target_index = self.tree.index(item)
                    indicator_y = item_y
                else:
                    # Insert after
                    self.drop_target_index = self.tree.index(item) + 1
                    indicator_y = item_y + item_h
            else:
                # If not on a row, check if we are at the end
                children = self.tree.get_children()
                if children:
                    last_item = children[-1]
                    bbox = self.tree.bbox(last_item)
                    if local_y > bbox[1] + bbox[3]:
                        # Below last item
                        self.drop_target_index = len(children)
                        indicator_y = bbox[1] + bbox[3]
                    else:
                        # Empty space but not below last item? (e.g. empty list)
                        # If list is empty, bbox might fail or children is empty
                        self.drop_target_index = len(children) # Append
                        indicator_y = 0 # Top?
                else:
                    # Empty list
                    self.drop_target_index = 0
                    indicator_y = 0

            # Show indicator
            self.drop_indicator.place(x=0, y=indicator_y, width=tree_w, height=2)
            self.drop_indicator.lift()

        except Exception:
            self.handle_external_drag_leave()

    def handle_external_drop(self, x_root, y_root, data):
        """
        Called by BrowserView when dropping onto the playlist.
        """
        try:
            # Hide indicator
            self.drop_indicator.place_forget()

            tree_x = self.tree.winfo_rootx()
            tree_y = self.tree.winfo_rooty()
            tree_w = self.tree.winfo_width()
            tree_h = self.tree.winfo_height()

            # If dropped outside, ignore
            if not (tree_x <= x_root <= tree_x + tree_w and tree_y <= y_root <= tree_y + tree_h):
                return

            # Use the index calculated during drag motion
            if self.drop_target_index is None:
                # Fallback if motion didn't catch it
                self.drop_target_index = len(self.state.playlist)

            index = self.drop_target_index

            # Insert files
            files = data.get("files", [])
            added_count = 0
            for i, f in enumerate(files):
                if f not in self.state.playlist:
                    self.state.playlist.insert(index + added_count, f)
                    added_count += 1

            if added_count > 0:
                # Adjust current_index if we inserted before it
                if self.state.current_index is not None and index <= self.state.current_index:
                    self.state.current_index += added_count

                self.refresh()
                if callable(self.change_callback):
                    self.change_callback()

        except Exception:
            pass
        finally:
            self.drop_target_index = None

    def handle_external_drag_leave(self):
        """
        Called when drag leaves the playlist area.
        """
        self.drop_indicator.place_forget()
        self.drop_target_index = None
