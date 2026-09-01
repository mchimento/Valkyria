"""Tests for ui_qt/playlist_generator_window.py."""
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog, QMessageBox, QPushButton

from audio.playlist_generator import (
    GeneratorRules,
    GeneratorTemplate,
    Group,
    Subgroup,
    load_templates,
    save_templates,
)
from ui_qt.playlist_generator_window import PlaylistGeneratorWindowQt

PALETTE = {"bg": "#1e1e1e", "fg": "#ffffff"}


def _mock_destination_dialog(monkeypatch, mode):
    """_ask_generate_destination builds its own themed QDialog (see its
    docstring — a plain QMessageBox doesn't pick up this app's theme on the
    user's system). Simulates clicking the button matching `mode` by
    patching QDialog.exec to find and click it, rather than blocking on a
    real exec() with no one there to close it."""
    label_for_mode = {
        "replace": "Replace Playlist",
        "append": "Append to Playlist",
        "browser": "Send to Browser",
        None: "Cancel",
    }[mode]

    def fake_exec(dlg_self):
        for btn in dlg_self.findChildren(QPushButton):
            if btn.text() == label_for_mode:
                btn.click()
                return None
        return None

    monkeypatch.setattr(QDialog, "exec", fake_exec)


@pytest.fixture
def dialog(qtbot, tmp_path):
    templates_path = str(tmp_path / "generator_templates.json")
    win = PlaylistGeneratorWindowQt(None, templates_path, PALETTE)
    qtbot.addWidget(win)
    return win


# ---------- template persistence ----------

def test_save_as_creates_and_persists_template(dialog):
    dialog._template.groups.append(Group(name="G1"))
    with patch.object(QInputDialog, "getText", return_value=("My Template", True)):
        dialog._on_save_as_template()
    assert dialog.template_combo.currentText() == "My Template"
    reloaded = load_templates(dialog._templates_path)
    assert len(reloaded) == 1
    assert reloaded[0].name == "My Template"
    assert reloaded[0].groups[0].name == "G1"


def test_save_as_existing_name_prompts_overwrite_and_declines(dialog):
    dialog._templates.append(GeneratorTemplate(name="Existing"))
    dialog._refresh_template_dropdown()
    with patch.object(QInputDialog, "getText", return_value=("Existing", True)), \
         patch.object(QMessageBox, "question", return_value=QMessageBox.No) as mock_q:
        dialog._on_save_as_template()
    mock_q.assert_called_once()
    assert len(dialog._templates) == 1


def test_save_with_blank_name_redirects_to_save_as(dialog):
    with patch.object(dialog, "_on_save_as_template") as mock_save_as:
        dialog._on_save_template()
    mock_save_as.assert_called_once()


def test_save_overwrites_existing_selected_template(dialog):
    dialog._templates.append(GeneratorTemplate(name="T1"))
    dialog._refresh_template_dropdown()
    dialog.template_combo.setCurrentText("T1")
    dialog._template.groups.append(Group(name="NewGroup"))
    dialog._on_save_template()
    assert len(dialog._templates) == 1
    assert dialog._templates[0].groups[0].name == "NewGroup"


def test_delete_template_removes_and_resets_when_selected(dialog):
    dialog._templates.append(GeneratorTemplate(name="ToDelete"))
    dialog._refresh_template_dropdown()
    dialog.template_combo.setCurrentText("ToDelete")
    with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
        dialog._on_delete_template()
    assert dialog._templates == []
    assert dialog._template.name == ""
    assert dialog.template_combo.currentText() == ""


def test_delete_template_declined_keeps_template(dialog):
    dialog._templates.append(GeneratorTemplate(name="Keep"))
    dialog._refresh_template_dropdown()
    dialog.template_combo.setCurrentText("Keep")
    with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
        dialog._on_delete_template()
    assert len(dialog._templates) == 1


def test_selecting_template_loads_tree_and_rules_as_a_deep_copy(dialog):
    tmpl = GeneratorTemplate(name="T", groups=[Group(name="G1")], rules=GeneratorRules(allow_repeats=True))
    dialog._templates.append(tmpl)
    dialog._refresh_template_dropdown()
    dialog.template_combo.setCurrentText("T")
    assert dialog._template.groups[0].name == "G1"
    assert dialog.allow_repeats_cb.isChecked() is True
    dialog._template.groups[0].name = "Changed"
    assert tmpl.groups[0].name == "G1"


def test_templates_load_from_disk_on_construction(qtbot, tmp_path):
    templates_path = str(tmp_path / "templates.json")
    save_templates(templates_path, [GeneratorTemplate(name="Preset", groups=[Group(name="G")])])
    win = PlaylistGeneratorWindowQt(None, templates_path, PALETTE)
    qtbot.addWidget(win)
    assert win.template_combo.findText("Preset") >= 0


# ---------- tree actions ----------

def test_add_group_appends_and_renders(dialog):
    with patch.object(QInputDialog, "getText", return_value=("MyGroup", True)):
        dialog._on_add_group()
    assert len(dialog._template.groups) == 1
    assert dialog._template.groups[0].name == "MyGroup"
    assert dialog._tree.topLevelItemCount() == 1


def test_add_group_cancelled_does_nothing(dialog):
    with patch.object(QInputDialog, "getText", return_value=("", False)):
        dialog._on_add_group()
    assert dialog._template.groups == []


def test_add_subgroup_without_selection_shows_info(dialog):
    with patch.object(QMessageBox, "information") as mock_info:
        dialog._on_add_subgroup()
    mock_info.assert_called_once()


def test_add_subgroup_with_group_selected(dialog):
    dialog._template.groups.append(Group(name="G1"))
    dialog._render_tree()
    dialog._tree.setCurrentItem(dialog._tree.topLevelItem(0))
    with patch.object(QInputDialog, "getText", return_value=("SG1", True)):
        dialog._on_add_subgroup()
    assert dialog._template.groups[0].subgroups[0].name == "SG1"


def test_remove_group(dialog):
    dialog._template.groups.append(Group(name="G1"))
    dialog._render_tree()
    dialog._tree.setCurrentItem(dialog._tree.topLevelItem(0))
    dialog._on_remove()
    assert dialog._template.groups == []


def test_move_group_up(dialog):
    dialog._template.groups.append(Group(name="A"))
    dialog._template.groups.append(Group(name="B"))
    dialog._render_tree()
    dialog._tree.setCurrentItem(dialog._tree.topLevelItem(1))
    dialog._on_move_up()
    assert [g.name for g in dialog._template.groups] == ["B", "A"]


def test_move_group_down(dialog):
    dialog._template.groups.append(Group(name="A"))
    dialog._template.groups.append(Group(name="B"))
    dialog._render_tree()
    dialog._tree.setCurrentItem(dialog._tree.topLevelItem(0))
    dialog._on_move_down()
    assert [g.name for g in dialog._template.groups] == ["B", "A"]


def test_rename_group(dialog):
    dialog._template.groups.append(Group(name="Old"))
    dialog._render_tree()
    dialog._tree.setCurrentItem(dialog._tree.topLevelItem(0))
    with patch.object(QInputDialog, "getText", return_value=("New", True)):
        dialog._on_rename()
    assert dialog._template.groups[0].name == "New"


# ---------- load-target resolution (Load Files/Folder/M3U) ----------

def test_resolve_load_target_no_selection_creates_group_and_subgroup(dialog):
    sg = dialog._resolve_load_target()
    assert len(dialog._template.groups) == 1
    assert dialog._template.groups[0].name == "Group 1"
    assert dialog._template.groups[0].subgroups[0] is sg
    assert sg.name == "Default"


def test_resolve_load_target_empty_group_selected_creates_default_subgroup(dialog):
    dialog._template.groups.append(Group(name="G1"))
    dialog._render_tree()
    dialog._tree.setCurrentItem(dialog._tree.topLevelItem(0))
    sg = dialog._resolve_load_target()
    assert sg.name == "Default"
    assert dialog._template.groups[0].subgroups == [sg]


def test_resolve_load_target_group_with_subgroups_creates_numbered_subgroup(dialog):
    group = Group(name="G1")
    group.subgroups.append(Subgroup(name="Default"))
    dialog._template.groups.append(group)
    dialog._render_tree()
    dialog._tree.setCurrentItem(dialog._tree.topLevelItem(0))
    sg = dialog._resolve_load_target()
    assert sg.name == "Subgroup 1"
    assert group.subgroups[-1] is sg


def test_resolve_load_target_subgroup_selected_extends_it(dialog):
    group = Group(name="G1")
    existing_sg = Subgroup(name="Existing")
    group.subgroups.append(existing_sg)
    dialog._template.groups.append(group)
    dialog._render_tree()
    dialog._tree.setCurrentItem(dialog._tree.topLevelItem(0).child(0))
    sg = dialog._resolve_load_target()
    assert sg is existing_sg


def test_load_files_adds_file_sources(dialog):
    with patch.object(QFileDialog, "getOpenFileNames", return_value=(["/music/a.mp3"], "")):
        dialog._on_load_files()
    src = dialog._template.groups[0].subgroups[0].sources[0]
    assert src.type == "file"
    assert src.path == "/music/a.mp3"


def test_load_folder_adds_directory_source(dialog):
    with patch.object(QFileDialog, "getExistingDirectory", return_value="/music/folder"):
        dialog._on_load_folder()
    src = dialog._template.groups[0].subgroups[0].sources[0]
    assert src.type == "directory"
    assert src.path == "/music/folder"


def test_load_m3u_adds_playlist_source(dialog):
    with patch.object(QFileDialog, "getOpenFileNames", return_value=(["/music/list.m3u"], "")):
        dialog._on_load_m3u()
    src = dialog._template.groups[0].subgroups[0].sources[0]
    assert src.type == "playlist"
    assert src.path == "/music/list.m3u"


def test_load_files_cancelled_adds_nothing(dialog):
    with patch.object(QFileDialog, "getOpenFileNames", return_value=([], "")):
        dialog._on_load_files()
    assert dialog._template.groups == []


# ---------- global rules ----------

def test_total_songs_unlimited_toggle_and_entry(dialog):
    dialog.total_songs_unlimited.setChecked(False)
    dialog.total_songs_entry.setText("42")
    assert dialog._template.rules.total_songs == 42
    dialog.total_songs_unlimited.setChecked(True)
    assert dialog._template.rules.total_songs is None


def test_total_duration_minutes_converted_to_seconds(dialog):
    dialog.total_duration_unlimited.setChecked(False)
    dialog.total_duration_entry.setText("5")
    assert dialog._template.rules.total_duration_sec == 300


def test_allow_repeats_and_skip_short_checkboxes(dialog):
    dialog.allow_repeats_cb.setChecked(True)
    assert dialog._template.rules.allow_repeats is True
    dialog.skip_short_cb.setChecked(True)
    assert dialog._template.rules.skip_short_subgroups is True


def test_order_mode_combo_writes_key(dialog):
    idx = dialog.order_mode_combo.findData("fully_random")
    dialog.order_mode_combo.setCurrentIndex(idx)
    assert dialog._template.rules.order_mode == "fully_random"


# ---------- group rules ----------

def test_group_rules_panel_hidden_without_selection(dialog):
    assert dialog.group_rules_box.isHidden()


def test_group_rules_panel_visible_with_group_selected(dialog):
    dialog._template.groups.append(Group(name="G1"))
    dialog._render_tree()
    dialog._tree.setCurrentItem(dialog._tree.topLevelItem(0))
    assert not dialog.group_rules_box.isHidden()
    assert "G1" in dialog.group_rules_box.title()


def test_group_rules_fields_write_into_selected_group(dialog):
    group = Group(name="G1")
    dialog._template.groups.append(group)
    dialog._render_tree()
    dialog._tree.setCurrentItem(dialog._tree.topLevelItem(0))
    dialog.songs_per_round_spin.setValue(4)
    dialog.bpm_min_entry.setText("120")
    dialog.bpm_max_entry.setText("130")
    dialog.key_combo.setCurrentText("Am")
    assert group.songs_per_round == 4
    assert group.filters.bpm_min == 120.0
    assert group.filters.bpm_max == 130.0
    assert group.filters.key == "Am"


# ---------- generation ----------

def test_generate_with_no_groups_blocked(dialog):
    with patch.object(QMessageBox, "information") as mock_info:
        dialog._on_generate()
    mock_info.assert_called_once()


def test_generate_with_empty_group_prompts_confirm_and_declines(dialog):
    dialog._template.groups.append(Group(name="Empty"))
    with patch.object(QMessageBox, "question", return_value=QMessageBox.No) as mock_q:
        dialog._on_generate()
    mock_q.assert_called_once()
    assert dialog.generate_btn.isEnabled()


def test_generation_done_empty_shows_no_match_status(dialog):
    dialog._on_generation_done([])
    assert dialog.status_label.text() == "No songs matched the configured rules."
    assert dialog.generate_btn.isEnabled()


def test_generation_done_builds_summary_and_emits_replace(dialog, qtbot, monkeypatch):
    monkeypatch.setattr(
        "ui_qt.playlist_generator_window.metadata_extractor.get_metadata",
        lambda p: {"duration_s": 125.0},
    )
    _mock_destination_dialog(monkeypatch, "replace")
    with qtbot.waitSignal(dialog.playlist_generated, timeout=1000) as blocker:
        dialog._on_generation_done(["/a.mp3", "/b.mp3"])
    assert blocker.args == [["/a.mp3", "/b.mp3"], "replace"]
    assert "Generated 2 songs" in dialog.status_label.text()
    assert dialog.generate_btn.isEnabled()


def test_generation_done_cancel_does_not_emit(dialog, monkeypatch):
    monkeypatch.setattr(
        "ui_qt.playlist_generator_window.metadata_extractor.get_metadata",
        lambda p: {"duration_s": 60.0},
    )
    _mock_destination_dialog(monkeypatch, None)
    received = []
    dialog.playlist_generated.connect(lambda songs, mode: received.append((songs, mode)))
    dialog._on_generation_done(["/a.mp3"])
    assert received == []
