import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

from audio.metadata import get_display_title

class BrowserView(ttk.Frame):
    def __init__(self, master, state, theme, tooltip_manager=None, status_callback=None):
        super().__init__(master)
        self.state = state
        self.theme = theme
        self.tooltip_manager = tooltip_manager
        self.status_callback = status_callback

        # Header label
        self.header_label = tk.Label(
            self,
            text="Browser",
            font=(self.theme.palette.get("ui_font", "Segoe UI"), 18, "bold"),
            fg=self.theme.palette.get("fg", "#FFFFFF"),
            bg=self.theme.palette.get("bg", "#121212"),
            anchor="w"
        )
        self.header_label.pack(fill="x", padx=10, pady=(5, 15))

        # Main container
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=(10, 0), pady=(0, 10))

        # Custom scrollbar (styled to be modern)
        self.scrollbar_canvas = tk.Canvas(
            tree_frame,
            width=12,
            highlightthickness=0,
            bg=self.theme.palette.get("bg", "#121212")
        )
        self.scrollbar_canvas.pack(side="right", fill="y")

        # Bind to configure event to update scrollbar when canvas is resized
        self.scrollbar_canvas.bind("<Configure>", lambda e: self._update_scrollbar())

        # Scrollbar track and thumb
        self.scroll_track = self.scrollbar_canvas.create_rectangle(
            2, 0, 10, 100,
            fill=self.theme.palette.get("scrollbar_track", "#282828"),
            outline=""
        )
        self.scroll_thumb = self.scrollbar_canvas.create_rectangle(
            2, 0, 10, 50,
            fill=self.theme.palette.get("scrollbar_thumb", "#535353"),
            outline=""
        )

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("name",),
            show="tree",  # Hide headings
            selectmode="extended",
            yscrollcommand=self._on_tree_scroll
        )
        self.tree.column('name', width=0, minwidth=0, stretch=False)
        self.tree.column('#0', width=300, minwidth=200, stretch=False, anchor="w")

        if "striped_bg" in self.theme.palette:
            self.tree.tag_configure("striped", background=self.theme.palette["striped_bg"])
        if "even" in self.theme.palette:
            self.tree.tag_configure("even", background=self.theme.palette["even"])
        if "odd" in self.theme.palette:
            self.tree.tag_configure("odd", background=self.theme.palette["odd"])

        # Configure hover tag last to ensure it takes precedence
        hover_bg = self.theme.palette.get("hover_bg", "#2A2A2A")
        self.tree.tag_configure("hover", background=hover_bg)

        self.tree.pack(fill="both", expand=True)

        # Initialize drag and drop variables
        self.playlist_view = None
        self.drag_data = None
        self.drag_start_pos = None
        self.suppress_selection = False

        # Track index for internal live reordering
        self.internal_drag_index = None

        # Drag tooltip for showing song names during drag
        self.drag_tooltip = tk.Toplevel(self)
        self.drag_tooltip.withdraw()
        self.drag_tooltip.overrideredirect(True)
        self.drag_tooltip_label = tk.Label(
            self.drag_tooltip,
            bg=self.theme.palette.get("tooltip_bg", "#2D2D2D"),
            fg=self.theme.palette.get("tooltip_fg", "#FFFFFF"),
            font=(self.theme.palette.get("ui_font", "Segoe UI"), 10),
            padx=8, pady=4,
            relief="solid",
            borderwidth=1
        )
        self.drag_tooltip_label.pack()
        self.drag_tooltip_visible = False

        self._setup_bindings()

    def _setup_bindings(self):
        """Setup event bindings."""
        self.tree.bind('<Delete>', self.remove_selected_from_browser)

        self.tree.bind("<ButtonPress-1>", self._on_drag_start)
        self.tree.bind("<B1-Motion>", self._on_drag_motion)
        self.tree.bind("<ButtonRelease-1>", self._on_drag_release)

        # Treeview hover effects
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Leave>", self._on_tree_leave)

        self.scrollbar_canvas.bind("<Button-1>", self._on_scrollbar_click)
        self.scrollbar_canvas.bind("<B1-Motion>", self._on_scrollbar_drag)
        self.scrollbar_canvas.bind("<Enter>", self._on_scrollbar_enter)
        self.scrollbar_canvas.bind("<Leave>", self._on_scrollbar_leave)

    def update_theme(self):
        """Update theme-dependent styles."""
        if "striped_bg" in self.theme.palette:
            self.tree.tag_configure("striped", background=self.theme.palette["striped_bg"])

        # Update header label colors
        self.header_label.config(
            fg=self.theme.palette.get("fg", "#FFFFFF"),
            bg=self.theme.palette.get("bg", "#121212")
        )

        # Update hover tag color last to ensure it takes precedence
        hover_bg = self.theme.palette.get("hover_bg", "#2A2A2A")
        self.tree.tag_configure("hover", background=hover_bg)

        self.scrollbar_canvas.config(bg=self.theme.palette.get("bg", "#121212"))
        self.scrollbar_canvas.itemconfig(
            self.scroll_track,
            fill=self.theme.palette.get("scrollbar_track", "#282828")
        )
        self.scrollbar_canvas.itemconfig(
            self.scroll_thumb,
            fill=self.theme.palette.get("scrollbar_thumb", "#535353")
        )

        self.drag_tooltip_label.config(
            bg=self.theme.palette.get("tooltip_bg", "#2D2D2D"),
            fg=self.theme.palette.get("tooltip_fg", "#FFFFFF")
        )

    def set_playlist_view(self, playlist_view):
        self.playlist_view = playlist_view

    # ---------- Refresh ----------
    def refresh(self, preserve_selection=False):
        selected_indices = []
        if preserve_selection:
            selected_indices = [self.tree.index(item) for item in self.tree.selection()]

        self.tree.delete(*self.tree.get_children())
        for i, f in enumerate(self.state.browser_files):
            # Tags for striping
            tags = ["odd" if i % 2 == 1 else "even"]
            if "striped_bg" in self.theme.palette and i % 2 == 1:
                tags.append("striped")

            self.tree.insert("", "end", text=get_display_title(f), tags=tuple(tags))

        # Restore selection
        if preserve_selection:
            children = self.tree.get_children()
            for i in selected_indices:
                if i < len(children):
                    self.tree.selection_add(children[i])

        # Update scrollbar
        self._update_scrollbar()

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

        paths = []  # Initialize paths here to make it accessible throughout the method

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

        # Get paths from drag_data for tooltip
        paths = self.drag_data.get("files", [])

        # Check if dragging outside browser tree bounds (external drag)
        tree_x = self.tree.winfo_rootx()
        tree_y = self.tree.winfo_rooty()
        tree_w = self.tree.winfo_width()
        tree_h = self.tree.winfo_height()

        is_inside_browser = (tree_x <= x_root <= tree_x + tree_w and
                            tree_y <= y_root <= tree_y + tree_h)

        # Show drag tooltip only when dragging outside browser (external drag)
        if not is_inside_browser and not self.drag_tooltip_visible:
            self._show_drag_tooltip(paths, x_root, y_root)
        elif is_inside_browser and self.drag_tooltip_visible:
            # Hide tooltip when dragging back inside browser
            self.drag_tooltip.withdraw()
            self.drag_tooltip_visible = False

        # Update drag tooltip position
        if self.drag_tooltip_visible:
            self.drag_tooltip.geometry(f"+{x_root + 10}+{y_root + 10}")

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

        # Hide drag tooltip
        if self.drag_tooltip_visible:
            self.drag_tooltip.withdraw()
            self.drag_tooltip_visible = False

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

    def _show_drag_tooltip(self, paths, x, y):
        """Show tooltip with song names during drag."""
        from audio.metadata import get_display_title

        if len(paths) == 1:
            # Show single song title
            tooltip_text = get_display_title(paths[0])
        else:
            # Show count for multiple songs
            tooltip_text = f"{len(paths)} songs"

        self.drag_tooltip_label.config(text=tooltip_text)
        self.drag_tooltip.geometry(f"+{x + 10}+{y + 10}")
        self.drag_tooltip.deiconify()
        self.drag_tooltip.lift()
        self.drag_tooltip_visible = True

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

    def _on_tree_scroll(self, *args):
        """Update custom scrollbar when tree scrolls."""
        self._update_scrollbar()

    def _update_scrollbar(self):
        """Update custom scrollbar appearance."""
        try:
            # Get scroll position
            first, last = self.tree.yview()

            # Update track height
            canvas_height = self.scrollbar_canvas.winfo_height()
            self.scrollbar_canvas.coords(
                self.scroll_track,
                2, 0, 10, canvas_height
            )

            visible_ratio = max(0.1, last - first)  # Minimum 10% visible ratio
            thumb_height = max(40, int(visible_ratio * canvas_height))  # Minimum 40px height
            thumb_y = int(first * canvas_height)

            self.scrollbar_canvas.coords(
                self.scroll_thumb,
                2, thumb_y, 10, thumb_y + thumb_height
            )

        except Exception:
            pass

    def _on_scrollbar_click(self, event):
        """Handle click on scrollbar."""
        canvas_height = self.scrollbar_canvas.winfo_height()
        click_position = event.y / canvas_height

        self.tree.yview_moveto(click_position)
        self._update_scrollbar()

    def _on_scrollbar_drag(self, event):
        """Handle dragging the scrollbar."""
        canvas_height = self.scrollbar_canvas.winfo_height()
        drag_position = event.y / canvas_height

        self.tree.yview_moveto(drag_position)
        self._update_scrollbar()

    def _on_scrollbar_enter(self, event):
        """Handle mouse entering scrollbar area."""
        self.scrollbar_canvas.itemconfig(
            self.scroll_thumb,
            fill=self.theme.palette.get("scrollbar_hover", "#525252")
        )

    def _on_scrollbar_leave(self, event):
        """Handle mouse leaving scrollbar area."""
        self.scrollbar_canvas.itemconfig(
            self.scroll_thumb,
            fill=self.theme.palette.get("scrollbar_thumb", "#535353")
        )

    def _on_tree_motion(self, event):
        """Handle mouse motion over treeview items for hover effect."""
        item = self.tree.identify_row(event.y)
        if item:
            # Remove hover from all items first
            children = self.tree.get_children()
            for child in children:
                tags = list(self.tree.item(child, "tags"))
                if "hover" in tags:
                    tags.remove("hover")
                    self.tree.item(child, tags=tuple(tags))

            # Add hover to current item (place at end to take precedence)
            tags = list(self.tree.item(item, "tags"))
            if "hover" not in tags:
                tags.append("hover")
                self.tree.item(item, tags=tuple(tags))
        else:
            # Remove hover from all items if not over any item
            self._on_tree_leave(event)

    def _on_tree_leave(self, event):
        """Handle mouse leaving treeview area."""
        children = self.tree.get_children()
        for child in children:
            tags = list(self.tree.item(child, "tags"))
            if "hover" in tags:
                tags.remove("hover")
                self.tree.item(child, tags=tuple(tags))
