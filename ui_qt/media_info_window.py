"""File info, codec details, and editable metadata (including BPM/Key
calculation) for a single track."""

import logging
import os
import re
from typing import Callable, Optional

import shiboken6
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from audio.bpm import analysis_manager
from audio.metadata import get_file_info, key_to_camelot, metadata_extractor, save_metadata
from ui_qt.preferences_window import _DialogTitleBar

logger = logging.getLogger(__name__)

_CAMELOT_ENTRY_RE = re.compile(r"\s*(\d{1,2})\s*([ABab])\s*")

_METADATA_FIELDS = [
    ("Title", "title"),
    ("Artist", "artist"),
    ("Album", "album"),
    ("Year", "date"),
    ("Genre", "genre"),
    ("Track Number", "tracknumber"),
]


class MediaInfoWindowQt(QDialog):
    _scheduled = Signal(object, tuple)
    _bpm_disk_changed = Signal(str)
    _key_disk_changed = Signal(str)

    def __init__(self, parent, file_path: str, palette: dict,
                 metadata_saved_callback: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.file_path = file_path
        self.palette = palette
        self.metadata_saved_callback = metadata_saved_callback
        self._bpm_raw_value: Optional[str] = None
        self._key_raw_value: Optional[str] = None

        self.setObjectName("MainWindow")
        self.setWindowTitle("Track Information")
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setModal(False)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(1, 1, 1, 1)
        outer.setSpacing(0)
        outer.addWidget(_DialogTitleBar(self, "Track Information"))

        body = QWidget(self)
        body_layout = QVBoxLayout(body)
        outer.addWidget(body, 1)

        self.file_info = get_file_info(file_path)

        self.tabs = QTabWidget(body)
        self.general_text = QTextEdit(readOnly=True)
        self.codec_text = QTextEdit(readOnly=True)
        self.tabs.addTab(self.general_text, "General")
        self.tabs.addTab(self.codec_text, "Codec")
        self.tabs.addTab(self._build_metadata_tab(), "Metadata")
        body_layout.addWidget(self.tabs, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        btn = buttons.button(QDialogButtonBox.Close)
        btn.setObjectName("DialogButton")
        btn.setIcon(QIcon())
        buttons.rejected.connect(self.reject)
        body_layout.addWidget(buttons)

        self._render_general_tab()
        self._render_codec_tab()

        self._scheduled.connect(self._run_scheduled, Qt.QueuedConnection)
        self._bpm_disk_changed.connect(self._on_bpm_metadata_changed, Qt.QueuedConnection)
        self._key_disk_changed.connect(self._on_key_metadata_changed, Qt.QueuedConnection)
        metadata_extractor.register_bpm_listener(self._on_bpm_disk_changed)
        metadata_extractor.register_key_listener(self._on_key_disk_changed)

        self.resize(600, 500)
        self._center_on_parent()

    def _center_on_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        parent_geo = parent.frameGeometry()
        x = parent_geo.x() + (parent_geo.width() - self.width()) // 2
        y = parent_geo.y() + (parent_geo.height() - self.height()) // 2
        self.move(x, y)

    # ---------- General / Codec tabs ----------

    def _render_general_tab(self) -> None:
        info = self.file_info
        meta = info.get("metadata", {})
        accent = self.palette.get("accent", "#0078d4")
        fg = self.palette.get("fg", "#000000")
        highlight = self.palette.get("highlight", "#EB5B00")

        def label(text):
            return f'<p style="color:{fg}; font-size:9pt; margin-bottom:0;">{text}</p>'

        def value(text):
            return f'<p style="margin-top:2px;">{text}</p>'

        def value_hl(text):
            return f'<p style="color:{highlight}; font-weight:bold; font-size:11pt; margin-top:2px;">{text}</p>'

        html = [f'<h2 style="color:{accent};">File Information</h2>']
        html.append(label("Filename"))
        html.append(value(info["filename"]))
        html.append(label("Path"))
        html.append(value(info["path"]))

        size = info["size"]
        size_mb = size / (1024 * 1024)
        size_kb = size / 1024
        html.append(label("Size"))
        if size_mb >= 1:
            html.append(value_hl(f"{size_mb:.2f} MB") + value(f"({size:,} bytes)"))
        else:
            html.append(value_hl(f"{size_kb:.2f} KB") + value(f"({size:,} bytes)"))

        if info["duration"] > 0:
            minutes, seconds = divmod(info["duration"], 60)
            html.append(label("Duration"))
            html.append(value_hl(f"{minutes}:{seconds:02d}") + value(f"({info['duration']} seconds)"))

        bpm_val = meta.get("bpm")
        if bpm_val is not None and bpm_val != "":
            html.append(label("BPM"))
            try:
                html.append(value_hl(str(int(round(float(bpm_val))))))
            except (ValueError, TypeError):
                html.append(value_hl(""))

        key_val = meta.get("key")
        if key_val is not None and key_val != "":
            html.append(label("Key"))
            html.append(value_hl(key_val))
            camelot_val = meta.get("camelot")
            if not camelot_val:
                try:
                    camelot_val = key_to_camelot(key_val)
                except Exception:
                    camelot_val = None
            if camelot_val:
                html.append(value_hl(f"{camelot_val} (Camelot)"))

        html.append(label("Format"))
        html.append(value_hl(info["format"]))
        self.general_text.setHtml("".join(html))

    def _render_codec_tab(self) -> None:
        info = self.file_info
        accent = self.palette.get("accent", "#0078d4")
        fg = self.palette.get("fg", "#000000")
        highlight = self.palette.get("highlight", "#EB5B00")

        def label(text):
            return f'<p style="color:{fg}; font-size:9pt; margin-bottom:0;">{text}</p>'

        def value_hl(text):
            return f'<p style="color:{highlight}; font-weight:bold; font-size:11pt; margin-top:2px;">{text}</p>'

        html = [f'<h2 style="color:{accent};">Audio Codec Information</h2>']
        html.append(label("Codec"))
        html.append(value_hl(info["codec"]))
        html.append(label("Format"))
        html.append(value_hl(info["format"]))
        if info["bitrate"] > 0:
            html.append(label("Bitrate"))
            html.append(value_hl(f"{info['bitrate'] // 1000} kbps"))
        if info["sample_rate"] > 0:
            html.append(label("Sample Rate"))
            html.append(value_hl(f"{info['sample_rate'] / 1000:.1f} kHz"))
        if info["channels"] > 0:
            html.append(label("Channels"))
            channels_text = "Stereo" if info["channels"] == 2 else f"{info['channels']} channels"
            html.append(value_hl(channels_text))
        self.codec_text.setHtml("".join(html))

    # ---------- Metadata tab ----------

    def _build_metadata_tab(self) -> QWidget:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        tab_layout.addWidget(form_widget)
        self.entries = {}
        meta = self.file_info.get("metadata", {})

        for label, key in _METADATA_FIELDS:
            entry = QLineEdit(str(meta.get(key) or ""))
            self.entries[key] = entry
            form.addRow(f"{label}:", entry)

        bpm_row = QHBoxLayout()
        self.entries["bpm"] = QLineEdit()
        self.bpm_btn = QPushButton("Calculate BPM")
        self.bpm_btn.setObjectName("CompactButton")
        self.bpm_btn.clicked.connect(self._calculate_bpm)
        bpm_row.addWidget(self.entries["bpm"], 1)
        bpm_row.addWidget(self.bpm_btn)
        form.addRow("BPM:", bpm_row)
        self._set_bpm_field(meta.get("bpm"))
        self.entries["bpm"].textEdited.connect(self._on_bpm_entry_edit)

        key_row = QHBoxLayout()
        self.entries["key"] = QLineEdit()
        self.key_btn = QPushButton("Calculate Key")
        self.key_btn.setObjectName("CompactButton")
        self.key_btn.clicked.connect(self._calculate_key)
        key_row.addWidget(self.entries["key"], 1)
        key_row.addWidget(self.key_btn)
        form.addRow("Key:", key_row)
        self._set_key_field(meta.get("key"))
        self.entries["key"].textEdited.connect(self._on_key_entry_edit)

        self.save_btn = QPushButton("Save Metadata")
        self.save_btn.setObjectName("DialogButton")
        self.save_btn.clicked.connect(self._save_metadata)
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        save_row.addWidget(self.save_btn)
        tab_layout.addStretch(1)
        tab_layout.addLayout(save_row)

        return tab

    def _set_bpm_field(self, bpm_val) -> None:
        if bpm_val is not None and bpm_val != "":
            try:
                self.entries["bpm"].setText(str(int(round(float(bpm_val)))))
                self._bpm_raw_value = str(bpm_val)
            except (ValueError, TypeError):
                self.entries["bpm"].setText("")
                self._bpm_raw_value = str(bpm_val)
        else:
            self.entries["bpm"].setText("")
            self._bpm_raw_value = None

    def _set_key_field(self, key_val) -> None:
        if key_val is not None and key_val != "":
            try:
                camelot_val = key_to_camelot(str(key_val))
            except Exception:
                camelot_val = None
            self.entries["key"].setText(camelot_val or str(key_val))
            self._key_raw_value = str(key_val)
        else:
            self.entries["key"].setText("")
            self._key_raw_value = None

    def _on_bpm_entry_edit(self, _text: str) -> None:
        self._bpm_raw_value = None

    def _on_key_entry_edit(self, text: str) -> None:
        full_text = text.strip()
        camelot_match = _CAMELOT_ENTRY_RE.fullmatch(full_text)
        if camelot_match:
            num, letter = camelot_match.group(1), camelot_match.group(2).upper()
            self.entries["key"].setText(f"{int(num)}{letter}")
            self._key_raw_value = None
            return
        try:
            camelot_val = key_to_camelot(full_text)
        except Exception:
            camelot_val = None
        if camelot_val:
            self.entries["key"].setText(camelot_val)
        self._key_raw_value = full_text

    def _save_metadata(self) -> None:
        metadata_to_save = {}
        for key, entry in self.entries.items():
            metadata_to_save[key] = entry.text().strip()
        if self._bpm_raw_value is not None:
            metadata_to_save["bpm"] = self._bpm_raw_value
        if self._key_raw_value is not None:
            metadata_to_save["key"] = self._key_raw_value

        if save_metadata(self.file_path, metadata_to_save):
            QMessageBox.information(self, "Success", "Metadata saved successfully!")
            self.file_info = get_file_info(self.file_path)
            self._render_general_tab()
            self._render_codec_tab()
            if self.metadata_saved_callback:
                try:
                    self.metadata_saved_callback(self.file_path)
                except Exception:
                    logger.exception("metadata_saved_callback failed")
        else:
            QMessageBox.critical(self, "Error", "Could not load file for writing.")

    # ---------- Calculate BPM/Key (background analysis) ----------

    def _qt_scheduler(self, func, *args):
        if shiboken6.isValid(self):
            self._scheduled.emit(func, args)

    def _run_scheduled(self, func, args):
        func(*args)

    def _calculate_bpm(self) -> None:
        self.bpm_btn.setEnabled(False)
        self.bpm_btn.setText("Calculating...")
        analysis_manager.submit_bpm_analysis(self.file_path, self._on_bpm_calculation_complete, self._qt_scheduler)

    def _on_bpm_calculation_complete(self, filepath, bpm_value) -> None:
        if filepath == self.file_path and bpm_value is not None:
            self._set_bpm_field(bpm_value)
        self.bpm_btn.setEnabled(True)
        self.bpm_btn.setText("Calculate BPM")

    def _calculate_key(self) -> None:
        self.key_btn.setEnabled(False)
        self.key_btn.setText("Calculating...")
        analysis_manager.submit_key_analysis(self.file_path, self._on_key_calculation_complete, self._qt_scheduler)

    def _on_key_calculation_complete(self, filepath, key_value) -> None:
        if filepath == self.file_path:
            if key_value is not None:
                self._set_key_field(key_value)
            else:
                QMessageBox.warning(self, "Key Analysis", "Could not calculate Key for this file.")
        self.key_btn.setEnabled(True)
        self.key_btn.setText("Calculate Key")

    # ---------- live listener refresh ----------

    def _on_bpm_disk_changed(self, filepath):
        if shiboken6.isValid(self):
            self._bpm_disk_changed.emit(filepath)

    def _on_key_disk_changed(self, filepath):
        if shiboken6.isValid(self):
            self._key_disk_changed.emit(filepath)

    def _on_bpm_metadata_changed(self, filepath: str) -> None:
        if os.path.abspath(filepath) != os.path.abspath(self.file_path):
            return
        self.file_info = get_file_info(self.file_path)
        self._render_general_tab()
        self._set_bpm_field(self.file_info.get("metadata", {}).get("bpm"))

    def _on_key_metadata_changed(self, filepath: str) -> None:
        if os.path.abspath(filepath) != os.path.abspath(self.file_path):
            return
        self.file_info = get_file_info(self.file_path)
        self._render_general_tab()
        self._set_key_field(self.file_info.get("metadata", {}).get("key"))

    # ---------- cleanup ----------

    def done(self, result) -> None:
        try:
            metadata_extractor.unregister_bpm_listener(self._on_bpm_disk_changed)
            metadata_extractor.unregister_key_listener(self._on_key_disk_changed)
        except Exception:
            logger.exception("Failed to unregister metadata listeners")
        super().done(result)
