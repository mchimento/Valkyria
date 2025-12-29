import tkinter as tk
from tkinter import ttk
import os
from audio.metadata import get_metadata, get_display_title
from ui.playlist_context_menu import PlaylistContextMenu


class PlaylistView(ttk.Frame):

    def __init__(self, master, state, theme, tooltip_manager=None,
                 select_callback=None, change_callback=None,
                 play_callback=None, metadata_callback=None,
                 remove_callback=None):
        super().__init__(master)

        self.state = state
        self.theme = theme
        self.select_callback = select_callback
        self.change_callback = change_callback
        self.tooltip_manager = tooltip_manager
        self.play_callback = play_callback
        self.metadata_callback = metadata_callback
        self.remove_callback = remove_callback

        # Cache for performance
        self._visible_items = []
        self._scroll_pending = False

        # Track clicked item for distinguishing click vs drag
        self._clicked_item = None

        self._setup_ui()
        self._setup_bindings()
        self._apply_modern_style()

        # Drop indicator for external drag-drop
        self.drop_indicator = tk.Frame(self.tree, background=self.theme.palette.get("accent", "#BB86FC"), height=3)
        self.drop_target_index = None

    def _setup_ui(self):
        """Initialize the UI components."""
        # Header label
        self.header_label = tk.Label(
            self,
            text="Playback queue",
            font=(self.theme.palette.get("ui_font", "Segoe UI"), 18, "bold"),
            fg=self.theme.palette.get("fg", "#FFFFFF"),
            bg=self.theme.palette.get("bg", "#121212"),
            anchor="w"
        )
        self.header_label.pack(fill="x", padx=10, pady=(5, 15))

        # Main container
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

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
            columns=("Title", "Artist", "Album", "Duration"),
            show="headings",  # Show column headings
            selectmode="extended",  # Allow multi-select
            yscrollcommand=self._on_tree_scroll
        )

        self.tree.heading("Title", text="Title", anchor="w")
        self.tree.heading("Artist", text="Artist", anchor="w")
        self.tree.heading("Album", text="Album", anchor="w")
        self.tree.heading("Duration", text="Duration", anchor="e")

        self.tree.column("Title", width=200, minwidth=150, stretch=True, anchor="w")
        self.tree.column("Artist", width=80, minwidth=50, stretch=True, anchor="w")
        self.tree.column("Album", width=100, minwidth=60, stretch=True, anchor="w")
        self.tree.column("Duration", width=100, minwidth=50, stretch=False, anchor="e")

        self.tree.pack(fill="both", expand=True, padx=(0, 10))

        # Context menu
        self.context_menu = PlaylistContextMenu(
            self.tree,
            play_callback=self._on_context_play,
            metadata_callback=self._on_context_metadata,
            remove_callback=self._on_context_remove,
            get_current_file_callback=self._get_current_file_path
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
            font=(self.theme.palette.get("ui_font", "Segoe UI"), 16, "bold")
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
        self.refresh(preserve_selection=True)

    # ========== Refresh and Rendering ==========

    def refresh(self, preserve_selection=False):
        """Efficiently refresh the playlist display."""
        # Store current selection
        selected_indices = []
        if preserve_selection:
            selected_indices = [self.tree.index(item) for item in self.tree.selection()]

        # Clear tree
        self.tree.delete(*self.tree.get_children())

        # Batch insert for performance
        items_to_insert = []
        for i, filepath in enumerate(self.state.playlist):
            # Get metadata for the file
            metadata = self._get_metadata(filepath)
            title = metadata.get("title", get_display_title(filepath))
            artist = metadata.get("artist", "")
            album = metadata.get("album", "")
            duration = metadata.get("duration", "")

            # Determine tags based on state
            tags = ["odd" if i % 2 == 1 else "even"]

            # Playing indicator
            icon = ""
            if self.state.current_index is not None and i == self.state.current_index:
                icon = "▶"
                tags.append("playing")

            items_to_insert.append((i, icon, title, artist, album, duration, filepath, tags))

        # Insert all at once
        for i, icon, title, artist, album, duration, filepath, tags in items_to_insert:
            self.tree.insert(
                '',
                tk.END,
                text=icon,
                values=(title, artist, album, duration),
                tags=tuple(tags)
            )

        # Restore selection
        if preserve_selection:
            children = self.tree.get_children()
            for idx in selected_indices:
                if idx < len(children):
                    self.tree.selection_add(children[idx])

        # Update scrollbar
        self._update_scrollbar()

        # Hide/show tree and scrollbar based on playlist content
        is_empty = len(self.state.playlist) == 0
        if is_empty:
            self.tree.pack_forget()
            self.scrollbar_canvas.pack_forget()
        else:
            self.scrollbar_canvas.pack(side="right", fill="y")
            self.tree.pack(fill="both", expand=True, padx=(0, 10))

    def _get_metadata(self, filepath):
        """Get metadata for a file using the centralized metadata module."""
        return get_metadata(filepath)

    def _highlight_current(self):
        """Update visual highlighting for currently playing track."""
        children = self.tree.get_children()

        for i, iid in enumerate(children):
            # Base tag (striping)
            tags = ["odd" if i % 2 == 1 else "even"]
            icon = ""

            # Only add playing tag and icon if this is the actual current playing track
            if self.state.current_index is not None and i == self.state.current_index:
                icon = "▶"
                tags.append("playing")

            # Update the item
            self.tree.item(iid, text=icon, tags=tuple(tags))

    # ========== Event Handlers ==========

    def _on_double(self, event):
        """Handle double-click to play track."""
        if not self.state.play_on_double:
            return

        sels = self.tree.selection()
        if not sels:
            return

        self.state.current_index = self.tree.index(sels[0])
        self.master.event_generate("<<PlaylistDouble>>", when="tail")
        self._highlight_current()

    def _on_selection_change(self, event):
        """Handle selection changes."""
        selections = self.tree.selection()
        self.state.selected_indices = [self.tree.index(s) for s in selections]

        # Don't let selection change affect the playing state
        # Just update the selection tracking
        if callable(self.select_callback) and selections:
            # Call with the first selected index for compatibility
            self.select_callback(self.tree.index(selections[0]))

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
        self.context_menu_index = self.tree.index(item)
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

    def _get_current_file_path(self):
        """Get the file path of the currently selected track."""
        if hasattr(self, 'context_menu_index') and self.context_menu_index is not None:
            if 0 <= self.context_menu_index < len(self.state.playlist):
                return self.state.playlist[self.context_menu_index]
        return None

    # ========== Drag and Drop ==========

    def _on_button_press(self, event):
        """Start drag operation."""
        item = self.tree.identify_row(event.y)
        if item:
            current_selection = self.tree.selection()
            if item in current_selection and len(current_selection) == 1:
                self.tree.selection_remove(item)
                self.state.selected_indices = []
                return "break"

            # If clicking on an item that's already part of a multi-selection,
            # preserve multi-selection for potential drag, but remember the clicked item
            if item in current_selection and len(current_selection) > 1:
                # Store the clicked item for potential single-click selection on release
                self._clicked_item = item
                # Keep the current multi-selection intact for dragging
                self.state.dragged_index = self.tree.index(item)
                return "break"

            self.state.dragged_index = self.tree.index(item)

    def _on_mouse_motion(self, event):
        """Handle drag motion with live swapping."""
        if self.state.dragged_index is None:
            return
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
            # Handle multi-item drag reordering
            selected_indices = [self.tree.index(item) for item in current_selection]
            selected_indices.sort()  # Sort to maintain order

            # Calculate new positions for all selected items
            if target_index < self.state.dragged_index:
                # Moving up - insert before target
                new_positions = list(range(target_index, target_index + len(selected_indices)))
            else:
                # Moving down - insert after target, accounting for removed items
                new_positions = list(range(target_index - len(selected_indices) + 1, target_index + 1))

            # Move items in data model
            selected_files = [self.state.playlist[i] for i in selected_indices]

            # Remove selected items from original positions
            for i in sorted(selected_indices, reverse=True):
                self.state.playlist.pop(i)

            # Insert at new positions
            for i, file_path in enumerate(selected_files):
                self.state.playlist.insert(new_positions[i], file_path)

            # Adjust current_index if needed
            if self.state.current_index is not None:
                if self.state.current_index in selected_indices:
                    # Current playing item was dragged, find its new position
                    old_pos = selected_indices.index(self.state.current_index)
                    self.state.current_index = new_positions[old_pos]
                else:
                    # Adjust for items moved before/after current position
                    moved_before = sum(1 for old, new in zip(selected_indices, new_positions)
                                     if old < self.state.current_index and new >= self.state.current_index)
                    moved_after = sum(1 for old, new in zip(selected_indices, new_positions)
                                    if old > self.state.current_index and new <= self.state.current_index)
                    self.state.current_index += moved_after - moved_after

            self.refresh()

            # Manually restore selection based on new positions
            children = self.tree.get_children()
            for new_pos in new_positions:
                if new_pos < len(children):
                    self.tree.selection_add(children[new_pos])

            # Update dragged_index to the first selected item's new position
            self.state.dragged_index = new_positions[0]
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
        # Handle single-click selection if no drag occurred
        if self._clicked_item and self.state.dragged_index is not None:
            current_selection = self.tree.selection()
            if self._clicked_item in current_selection and len(current_selection) > 1:
                # Change selection to just the clicked item
                self.tree.selection_set(self._clicked_item)
                self.state.selected_indices = [self.tree.index(self._clicked_item)]

        # Clear clicked item
        self._clicked_item = None

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

            # Add hover to current item
            tags = list(self.tree.item(item, "tags"))
            if "hover" not in tags:
                tags.append("hover")
                self.tree.item(item, tags=tuple(tags))
        else:
            # Remove hover from all items if not over any item
            self._on_tree_leave(event)

    def get_selected_indices(self):
        """Return a list of indices of selected items."""
        return [self.tree.index(item) for item in self.tree.selection()]

    def clear_selection(self):
        """Clear all selected items in the playlist."""
        self.tree.selection_remove(self.tree.selection())
        self.state.selected_indices = []

    def _on_tree_leave(self, event):
        """Handle mouse leaving treeview area."""
        children = self.tree.get_children()
        for child in children:
            tags = list(self.tree.item(child, "tags"))
            if "hover" in tags:
                tags.remove("hover")
                self.tree.item(child, tags=tuple(tags))
