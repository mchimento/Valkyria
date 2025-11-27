import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

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
                    self.tree.insert("", "end", values=(f,))
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
                self.tree.insert("", "end", values=(os.path.basename(p),))
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
