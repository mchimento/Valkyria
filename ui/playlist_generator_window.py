"""
Playlist Generator window — configure groups, subgroups, sources and rules,
then generate a playlist from your music library.
"""
import copy
import threading
import tkinter as tk
from tkinter import ttk, filedialog
import customtkinter as ctk

from audio.playlist_generator import (
    GeneratorTemplate, Group, Subgroup, Source, FilterSet, GeneratorRules,
    generate, load_templates, save_templates, MUSICAL_KEYS, ORDER_MODES,
)
from audio.metadata import metadata_extractor
from ui.utils import apply_theme_titlebar

_ORDER_MODE_LABELS = list(ORDER_MODES.values())
_ORDER_MODE_KEYS = list(ORDER_MODES.keys())


class PlaylistGeneratorWindow(tk.Toplevel):

    def __init__(self, master, theme_manager, on_generate, templates_path):
        # Resolve bg before creating the window so it's born with the correct
        # background color, then withdraw immediately — both steps together
        # prevent the default white Toplevel from ever being painted on screen.
        _bg = theme_manager.palette.get("bg", "#1e1e1e")
        super().__init__(master, bg=_bg)
        self.withdraw()

        self.theme_manager = theme_manager
        self.palette = theme_manager.palette
        self.on_generate = on_generate
        self._templates_path = templates_path

        self._templates: list = []
        self._template: GeneratorTemplate = GeneratorTemplate(name="", groups=[], rules=GeneratorRules())
        self._selected_template_name: str = ""

        # Maps tree iid → ("group"|"subgroup"|"source", *objects)
        self._tree_map: dict = {}

        # Currently selected Group object for the right-panel rules
        self._selected_group: "Group | None" = None

        # Guards against feedback loops when programmatically setting vars
        self._updating = False

        self.title("Playlist Generator")
        self.minsize(720, 520)
        self.resizable(True, True)
        self.transient(master)

        bg = _bg
        self.configure(bg=bg)

        self._content = tk.Frame(self, bg=bg)
        self._content.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_template_bar(self._content)
        ttk.Separator(self._content, orient="horizontal").pack(fill="x", pady=6)
        self._build_main_area(self._content)
        self._build_bottom_bar(self._content)

        self._load_from_disk()
        self._refresh_template_dropdown()

        self._position_centered(master, 960, 680)
        self.update_idletasks()  # ensure outer HWND is linked before DWM coloring
        apply_theme_titlebar(self, self.palette)
        self.bind("<Configure>", self._on_configure)
        self.deiconify()

    def _position_centered(self, parent, w: int, h: int):
        """Position and size the window relative to parent without update_idletasks."""
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        x = max(0, px + (pw - w) // 2)
        y = max(0, py + (ph - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _on_configure(self, event):
        if event.widget is self:
            apply_theme_titlebar(self, self.palette)

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------

    def _build_template_bar(self, parent):
        bar = tk.Frame(parent, bg=self.palette.get("bg", "#1e1e1e"))
        bar.pack(fill="x", pady=(0, 2))

        fg = self.palette.get("fg", "#ffffff")
        bg = self.palette.get("bg", "#1e1e1e")
        font = (self.palette.get("ui_font", "Segoe UI"), 11)

        tk.Label(bar, text="Template:", bg=bg, fg=fg, font=font).pack(side="left", padx=(0, 6))

        self._template_var = tk.StringVar()
        self._template_combo = ttk.Combobox(
            bar, textvariable=self._template_var, state="readonly", width=28, font=font
        )
        self._template_combo.pack(side="left", padx=(0, 8))
        self._template_combo.bind("<<ComboboxSelected>>", self._on_template_selected)

        for text, cmd in [("Save", self._on_save_template),
                          ("Save As…", self._on_save_as_template), ("Delete", self._on_delete_template)]:
            self._make_btn(bar, text, cmd, width=74, side="left", padx=(0, 4))

        self._template_bar = bar

    def _build_main_area(self, parent):
        frame = tk.Frame(parent, bg=self.palette.get("bg", "#1e1e1e"))
        frame.pack(fill="both", expand=True)

        self._build_left_panel(frame)
        self._build_right_panel(frame)

    def _build_left_panel(self, parent):
        bg = self.palette.get("bg", "#1e1e1e")
        fg = self.palette.get("fg", "#ffffff")
        font = (self.palette.get("ui_font", "Segoe UI"), 11)

        left = tk.Frame(parent, bg=bg, width=390)
        left.pack(side="left", fill="both", padx=(0, 10))
        left.pack_propagate(False)

        tk.Label(left, text="Groups & Sources", bg=bg, fg=fg,
                 font=(self.palette.get("ui_font", "Segoe UI"), 11, "bold")).pack(anchor="w", pady=(0, 4))

        tree_frame = tk.Frame(left, bg=bg)
        tree_frame.pack(fill="both", expand=True)

        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        vsb.pack(side="right", fill="y")

        self.tree = ttk.Treeview(tree_frame, show="tree", yscrollcommand=vsb.set, selectmode="browse")
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.configure(command=self.tree.yview)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-Button-1>", self._on_tree_double_click)

        # Button rows
        row1 = tk.Frame(left, bg=bg)
        row1.pack(fill="x", pady=(8, 2))
        row2 = tk.Frame(left, bg=bg)
        row2.pack(fill="x")

        for text, cmd in [("+ Group", self._on_add_group), ("+ Subgroup", self._on_add_subgroup),
                          ("Load Files", self._on_load_files), ("Load M3U", self._on_load_m3u),
                          ("Load Folder", self._on_load_folder)]:
            self._make_btn(row1, text, cmd, width=73, side="left", padx=(0, 3))

        for text, cmd in [("↑ Up", self._on_move_up), ("↓ Down", self._on_move_down),
                          ("Rename", self._on_rename), ("Remove", self._on_remove)]:
            self._make_btn(row2, text, cmd, width=86, side="left", padx=(0, 3))

    def _build_right_panel(self, parent):
        bg = self.palette.get("bg", "#1e1e1e")
        fg = self.palette.get("fg", "#ffffff")
        font_bold = (self.palette.get("ui_font", "Segoe UI"), 11, "bold")
        font = (self.palette.get("ui_font", "Segoe UI"), 10)

        right = tk.Frame(parent, bg=bg)
        right.pack(side="left", fill="both", expand=True)

        # --- Global rules ---
        self._global_frame = tk.LabelFrame(right, text="Global Rules", bg=bg, fg=fg,
                                           font=font_bold, padx=10, pady=8)
        self._global_frame.pack(fill="x", pady=(0, 10))

        self._var_total_songs = tk.StringVar()
        self._var_total_songs_unlimited = tk.BooleanVar(value=True)
        self._var_total_duration = tk.StringVar()
        self._var_total_duration_unlimited = tk.BooleanVar(value=True)
        self._var_allow_repeats = tk.BooleanVar(value=False)
        self._var_order_mode = tk.StringVar(value=ORDER_MODES["subgroup_round"])

        self._total_songs_entry, self._total_songs_unlimited_cb = self._make_limit_row(
            self._global_frame, "Total songs:", self._var_total_songs,
            self._var_total_songs_unlimited, self._on_total_songs_change
        )
        self._total_duration_entry, self._total_duration_unlimited_cb = self._make_limit_row(
            self._global_frame, "Total duration (min):", self._var_total_duration,
            self._var_total_duration_unlimited, self._on_total_duration_change,
        )

        rep_row = tk.Frame(self._global_frame, bg=bg)
        rep_row.pack(fill="x", pady=3)
        self._allow_repeats_cb = ttk.Checkbutton(
            rep_row, text="Allow repeats", variable=self._var_allow_repeats,
            command=self._on_allow_repeats_change
        )
        self._allow_repeats_cb.pack(side="left")

        order_row = tk.Frame(self._global_frame, bg=bg)
        order_row.pack(fill="x", pady=3)
        tk.Label(order_row, text="Order mode:", bg=bg, fg=fg, font=font, width=18, anchor="w").pack(side="left")
        self._order_mode_combo = ttk.Combobox(
            order_row, textvariable=self._var_order_mode,
            values=_ORDER_MODE_LABELS, state="readonly", width=26, font=font
        )
        self._order_mode_combo.pack(side="left")
        self._order_mode_combo.bind("<<ComboboxSelected>>", self._on_order_mode_change)

        # --- Group rules (visible when a group is selected) ---
        self._group_frame = tk.LabelFrame(right, text="Group Rules", bg=bg, fg=fg,
                                          font=font_bold, padx=10, pady=8)
        self._group_frame.pack(fill="x")

        self._var_songs_per_round = tk.StringVar(value="1")
        self._var_bpm_min = tk.StringVar()
        self._var_bpm_max = tk.StringVar()
        self._var_key = tk.StringVar(value="Any")

        spr_row = tk.Frame(self._group_frame, bg=bg)
        spr_row.pack(fill="x", pady=3)
        tk.Label(spr_row, text="Songs per round:", bg=bg, fg=fg, font=font, width=18, anchor="w").pack(side="left")
        self._spr_spin = ttk.Spinbox(spr_row, textvariable=self._var_songs_per_round,
                                     from_=1, to=999, width=6, command=self._on_group_rules_change)
        self._spr_spin.pack(side="left")
        self._var_songs_per_round.trace_add("write", lambda *_: self._on_group_rules_change())

        bpm_row = tk.Frame(self._group_frame, bg=bg)
        bpm_row.pack(fill="x", pady=3)
        tk.Label(bpm_row, text="BPM range:", bg=bg, fg=fg, font=font, width=18, anchor="w").pack(side="left")
        self._bpm_min_entry = ttk.Entry(bpm_row, textvariable=self._var_bpm_min, width=7)
        self._bpm_min_entry.pack(side="left")
        tk.Label(bpm_row, text=" – ", bg=bg, fg=fg, font=font).pack(side="left")
        self._bpm_max_entry = ttk.Entry(bpm_row, textvariable=self._var_bpm_max, width=7)
        self._bpm_max_entry.pack(side="left")
        tk.Label(bpm_row, text=" (leave blank for any)", bg=bg, fg=fg,
                 font=(self.palette.get("ui_font", "Segoe UI"), 9)).pack(side="left")
        self._var_bpm_min.trace_add("write", lambda *_: self._on_group_rules_change())
        self._var_bpm_max.trace_add("write", lambda *_: self._on_group_rules_change())

        key_row = tk.Frame(self._group_frame, bg=bg)
        key_row.pack(fill="x", pady=3)
        tk.Label(key_row, text="Key:", bg=bg, fg=fg, font=font, width=18, anchor="w").pack(side="left")
        self._key_combo = ttk.Combobox(key_row, textvariable=self._var_key,
                                       values=MUSICAL_KEYS, state="readonly", width=10, font=font)
        self._key_combo.pack(side="left")
        self._key_combo.bind("<<ComboboxSelected>>", lambda *_: self._on_group_rules_change())

        self._no_group_label = tk.Label(
            self._group_frame, text="Select a group to configure its rules.",
            bg=bg, fg=self.palette.get("fg_muted", "#888888"),
            font=(self.palette.get("ui_font", "Segoe UI"), 10, "italic")
        )

        self._set_group_rules_visible(False)

    def _make_limit_row(self, parent, label, str_var, unlimited_var, on_change):
        bg = self.palette.get("bg", "#1e1e1e")
        fg = self.palette.get("fg", "#ffffff")
        font = (self.palette.get("ui_font", "Segoe UI"), 10)

        row = tk.Frame(parent, bg=bg)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, bg=bg, fg=fg, font=font, width=18, anchor="w").pack(side="left")
        entry = ttk.Entry(row, textvariable=str_var, width=7)
        entry.pack(side="left", padx=(0, 6))
        cb = ttk.Checkbutton(row, text="Unlimited", variable=unlimited_var,
                              command=lambda: self._on_unlimited_toggle(entry, unlimited_var, on_change))
        cb.pack(side="left")
        str_var.trace_add("write", lambda *_: on_change())
        # Apply initial state
        entry.configure(state="disabled" if unlimited_var.get() else "normal")
        return entry, cb

    def _build_bottom_bar(self, parent):
        bg = self.palette.get("bg", "#1e1e1e")
        bar = tk.Frame(parent, bg=bg)
        bar.pack(fill="x", pady=(10, 0))
        ttk.Separator(bar, orient="horizontal").pack(fill="x", pady=(0, 8))
        self._generate_btn = self._make_btn(bar, "Generate Playlist", self._on_generate,
                                            width=180, height=36, side="right")
        self._status_label = tk.Label(bar, text="", bg=bg,
                                      fg=self.palette.get("fg_muted", "#888888"),
                                      font=(self.palette.get("ui_font", "Segoe UI"), 10))
        self._status_label.pack(side="left")

    # ------------------------------------------------------------------
    # Widget helpers
    # ------------------------------------------------------------------

    def _show_info(self, title: str, message: str) -> None:
        self._themed_dialog(title, message, buttons=[("OK", True)])

    def _show_error(self, title: str, message: str) -> None:
        self._themed_dialog(title, message, buttons=[("OK", True)], error=True)

    def _ask_yesno(self, title: str, message: str) -> bool:
        return bool(self._themed_dialog(title, message, buttons=[("Yes", True), ("No", False)]))

    def _themed_dialog(self, title: str, message: str, buttons: list, error: bool = False):
        """Generic themed modal dialog. Returns the value of the clicked button."""
        result = [None]
        p = self.palette
        bg = p.get("bg", "#1e1e1e")
        fg = p.get("error", "#ff6b6b") if error else p.get("fg", "#ffffff")

        dlg = tk.Toplevel(self, bg=bg)
        dlg.title(title)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text=message, bg=bg, fg=fg,
                 font=(p.get("ui_font", "Segoe UI"), 11),
                 wraplength=340, justify="left").pack(padx=24, pady=(20, 16))

        btn_row = tk.Frame(dlg, bg=bg)
        btn_row.pack(padx=24, pady=(0, 18))

        def _pick(val):
            result[0] = val
            dlg.destroy()

        for i, (label, val) in enumerate(buttons):
            self._make_btn(btn_row, label, lambda v=val: _pick(v),
                           width=80, side="left", padx=(0, 8) if i < len(buttons) - 1 else 0)

        dlg.bind("<Return>", lambda _: _pick(buttons[0][1]))
        dlg.bind("<Escape>", lambda _: _pick(buttons[-1][1]))

        dlg.update_idletasks()
        apply_theme_titlebar(dlg, self.palette)
        x = self.winfo_rootx() + (self.winfo_width() - dlg.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{max(0, x)}+{max(0, y)}")

        self.wait_window(dlg)
        return result[0]

    def _ask_string(self, title: str, prompt: str, initial: str = "") -> "str | None":
        """Themed single-line text entry dialog matching the generator window palette."""
        result = [None]
        p = self.palette
        bg = p.get("bg", "#1e1e1e")
        fg = p.get("fg", "#ffffff")

        dlg = tk.Toplevel(self, bg=bg)
        dlg.title(title)
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text=prompt, bg=bg, fg=fg,
                 font=(p.get("ui_font", "Segoe UI"), 11)).pack(padx=24, pady=(18, 6))

        var = tk.StringVar(value=initial)
        entry = ttk.Entry(dlg, textvariable=var, width=32)
        entry.pack(padx=24, pady=(0, 14))
        entry.focus_set()
        if initial:
            entry.select_range(0, tk.END)

        btn_row = tk.Frame(dlg, bg=bg)
        btn_row.pack(padx=24, pady=(0, 18))

        def _ok(_event=None):
            result[0] = var.get()
            dlg.destroy()

        def _cancel(_event=None):
            dlg.destroy()

        self._make_btn(btn_row, "OK", _ok, width=80, side="left", padx=(0, 8))
        self._make_btn(btn_row, "Cancel", _cancel, width=80, side="left")
        dlg.bind("<Return>", _ok)
        dlg.bind("<Escape>", _cancel)

        dlg.update_idletasks()
        apply_theme_titlebar(dlg, self.palette)
        x = self.winfo_rootx() + (self.winfo_width() - dlg.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{max(0, x)}+{max(0, y)}")

        self.wait_window(dlg)
        return result[0]

    def _make_btn(self, parent, text, command, width=90, height=28, side=None, padx=0):
        p = self.palette
        btn = ctk.CTkButton(
            parent, text=text, command=command,
            width=width, height=height,
            fg_color=p.get("button_bg_color", p.get("accent", "#0078d4")),
            text_color=p.get("button_fg_color", "#ffffff"),
            hover_color=p.get("button_hover", p.get("accent_hover", "#106ebe")),
            bg_color=p.get("bg", "#1e1e1e"),
            font=(p.get("ui_font", "Segoe UI"), 12),
        )
        if side:
            btn.pack(side=side, padx=padx)
        return btn

    def _set_group_rules_visible(self, visible: bool):
        for w in (self._spr_spin.master, self._bpm_min_entry.master,
                  self._key_combo.master):
            if visible:
                w.pack(fill="x", pady=3)
            else:
                w.pack_forget()
        if visible:
            self._no_group_label.pack_forget()
        else:
            self._no_group_label.pack(pady=6)

    # ------------------------------------------------------------------
    # Template management
    # ------------------------------------------------------------------

    def _load_from_disk(self):
        self._templates = load_templates(self._templates_path)

    def _refresh_template_dropdown(self):
        names = [t.name for t in self._templates]
        self._template_combo.configure(values=names)
        if self._selected_template_name in names:
            self._template_var.set(self._selected_template_name)
        else:
            self._template_var.set("")

    def _on_template_selected(self, _event=None):
        name = self._template_var.get()
        if not name:
            return
        tmpl = next((t for t in self._templates if t.name == name), None)
        if tmpl is None:
            return
        self._template = copy.deepcopy(tmpl)
        self._selected_template_name = name
        self.title(f"Playlist Generator — {name}")
        self._selected_group = None
        self._render_tree()
        self._load_global_rules_to_ui()
        self._set_group_rules_visible(False)

    def _on_save_template(self):
        name = self._template_var.get().strip()
        if not name:
            self._on_save_as_template()
            return
        self._template.name = name
        self._selected_template_name = name
        existing = next((i for i, t in enumerate(self._templates) if t.name == name), None)
        if existing is not None:
            self._templates[existing] = copy.deepcopy(self._template)
        else:
            self._templates.append(copy.deepcopy(self._template))
        save_templates(self._templates_path, self._templates)
        self._refresh_template_dropdown()
        self._template_var.set(name)

    def _on_save_as_template(self):
        name = self._ask_string("Save Template", "Template name:")
        if not name or not name.strip():
            return
        name = name.strip()
        if any(t.name == name for t in self._templates):
            if not self._ask_yesno("Overwrite", f'Template "{name}" already exists. Overwrite?'):
                return
            self._templates = [t for t in self._templates if t.name != name]
        self._template.name = name
        self._selected_template_name = name
        self._templates.append(copy.deepcopy(self._template))
        save_templates(self._templates_path, self._templates)
        self._refresh_template_dropdown()
        self._template_var.set(name)
        self.title(f"Playlist Generator — {name}")

    def _on_delete_template(self):
        name = self._template_var.get()
        if not name:
            return
        if not self._ask_yesno("Delete Template", f'Delete template "{name}"?'):
            return
        self._templates = [t for t in self._templates if t.name != name]
        save_templates(self._templates_path, self._templates)
        if self._selected_template_name == name:
            self._selected_template_name = ""
            self._template = GeneratorTemplate(name="", groups=[], rules=GeneratorRules())
            self.title("Playlist Generator")
            self._selected_group = None
            self._render_tree()
            self._load_global_rules_to_ui()
            self._set_group_rules_visible(False)
        self._refresh_template_dropdown()

    # ------------------------------------------------------------------
    # Tree rendering
    # ------------------------------------------------------------------

    def _render_tree(self):
        # Capture selected object (by identity) before wiping the tree
        _sel_obj = None
        sel = self.tree.selection()
        if sel:
            data = self._tree_map.get(sel[0])
            if data:
                if data[0] == "group":
                    _sel_obj = data[1]
                elif data[0] == "subgroup":
                    _sel_obj = data[2]
                elif data[0] == "source":
                    _sel_obj = data[3]

        self.tree.delete(*self.tree.get_children())
        self._tree_map.clear()

        font = self.palette.get("ui_font", "Segoe UI")
        self.tree.tag_configure("group", font=(font, 11, "bold"))
        self.tree.tag_configure("subgroup", font=(font, 10))
        self.tree.tag_configure("source", font=(font, 9),
                                foreground=self.palette.get("fg_muted", "#888888"))

        for group in self._template.groups:
            g_iid = self.tree.insert("", "end", text=f"  {group.name}", tags=("group",), open=True)
            self._tree_map[g_iid] = ("group", group)

            for subgroup in group.subgroups:
                sg_iid = self.tree.insert(g_iid, "end", text=f"  {subgroup.name}", tags=("subgroup",), open=True)
                self._tree_map[sg_iid] = ("subgroup", group, subgroup)

                for source in subgroup.sources:
                    if source.type == "directory":
                        icon = "📁"
                    elif source.type == "playlist":
                        icon = "📋"
                    else:
                        icon = "🎵"
                    short = self._short_path(source.path)
                    s_iid = self.tree.insert(sg_iid, "end", text=f"  {icon} {short}", tags=("source",))
                    self._tree_map[s_iid] = ("source", group, subgroup, source)

        if _sel_obj is not None:
            self._reselect_item(_sel_obj)

    def _short_path(self, path: str, max_len: int = 48) -> str:
        if len(path) <= max_len:
            return path
        import os
        parts = path.replace("\\", "/").split("/")
        if len(parts) > 3:
            return "…/" + "/".join(parts[-2:])
        return "…" + path[-(max_len - 1):]

    # ------------------------------------------------------------------
    # Tree selection / interaction
    # ------------------------------------------------------------------

    def _on_tree_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            self._selected_group = None
            self._set_group_rules_visible(False)
            return
        iid = sel[0]
        data = self._tree_map.get(iid)
        if data is None:
            return
        kind = data[0]
        if kind == "group":
            self._selected_group = data[1]
            self._load_group_rules_to_ui(data[1])
            self._set_group_rules_visible(True)
        elif kind == "subgroup":
            self._selected_group = data[1]
            self._load_group_rules_to_ui(data[1])
            self._set_group_rules_visible(True)
        else:
            # source selected — show parent group rules
            self._selected_group = data[1]
            self._load_group_rules_to_ui(data[1])
            self._set_group_rules_visible(True)

    def _on_tree_double_click(self, event):
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        data = self._tree_map.get(iid)
        if data and data[0] in ("group", "subgroup"):
            self._do_rename(iid, data)

    # ------------------------------------------------------------------
    # Tree actions
    # ------------------------------------------------------------------

    def _on_add_group(self):
        name = self._ask_string("Add Group", "Group name:")
        if not name or not name.strip():
            return
        self._template.groups.append(Group(name=name.strip()))
        self._render_tree()

    def _on_add_subgroup(self):
        group = self._get_selected_group()
        if group is None:
            self._show_info("Add Subgroup", "Select a group first.")
            return
        name = self._ask_string("Add Subgroup", "Subgroup name:")
        if not name or not name.strip():
            return
        group.subgroups.append(Subgroup(name=name.strip()))
        self._render_tree()

    def _on_load_files(self):
        paths = filedialog.askopenfilenames(
            parent=self, title="Select Audio File(s)",
            filetypes=[("Audio files", "*.mp3 *.wav *.flac *.ogg *.m4a"), ("All files", "*.*")]
        )
        if not paths:
            return
        subgroup = self._resolve_load_target()
        for p in paths:
            subgroup.sources.append(Source(type="file", path=str(p)))
        self._render_tree()
        self._reselect_item(subgroup)

    def _on_load_m3u(self):
        paths = filedialog.askopenfilenames(
            parent=self, title="Select M3U Playlist(s)",
            filetypes=[("M3U Playlists", "*.m3u *.m3u8"), ("All files", "*.*")]
        )
        if not paths:
            return
        subgroup = self._resolve_load_target()
        for p in paths:
            subgroup.sources.append(Source(type="playlist", path=str(p)))
        self._render_tree()
        self._reselect_item(subgroup)

    def _on_load_folder(self):
        path = filedialog.askdirectory(parent=self, title="Select Music Folder")
        if not path:
            return
        subgroup = self._resolve_load_target()
        subgroup.sources.append(Source(type="directory", path=str(path)))
        self._render_tree()
        self._reselect_item(subgroup)

    def _on_move_up(self):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        data = self._tree_map.get(iid)
        if data is None:
            return
        kind = data[0]
        if kind == "group":
            lst = self._template.groups
            obj = data[1]
        elif kind == "subgroup":
            lst = data[1].subgroups
            obj = data[2]
        elif kind == "source":
            lst = data[2].sources
            obj = data[3]
        else:
            return
        idx = lst.index(obj)
        if idx > 0:
            lst[idx], lst[idx - 1] = lst[idx - 1], lst[idx]
            self._render_tree()
            self._reselect_item(obj)

    def _on_move_down(self):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        data = self._tree_map.get(iid)
        if data is None:
            return
        kind = data[0]
        if kind == "group":
            lst = self._template.groups
            obj = data[1]
        elif kind == "subgroup":
            lst = data[1].subgroups
            obj = data[2]
        elif kind == "source":
            lst = data[2].sources
            obj = data[3]
        else:
            return
        idx = lst.index(obj)
        if idx < len(lst) - 1:
            lst[idx], lst[idx + 1] = lst[idx + 1], lst[idx]
            self._render_tree()
            self._reselect_item(obj)

    def _on_rename(self):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        data = self._tree_map.get(iid)
        if data:
            self._do_rename(iid, data)

    def _do_rename(self, iid, data):
        kind = data[0]
        if kind not in ("group", "subgroup"):
            return
        obj = data[1] if kind == "group" else data[2]
        current = obj.name
        new_name = self._ask_string("Rename", "New name:", initial=current)
        if new_name and new_name.strip() and new_name.strip() != current:
            obj.name = new_name.strip()
            self._render_tree()
            if kind == "group":
                self._group_frame.configure(text=f"Group Rules — {obj.name}")

    def _on_remove(self):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        data = self._tree_map.get(iid)
        if data is None:
            return
        kind = data[0]
        if kind == "group":
            obj = data[1]
            if obj in self._template.groups:
                self._template.groups.remove(obj)
        elif kind == "subgroup":
            lst = data[1].subgroups
            obj = data[2]
            if obj in lst:
                lst.remove(obj)
        elif kind == "source":
            lst = data[2].sources
            obj = data[3]
            if obj in lst:
                lst.remove(obj)
        self._selected_group = None
        self._render_tree()
        self._set_group_rules_visible(False)

    def _reselect_item(self, obj):
        for iid, data in self._tree_map.items():
            target = data[1] if data[0] == "group" else (data[2] if data[0] == "subgroup" else
                     data[3] if data[0] == "source" else None)
            if target is obj:
                self.tree.selection_set(iid)
                self.tree.see(iid)
                break

    def _get_selected_group(self):
        sel = self.tree.selection()
        if not sel:
            return None
        data = self._tree_map.get(sel[0])
        if data is None:
            return None
        if data[0] in ("group", "subgroup", "source"):
            return data[1]
        return None

    def _get_selected_subgroup(self):
        sel = self.tree.selection()
        if not sel:
            return None
        data = self._tree_map.get(sel[0])
        if data is None:
            return None
        if data[0] == "subgroup":
            return data[2]
        if data[0] == "source":
            return data[2]
        return None

    def _resolve_load_target(self) -> "Subgroup":
        """
        Return the subgroup that newly loaded sources should go into.

        - No selection        → new auto-numbered Group N + Default subgroup
        - Group, no subgroups → Default subgroup (auto-created inside that group)
        - Group, has subgroups→ new auto-numbered Subgroup N inside that group
        - Subgroup selected   → that subgroup (extend it)
        - Source selected     → parent subgroup (extend it)
        """
        sel = self.tree.selection()
        data = self._tree_map.get(sel[0]) if sel else None

        if data is None:
            # No selection — auto-create a new top-level group
            n = 1
            existing = {g.name for g in self._template.groups}
            while f"Group {n}" in existing:
                n += 1
            grp = Group(name=f"Group {n}")
            self._template.groups.append(grp)
            sg = Subgroup(name="Default")
            grp.subgroups.append(sg)
            return sg

        if data[0] in ("subgroup", "source"):
            return data[2]

        # Group selected
        grp = data[1]
        if not grp.subgroups:
            sg = Subgroup(name="Default")
            grp.subgroups.append(sg)
            return sg

        # Group already has subgroups → new numbered subgroup
        n = 1
        existing = {sg.name for sg in grp.subgroups}
        while f"Subgroup {n}" in existing:
            n += 1
        sg = Subgroup(name=f"Subgroup {n}")
        grp.subgroups.append(sg)
        return sg

    # ------------------------------------------------------------------
    # Rules UI ↔ template sync
    # ------------------------------------------------------------------

    def _load_global_rules_to_ui(self):
        self._updating = True
        r = self._template.rules
        if r.total_songs is None:
            self._var_total_songs_unlimited.set(True)
            self._var_total_songs.set("")
            self._total_songs_entry.configure(state="disabled")
        else:
            self._var_total_songs_unlimited.set(False)
            self._var_total_songs.set(str(r.total_songs))
            self._total_songs_entry.configure(state="normal")

        if r.total_duration_sec is None:
            self._var_total_duration_unlimited.set(True)
            self._var_total_duration.set("")
            self._total_duration_entry.configure(state="disabled")
        else:
            self._var_total_duration_unlimited.set(False)
            self._var_total_duration.set(str(r.total_duration_sec // 60))
            self._total_duration_entry.configure(state="normal")

        self._var_allow_repeats.set(r.allow_repeats)
        label = ORDER_MODES.get(r.order_mode, ORDER_MODES["subgroup_round"])
        self._var_order_mode.set(label)
        self._updating = False

    def _load_group_rules_to_ui(self, group: Group):
        self._updating = True
        self._group_frame.configure(text=f"Group Rules — {group.name}")
        self._var_songs_per_round.set(str(group.songs_per_round))
        self._var_bpm_min.set("" if group.filters.bpm_min is None else str(group.filters.bpm_min))
        self._var_bpm_max.set("" if group.filters.bpm_max is None else str(group.filters.bpm_max))
        self._var_key.set(group.filters.key or "Any")
        self._updating = False

    def _on_unlimited_toggle(self, entry, unlimited_var, on_change):
        if unlimited_var.get():
            entry.configure(state="disabled")
        else:
            entry.configure(state="normal")
            entry.focus_set()
        on_change()

    def _on_total_songs_change(self):
        if self._updating:
            return
        if self._var_total_songs_unlimited.get():
            self._template.rules.total_songs = None
        else:
            try:
                v = int(self._var_total_songs.get())
                self._template.rules.total_songs = max(1, v)
            except ValueError:
                self._template.rules.total_songs = None

    def _on_total_duration_change(self):
        if self._updating:
            return
        if self._var_total_duration_unlimited.get():
            self._template.rules.total_duration_sec = None
        else:
            try:
                minutes = float(self._var_total_duration.get())
                self._template.rules.total_duration_sec = max(1, int(minutes * 60))
            except ValueError:
                self._template.rules.total_duration_sec = None

    def _on_allow_repeats_change(self):
        if self._updating:
            return
        self._template.rules.allow_repeats = self._var_allow_repeats.get()

    def _on_order_mode_change(self, _event=None):
        if self._updating:
            return
        label = self._var_order_mode.get()
        if label in _ORDER_MODE_LABELS:
            self._template.rules.order_mode = _ORDER_MODE_KEYS[_ORDER_MODE_LABELS.index(label)]

    def _on_group_rules_change(self):
        if self._updating or self._selected_group is None:
            return
        g = self._selected_group

        try:
            g.songs_per_round = max(1, int(self._var_songs_per_round.get()))
        except ValueError:
            pass

        bmin_s = self._var_bpm_min.get().strip()
        bmax_s = self._var_bpm_max.get().strip()
        try:
            g.filters.bpm_min = float(bmin_s) if bmin_s else None
        except ValueError:
            g.filters.bpm_min = None
        try:
            g.filters.bpm_max = float(bmax_s) if bmax_s else None
        except ValueError:
            g.filters.bpm_max = None

        key = self._var_key.get()
        g.filters.key = None if key == "Any" else key

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _on_generate(self):
        if not self._template.groups:
            self._show_info("Generate", "Add at least one group with sources first.")
            return

        empty = [g.name for g in self._template.groups
                 if not any(sg.sources for sg in g.subgroups)]
        if empty:
            names = "\n".join(f"  • {n}" for n in empty)
            if not self._ask_yesno(
                "Groups Without Sources",
                f"These groups have no sources and will contribute no songs:\n{names}\n\nContinue anyway?",
            ):
                return

        self._generate_btn.configure(state="disabled")
        self._status_label.configure(text="Generating…")
        self.update_idletasks()

        def _run():
            try:
                songs = generate(self._template, metadata_extractor)
            except Exception as e:
                songs = []
                self.after(0, lambda err=e: self._show_error("Error", str(err)))
            self.after(0, lambda: self._on_generate_done(songs))

        threading.Thread(target=_run, daemon=True).start()

    def _on_generate_done(self, songs: list):
        self._generate_btn.configure(state="normal")
        if not songs:
            self._status_label.configure(text="No songs matched the configured rules.")
            return

        total_dur = 0.0
        for p in songs:
            try:
                total_dur += metadata_extractor.get_metadata(p).get("duration_s") or 0
            except Exception:
                pass
        h, rem = divmod(int(total_dur), 3600)
        m, s = divmod(rem, 60)
        dur_str = f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"
        summary = f"Generated {len(songs)} songs ({dur_str})"
        self._status_label.configure(text=summary)

        mode = self._ask_generate_destination(summary)
        if mode is None:
            return
        if callable(self.on_generate):
            self.on_generate(songs, mode)

    def _ask_generate_destination(self, summary: str):
        """Modal dialog; returns 'replace', 'append', 'browser', or None."""
        result = [None]
        p = self.palette
        bg = p.get("bg", "#1e1e1e")
        fg = p.get("fg", "#ffffff")
        fg_muted = p.get("fg_muted", "#888888")
        font = (p.get("ui_font", "Segoe UI"), 11)

        dlg = tk.Toplevel(self, bg=bg)
        dlg.title("Send Songs")
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()

        tk.Label(dlg, text=summary, bg=bg, fg=fg, font=font).pack(padx=24, pady=(18, 4))
        tk.Label(dlg, text="Where do you want to send them?",
                 bg=bg, fg=fg_muted,
                 font=(p.get("ui_font", "Segoe UI"), 10)).pack(padx=24, pady=(0, 14))

        btn_row = tk.Frame(dlg, bg=bg)
        btn_row.pack(padx=24, pady=(0, 20))

        def _pick(val):
            result[0] = val
            dlg.destroy()

        for text, val in [("Replace Playlist", "replace"), ("Append to Playlist", "append"),
                          ("Send to Browser", "browser"), ("Cancel", None)]:
            self._make_btn(btn_row, text, lambda v=val: _pick(v), width=148, side="left", padx=(0, 6))

        dlg.update_idletasks()
        apply_theme_titlebar(dlg, self.palette)
        x = self.winfo_rootx() + (self.winfo_width() - dlg.winfo_width()) // 2
        y = self.winfo_rooty() + (self.winfo_height() - dlg.winfo_height()) // 2
        dlg.geometry(f"+{max(0, x)}+{max(0, y)}")

        self.wait_window(dlg)
        return result[0]

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------

    def update_theme(self, palette=None):
        if palette is not None:
            self.palette = palette
        else:
            self.palette = self.theme_manager.palette
        apply_theme_titlebar(self, self.palette)
        self._restyle_tk_widgets()

    def _restyle_tk_widgets(self):
        p = self.palette
        bg = p.get("bg", "#1e1e1e")
        fg = p.get("fg", "#ffffff")
        fg_muted = p.get("fg_muted", "#888888")
        btn_bg = p.get("button_bg_color", p.get("accent", "#0078d4"))
        btn_fg = p.get("button_fg_color", "#ffffff")
        btn_hover = p.get("button_hover", p.get("accent_hover", "#106ebe"))

        self.configure(bg=bg)
        if hasattr(self, "_content"):
            self._content.configure(bg=bg)

        def _restyle(widget):
            if isinstance(widget, ctk.CTkButton):
                widget.configure(fg_color=btn_bg, text_color=btn_fg,
                                 hover_color=btn_hover, bg_color=bg)
                return
            if isinstance(widget, ctk.CTkBaseClass):
                return
            if isinstance(widget, tk.LabelFrame):
                widget.configure(bg=bg, fg=fg)
            elif isinstance(widget, tk.Frame):
                widget.configure(bg=bg)
            elif isinstance(widget, tk.Label):
                # Keep the muted colour on the "no group selected" hint label
                label_fg = fg_muted if widget is getattr(self, "_no_group_label", None) else fg
                widget.configure(bg=bg, fg=label_fg)
            for child in widget.winfo_children():
                _restyle(child)

        _restyle(self._content)

        # Re-apply tree row tag colours (foreground uses muted for sources)
        if hasattr(self, "tree"):
            font = p.get("ui_font", "Segoe UI")
            self.tree.tag_configure("group", font=(font, 11, "bold"))
            self.tree.tag_configure("subgroup", font=(font, 10))
            self.tree.tag_configure("source", font=(font, 9), foreground=fg_muted)
