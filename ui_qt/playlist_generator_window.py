"""Build named, rule-based playlist templates (groups/subgroups/sources
with BPM/key filters and an ordering strategy) and generate a playlist
from them.
"""

import copy
import logging
import threading
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from audio.metadata import metadata_extractor
from audio.playlist_generator import (
    MUSICAL_KEYS,
    ORDER_MODES,
    GeneratorRules,
    GeneratorTemplate,
    Group,
    Source,
    Subgroup,
    generate,
    load_templates,
    save_templates,
)
from ui_qt.preferences_window import _DialogTitleBar

logger = logging.getLogger(__name__)


class PlaylistGeneratorWindowQt(QDialog):
    # (songs, mode) — mode is "replace" | "append" | "browser"
    playlist_generated = Signal(list, str)
    _generation_done = Signal(list)

    def __init__(self, parent, templates_path: str, palette: dict):
        super().__init__(parent)
        self._templates_path = templates_path
        self.palette = palette

        self._templates: list = []
        self._template = GeneratorTemplate(name="", groups=[], rules=GeneratorRules())
        self._selected_template_name = ""
        self._selected_group: Optional[Group] = None
        self._updating = False
        self._sized_once = False

        self.setObjectName("MainWindow")
        self.setWindowTitle("Playlist Generator")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setModal(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        outer.addWidget(_DialogTitleBar(self, "Playlist Generator"))

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(12, 12, 12, 12)
        body_layout.setSpacing(10)
        outer.addWidget(body, 1)

        body_layout.addLayout(self._build_template_bar())

        main_area = QHBoxLayout()
        main_area.setSpacing(12)
        main_area.addWidget(self._build_left_panel())
        main_area.addWidget(self._build_right_panel(), 1)
        body_layout.addLayout(main_area)

        body_layout.addLayout(self._build_bottom_bar())

        self._generation_done.connect(self._on_generation_done, Qt.QueuedConnection)

        self._templates = load_templates(self._templates_path)
        self._refresh_template_dropdown()
        self._render_tree()
        self._load_global_rules_to_ui()
        self._set_group_rules_visible(False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._sized_once:
            self._sized_once = True
            self.adjustSize()
            self.resize(960, self.height())
        self._center_on_parent()

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        parent_geo = parent.frameGeometry()
        x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
        y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
        self.move(x, y)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_template_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel("Template:"))
        self.template_combo = QComboBox()
        self.template_combo.setMinimumWidth(220)
        self.template_combo.currentTextChanged.connect(self._on_template_selected)
        row.addWidget(self.template_combo)

        for text, handler in [("Save", self._on_save_template),
                               ("Save As", self._on_save_as_template),
                               ("Delete", self._on_delete_template)]:
            btn = QPushButton(text)
            btn.setObjectName("CompactButton")
            btn.clicked.connect(handler)
            row.addWidget(btn)
        row.addStretch(1)
        return row

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(390)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)

        canvas_group = QGroupBox("Playlist Canvas")
        canvas_layout = QVBoxLayout(canvas_group)
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setMinimumHeight(320)
        self._tree.itemSelectionChanged.connect(self._on_tree_selection_changed)
        self._tree.itemDoubleClicked.connect(self._on_tree_double_clicked)
        canvas_layout.addWidget(self._tree)
        layout.addWidget(canvas_group)

        rows = [
            [("Add Group", self._on_add_group), ("Add Subgroup", self._on_add_subgroup), ("Remove", self._on_remove)],
            [("Load Files", self._on_load_files), ("Load M3U", self._on_load_m3u), ("Load Folder", self._on_load_folder)],
            [("Move Up", self._on_move_up), ("Move Down", self._on_move_down), ("Rename", self._on_rename)],
        ]
        grid = QGridLayout()
        grid.setSpacing(4)
        for r, row_items in enumerate(rows):
            for c, (text, handler) in enumerate(row_items):
                btn = QPushButton(text)
                btn.setObjectName("CompactButton")
                btn.clicked.connect(handler)
                grid.addWidget(btn, r, c)
        layout.addLayout(grid)
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_global_rules_group())
        layout.addWidget(self._build_group_rules_group())
        layout.addStretch(1)
        return panel

    def _build_global_rules_group(self) -> QGroupBox:
        box = QGroupBox("Global Rules")
        layout = QVBoxLayout(box)

        songs_row = QHBoxLayout()
        songs_row.addWidget(QLabel("Total songs:"))
        self.total_songs_entry = QLineEdit()
        self.total_songs_entry.setFixedWidth(70)
        self.total_songs_entry.setEnabled(False)
        self.total_songs_entry.textChanged.connect(self._on_total_songs_change)
        songs_row.addWidget(self.total_songs_entry)
        self.total_songs_unlimited = QCheckBox("Unlimited")
        self.total_songs_unlimited.setChecked(True)
        self.total_songs_unlimited.toggled.connect(self._on_total_songs_unlimited_toggle)
        songs_row.addWidget(self.total_songs_unlimited)
        songs_row.addStretch(1)
        layout.addLayout(songs_row)

        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("Total duration (min):"))
        self.total_duration_entry = QLineEdit()
        self.total_duration_entry.setFixedWidth(70)
        self.total_duration_entry.setEnabled(False)
        self.total_duration_entry.textChanged.connect(self._on_total_duration_change)
        duration_row.addWidget(self.total_duration_entry)
        self.total_duration_unlimited = QCheckBox("Unlimited")
        self.total_duration_unlimited.setChecked(True)
        self.total_duration_unlimited.toggled.connect(self._on_total_duration_unlimited_toggle)
        duration_row.addWidget(self.total_duration_unlimited)
        duration_row.addStretch(1)
        layout.addLayout(duration_row)

        rep_row = QHBoxLayout()
        self.allow_repeats_cb = QCheckBox("Allow repeats")
        self.allow_repeats_cb.toggled.connect(self._on_allow_repeats_change)
        rep_row.addWidget(self.allow_repeats_cb)
        self.skip_short_cb = QCheckBox("Skip subgroups with insufficient songs")
        self.skip_short_cb.toggled.connect(self._on_skip_short_change)
        rep_row.addWidget(self.skip_short_cb)
        rep_row.addStretch(1)
        layout.addLayout(rep_row)

        order_row = QHBoxLayout()
        order_row.addWidget(QLabel("Order mode:"))
        self.order_mode_combo = QComboBox()
        for key, label in ORDER_MODES.items():
            self.order_mode_combo.addItem(label, key)
        self.order_mode_combo.currentIndexChanged.connect(self._on_order_mode_change)
        order_row.addWidget(self.order_mode_combo, 1)
        layout.addLayout(order_row)

        return box

    def _build_group_rules_group(self) -> QGroupBox:
        self.group_rules_box = QGroupBox("Group Rules")
        layout = QVBoxLayout(self.group_rules_box)

        spr_row = QHBoxLayout()
        spr_row.addWidget(QLabel("Songs per round:"))
        self.songs_per_round_spin = QSpinBox()
        self.songs_per_round_spin.setRange(1, 999)
        self.songs_per_round_spin.valueChanged.connect(self._on_group_rules_change)
        spr_row.addWidget(self.songs_per_round_spin)
        spr_row.addStretch(1)
        layout.addLayout(spr_row)

        bpm_row = QHBoxLayout()
        bpm_row.addWidget(QLabel("BPM range:"))
        self.bpm_min_entry = QLineEdit()
        self.bpm_min_entry.setFixedWidth(60)
        self.bpm_min_entry.textChanged.connect(self._on_group_rules_change)
        bpm_row.addWidget(self.bpm_min_entry)
        bpm_row.addWidget(QLabel("–"))
        self.bpm_max_entry = QLineEdit()
        self.bpm_max_entry.setFixedWidth(60)
        self.bpm_max_entry.textChanged.connect(self._on_group_rules_change)
        bpm_row.addWidget(self.bpm_max_entry)
        bpm_row.addWidget(QLabel("(leave blank for any)"))
        bpm_row.addStretch(1)
        layout.addLayout(bpm_row)

        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("Key:"))
        self.key_combo = QComboBox()
        self.key_combo.addItems(MUSICAL_KEYS)
        self.key_combo.currentTextChanged.connect(self._on_group_rules_change)
        key_row.addWidget(self.key_combo)
        key_row.addStretch(1)
        layout.addLayout(key_row)

        return self.group_rules_box

    def _build_bottom_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.status_label = QLabel("")
        row.addWidget(self.status_label)
        row.addStretch(1)
        self.generate_btn = QPushButton("Generate Playlist")
        self.generate_btn.setObjectName("DialogButton")
        self.generate_btn.clicked.connect(self._on_generate)
        row.addWidget(self.generate_btn)
        return row

    def _set_group_rules_visible(self, visible: bool) -> None:
        self.group_rules_box.setVisible(visible)

    # ------------------------------------------------------------------
    # Template management
    # ------------------------------------------------------------------

    def _refresh_template_dropdown(self) -> None:
        self._updating = True
        self.template_combo.clear()
        self.template_combo.addItem("")
        self.template_combo.addItems([t.name for t in self._templates])
        idx = self.template_combo.findText(self._selected_template_name)
        self.template_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._updating = False

    def _on_template_selected(self, name: str) -> None:
        if self._updating or not name:
            return
        tmpl = next((t for t in self._templates if t.name == name), None)
        if tmpl is None:
            return
        self._template = copy.deepcopy(tmpl)
        self._selected_template_name = name
        self._selected_group = None
        self._render_tree()
        self._load_global_rules_to_ui()
        self._set_group_rules_visible(False)

    def _on_save_template(self) -> None:
        name = self.template_combo.currentText().strip()
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

    def _on_save_as_template(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Template", "Template name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        if any(t.name == name for t in self._templates):
            reply = QMessageBox.question(
                self, "Overwrite", f'Template "{name}" already exists. Overwrite?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            self._templates = [t for t in self._templates if t.name != name]
        self._template.name = name
        self._selected_template_name = name
        self._templates.append(copy.deepcopy(self._template))
        save_templates(self._templates_path, self._templates)
        self._refresh_template_dropdown()

    def _on_delete_template(self) -> None:
        name = self.template_combo.currentText()
        if not name:
            return
        reply = QMessageBox.question(
            self, "Delete Template", f'Delete template "{name}"?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self._templates = [t for t in self._templates if t.name != name]
        save_templates(self._templates_path, self._templates)
        if self._selected_template_name == name:
            self._selected_template_name = ""
            self._template = GeneratorTemplate(name="", groups=[], rules=GeneratorRules())
            self._selected_group = None
            self._render_tree()
            self._load_global_rules_to_ui()
            self._set_group_rules_visible(False)
        self._refresh_template_dropdown()

    # ------------------------------------------------------------------
    # Tree rendering
    # ------------------------------------------------------------------

    def _render_tree(self) -> None:
        sel_obj = self._get_selected_object()
        self._tree.clear()

        for group in self._template.groups:
            g_item = QTreeWidgetItem([group.name])
            g_item.setData(0, Qt.UserRole, ("group", group))
            font = g_item.font(0)
            font.setBold(True)
            g_item.setFont(0, font)
            self._tree.addTopLevelItem(g_item)
            g_item.setExpanded(True)

            for subgroup in group.subgroups:
                sg_item = QTreeWidgetItem([subgroup.name])
                sg_item.setData(0, Qt.UserRole, ("subgroup", group, subgroup))
                g_item.addChild(sg_item)
                sg_item.setExpanded(True)

                for source in subgroup.sources:
                    icon = {"directory": "📁", "playlist": "📋", "file": "🎵"}.get(source.type, "")
                    label = f"{icon} {self._short_path(source.path)}" if icon else self._short_path(source.path)
                    s_item = QTreeWidgetItem([label])
                    s_item.setData(0, Qt.UserRole, ("source", group, subgroup, source))
                    sg_item.addChild(s_item)

        if sel_obj is not None:
            self._reselect_item(sel_obj)

    def _short_path(self, path: str, max_len: int = 48) -> str:
        if len(path) <= max_len:
            return path
        parts = path.replace("\\", "/").split("/")
        if len(parts) > 3:
            return "…/" + "/".join(parts[-2:])
        return "…" + path[-(max_len - 1):]

    def _get_selected_object(self):
        item = self._tree.currentItem()
        if item is None:
            return None
        data = item.data(0, Qt.UserRole)
        if data is None:
            return None
        if data[0] == "group":
            return data[1]
        if data[0] == "subgroup":
            return data[2]
        return data[3]

    def _reselect_item(self, obj) -> None:
        def _target_of(item):
            data = item.data(0, Qt.UserRole)
            if data is None:
                return None
            if data[0] == "group":
                return data[1]
            if data[0] == "subgroup":
                return data[2]
            return data[3]

        def _walk(item):
            if _target_of(item) is obj:
                return item
            for i in range(item.childCount()):
                found = _walk(item.child(i))
                if found is not None:
                    return found
            return None

        for i in range(self._tree.topLevelItemCount()):
            found = _walk(self._tree.topLevelItem(i))
            if found is not None:
                self._tree.setCurrentItem(found)
                return

    # ------------------------------------------------------------------
    # Tree selection / interaction
    # ------------------------------------------------------------------

    def _on_tree_selection_changed(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            self._selected_group = None
            self._set_group_rules_visible(False)
            return
        data = item.data(0, Qt.UserRole)
        if data is None:
            return
        group = data[1]
        self._selected_group = group
        self._load_group_rules_to_ui(group)
        self._set_group_rules_visible(True)

    def _on_tree_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        data = item.data(0, Qt.UserRole)
        if data and data[0] in ("group", "subgroup"):
            self._do_rename(data)

    def _do_rename(self, data) -> None:
        kind = data[0]
        obj = data[1] if kind == "group" else data[2]
        current = obj.name
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=current)
        if ok and new_name.strip() and new_name.strip() != current:
            obj.name = new_name.strip()
            self._render_tree()

    # ------------------------------------------------------------------
    # Tree actions
    # ------------------------------------------------------------------

    def _get_selected_group(self) -> Optional[Group]:
        item = self._tree.currentItem()
        if item is None:
            return None
        data = item.data(0, Qt.UserRole)
        if data is None:
            return None
        return data[1]

    def _list_and_obj_for(self, data):
        if data is None:
            return None, None
        kind = data[0]
        if kind == "group":
            return self._template.groups, data[1]
        if kind == "subgroup":
            return data[1].subgroups, data[2]
        if kind == "source":
            return data[2].sources, data[3]
        return None, None

    def _on_add_group(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Group", "Group name:")
        if not ok or not name.strip():
            return
        self._template.groups.append(Group(name=name.strip()))
        self._render_tree()

    def _on_add_subgroup(self) -> None:
        group = self._get_selected_group()
        if group is None:
            QMessageBox.information(self, "Add Subgroup", "Select a group first")
            return
        name, ok = QInputDialog.getText(self, "Add Subgroup", "Subgroup name:")
        if not ok or not name.strip():
            return
        group.subgroups.append(Subgroup(name=name.strip()))
        self._render_tree()

    def _resolve_load_target(self) -> Subgroup:
        """Where newly loaded sources land: nothing selected -> new
        auto-numbered Group+Default subgroup; group with no subgroups ->
        auto-created Default subgroup; group with subgroups -> new
        auto-numbered subgroup; subgroup/source selected -> that subgroup."""
        item = self._tree.currentItem()
        data = item.data(0, Qt.UserRole) if item is not None else None

        if data is None:
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

        grp = data[1]
        if not grp.subgroups:
            sg = Subgroup(name="Default")
            grp.subgroups.append(sg)
            return sg

        n = 1
        existing = {sg.name for sg in grp.subgroups}
        while f"Subgroup {n}" in existing:
            n += 1
        sg = Subgroup(name=f"Subgroup {n}")
        grp.subgroups.append(sg)
        return sg

    def _on_load_files(self) -> None:
        paths, _filter = QFileDialog.getOpenFileNames(
            self, "Select Audio File(s)", "", "Audio files (*.mp3 *.wav *.flac *.ogg *.m4a);;All files (*.*)"
        )
        if not paths:
            return
        subgroup = self._resolve_load_target()
        for p in paths:
            subgroup.sources.append(Source(type="file", path=str(p)))
        self._render_tree()
        self._reselect_item(subgroup)

    def _on_load_m3u(self) -> None:
        paths, _filter = QFileDialog.getOpenFileNames(
            self, "Select M3U Playlist(s)", "", "M3U Playlists (*.m3u *.m3u8);;All files (*.*)"
        )
        if not paths:
            return
        subgroup = self._resolve_load_target()
        for p in paths:
            subgroup.sources.append(Source(type="playlist", path=str(p)))
        self._render_tree()
        self._reselect_item(subgroup)

    def _on_load_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if not path:
            return
        subgroup = self._resolve_load_target()
        subgroup.sources.append(Source(type="directory", path=str(path)))
        self._render_tree()
        self._reselect_item(subgroup)

    def _on_move_up(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        lst, obj = self._list_and_obj_for(item.data(0, Qt.UserRole))
        if lst is None:
            return
        idx = lst.index(obj)
        if idx > 0:
            lst[idx], lst[idx - 1] = lst[idx - 1], lst[idx]
            self._render_tree()
            self._reselect_item(obj)

    def _on_move_down(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        lst, obj = self._list_and_obj_for(item.data(0, Qt.UserRole))
        if lst is None:
            return
        idx = lst.index(obj)
        if idx < len(lst) - 1:
            lst[idx], lst[idx + 1] = lst[idx + 1], lst[idx]
            self._render_tree()
            self._reselect_item(obj)

    def _on_rename(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        data = item.data(0, Qt.UserRole)
        if data:
            self._do_rename(data)

    def _on_remove(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        lst, obj = self._list_and_obj_for(item.data(0, Qt.UserRole))
        if lst is not None and obj in lst:
            lst.remove(obj)
        self._selected_group = None
        self._render_tree()
        self._set_group_rules_visible(False)

    # ------------------------------------------------------------------
    # Rules UI <-> template sync
    # ------------------------------------------------------------------

    def _load_global_rules_to_ui(self) -> None:
        self._updating = True
        r = self._template.rules
        if r.total_songs is None:
            self.total_songs_unlimited.setChecked(True)
            self.total_songs_entry.setText("")
            self.total_songs_entry.setEnabled(False)
        else:
            self.total_songs_unlimited.setChecked(False)
            self.total_songs_entry.setText(str(r.total_songs))
            self.total_songs_entry.setEnabled(True)

        if r.total_duration_sec is None:
            self.total_duration_unlimited.setChecked(True)
            self.total_duration_entry.setText("")
            self.total_duration_entry.setEnabled(False)
        else:
            self.total_duration_unlimited.setChecked(False)
            self.total_duration_entry.setText(str(r.total_duration_sec // 60))
            self.total_duration_entry.setEnabled(True)

        self.allow_repeats_cb.setChecked(r.allow_repeats)
        self.skip_short_cb.setChecked(r.skip_short_subgroups)
        idx = self.order_mode_combo.findData(r.order_mode)
        self.order_mode_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._updating = False

    def _load_group_rules_to_ui(self, group: Group) -> None:
        self._updating = True
        self.group_rules_box.setTitle(f"Group Rules — {group.name}")
        self.songs_per_round_spin.setValue(group.songs_per_round)
        self.bpm_min_entry.setText("" if group.filters.bpm_min is None else str(group.filters.bpm_min))
        self.bpm_max_entry.setText("" if group.filters.bpm_max is None else str(group.filters.bpm_max))
        idx = self.key_combo.findText(group.filters.key or "Any")
        self.key_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._updating = False

    def _on_total_songs_unlimited_toggle(self, checked: bool) -> None:
        self.total_songs_entry.setEnabled(not checked)
        self._on_total_songs_change()

    def _on_total_songs_change(self) -> None:
        if self._updating:
            return
        if self.total_songs_unlimited.isChecked():
            self._template.rules.total_songs = None
        else:
            try:
                self._template.rules.total_songs = max(1, int(self.total_songs_entry.text()))
            except ValueError:
                self._template.rules.total_songs = None

    def _on_total_duration_unlimited_toggle(self, checked: bool) -> None:
        self.total_duration_entry.setEnabled(not checked)
        self._on_total_duration_change()

    def _on_total_duration_change(self) -> None:
        if self._updating:
            return
        if self.total_duration_unlimited.isChecked():
            self._template.rules.total_duration_sec = None
        else:
            try:
                minutes = float(self.total_duration_entry.text())
                self._template.rules.total_duration_sec = max(1, int(minutes * 60))
            except ValueError:
                self._template.rules.total_duration_sec = None

    def _on_allow_repeats_change(self, checked: bool) -> None:
        if self._updating:
            return
        self._template.rules.allow_repeats = checked

    def _on_skip_short_change(self, checked: bool) -> None:
        if self._updating:
            return
        self._template.rules.skip_short_subgroups = checked

    def _on_order_mode_change(self, index: int) -> None:
        if self._updating:
            return
        key = self.order_mode_combo.itemData(index)
        if key:
            self._template.rules.order_mode = key

    def _on_group_rules_change(self) -> None:
        if self._updating or self._selected_group is None:
            return
        g = self._selected_group
        g.songs_per_round = max(1, self.songs_per_round_spin.value())

        bmin_s = self.bpm_min_entry.text().strip()
        bmax_s = self.bpm_max_entry.text().strip()
        try:
            g.filters.bpm_min = float(bmin_s) if bmin_s else None
        except ValueError:
            g.filters.bpm_min = None
        try:
            g.filters.bpm_max = float(bmax_s) if bmax_s else None
        except ValueError:
            g.filters.bpm_max = None

        key = self.key_combo.currentText()
        g.filters.key = None if key == "Any" else key

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _on_generate(self) -> None:
        if not self._template.groups:
            QMessageBox.information(self, "Generate", "Add at least one group with sources first")
            return

        empty = [g.name for g in self._template.groups if not any(sg.sources for sg in g.subgroups)]
        if empty:
            names = "\n".join(f"  • {n}" for n in empty)
            reply = QMessageBox.question(
                self, "Groups Without Sources",
                f"These groups have no sources and will contribute no songs:\n{names}\n\nContinue anyway?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self.generate_btn.setEnabled(False)
        self.status_label.setText("Generating…")

        def _run():
            try:
                songs = generate(self._template, metadata_extractor)
            except Exception:
                logger.exception("Playlist generation failed")
                songs = []
            self._generation_done.emit(songs)

        threading.Thread(target=_run, daemon=True).start()

    def _on_generation_done(self, songs: list) -> None:
        self.generate_btn.setEnabled(True)
        if not songs:
            self.status_label.setText("No songs matched the configured rules.")
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
        self.status_label.setText(summary)

        mode = self._ask_generate_destination(summary)
        if mode is None:
            return
        self.playlist_generated.emit(songs, mode)

    def _ask_generate_destination(self, summary: str) -> Optional[str]:
        # A plain QMessageBox renders with no app theming at all (native OS
        # chrome, white background, default buttons) — built the same way
        # every other dialog in this app is: frameless + _DialogTitleBar +
        # CompactButton-styled buttons.
        dlg = QDialog(self)
        dlg.setObjectName("MainWindow")
        dlg.setWindowFlag(Qt.FramelessWindowHint)
        dlg.setModal(True)

        outer = QVBoxLayout(dlg)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        outer.addWidget(_DialogTitleBar(dlg, "Send Songs"))

        body = QWidget(dlg)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 16, 20, 16)
        body_layout.setSpacing(10)
        outer.addWidget(body, 1)

        body_layout.addWidget(QLabel(summary))
        body_layout.addWidget(QLabel("Where do you want to send them?"))

        button_row = QHBoxLayout()
        result = {"mode": None}

        def _pick(mode):
            result["mode"] = mode
            dlg.accept()

        for text, mode in [("Replace Playlist", "replace"), ("Append to Playlist", "append"),
                            ("Send to Browser", "browser"), ("Cancel", None)]:
            btn = QPushButton(text)
            btn.setObjectName("CompactButton")
            btn.clicked.connect(lambda checked=False, m=mode: _pick(m))
            button_row.addWidget(btn)
        body_layout.addLayout(button_row)

        dlg.adjustSize()
        parent_geo = self.frameGeometry()
        dlg.move(
            parent_geo.x() + (parent_geo.width() - dlg.width()) // 2,
            parent_geo.y() + (parent_geo.height() - dlg.height()) // 2,
        )
        dlg.exec()
        return result["mode"]
