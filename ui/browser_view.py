import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

from ui.utils import get_display_title

class BrowserView(ttk.Frame):
    def __init__(self, master, state, tooltip_manager=None, status_callback=None):
        super().__init__(master)
        self.state = state
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
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Connect scrollbars to Treeview
        vsb.config(command=self.tree.yview)

        # Make the container grid expandable
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # ---------- Bindings ----------
        self.tree.bind('<Delete>', self.remove_selected_from_browser)

        if tooltip_manager:
            tooltip_manager.attach(self.tree, lambda: "Browse and select songs")

        # ---------- Drag & Drop ----------
        self.playlist_view = None
        self.drag_data = None
        self.drag_start_pos = None
        self.suppress_selection = False

        self.tree.bind("<ButtonPress-1>", self._on_drag_start)
        self.tree.bind("<B1-Motion>", self._on_drag_motion)
        self.tree.bind("<ButtonRelease-1>", self._on_drag_release)

    def set_playlist_view(self, playlist_view):
        self.playlist_view = playlist_view

    def _on_drag_start(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return

        self.drag_start_pos = (event.x, event.y)
        self.drag_data = None
        self.suppress_selection = False

        # If clicking on an already selected item, we might be starting a drag of multiple items.
        # We want to prevent the default behavior (which would deselect others) until we know if it's a drag or click.
        if item in self.tree.selection():
            self.suppress_selection = True
            # Return 'break' to prevent Treeview's default selection handler from running now
            return "break"

        # If not selected, let default handler run (it will select this item)
        pass

    def _on_drag_motion(self, event):
        if not self.drag_start_pos:
            return

        # Check threshold
        if not self.drag_data:
            dx = abs(event.x - self.drag_start_pos[0])
            dy = abs(event.y - self.drag_start_pos[1])
            if dx < 5 and dy < 5:
                return

            # Threshold exceeded, start drag
            # If we suppressed selection, the selection is still intact (multiple items).
            # If we didn't, the selection is just this item (or whatever default behavior did).

            sels = self.tree.selection()
            paths = []
            for s in sels:
                idx = self.tree.index(s)
                if 0 <= idx < len(self.state.browser_files):
                    paths.append(self.state.browser_files[idx])

            if paths:
                self.drag_data = {"files": paths}
                self.winfo_toplevel().configure(cursor="fleur")

        if not self.drag_data or not self.playlist_view:
            return

        # Check if cursor is over the playlist view
        x_root, y_root = event.x_root, event.y_root
        self.playlist_view.handle_external_drag_motion(x_root, y_root, self.drag_data)

    def _on_drag_release(self, event):
        self.winfo_toplevel().configure(cursor="")
        self.drag_start_pos = None

        if self.drag_data:
            # Drag happened
            if self.playlist_view:
                x_root, y_root = event.x_root, event.y_root
                self.playlist_view.handle_external_drop(x_root, y_root, self.drag_data)
                self.playlist_view.handle_external_drag_leave()
            self.drag_data = None
        else:
            # No drag happened (it was a click)
            if self.suppress_selection:
                # We blocked the default selection, so we must manually select the clicked item now
                # This mimics the behavior: Click on selected group -> Select only clicked item
                item = self.tree.identify_row(event.y)
                if item:
                    self.tree.selection_set(item)
                    self.tree.focus(item)


    # ---------- Middle Buttons: Browse Song, Add, Add below ----------
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return

        exts = self.state.exts

        self.state.browser_files.clear()
        self.tree.delete(*self.tree.get_children())

        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(exts):
                    full = os.path.join(root, f)
                    self.state.browser_files.append(full)
                    self.tree.insert("", "end", values=(get_display_title(full),))
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
            if p not in self.state.browser_files:
                self.state.browser_files.append(p)
                # insert into browser tree view display directly
                self.tree.insert("", "end", values=(get_display_title(p),))
        if self.state.browser_files:
            self._send_status("browsed_files", len(self.state.browser_files))

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
