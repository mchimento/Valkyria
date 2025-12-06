import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

from ui.utils import get_display_title

class BrowserView(ttk.Frame):
    def __init__(self, master, state, theme, tooltip_manager=None, status_callback=None):
        super().__init__(master)
        self.state = state
        self.theme = theme
        self.tooltip_manager = tooltip_manager
        self.status_callback = status_callback

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Vertical scrollbar
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill="y")

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("name",),
            show="headings",
            selectmode="extended",
            yscrollcommand=vsb.set
        )
        self.tree.column('name', width=350, minwidth=100, stretch=True)
        self.tree.heading("name", text="Songs")

        if "striped_bg" in self.theme.palette:
            self.tree.tag_configure("striped", background=self.theme.palette["striped_bg"])

        self.tree.pack(fill=tk.BOTH, expand=True)

        # Connect scrollbars to Treeview
        vsb.config(command=self.tree.yview)

        # Make the container grid expandable
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # ---------- Bindings ----------
        self.tree.bind('<Delete>', self.remove_selected_from_browser)

        # ---------- Drag & Drop ----------
        self.playlist_view = None
        self.drag_data = None
        self.drag_start_pos = None
        self.suppress_selection = False

        # Track index for internal live reordering
        self.internal_drag_index = None

        self.tree.bind("<ButtonPress-1>", self._on_drag_start)
        self.tree.bind("<B1-Motion>", self._on_drag_motion)
        self.tree.bind("<ButtonRelease-1>", self._on_drag_release)

    def update_theme(self):
        """Update theme-dependent styles."""
        if "striped_bg" in self.theme.palette:
            self.tree.tag_configure("striped", background=self.theme.palette["striped_bg"])

    def set_playlist_view(self, playlist_view):
        self.playlist_view = playlist_view

    # ---------- Refresh ----------
    def refresh(self, preserve_selection=False):
        selected_indices = []
        if preserve_selection:
            selected_indices = [self.tree.index(item) for item in self.tree.selection()]

        self.tree.delete(*self.tree.get_children())
        for i, f in enumerate(self.state.browser_files):
            tags = ("striped",) if i % 2 == 1 else ()
            self.tree.insert("", "end", values=(get_display_title(f),), tags=tags)

        # Restore selection
        if preserve_selection:
            children = self.tree.get_children()
            for i in selected_indices:
                if i < len(children):
                    self.tree.selection_add(children[i])

    # ---------- Middle Buttons: Browse Song, Add, Add below ----------
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return

        exts = self.state.exts

        self.state.browser_files.clear()

        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(exts):
                    full = os.path.join(root, f)
                    self.state.browser_files.append(full)

        self.refresh()

        if self.state.browser_files:
            self._send_status("browsed_folder", len(self.state.browser_files))

    def browse_files(self):
        paths = filedialog.askopenfilenames(title="Add Song(s) to Browser",
                                            filetypes=[("Audio files", "*.mp3 *.wav *.flac *.ogg *.m4a"), ("All files", "*.*")])
        if not paths:
            return

        self.state.browser_files.clear()

        for p in paths:
            p = os.path.abspath(p)
            self.state.browser_files.append(p)

        self.refresh()

        if self.state.browser_files:
            self._send_status("browsed_files", len(self.state.browser_files))

    # ---------- Drag & Drop ----------
    def _on_drag_start(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return

        self.drag_start_pos = (event.x, event.y)
        self.drag_data = None
        self.internal_drag_index = None

    def _on_drag_motion(self, event):
        if not self.drag_start_pos:
            return

        # Check threshold if not already dragging
        if not self.drag_data:
            dx = abs(event.x - self.drag_start_pos[0])
            dy = abs(event.y - self.drag_start_pos[1])
            if dx < 5 and dy < 5:
                # Still within threshold, treat as potential click
                return

            # Start drag
            sels = self.tree.selection()

            if len(sels) == 1:
                # We can do internal reorder
                self.internal_drag_index = self.tree.index(sels[0])
            else:
                self.internal_drag_index = None

            paths = []
            for s in sels:
                idx = self.tree.index(s)
                if 0 <= idx < len(self.state.browser_files):
                    paths.append(self.state.browser_files[idx])

            if paths:
                self.drag_data = {"files": paths}
                self.winfo_toplevel().configure(cursor="fleur")

        if not self.drag_data:
            return

        x_root, y_root = event.x_root, event.y_root

        # 1. External drag to Playlist (delegation)
        if self.playlist_view:
             self.playlist_view.handle_external_drag_motion(x_root, y_root, self.drag_data)

        # 2. Internal Live Reorder (if single item)
        if self.internal_drag_index is not None:
            # Check if over BrowserView
            tree_x = self.tree.winfo_rootx()
            tree_y = self.tree.winfo_rooty()
            tree_w = self.tree.winfo_width()
            tree_h = self.tree.winfo_height()

            if (tree_x <= x_root <= tree_x + tree_w and tree_y <= y_root <= tree_y + tree_h):
                 target_row = self.tree.identify_row(event.y)
                 if target_row:
                      target_index = self.tree.index(target_row)
                      if target_index != self.internal_drag_index:
                           # Valid swap
                           if 0 <= target_index < len(self.state.browser_files) and 0 <= self.internal_drag_index < len(self.state.browser_files):
                                # Visual update: Move item
                                dragged_item = self.tree.get_children()[self.internal_drag_index]
                                self.tree.move(dragged_item, '', target_index)

                                # Data update: Swap files
                                self.state.browser_files.insert(target_index, self.state.browser_files.pop(self.internal_drag_index))

                                # Re-apply stripes (visual only)
                                self._restripe_tree()

                                self.internal_drag_index = target_index

                                # Move selection highlight to follow dragged item
                                self.tree.selection_set(dragged_item)
                                self.tree.see(dragged_item)

    def _on_drag_release(self, event):
        self.winfo_toplevel().configure(cursor="")
        self.drag_start_pos = None

        if self.drag_data:
            x_root, y_root = event.x_root, event.y_root

            # 1. Check if dropped on playlist
            if self.playlist_view:
                 # Check bounds internally in handle_external_drop
                 self.playlist_view.handle_external_drop(x_root, y_root, self.drag_data)

            # Internal reorder (live) happened during motion, no finalization needed.

            self.drag_data = None
            self.internal_drag_index = None

            # NOW allow playlist to clean up (reset drop index)
            if self.playlist_view:
                 self.playlist_view.handle_external_drag_leave()

        else:
            # Click (No drag threshold exceeded)
            if self.playlist_view:
                 self.playlist_view.handle_external_drag_leave()

    def add_selected_to_playlist(self):
        # Read selection from browser view
        sels = self.tree.selection()
        if not sels:
            return
        added = 0
        for s in sels:
            idx = self.tree.index(s)
            if 0 <= idx < len(self.state.browser_files):
                p = self.state.browser_files[idx]
                if p not in self.state.playlist:
                    self.state.playlist.append(p)
                    added += 1

        self._send_status("added_to_playlist", added)

    def add_selected_below_playlist(self):
        sels = self.tree.selection()
        if not sels:
            return
        sel_indices = sorted([self.tree.index(s) for s in sels])
        files_to_add = [self.state.browser_files[i] for i in sel_indices if 0 <= i < len(self.state.browser_files)]
        # insert position after current_index or end if none
        insert_pos = len(self.state.playlist)
        if self.state.current_index is not None and 0 <= self.state.current_index < len(self.state.playlist):
            insert_pos = self.state.current_index + 1

        added = 0
        for i, f in enumerate(files_to_add):
            if f in self.state.playlist:
                continue
            self.state.playlist.insert(insert_pos + added, f)
            added += 1

        self._send_status("added_to_playlist_below", added)

    # ---------- Extras ----------
    def remove_selected_from_browser(self, event=None):
        selections = self.tree.selection()
        for sel in selections[::-1]:
            idx = self.tree.index(sel)
            self.state.browser_files.pop(idx)
            self.tree.delete(sel)

    def _send_status(self, event_type, count=0):
        if self.status_callback:
            self.status_callback(event_type, count)

    def _restripe_tree(self):
        """Re-apply striped tags to all items (fast, no I/O)."""
        if "striped_bg" in self.theme.palette:
            for i, iid in enumerate(self.tree.get_children()):
                tags = ["striped"] if i % 2 == 1 else []
                self.tree.item(iid, tags=tuple(tags))
