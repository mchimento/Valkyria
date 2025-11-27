import tkinter as tk
from tkinter import ttk
import os


class PlaylistView(ttk.Frame):
    def __init__(self, master, state, tooltip_manager=None, select_callback=None):
        super().__init__(master)
        self.state = state
        self.select_callback = select_callback
        self.tooltip_manager = tooltip_manager

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
        self.tree.tag_configure('current', background="#FFF59D")
        self.tree.pack(fill="both", expand=True)

        # Connect scrollbars to Treeview
        vsb.config(command=self.tree.yview)

        # ---------- Bindings ----------
        self.tree.bind("<Double-1>", self._on_double)
        self.tree.bind("<ButtonPress-1>", self._on_button_press)
        self.tree.bind("<B1-Motion>", self._on_mouse_motion)
        self.tree.bind("<ButtonRelease-1>", self._on_button_release)
        self.tree.bind('<Delete>', self.remove_selected_from_playlist)

    # ---------- Refresh ----------
    def refresh(self, preserve_selection=False):
        selected_indices = []
        if preserve_selection:
            selected_items = self.tree.selection()
            selected_indices = [self.tree.index(i) for i in selected_items]

        self.tree.delete(*self.tree.get_children())
        for f in self.state.playlist:
            self.tree.insert('', tk.END, values=(os.path.basename(f), f))

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
