import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

from audio.metadata import get_display_title
from audio.audio_player import AudioPlayer


class _RoundedButton(tk.Canvas):
    """Flat canvas button with rounded corners — no CTk dependency."""

    def __init__(self, parent, text, command,
                 bg="#0078d4", fg="#ffffff", hover_bg="#106ebe",
                 canvas_bg="#121212", width=120, height=32,
                 radius=8, font=None):
        super().__init__(parent, width=width, height=height,
                         highlightthickness=0, bd=0, bg=canvas_bg)
        self._btn_bg = bg
        self._btn_fg = fg
        self._btn_hover = hover_bg
        self._command = command
        self._radius = radius
        self._btn_w = width
        self._btn_h = height
        self._font = font or ("Segoe UI", 10)
        self._disabled = False
        self._hovered = False

        self._shape = self._create_shape(bg)
        self._label = self.create_text(
            width // 2, height // 2, text=text,
            fill=fg, font=self._font, anchor="center",
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)

    def _create_shape(self, color):
        r, w, h = self._radius, self._btn_w, self._btn_h
        pts = [r, 0,   w-r, 0,   w, 0,   w, r,
               w, h-r, w, h,    w-r, h,  r, h,
               0, h,   0, h-r,  0, r,    0, 0]
        return self.create_polygon(pts, smooth=True, fill=color, outline="")

    def _on_enter(self, _):
        if not self._disabled:
            self.itemconfig(self._shape, fill=self._btn_hover)
            self._hovered = True

    def _on_leave(self, _):
        if not self._disabled:
            self.itemconfig(self._shape, fill=self._btn_bg)
            self._hovered = False

    def _on_press(self, _):
        if not self._disabled and self._command:
            self._command()

    def configure(self, **kwargs):
        if "state" in kwargs:
            self._disabled = kwargs.pop("state") == "disabled"
            self.itemconfig(self._shape,
                            fill="#555555" if self._disabled else self._btn_bg)
            self.itemconfig(self._label,
                            fill="#888888" if self._disabled else self._btn_fg)
        if "bg" in kwargs:
            self._btn_bg = kwargs.pop("bg")
            if not self._disabled and not self._hovered:
                self.itemconfig(self._shape, fill=self._btn_bg)
        if "fg" in kwargs:
            self._btn_fg = kwargs.pop("fg")
            if not self._disabled:
                self.itemconfig(self._label, fill=self._btn_fg)
        if "hover_bg" in kwargs:
            self._btn_hover = kwargs.pop("hover_bg")
        if "activebackground" in kwargs:
            self._btn_hover = kwargs.pop("activebackground")
        if "activeforeground" in kwargs:
            kwargs.pop("activeforeground")
        if "canvas_bg" in kwargs:
            super().configure(bg=kwargs.pop("canvas_bg"))
        super().configure(**kwargs)

    config = configure

class BrowserView(ttk.Frame):
    def __init__(self, master, state, theme, tooltip_manager=None, status_callback=None, player=None):
        super().__init__(master)
        self.state = state
        self.theme = theme
        self.tooltip_manager = tooltip_manager
        self.status_callback = status_callback

        self._main_player = player
        self._preview_player = AudioPlayer(on_track_end=self._on_preview_track_end) if player is not None else None
        self._preview_path = None
        self._preview_devices = []

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

        # Content container (holds buttons and tree)
        content_frame = ttk.Frame(self)
        content_frame.pack(fill="both", expand=True, padx=(10, 0), pady=(0, 10))

        # Buttons frame (Left side)
        self.button_frame = ttk.Frame(content_frame)
        self.button_frame.pack(side="left", fill="y", padx=(0, 10))

        # Create a container to center buttons vertically
        button_container = ttk.Frame(self.button_frame)
        button_container.pack(expand=True, fill="both")

        # Create another frame to center buttons horizontally within the container
        self._center_frame = tk.Frame(button_container, bg=self.theme.palette.get("bg", "#121212"))
        self._center_frame.pack(expand=True)
        center_frame = self._center_frame

        btn_bg = self.theme.palette.get("button_bg_color", self.theme.palette.get("accent", "#0078d4"))
        btn_fg = self.theme.palette.get("button_fg_color", "#ffffff")
        btn_hover = self.theme.palette.get("button_hover", self.theme.palette.get("accent_hover", "#106ebe"))
        bg = self.theme.palette.get("bg", "#121212")
        ui_font = self.theme.palette.get("ui_font", "Segoe UI")

        def _make_btn(parent, text, command, width=120, height=32):
            return _RoundedButton(
                parent, text=text, command=command,
                bg=btn_bg, fg=btn_fg, hover_bg=btn_hover,
                canvas_bg=bg, width=width, height=height,
                radius=8, font=(ui_font, 10),
            )

        self.btn_folder = _make_btn(center_frame, "📂 Folder", self.browse_folder)
        self.btn_folder.pack(pady=6)

        self.btn_file = _make_btn(center_frame, "🎵 File", self.browse_files)
        self.btn_file.pack(pady=6)

        self.btn_add = _make_btn(center_frame, "➕ Add", self.add_selected_to_playlist)
        self.btn_add.pack(pady=8)

        self.btn_add_below = _make_btn(center_frame, "⬇ Add Below", self.add_selected_below_playlist)
        self.btn_add_below.pack(pady=8)

        self._preview_btn_row = tk.Frame(center_frame, bg=bg)
        self._preview_btn_row.pack(pady=(10, 6))

        self._btn_preview_play = _make_btn(self._preview_btn_row, "▶", self._on_preview_play_btn, width=58, height=32)
        self._btn_preview_play.pack(side="left", padx=(0, 4))

        self._btn_preview_stop = _make_btn(self._preview_btn_row, "⏹", self._preview_stop, width=58, height=32)
        self._btn_preview_stop.pack(side="left")

        # Right side: device selector row + tree
        right_side_frame = ttk.Frame(content_frame)
        right_side_frame.pack(side="left", fill="both", expand=True)

        # Preview device selector — above the browse list
        self._device_row = ttk.Frame(right_side_frame)
        self._device_row.pack(fill="x", pady=(0, 6))

        self._preview_device_label = ttk.Label(
            self._device_row,
            text="Preview output:",
        )
        self._preview_device_label.pack(side="left", padx=(0, 6))

        self._preview_device_var = tk.StringVar()
        self._preview_device_menu = ttk.Combobox(
            self._device_row,
            textvariable=self._preview_device_var,
            values=["No device"],
            state="readonly",
            width=28,
        )
        self._preview_device_menu.bind("<<ComboboxSelected>>", lambda e: self._on_preview_device_changed(self._preview_device_var.get()))
        self._preview_device_menu.pack(side="left", fill="x", expand=True)

        # Tree frame
        tree_frame = ttk.Frame(right_side_frame)
        tree_frame.pack(fill="both", expand=True)

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

        # Track clicked item for distinguishing click vs drag
        self._clicked_item = None
        self._single_click_timer = None
        self._mouse_moved = False

        # Track index for internal live reordering
        self.internal_drag_index = None
        self.internal_drag_indices = []  # For multi-item reordering
        self.last_internal_target = None

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

        self._refresh_preview_devices()
        self.bind("<Destroy>", self._on_destroy)

        self._setup_bindings()

    def _setup_bindings(self):
        """Setup event bindings."""
        self.tree.bind('<Delete>', self.remove_selected_from_browser)
        self.tree.bind("<Double-1>", self._on_double_click)

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
        p = self.theme.palette
        bg = p.get("bg", "#121212")
        btn_bg = p.get("button_bg_color", p.get("accent", "#0078d4"))
        btn_fg = p.get("button_fg_color", "#ffffff")
        btn_hover = p.get("button_hover", p.get("accent_hover", "#106ebe"))

        if "striped_bg" in p:
            self.tree.tag_configure("striped", background=p["striped_bg"])

        self.header_label.config(fg=p.get("fg", "#FFFFFF"), bg=bg)

        for btn in [self.btn_folder, self.btn_file, self.btn_add, self.btn_add_below,
                    getattr(self, "_btn_preview_play", None),
                    getattr(self, "_btn_preview_stop", None)]:
            if btn is not None:
                btn.configure(bg=btn_bg, fg=btn_fg,
                               activebackground=btn_hover, canvas_bg=bg)

        if hasattr(self, "_center_frame"):
            self._center_frame.configure(bg=bg)
        if hasattr(self, "_preview_btn_row"):
            self._preview_btn_row.configure(bg=bg)

        self.tree.tag_configure("hover", background=p.get("hover_bg", "#2A2A2A"))

        self.scrollbar_canvas.config(bg=bg)
        self.scrollbar_canvas.itemconfig(self.scroll_track, fill=p.get("scrollbar_track", "#282828"))
        self.scrollbar_canvas.itemconfig(self.scroll_thumb, fill=p.get("scrollbar_thumb", "#535353"))

        self.drag_tooltip_label.config(
            bg=p.get("tooltip_bg", "#2D2D2D"),
            fg=p.get("tooltip_fg", "#FFFFFF")
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

    def _reorder_browser_tree(self):
        """Efficiently reorder browser tree items without re-fetching metadata."""
        # Store current items' data
        current_items = []
        children = self.tree.get_children()
        for iid in children:
            text = self.tree.item(iid, 'text')
            current_items.append(text)

        # Clear tree
        self.tree.delete(*children)

        # Re-insert in new order
        for i, text in enumerate(current_items):
            # Update tags based on new position
            tags = ["odd" if i % 2 == 1 else "even"]
            if "striped_bg" in self.theme.palette and i % 2 == 1:
                tags.append("striped")

            self.tree.insert('', tk.END, text=text, tags=tuple(tags))

        # Update scrollbar
        self._update_scrollbar()

    def _handle_single_click(self, item):
        """Handle a confirmed single click by removing selection."""
        if item and item in self.tree.selection():
            self.tree.selection_remove(item)
        # Clean up timer since it fired
        self._single_click_timer = None

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
        self.internal_drag_indices = []  # For multi-item reordering
        self.last_internal_target = None

        # Handle click vs drag distinction for multi-selection
        current_selection = self.tree.selection()
        if item in current_selection and len(current_selection) > 1:
            # Multi-selection: allow dragging without changing selection
            self._clicked_item = item
            # Set up drag state for multi-selection
            self.internal_drag_indices = [self.tree.index(s) for s in current_selection]
            return "break"
        elif item in current_selection and len(current_selection) == 1:
            # Single selection: allow immediate drag
            self._clicked_item = item
            self.state.dragged_index = self.tree.index(item)

    def _on_drag_motion(self, event):
        if not self.drag_start_pos:
            return

        self._clicked_item = None

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
                # Single item internal reorder
                self.internal_drag_index = self.tree.index(sels[0])
                self.internal_drag_indices = []
            elif not self.internal_drag_indices:  # Only set if not already set from drag start
                # Multi-item reorder
                self.internal_drag_index = None
                self.internal_drag_indices = [self.tree.index(s) for s in sels]
                self.last_internal_target = None

            for s in sels:
                idx = self.tree.index(s)
                if 0 <= idx < len(self.state.browser_files):
                    paths.append(self.state.browser_files[idx])

            if paths:
                self.drag_data = {"files": paths}

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
            # Calculate tooltip position relative to the browser tree (above the row)
            tree_x = self.tree.winfo_rootx()
            tree_y = self.tree.winfo_rooty()
            tooltip_x = tree_x + self.drag_start_pos[0] + 10
            tooltip_y = tree_y + self.drag_start_pos[1] - 20  # Position above the row
            self._show_drag_tooltip(paths, tooltip_x, tooltip_y)
        elif is_inside_browser and self.drag_tooltip_visible:
            # Hide tooltip when dragging back inside browser
            self.drag_tooltip.withdraw()
            self.drag_tooltip_visible = False

        # Update drag tooltip position to follow mouse when visible (position above cursor)
        if self.drag_tooltip_visible:
            self.drag_tooltip.geometry(f"+{x_root + 10}+{y_root - 20}")

        # 1. External drag to Playlist (delegation)
        if self.playlist_view:
             self.playlist_view.handle_external_drag_motion(x_root, y_root, self.drag_data)

        # 2. Internal Live Reorder
        if self.internal_drag_index is not None or self.internal_drag_indices:
            # Check if over BrowserView
            tree_x = self.tree.winfo_rootx()
            tree_y = self.tree.winfo_rooty()
            tree_w = self.tree.winfo_width()
            tree_h = self.tree.winfo_height()

            if (tree_x <= x_root <= tree_x + tree_w and tree_y <= y_root <= tree_y + tree_h):
                 target_row = self.tree.identify_row(event.y)
                 if target_row:
                      target_index = self.tree.index(target_row)

                      if self.internal_drag_index is not None:
                          # Single item reorder (existing logic)
                          if target_index != self.internal_drag_index:
                               if 0 <= target_index < len(self.state.browser_files) and 0 <= self.internal_drag_index < len(self.state.browser_files):
                                    dragged_item = self.tree.get_children()[self.internal_drag_index]
                                    self.tree.move(dragged_item, '', target_index)
                                    self.state.browser_files.insert(target_index, self.state.browser_files.pop(self.internal_drag_index))
                                    self._restripe_tree()
                                    self.internal_drag_index = target_index
                                    self.tree.selection_set(dragged_item)
                                    self.tree.see(dragged_item)
                      else:
                          # Multi-item reorder
                          if self.internal_drag_indices and target_index not in self.internal_drag_indices:
                              if self.last_internal_target != target_index:
                                  self.last_internal_target = target_index

                                  # Calculate new positions
                                  selected_indices = sorted(self.internal_drag_indices)
                                  if target_index < selected_indices[0]:
                                      # Moving up
                                      new_positions = list(range(target_index, target_index + len(selected_indices)))
                                  else:
                                      # Moving down
                                      new_positions = list(range(target_index - len(selected_indices) + 1, target_index + 1))

                                  # Move items in data
                                  selected_files = [self.state.browser_files[i] for i in selected_indices]

                                  # Remove from old positions (reverse order)
                                  for i in sorted(selected_indices, reverse=True):
                                      self.state.browser_files.pop(i)

                                  # Insert at new positions
                                  for i, file_path in enumerate(selected_files):
                                      self.state.browser_files.insert(new_positions[i], file_path)

                                  # Update treeview efficiently
                                  self._reorder_browser_tree()

                                  # Update indices
                                  self.internal_drag_indices = new_positions

                                  # Restore selection
                                  children = self.tree.get_children()
                                  for new_pos in new_positions:
                                      if new_pos < len(children):
                                          self.tree.selection_add(children[new_pos])

                                  # Scroll to dragged items
                                  if new_positions:
                                      self.tree.see(children[new_positions[0]])

    def _on_drag_release(self, event):
        # Cancel single-click timer only if there was mouse movement (drag)
        if self._single_click_timer is not None and self._mouse_moved:
            self.after_cancel(self._single_click_timer)
            self._single_click_timer = None
            self._mouse_moved = False

        # Handle single-click selection if no drag occurred
        if self._clicked_item and not self._mouse_moved and not self.drag_data:
            current_selection = self.tree.selection()
            if self._clicked_item in current_selection and len(current_selection) > 1:
                # Change selection to just the clicked item
                self.tree.selection_set(self._clicked_item)

        # Clear clicked item
        self._clicked_item = None

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
            self.internal_drag_indices = []
            self.last_internal_target = None

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
        for f in files_to_add:
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

    # ========== Preview ==========

    def _get_preview_devices(self):
        """Return (id, name) pairs available for preview, excluding the main player's device."""
        if self._main_player is None:
            return []
        all_devices = self._main_player.get_audio_devices()
        try:
            import sounddevice as sd
            default_idx = sd.default.device[1]
            default_id = str(default_idx) if default_idx >= 0 else None
        except Exception:
            default_id = None

        main_id = self._main_player._device_id  # None = system default
        excluded = set()
        if main_id is None:
            excluded.add('__DEFAULT__')
            if default_id is not None:
                excluded.add(default_id)
        else:
            excluded.add(main_id)
            if main_id == default_id:
                excluded.add('__DEFAULT__')
        return [(did, name) for did, name in all_devices if did not in excluded]

    def _refresh_preview_devices(self):
        """Rebuild the preview device dropdown, filtering out the main player's current device."""
        if not hasattr(self, '_preview_device_menu'):
            return
        devices = self._get_preview_devices()
        self._preview_devices = devices
        if not devices:
            self._preview_device_menu.configure(values=["No device available"], state="disabled")
            self._preview_device_var.set("No device available")
            self._set_preview_controls_state("disabled")
        else:
            names = [name for _, name in devices]
            self._preview_device_menu.configure(values=names, state="readonly")
            if self._preview_device_var.get() not in names:
                self._preview_device_var.set(names[0])
            self._set_preview_controls_state("normal")

    def refresh_preview_devices(self):
        """Public entry point — call when the main player's output device changes."""
        self._refresh_preview_devices()

    def _set_preview_controls_state(self, state):
        for widget in (getattr(self, '_btn_preview_play', None), getattr(self, '_btn_preview_stop', None)):
            if widget is not None:
                try:
                    widget.configure(state=state)
                except Exception:
                    pass

    def _on_preview_device_changed(self, _name):
        """Stop any active preview when the user picks a different output device."""
        if self._preview_path is not None:
            self._preview_stop()

    def _preview_play(self, path):
        """Start (or restart) preview of *path* on the selected preview device."""
        if self._preview_player is None:
            return
        self._refresh_preview_devices()
        if not self._preview_devices:
            return
        selected_name = self._preview_device_var.get()
        device_id = next((did for did, name in self._preview_devices if name == selected_name), None)
        if device_id is None:
            return
        self._preview_path = path
        def _start():
            self._preview_player.set_audio_device(device_id)
            self._preview_player.play(path)
        threading.Thread(target=_start, daemon=True).start()

    def _preview_stop(self):
        """Stop the preview player."""
        self._preview_path = None
        if self._preview_player is not None:
            threading.Thread(target=self._preview_player.stop, daemon=True).start()

    def _on_preview_play_btn(self):
        sels = self.tree.selection()
        if not sels:
            return
        idx = self.tree.index(sels[0])
        if 0 <= idx < len(self.state.browser_files):
            self._preview_play(self.state.browser_files[idx])

    def _on_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        idx = self.tree.index(item)
        if not (0 <= idx < len(self.state.browser_files)):
            return
        path = self.state.browser_files[idx]
        # Toggle: double-clicking the same song stops it; any other song switches to it
        if path == self._preview_path:
            self._preview_stop()
        else:
            self._preview_play(path)

    def _on_preview_track_end(self):
        """Called from the preview player's background thread when a track finishes."""
        self._preview_path = None

    def _on_destroy(self, event):
        if event.widget is self and self._preview_player is not None:
            try:
                self._preview_player.stop()
            except Exception:
                pass
