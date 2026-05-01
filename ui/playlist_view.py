import queue
import threading
import tkinter as tk
from tkinter import ttk
from audio.metadata import get_metadata, get_display_title, metadata_extractor
from ui.playlist_context_menu import PlaylistContextMenu


class PlaylistView(ttk.Frame):

    def __init__(self, master, state, theme, tooltip_manager=None,
                 select_callback=None, change_callback=None,
                 play_callback=None, metadata_callback=None,
                 remove_callback=None, play_after_current_callback=None,
                 set_time_limit_callback=None, clear_time_limit_callback=None):
        super().__init__(master)

        self.state = state
        self.theme = theme
        self.select_callback = select_callback
        self.change_callback = change_callback
        self.tooltip_manager = tooltip_manager
        self.play_callback = play_callback
        self.metadata_callback = metadata_callback
        self.remove_callback = remove_callback
        self.play_after_current_callback = play_after_current_callback
        self.set_time_limit_callback = set_time_limit_callback
        self.clear_time_limit_callback = clear_time_limit_callback

        # Search filter
        self._search_text = ""
        self._filtered_indices = []  # Indices of tracks that match search

        # Cache for performance
        self._visible_items = []
        self._scroll_pending = False

        self._clicked_item = None
        self._last_highlighted_index = None

        # Background metadata load cancellation token
        self._bg_load_id = 0

        # Column resize tracking
        self._resize_indicators = []
        self._last_hover_region = None
        self._is_resizing = False

        self._setup_ui()
        self._setup_bindings()
        self._apply_modern_style()

        # Drop indicator for external drag-drop
        self.drop_indicator = tk.Frame(self.tree, background=self.theme.palette.get("accent", "#BB86FC"), height=3)
        self.drop_target_index = None

    def _setup_ui(self):
        """Initialize the UI components."""
        # Header label
        self.header_label_font_size = 18
        self.header_label = tk.Label(
            self,
            text="Playback queue",
            font=(self.theme.palette.get("ui_font", "Segoe UI"), self.header_label_font_size, "bold"),
            fg=self.theme.palette.get("fg", "#FFFFFF"),
            bg=self.theme.palette.get("bg", "#121212"),
            anchor="w"
        )
        self.header_label.pack(fill="x", padx=10, pady=(5, 15))

        # Search bar container (right-aligned, fixed width)
        self.search_frame = tk.Frame(self, bg=self.theme.palette.get("bg", "#121212"))
        self.search_frame.pack(anchor="e", padx=10, pady=(0, 10))

        # Search icon/label
        self.search_label = tk.Label(
            self.search_frame,
            text="🔍",
            font=(self.theme.palette.get("ui_font", "Segoe UI"), 12),
            fg=self.theme.palette.get("fg", "#FFFFFF"),
            bg=self.theme.palette.get("bg", "#121212")
        )
        self.search_label.pack(side="left", padx=(0, 5))

        # Search entry with placeholder (fixed width)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search_changed)
        self.search_entry = tk.Entry(
            self.search_frame,
            textvariable=self.search_var,
            font=(self.theme.palette.get("ui_font", "Segoe UI"), 11),
            bg=self.theme.palette.get("entry_bg", "#2A2A2A"),
            fg=self.theme.palette.get("fg_dim", "#888888"),
            insertbackground=self.theme.palette.get("fg", "#FFFFFF"),
            relief="flat",
            bd=0,
            width=25
        )
        self.search_entry.pack(side="left", ipady=5)

        # Placeholder management
        self._placeholder_active = True
        self.search_entry.insert(0, "Search")
        self.search_entry.bind("<FocusIn>", self._on_search_focus_in)
        self.search_entry.bind("<FocusOut>", self._on_search_focus_out)

        # Clear button
        self.clear_button = tk.Label(
            self.search_frame,
            text="✕",
            font=(self.theme.palette.get("ui_font", "Segoe UI"), 12),
            fg=self.theme.palette.get("fg_dim", "#888888"),
            bg=self.theme.palette.get("bg", "#121212"),
            cursor="hand2"
        )
        self.clear_button.pack(side="left", padx=(5, 0))
        self.clear_button.bind("<Button-1>", lambda e: self._clear_search())

        # Main container
        self.tree_frame = ttk.Frame(self)
        self.tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Custom scrollbar (styled to be modern)
        self.scrollbar_canvas = tk.Canvas(
            self.tree_frame,
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
            self.tree_frame,
            columns=("Title", "Artist", "Album", "Duration"),
            show="headings",  # Show column headings
            selectmode="extended",  # Allow multi-select
            yscrollcommand=self._on_tree_scroll
        )

        self.tree.heading("Title", text="Title", anchor="w")
        self.tree.heading("Artist", text="  Artist", anchor="w")
        self.tree.heading("Album", text="  Album", anchor="w")
        self.tree.heading("Duration", text="  Duration", anchor="w")

        self.tree.column("Title", width=200, minwidth=150, stretch=True, anchor="w")
        self.tree.column("Artist", width=80, minwidth=50, stretch=True, anchor="w")
        self.tree.column("Album", width=100, minwidth=60, stretch=True, anchor="w")
        self.tree.column("Duration", width=100, minwidth=50, stretch=False, anchor="center")

        self.tree.pack(fill="both", expand=True, padx=(0, 10))

        # Context menu
        self.context_menu = PlaylistContextMenu(
            self.tree,
            play_callback=self._on_context_play,
            metadata_callback=self._on_context_metadata,
            remove_callback=self._on_context_remove,
            get_current_file_callback=self._get_current_file_path,
            play_after_current_callback=self._on_context_play_after_current,
            set_time_limit_callback=self._on_context_set_time_limit,
            clear_time_limit_callback=self._on_context_clear_time_limit,
            theme=self.theme
        )

    def _setup_bindings(self):
        """Setup event bindings."""
        # Selection and playback
        self.tree.bind("<Double-1>", self._on_double)
        self.tree.bind("<<TreeviewSelect>>", self._on_selection_change)

        # Drag and drop
        self.tree.bind("<ButtonPress-1>", self._on_button_press)
        self.tree.bind("<B1-Motion>", self._on_mouse_motion)
        self.tree.bind("<ButtonRelease-1>", self._on_button_release)

        # Keyboard navigation
        self.tree.bind("<Up>", self._on_key_up)
        self.tree.bind("<Down>", self._on_key_down)
        self.tree.bind("<Return>", self._on_key_enter)
        self.tree.bind('<Delete>', self.remove_selected_from_playlist)

        # Context menu
        self.tree.bind("<Button-3>", self._on_right_click)

        # Smooth scrolling
        self.tree.bind("<MouseWheel>", self._on_mousewheel)
        self.tree.bind("<Button-4>", self._on_mousewheel)  # Linux
        self.tree.bind("<Button-5>", self._on_mousewheel)  # Linux

        # Custom scrollbar interaction
        self.scrollbar_canvas.bind("<Button-1>", self._on_scrollbar_click)
        self.scrollbar_canvas.bind("<B1-Motion>", self._on_scrollbar_drag)
        self.scrollbar_canvas.bind("<Enter>", self._on_scrollbar_enter)
        self.scrollbar_canvas.bind("<Leave>", self._on_scrollbar_leave)

        # Treeview hover effects
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Leave>", self._on_tree_leave)

        # Remove focus from search bar when clicking anywhere in the application
        self.bind_all("<Button-1>", self._on_global_click, add="+")

    def _apply_modern_style(self):
        """Apply modern, theme-aware styling."""
        style = ttk.Style()

        style.layout("Playlist.Treeview", [
        ("Treeview.treearea", {"sticky": "nswe"})
        ])
        style.layout("Playlist.Treeview.Heading", [
            ("Treeheading.cell", {"sticky": "nswe"}),
            ("Treeheading.text", {"sticky": "nswe"})
        ])

        # Get theme colors
        bg = self.theme.palette.get("bg", "#121212")
        fg = self.theme.palette.get("fg", "#FFFFFF")
        select_bg = self.theme.palette.get("select_bg", "#3E3E3E")
        select_fg = self.theme.palette.get("select_fg", "#FFFFFF")
        hover_bg = self.theme.palette.get("hover_bg", "#2A2A2A")
        playing_bg = self.theme.palette.get("highlight", "#FFF59D")
        playing_fg = self.theme.palette.get("playing_fg", "#000000")

        # Configure treeview style
        style.configure(
            "Playlist.Treeview",
            background=bg,
            foreground=fg,
            fieldbackground=bg,
            borderwidth=0,
            relief="flat",
            rowheight=40  # Taller rows for modern look
        )

        style.configure(
            "Playlist.Treeview.Heading",
            background=bg,
            foreground=fg,
            borderwidth=0,
            relief="flat",
            font=(self.theme.palette.get("ui_font", "Segoe UI"), 13, "bold"),
            padding=(0, 0, 0, 0)
        )

        style.map(
            "Playlist.Treeview.Heading",
            background=[("active", bg)],  # Remove hover effect
            foreground=[("active", fg)]
        )

        style.map(
            "Playlist.Treeview",
            background=[("selected", select_bg)],
            foreground=[("selected", select_fg)]
        )

        self.tree.configure(style="Playlist.Treeview")

        # Configure tags for different states
        self.tree.tag_configure("hover", background=hover_bg)
        self.tree.tag_configure("playing", background=playing_bg, foreground=playing_fg)
        self.tree.tag_configure("even", background=bg)
        self.tree.tag_configure("odd", background=self.theme.palette.get("striped_bg", bg))

    def update_theme(self):
        """Update theme-dependent styles."""
        self._apply_modern_style()

        # Update header label
        self.header_label.configure(
            fg=self.theme.palette.get("fg", "#FFFFFF"),
            bg=self.theme.palette.get("bg", "#121212"),
            font=(self.theme.palette.get("ui_font", "Segoe UI"), self.header_label_font_size, "bold")
        )

        # Update search bar components
        if hasattr(self, 'search_frame'):
            self.search_frame.configure(bg=self.theme.palette.get("bg", "#121212"))

        if hasattr(self, 'search_label'):
            self.search_label.configure(
                fg=self.theme.palette.get("fg", "#FFFFFF"),
                bg=self.theme.palette.get("bg", "#121212")
            )

        if hasattr(self, 'search_entry'):
            # Update colors based on placeholder state
            if self._placeholder_active:
                fg_color = self.theme.palette.get("fg_dim", "#888888")
            else:
                fg_color = self.theme.palette.get("fg", "#FFFFFF")

            self.search_entry.configure(
                bg=self.theme.palette.get("entry_bg", "#2A2A2A"),
                fg=fg_color,
                insertbackground=self.theme.palette.get("fg", "#FFFFFF")
            )

        if hasattr(self, 'clear_button'):
            self.clear_button.configure(
                fg=self.theme.palette.get("fg_dim", "#888888"),
                bg=self.theme.palette.get("bg", "#121212")
            )

        self.scrollbar_canvas.configure(
            bg=self.theme.palette.get("bg", "#121212")
        )
        self.scrollbar_canvas.itemconfig(
            self.scroll_track,
            fill=self.theme.palette.get("scrollbar_track", "#404040")
        )
        self.scrollbar_canvas.itemconfig(
            self.scroll_thumb,
            fill=self.theme.palette.get("scrollbar_thumb", "#BB86FC")
        )

    # ========== Refresh and Rendering ==========

    def refresh_metadata_for_file(self, filepath):
        """Refresh metadata display for a specific file in the playlist."""
        try:
            # Find the file in the playlist
            for i, playlist_file in enumerate(self.state.playlist):
                if playlist_file == filepath:
                    # Get updated metadata
                    metadata = self._get_metadata(filepath)
                    title = metadata.get("title", get_display_title(filepath))
                    artist = metadata.get("artist", "")
                    album = metadata.get("album", "")
                    duration = metadata.get("duration", "")

                    # Check if there's a time limit for this track
                    if filepath in self.state.play_limits:
                        limit_seconds = self.state.play_limits[filepath]
                        duration = f"⏱ {int(limit_seconds)}s"

                    children = self.tree.get_children()
                    if i < len(children):
                        item_id = children[i]
                        # Add padding to column values to match main refresh method
                        padded_artist = f"  {artist}"
                        padded_album = f"  {album}"
                        padded_duration = f"  {duration}"
                        values = (title, padded_artist, padded_album, padded_duration)
                        self.tree.item(item_id, values=values)
                    break
        except Exception as e:
            pass

    def refresh(self, preserve_selection=False):
        """Refresh the playlist display using a two-phase load when metadata is not yet cached."""
        # Increment token so any in-progress background load knows to stop
        self._bg_load_id += 1
        load_id = self._bg_load_id

        # Store current selection
        selected_indices = []
        if preserve_selection:
            selected_indices = [self.tree.index(item) for item in self.tree.selection()]

        # Clear tree
        self.tree.delete(*self.tree.get_children())

        # Rebuild search filter — requires metadata, so always synchronous
        if self._search_text:
            self._filtered_indices = []
            for i, filepath in enumerate(self.state.playlist):
                metadata = self._get_metadata(filepath)
                title = metadata.get("title", get_display_title(filepath)).lower()
                artist = metadata.get("artist", "").lower()
                album = metadata.get("album", "").lower()
                if (self._search_text in title or
                        self._search_text in artist or
                        self._search_text in album):
                    self._filtered_indices.append(i)

        # Determine which tracks to display
        if self._search_text:
            display_tracks = [(i, self.state.playlist[i]) for i in self._filtered_indices]
        else:
            display_tracks = list(enumerate(self.state.playlist))

        # Progressive insert when uncached; synchronous when already cached
        uncached = [fp for _, fp in display_tracks if fp not in metadata_extractor._cache]
        if uncached:
            # Rows are inserted by the background thread as metadata becomes ready,
            # so each row appears with all columns complete — no empty-column flash.
            self._start_progressive_insert(display_tracks, load_id)
        else:
            self._insert_rows_with_metadata(display_tracks)
            if preserve_selection:
                children = self.tree.get_children()
                for idx in selected_indices:
                    if idx < len(children):
                        self.tree.selection_add(children[idx])

        # Update scrollbar and tracking state
        self._update_scrollbar()
        self._last_highlighted_index = self.state.current_index

        # Show/hide search bar, tree and scrollbar based on playlist content
        has_songs = len(self.state.playlist) > 0
        is_empty = len(display_tracks) == 0

        if has_songs:
            if not self.search_frame.winfo_ismapped():
                self.search_frame.pack(before=self.tree_frame, anchor="e", padx=10, pady=(0, 10))
        else:
            self.search_frame.pack_forget()

        if is_empty:
            self.tree.pack_forget()
            self.scrollbar_canvas.pack_forget()
        else:
            self.scrollbar_canvas.pack(side="right", fill="y")
            self.tree.pack(fill="both", expand=True, padx=(0, 10))

    def _insert_rows_with_metadata(self, display_tracks):
        """Insert all rows with fully resolved metadata (called when everything is cached)."""
        for display_index, (actual_index, filepath) in enumerate(display_tracks):
            metadata = self._get_metadata(filepath)
            title = metadata.get("title", get_display_title(filepath))
            artist = metadata.get("artist", "")
            album = metadata.get("album", "")
            duration = metadata.get("duration", "")
            if filepath in self.state.play_limits:
                duration = f"⏱ {int(self.state.play_limits[filepath])}s"
            tags = ["odd" if display_index % 2 == 1 else "even"]
            icon = ""
            if self.state.current_index is not None and actual_index == self.state.current_index:
                icon = "▶"
                tags.append("playing")
            self.tree.insert(
                '', tk.END, text=icon,
                values=(title, f"  {artist}", f"  {album}", f"  {duration}"),
                tags=tuple(tags) + (f"index_{actual_index}",)
            )

    def _start_progressive_insert(self, display_tracks, load_id):
        """Insert rows into the treeview progressively as metadata is loaded.

        Each row appears only once all its columns are ready, so there is never
        a visible empty-column state. The drain loop keeps at most one pending
        after() in the event queue so other UI events are never blocked.
        """
        root = self.winfo_toplevel()
        BATCH_SIZE = 50
        batch_q = queue.SimpleQueue()

        def worker():
            batch = []
            for display_idx, (actual_index, filepath) in enumerate(display_tracks):
                if self._bg_load_id != load_id:
                    break
                try:
                    meta = get_metadata(filepath)
                    title = meta.get("title", get_display_title(filepath))
                    artist = meta.get("artist", "")
                    album = meta.get("album", "")
                    duration = meta.get("duration", "")
                except Exception:
                    title = get_display_title(filepath)
                    artist = album = duration = ""
                batch.append((display_idx, actual_index, filepath, title, artist, album, duration))
                if len(batch) >= BATCH_SIZE:
                    batch_q.put(list(batch))
                    batch.clear()
            if batch:
                batch_q.put(list(batch))
            batch_q.put(None)

        def drain():
            if self._bg_load_id != load_id:
                return
            try:
                batch = batch_q.get_nowait()
            except queue.Empty:
                root.after(10, drain)
                return
            if batch is None:
                return
            self._insert_rows_batch(batch, load_id)
            root.after(1, drain)

        threading.Thread(target=worker, daemon=True, name="metadata-bg-load").start()
        root.after(10, drain)

    def _insert_rows_batch(self, updates, load_id):
        """Append a batch of fully-loaded rows to the treeview (runs on the main thread)."""
        if self._bg_load_id != load_id:
            return
        for display_idx, actual_index, filepath, title, artist, album, duration in updates:
            if filepath in self.state.play_limits:
                duration = f"⏱ {int(self.state.play_limits[filepath])}s"
            tags = ["odd" if display_idx % 2 == 1 else "even"]
            icon = ""
            if self.state.current_index is not None and actual_index == self.state.current_index:
                icon = "▶"
                tags.append("playing")
            self.tree.insert(
                '', tk.END, text=icon,
                values=(title, f"  {artist}", f"  {album}", f"  {duration}"),
                tags=tuple(tags) + (f"index_{actual_index}",)
            )
        self._update_scrollbar()

    def _get_metadata(self, filepath):
        """Get metadata for a file using the centralized metadata module."""
        return get_metadata(filepath)

    def _highlight_current(self):
        """Update visual highlighting for currently playing track efficiently."""
        children = self.tree.get_children()

        # Handle previous highlight
        if self._last_highlighted_index is not None:
            if 0 <= self._last_highlighted_index < len(children):
                prev_iid = children[self._last_highlighted_index]
                # Reset to base tag
                tags = ["odd" if self._last_highlighted_index % 2 == 1 else "even"]
                # Check if it's hovered (optional, but good for consistency)
                current_tags = self.tree.item(prev_iid, "tags")
                if "hover" in current_tags:
                    tags.append("hover")

                self.tree.item(prev_iid, text="", tags=tuple(tags))

        # Handle new highlight
        if self.state.current_index is not None:
            if 0 <= self.state.current_index < len(children):
                curr_iid = children[self.state.current_index]
                tags = ["odd" if self.state.current_index % 2 == 1 else "even"]
                tags.append("playing")
                # Preserve hover
                current_tags = self.tree.item(curr_iid, "tags")
                if "hover" in current_tags:
                    tags.append("hover")

                self.tree.item(curr_iid, text="▶", tags=tuple(tags))

        self._last_highlighted_index = self.state.current_index

    # ========== Event Handlers ==========

    def _on_double(self, event):
        """Handle double-click to play track."""
        if not self.state.play_on_double:
            return

        sels = self.tree.selection()
        if not sels:
            # If no selection (e.g. due to timing issues), try to identify row under mouse
            item = self.tree.identify_row(event.y)
            if item:
                self.tree.selection_set(item)
                sels = [item]
            else:
                return

        # Get actual playlist index (not tree display index)
        actual_index = self._get_actual_index_from_tree_item(sels[0])
        self.state.current_index = actual_index
        self.master.event_generate("<<PlaylistDouble>>")
        self._highlight_current()

    def _on_selection_change(self, event):
        """Handle selection changes."""
        selections = self.tree.selection()
        # Store actual playlist indices, not tree display indices
        self.state.selected_indices = [self._get_actual_index_from_tree_item(s) for s in selections]

        # Don't let selection change affect the playing state
        # Just update the selection tracking
        if callable(self.select_callback) and selections:
            # Call with the first selected actual index for compatibility
            actual_index = self._get_actual_index_from_tree_item(selections[0])
            self.select_callback(actual_index)

    def _on_key_up(self, event):
        """Navigate up with arrow key."""
        selection = self.tree.selection()
        if selection:
            current = selection[0]
            idx = self.tree.index(current)
            if idx > 0:
                children = self.tree.get_children()
                self.tree.selection_set(children[idx - 1])
                self.tree.see(children[idx - 1])
        return "break"

    def _on_key_down(self, event):
        """Navigate down with arrow key."""
        selection = self.tree.selection()
        if selection:
            current = selection[0]
            idx = self.tree.index(current)
            children = self.tree.get_children()
            if idx < len(children) - 1:
                self.tree.selection_set(children[idx + 1])
                self.tree.see(children[idx + 1])
        return "break"

    def _on_key_enter(self, event):
        """Play selected track with Enter key."""
        sels = self.tree.selection()
        if sels:
            self.state.current_index = self.tree.index(sels[0])
            self.master.event_generate("<<PlaylistDouble>>", when="tail")
            self._highlight_current()
        return "break"

    def remove_selected_from_playlist(self, event=None):
        """Remove selected tracks from playlist."""
        selections = self.tree.selection()
        if not selections:
            return

        removed_indices = sorted([self.tree.index(sel) for sel in selections], reverse=True)

        for idx in removed_indices:
            self.state.playlist.pop(idx)

        # Adjust current_index
        if self.state.current_index is not None:
            if self.state.current_index in removed_indices:
                self.state.current_index = None
            else:
                shift = sum(1 for i in removed_indices if i < self.state.current_index)
                self.state.current_index -= shift

        self.refresh()

        if callable(self.change_callback):
            self.change_callback()

    # ========== Context Menu ==========

    def _on_right_click(self, event):
        """Show context menu on right-click."""
        item = self.tree.identify_row(event.y)
        if not item:
            return

        self.tree.selection_set(item)
        # Get actual playlist index, not tree display index
        self.context_menu_index = self._get_actual_index_from_tree_item(item)
        self.context_menu.show(event)

    def _on_context_play(self):
        """Play track from context menu."""
        if callable(self.play_callback):
            self.play_callback(self.context_menu_index)

    def _on_context_metadata(self):
        """Show metadata from context menu."""
        if callable(self.metadata_callback):
            self.metadata_callback(self.context_menu_index)

    def _on_context_remove(self):
        """Remove track from context menu."""
        if callable(self.remove_callback):
            self.remove_callback(self.context_menu_index)

    def _on_context_play_after_current(self):
        """Play track after current song from context menu."""
        if callable(self.play_after_current_callback):
            self.play_after_current_callback(self.context_menu_index)

    def _on_context_set_time_limit(self):
        """Set time limit for track from context menu."""
        if callable(self.set_time_limit_callback):
            self.set_time_limit_callback(self.context_menu_index)

    def _on_context_clear_time_limit(self):
        """Clear time limit for track from context menu."""
        if callable(self.clear_time_limit_callback):
            self.clear_time_limit_callback(self.context_menu_index)

    def _get_current_file_path(self):
        """Get the file path of the currently selected track."""
        if hasattr(self, 'context_menu_index') and self.context_menu_index is not None:
            if 0 <= self.context_menu_index < len(self.state.playlist):
                return self.state.playlist[self.context_menu_index]
        return None

    # ========== Drag and Drop ==========

    def _on_button_press(self, event):
        """Start drag operation."""
        # Hide resize indicators when mouse button is pressed
        self._hide_resize_indicators()

        # Check if click is on header or separator (for resizing)
        region = self.tree.identify_region(event.x, event.y)
        if region == "separator":
            self._is_resizing = True
            return
        elif region == "heading":
            return

        item = self.tree.identify_row(event.y)
        if item:
            current_selection = self.tree.selection()
            if item in current_selection and len(current_selection) == 1:
                self._clicked_item = item
                self.state.dragged_index = self.tree.index(item)
                return "break"

            if item in current_selection and len(current_selection) > 1:
                self._clicked_item = item
                self.state.dragged_index = self.tree.index(item)
                self._original_selection_indices = [self.tree.index(item) for item in current_selection]
                self._original_current_in_selection = self.state.current_index in self._original_selection_indices
                self._original_current_index = self.state.current_index
                return "break"

            self.state.dragged_index = self.tree.index(item)
        else:
            # Click in empty area - clear selection but don't affect songs
            self.tree.selection_remove(self.tree.selection())
            self.state.selected_indices = []
            self._clicked_item = None
            self.state.dragged_index = None
            return "break"

    def _on_mouse_motion(self, event):
        """Handle drag motion with live swapping."""
        if self.state.dragged_index is None:
            return

        # Mark that mouse moved (drag started)
        self._mouse_moved = True

        self._clicked_item = None

        target_row = self.tree.identify_row(event.y)
        if not target_row:
            return

        target_index = self.tree.index(target_row)

        # Check if we're dragging multiple items
        current_selection = self.tree.selection()
        dragged_item = self.tree.get_children()[self.state.dragged_index]
        is_multi_drag = dragged_item in current_selection and len(current_selection) > 1

        if is_multi_drag:
            # Check if target is within selected items - if so, don't move
            if target_row in current_selection:
                return

            # Prevent multiple updates during the same drag operation
            if hasattr(self, '_last_multi_drag_target') and self._last_multi_drag_target == target_index:
                return
            self._last_multi_drag_target = target_index

            # Use stored original selection values from drag start
            original_current_in_selection = getattr(self, '_original_current_in_selection', False)
            original_selection_indices = getattr(self, '_original_selection_indices', [])

            # Handle multi-item drag reordering
            selected_indices = [self.tree.index(item) for item in current_selection]
            selected_indices.sort()  # Sort to maintain order

            # Save old playlist for mapping data
            old_playlist = self.state.playlist.copy()

            # Calculate new positions for all selected items
            if target_index < self.state.dragged_index:
                # Moving up - insert before target
                new_positions = list(range(target_index, target_index + len(selected_indices)))
            else:
                # Moving down - insert after target, accounting for removed items
                new_positions = list(range(target_index - len(selected_indices) + 1, target_index + 1))

            # Move items in data model
            selected_files = [self.state.playlist[i] for i in selected_indices]

            # Get the current playing song's file path BEFORE reordering
            current_song = None
            if self.state.current_index is not None:
                current_song = self.state.playlist[self.state.current_index]

            # Remove selected items from original positions
            for i in sorted(selected_indices, reverse=True):
                self.state.playlist.pop(i)

            # Insert at new positions
            for i, file_path in enumerate(selected_files):
                self.state.playlist.insert(new_positions[i], file_path)

            # Adjust current_index if needed
            if self.state.current_index is not None and current_song is not None:
                if original_current_in_selection:
                    # Current playing item was originally in the dragged selection
                    original_current_index = getattr(self, '_original_current_index', None)
                    if original_current_index is not None and original_current_index in original_selection_indices:
                        old_pos = original_selection_indices.index(original_current_index)
                        self.state.current_index = new_positions[old_pos]
                else:
                    # Find where the current song ended up after the reordering
                    try:
                        new_current_index = self.state.playlist.index(current_song)
                        self.state.current_index = new_current_index
                    except ValueError:
                        # Song was somehow removed from playlist
                        self.state.current_index = None

            # Efficiently update treeview without re-fetching metadata
            children = self.tree.get_children()
            current_items = []
            for iid in children:
                values = self.tree.item(iid, 'values')
                text = self.tree.item(iid, 'text')
                current_items.append((text, values))

            # Clear tree
            self.tree.delete(*children)

            # Re-insert in new order, mapping to correct old data
            for i, file_path in enumerate(self.state.playlist):
                # Find the old index of this file
                old_index = old_playlist.index(file_path)
                old_text, values = current_items[old_index]

                # Set text based on new playing position (ignore old text which may have wrong ▶)
                text = "▶" if self.state.current_index is not None and i == self.state.current_index else ""

                tags = ["odd" if i % 2 == 1 else "even"]
                if self.state.current_index is not None and i == self.state.current_index:
                    tags.append("playing")

                self.tree.insert('', tk.END, text=text, values=values, tags=tuple(tags))

            # Update scrollbar
            self._update_scrollbar()

            # Manually restore selection based on new positions
            children = self.tree.get_children()
            for new_pos in new_positions:
                if new_pos < len(children):
                    self.tree.selection_add(children[new_pos])

            # Update dragged_index to the first selected item's new position
            self.state.dragged_index = new_positions[0]

            # Scroll to the dragged item
            dragged_item = children[self.state.dragged_index]
            self.tree.see(dragged_item)

            return

        # Move in tree (visual)
        dragged_item = self.tree.get_children()[self.state.dragged_index]
        self.tree.move(dragged_item, '', target_index)

        # Update data
        self.state.playlist.insert(target_index, self.state.playlist.pop(self.state.dragged_index))

        # Adjust current_index
        if self.state.current_index is not None:
            if self.state.dragged_index == self.state.current_index:
                self.state.current_index = target_index
            elif self.state.dragged_index < self.state.current_index <= target_index:
                self.state.current_index -= 1
            elif target_index <= self.state.current_index < self.state.dragged_index:
                self.state.current_index += 1

        # Update tags efficiently
        self._reapply_tags()

        # Update dragged index
        self.state.dragged_index = target_index

        # Keep selection
        self.tree.selection_set(dragged_item)
        self.tree.see(dragged_item)

    def _on_button_release(self, event):
        """End drag operation."""
        self._is_resizing = False

        # Handle single-click selection if no drag occurred
        if self._clicked_item and self.state.dragged_index is not None:
            current_selection = self.tree.selection()
            drag_occurred = hasattr(self, '_mouse_moved')

            if not drag_occurred:
                # If item is already selected
                if self._clicked_item in current_selection:
                    # If it's the only selected item, deselect it (toggle off)
                    if len(current_selection) == 1:
                        self.tree.selection_remove(self._clicked_item)
                        self.state.selected_indices = []
                    # If multiple items are selected, select only this one
                    else:
                        self.tree.selection_set(self._clicked_item)
                        self.state.selected_indices = [self.tree.index(self._clicked_item)]
                else:
                    # Fallback: select the item
                    self.tree.selection_set(self._clicked_item)
                    self.state.selected_indices = [self.tree.index(self._clicked_item)]

        # Clean up mouse moved flag
        if hasattr(self, '_mouse_moved'):
            delattr(self, '_mouse_moved')

        # Clear clicked item
        self._clicked_item = None

        # Clear stored original selection values
        if hasattr(self, '_original_selection_indices'):
            delattr(self, '_original_selection_indices')
        if hasattr(self, '_original_current_in_selection'):
            delattr(self, '_original_current_in_selection')
        if hasattr(self, '_original_current_index'):
            delattr(self, '_original_current_index')
        if hasattr(self, '_last_multi_drag_target'):
            delattr(self, '_last_multi_drag_target')

        self.state.dragged_index = None
        if self.state.current_index is not None:
            self._highlight_current()

    def _reapply_tags(self):
        """Efficiently reapply tags after reordering."""
        children = self.tree.get_children()
        for i, iid in enumerate(children):
            # Base striping tags
            tags = ["odd" if i % 2 == 1 else "even"]
            icon = ""

            # Only mark as playing if it matches current_index
            if self.state.current_index is not None and i == self.state.current_index:
                tags.append("playing")
                icon = "▶"

            self.tree.item(iid, text=icon, tags=tuple(tags))


    # ========== External Drag & Drop ==========

    def handle_external_drag_motion(self, x_root, y_root, data):
        """Handle drag motion from external sources."""
        try:
            tree_x = self.tree.winfo_rootx()
            tree_y = self.tree.winfo_rooty()
            tree_w = self.tree.winfo_width()
            tree_h = self.tree.winfo_height()

            if not (tree_x <= x_root <= tree_x + tree_w and
                    tree_y <= y_root <= tree_y + tree_h):
                self.handle_external_drag_leave()
                return

            local_y = y_root - tree_y
            item = self.tree.identify_row(local_y)

            if item:
                bbox = self.tree.bbox(item)
                item_y, item_h = bbox[1], bbox[3]

                if local_y < item_y + item_h / 2:
                    self.drop_target_index = self.tree.index(item)
                    indicator_y = item_y
                else:
                    self.drop_target_index = self.tree.index(item) + 1
                    indicator_y = item_y + item_h
            else:
                children = self.tree.get_children()
                if children:
                    last_item = children[-1]
                    bbox = self.tree.bbox(last_item)
                    if local_y > bbox[1] + bbox[3]:
                        self.drop_target_index = len(children)
                        indicator_y = bbox[1] + bbox[3]
                    else:
                        self.drop_target_index = len(children)
                        indicator_y = 0
                else:
                    self.drop_target_index = 0
                    indicator_y = 0

            self.drop_indicator.place(x=0, y=indicator_y, width=tree_w, height=3)
            self.drop_indicator.lift()

        except Exception:
            self.handle_external_drag_leave()

    def handle_external_drop(self, x_root, y_root, data):
        """Handle drop from external sources."""
        try:
            self.drop_indicator.place_forget()

            tree_x = self.tree.winfo_rootx()
            tree_y = self.tree.winfo_rooty()
            tree_w = self.tree.winfo_width()
            tree_h = self.tree.winfo_height()

            if not (tree_x <= x_root <= tree_x + tree_w and
                    tree_y <= y_root <= tree_y + tree_h):
                return

            if self.drop_target_index is None:
                self.drop_target_index = len(self.state.playlist)

            index = self.drop_target_index
            files = data.get("files", [])
            added_count = 0

            for f in files:
                self.state.playlist.insert(index + added_count, f)
                added_count += 1

            if added_count > 0:
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
        """Handle drag leaving the playlist area."""
        self.drop_indicator.place_forget()
        self.drop_target_index = None

    # ========== Scrolling ==========

    def _on_mousewheel(self, event):
        """Handle smooth mouse wheel scrolling."""
        if event.num == 4 or event.delta > 0:
            delta = -1
        elif event.num == 5 or event.delta < 0:
            delta = 1
        else:
            delta = -event.delta // 120

        self.tree.yview_scroll(delta, "units")
        self._update_scrollbar()
        return "break"

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
            fill=self.theme.palette.get("scrollbar_thumb", "#BB86FC")
        )

    def _show_resize_indicator(self, x, y):
        """Show visual indicators for all column boundaries when hovering over headers."""
        # Check if we're in the header area
        if y > 20:
            self._hide_resize_indicators()
            return

        # Don't show indicators if column is being resized
        if self._is_resizing:
            return

        # Get column boundaries
        columns = self.tree.cget("columns")
        if not columns:
            return

        # Clear existing indicators
        self._hide_resize_indicators()

        # Calculate cumulative widths and show indicators for all column boundaries
        current_x = 0
        for col in columns:
            col_width = self.tree.column(col, "width")
            # Show indicator at the right edge of each column
            self._show_resize_line(current_x + col_width)
            current_x += col_width

    def _show_resize_line(self, x_pos):
        """Show a vertical line at the column boundary."""
        indicator = tk.Frame(
            self.tree,
            background=self.theme.palette.get("resize_column_color", "#BB86FC"),
            width=2
        )

        # Position the line at the column boundary
        indicator.place(x=x_pos, y=0, height=20)  # Only in header area
        indicator.lift()
        self._resize_indicators.append(indicator)

    def _hide_resize_indicators(self):
        """Hide all resize indicators."""
        for indicator in self._resize_indicators:
            indicator.destroy()
        self._resize_indicators.clear()
        self._last_hover_region = None

    def _on_tree_motion(self, event):
        """Handle mouse motion over treeview items for hover effect."""
        # Check for column resize hover first
        self._show_resize_indicator(event.x, event.y)
        item = self.tree.identify_row(event.y)
        if item:
            # Remove hover from all items first
            children = self.tree.get_children()
            for child in children:
                tags = list(self.tree.item(child, "tags"))
                if "hover" in tags:
                    tags.remove("hover")
                    self.tree.item(child, tags=tuple(tags))

            # Add hover to current item
            tags = list(self.tree.item(item, "tags"))
            if "hover" not in tags:
                tags.append("hover")
                self.tree.item(item, tags=tuple(tags))
        else:
            # Remove hover from all items
            children = self.tree.get_children()
            for child in children:
                tags = list(self.tree.item(child, "tags"))
                if "hover" in tags:
                    tags.remove("hover")
                    self.tree.item(child, tags=tuple(tags))

    def _on_global_click(self, event):
        """Remove focus from search bar when clicking anywhere outside of it."""
        # Get the widget that was clicked
        clicked_widget = event.widget

        # Check if the click was on the search entry or any of its children
        # Walk up the widget hierarchy to see if search_entry is an ancestor
        widget = clicked_widget
        while widget:
            if widget == self.search_entry:
                # Click was on search entry, do nothing
                return
            try:
                widget = widget.master
            except:
                break

        # Click was outside search entry, remove focus if search entry has it
        if self.search_entry == self.focus_get():
            self.tree.focus_set()

    def _on_search_focus_in(self, event):
        """Handle search entry gaining focus - remove placeholder."""
        if self._placeholder_active:
            self.search_var.set("")
            self.search_entry.configure(fg=self.theme.palette.get("fg", "#FFFFFF"))
            self._placeholder_active = False

    def _on_search_focus_out(self, event):
        """Handle search entry losing focus - restore placeholder if empty."""
        if not self.search_var.get().strip():
            self._placeholder_active = True
            self.search_var.set("Search")
            self.search_entry.configure(fg=self.theme.palette.get("fg_dim", "#888888"))

    def _on_search_changed(self, *args):
        """Handle search text changes - instant filtering."""
        # Don't filter while placeholder is active
        if self._placeholder_active:
            return

        search_text = self.search_var.get().strip().lower()
        self._search_text = search_text

        if search_text:
            # Filter playlist based on search text
            self._filtered_indices = []
            for i, filepath in enumerate(self.state.playlist):
                metadata = self._get_metadata(filepath)
                title = metadata.get("title", get_display_title(filepath)).lower()
                artist = metadata.get("artist", "").lower()
                album = metadata.get("album", "").lower()

                # Match against title, artist, or album (case-insensitive)
                if (search_text in title or
                    search_text in artist or
                    search_text in album):
                    self._filtered_indices.append(i)
        else:
            # No search text - show all
            self._filtered_indices = []

        # Refresh display with filtered results
        self.refresh(preserve_selection=False)

    def _clear_search(self):
        """Clear the search filter."""
        self._placeholder_active = False
        self.search_var.set("")
        self.search_entry.configure(fg=self.theme.palette.get("fg", "#FFFFFF"))
        self.search_entry.focus_set()

    def _get_actual_index_from_tree_item(self, item_id):
        """Get the actual playlist index from a tree item ID."""
        tags = self.tree.item(item_id, "tags")
        for tag in tags:
            if tag.startswith("index_"):
                return int(tag.split("_")[1])
        # Fallback: if filtering is not active, tree index = actual index
        return self.tree.index(item_id)

    def get_selected_indices(self):
        """Return a list of actual playlist indices of selected items."""
        actual_indices = []
        for item in self.tree.selection():
            actual_index = self._get_actual_index_from_tree_item(item)
            actual_indices.append(actual_index)
        return actual_indices

    def clear_selection(self):
        self.tree.selection_remove(self.tree.selection())
        self.state.selected_indices = []

    def _on_tree_leave(self, event):
        """Handle mouse leaving treeview area."""
        # Hide resize indicators when leaving tree
        self._hide_resize_indicators()
        children = self.tree.get_children()
        for child in children:
            tags = list(self.tree.item(child, "tags"))
            if "hover" in tags:
                tags.remove("hover")
                self.tree.item(child, tags=tuple(tags))
