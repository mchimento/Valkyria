"""Live LUFS/peak/limiter/energy meters plus BPM/Key display and
save-to-tag buttons."""

import logging
import os

import shiboken6
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from audio.bpm import analysis_manager
from audio.metadata import get_display_bpm, get_metadata, key_to_camelot, metadata_extractor

logger = logging.getLogger(__name__)

ROW_HEIGHT = 26


def _peak_color(normalized: float) -> str:
    if normalized < 0.4:
        return "#4080FF"
    if normalized < 0.7:
        return "#00FF00"
    return "#FF4040"


def _limiter_color(activity: float) -> str:
    if activity < 0.3:
        return "#00FF00"
    if activity < 0.7:
        return "#FFAA00"
    return "#FF0000"


class MeterBar(QWidget):
    """Small horizontal bar meter — outlined rect + a filled rect for the value."""

    def __init__(self, width_px: int, height_px: int = 14, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self._border = QColor("#3E3E3E")
        self._fill = QColor("#4080FF")
        self.setFixedSize(width_px, height_px)
        self.setStyleSheet("background: transparent;")

    def set_value(self, value: float, fill_color: str) -> None:
        self._value = max(0.0, min(1.0, value))
        self._fill = QColor(fill_color)
        self.update()

    def set_border_color(self, color: str) -> None:
        self._border = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        w, h = self.width(), self.height()
        painter.setPen(self._border)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(0, 0, w - 1, h - 1)
        if self._value > 0:
            fill_w = int((w - 4) * self._value)
            if fill_w > 0:
                painter.setPen(Qt.NoPen)
                painter.setBrush(self._fill)
                painter.drawRect(2, 2, fill_w, h - 4)


class DJViewQt(QWidget):
    _metrics_ready = Signal(float, float, float, float, float)
    _scheduled = Signal(object, tuple)
    _bpm_disk_changed = Signal(str)
    _key_disk_changed = Signal(str)

    def __init__(self, state, theme, settings, player, parent=None):
        super().__init__(parent)
        self.state = state
        self.theme = theme
        self.settings = settings
        self.player = player
        self.palette = theme.palette

        self.lufs_value = -60.0
        self.overall_lufs_value = -60.0
        self.peak_dbfs = -60.0
        self.limiter_activity = 0.0
        self.energy_level = 0.0

        self.current_temp_bpm = None
        self.temporary_bpm_values = {}
        self._estimating_file = None

        self.current_temp_key = None
        self.temporary_key_values = {}
        self._estimating_key_file = None

        self.setFixedHeight(150)
        self._build_widgets()

        self._metrics_ready.connect(self._on_metrics_ready, Qt.QueuedConnection)
        self._scheduled.connect(self._run_scheduled, Qt.QueuedConnection)
        self._bpm_disk_changed.connect(self._on_bpm_metadata_changed, Qt.QueuedConnection)
        self._key_disk_changed.connect(self._on_key_metadata_changed, Qt.QueuedConnection)
        metadata_extractor.register_bpm_listener(self._on_bpm_disk_changed)
        metadata_extractor.register_key_listener(self._on_key_disk_changed)

        if self.player is not None:
            self.player.set_audio_metrics_callback(self._emit_metrics)

        self.apply_palette(self.palette)

    # ---------- construction ----------

    def _build_widgets(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 0, 0)

        self.panel = QFrame(self)
        self.panel.setObjectName("DJPanel")
        self.panel.setAttribute(Qt.WA_StyledBackground, True)
        outer.addWidget(self.panel, 1)

        content = QHBoxLayout(self.panel)
        content.setContentsMargins(12, 10, 12, 10)
        content.setSpacing(20)

        left_column = QVBoxLayout()
        left_column.setSpacing(3)
        self.lufs_title, self.lufs_label = self._add_value_row(left_column, "LUFS", "-100.0")
        self.overall_lufs_title, self.overall_lufs_label = self._add_value_row(left_column, "LUFS (Overall)", "-100.0")
        self.peak_title, self.peak_meter = self._add_meter_row(left_column, "PEAK", 80)
        self.limit_title, self.limiter_meter = self._add_meter_row(left_column, "LIMIT", 80)
        content.addLayout(left_column)
        content.setAlignment(left_column, Qt.AlignVCenter)

        right_column = QVBoxLayout()
        right_column.setSpacing(3)
        self.bpm_title, self.bpm_label = self._add_value_row(right_column, "BPM", "Estimating...")
        self.key_title, self.key_label = self._add_value_row(right_column, "KEY", "Estimating...")
        self.energy_title, self.energy_meter = self._add_meter_row(right_column, "ENERGY", 100)

        button_container = QWidget()
        button_container.setObjectName("DJButtonRow")
        button_container.setFixedHeight(ROW_HEIGHT)
        button_row = QHBoxLayout(button_container)
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        self.save_btn = QPushButton("Save BPM")
        self.save_btn.setObjectName("CompactButton")
        self.save_btn.clicked.connect(self._on_bpm_button_click)
        self.save_btn.setVisible(False)
        self.save_key_btn = QPushButton("Save Key")
        self.save_key_btn.setObjectName("CompactButton")
        self.save_key_btn.clicked.connect(self._on_key_button_click)
        self.save_key_btn.setVisible(False)
        button_row.addWidget(self.save_btn)
        button_row.addWidget(self.save_key_btn)
        button_row.addStretch(1)
        right_column.addWidget(button_container)
        content.addLayout(right_column, 1)
        content.setAlignment(right_column, Qt.AlignVCenter)

    def _add_value_row(self, parent_layout, title_text, widest_text):
        row = QHBoxLayout()
        row.setSpacing(10)
        title = QLabel(title_text)
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setFixedWidth(100 if "Overall" in title_text else 60)
        title.setFixedHeight(ROW_HEIGHT)
        row.addWidget(title, 0, Qt.AlignVCenter)

        value = QLabel("-60.0" if title_text.startswith("LUFS") else "--")
        value_font = QFont()
        value_font.setPointSize(15)
        value_font.setBold(True)
        value.setFont(value_font)
        value.setFixedWidth(QFontMetrics(value_font).horizontalAdvance(widest_text) + 4)
        value.setFixedHeight(ROW_HEIGHT)
        row.addWidget(value, 0, Qt.AlignVCenter)
        row.addStretch(1)
        parent_layout.addLayout(row)
        return title, value

    def _add_meter_row(self, parent_layout, title_text, meter_width):
        row = QHBoxLayout()
        row.setSpacing(10)
        title = QLabel(title_text)
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setFixedWidth(max(50, QFontMetrics(title_font).horizontalAdvance(title_text) + 4))
        title.setFixedHeight(ROW_HEIGHT)
        row.addWidget(title, 0, Qt.AlignVCenter)
        meter = MeterBar(meter_width)
        row.addWidget(meter, 0, Qt.AlignVCenter)
        row.addStretch(1)
        parent_layout.addLayout(row)
        return title, meter

    # ---------- theming ----------

    def apply_palette(self, palette: dict) -> None:
        self.palette = palette
        meta_fg = palette.get("status_fg", "#505050")
        dj_fg = palette.get("status_meta_fg", "#202020")
        for title in (self.lufs_title, self.overall_lufs_title, self.peak_title,
                      self.limit_title, self.bpm_title, self.key_title, self.energy_title):
            title.setStyleSheet(f"color: {meta_fg}; background: transparent;")
        for value in (self.bpm_label, self.key_label, self.lufs_label, self.overall_lufs_label):
            value.setStyleSheet(f"color: {dj_fg}; background: transparent;")
        self._redraw_meters()

    def _redraw_meters(self) -> None:
        border = self.palette.get("status_border", "#D0D0D0")
        for meter in (self.peak_meter, self.limiter_meter, self.energy_meter):
            meter.set_border_color(border)

        normalized_peak = 0.0
        if self.peak_dbfs > -60.0:
            normalized_peak = max(0.0, min(1.0, (self.peak_dbfs + 60.0) / 60.0))
        self.peak_meter.set_value(normalized_peak, _peak_color(normalized_peak))
        self.limiter_meter.set_value(self.limiter_activity, _limiter_color(self.limiter_activity))
        self.energy_meter.set_value(self.energy_level, _peak_color(self.energy_level))

    # ---------- real-time metrics (background-thread callback) ----------

    def is_visible(self) -> bool:
        return self.isVisible()

    def _emit_metrics(self, lufs, overall_lufs, peak_dbfs, limiter_activity, energy_level):
        if not self.is_visible():
            return
        if shiboken6.isValid(self):
            self._metrics_ready.emit(lufs, overall_lufs, peak_dbfs, limiter_activity, energy_level)

    def _on_metrics_ready(self, lufs, overall_lufs, peak_dbfs, limiter_activity, energy_level):
        self.overall_lufs_value = overall_lufs
        self.overall_lufs_label.setText(f"{overall_lufs:.1f}")
        if (lufs, peak_dbfs, limiter_activity, energy_level) == (-60.0, -60.0, 0.0, 0.0):
            return
        self.lufs_value = lufs
        self.peak_dbfs = peak_dbfs
        self.limiter_activity = limiter_activity
        self.energy_level = energy_level
        self.lufs_label.setText(f"{lufs:.1f}")
        self._redraw_meters()

    def update_meter_values(self, lufs=-60.0, peak_dbfs=-60.0, limiter_activity=0.0, overall_lufs=None):
        self.lufs_value = max(-60.0, min(0.0, lufs))
        self.peak_dbfs = max(-60.0, min(0.0, peak_dbfs))
        self.limiter_activity = max(0.0, min(1.0, limiter_activity))
        self.lufs_label.setText(f"{self.lufs_value:.1f}")
        if overall_lufs is not None:
            self.overall_lufs_value = max(-60.0, min(0.0, overall_lufs))
            self.overall_lufs_label.setText(f"{self.overall_lufs_value:.1f}")
        self._redraw_meters()

    def update_energy_level(self, energy=0.0):
        self.energy_level = max(0.0, min(1.0, energy))
        self._redraw_meters()

    def update_meter_level(self, level):
        """Legacy passthrough — approximates LUFS/peak/limiter from a single 0..1 level."""
        if level > 0:
            dbfs = -60 + (level * 60)
            self.update_meter_values(lufs=dbfs, peak_dbfs=dbfs, limiter_activity=level * 0.5)

    # ---------- async scheduler adapter (AnalysisManager) ----------

    def _qt_scheduler(self, func, *args):
        if shiboken6.isValid(self):
            self._scheduled.emit(func, args)

    def _run_scheduled(self, func, args):
        func(*args)

    # ---------- public API ----------

    def update_info(self, filepath=None) -> None:
        if filepath is None:
            idx = self.state.current_index
            if idx is None or idx >= len(self.state.playlist):
                self._clear_info()
                return
            filepath = self.state.playlist[idx]

        meta = get_metadata(filepath)

        bpm = meta.get("bpm")
        display_bpm = get_display_bpm(bpm)
        if display_bpm:
            self.bpm_label.setText(display_bpm)
            self._estimating_file = None
            self.current_temp_bpm = None
            self.save_btn.setVisible(False)
        else:
            if self._estimating_file == filepath:
                pass
            elif filepath in self.temporary_bpm_values:
                bpm_val = self.temporary_bpm_values.get(filepath)
                self.current_temp_bpm = bpm_val
                self.bpm_label.setText(get_display_bpm(bpm_val))
                self.save_btn.setText("Save BPM")
                self.save_btn.setEnabled(True)
                self.save_btn.setVisible(True)
                self._estimating_file = None
            elif not self.is_visible():
                self.bpm_label.setText("--")
                self.save_btn.setVisible(False)
            else:
                self.bpm_label.setText("Estimating...")
                self._estimating_file = filepath
                self.current_temp_bpm = None
                self.save_btn.setVisible(False)
                analysis_manager.submit_bpm_analysis(filepath, self._on_bpm_analysis_complete, self._qt_scheduler)

        key = meta.get("key")
        if key:
            camelot_val = meta.get("camelot") if isinstance(meta, dict) else None
            if not camelot_val:
                try:
                    camelot_val = key_to_camelot(key)
                except Exception:
                    camelot_val = None
            self.key_label.setText(camelot_val or key)
            self._estimating_key_file = None
            self.current_temp_key = None
            self.save_key_btn.setVisible(False)
        else:
            if self._estimating_key_file == filepath:
                pass
            elif filepath in self.temporary_key_values:
                key_val = self.temporary_key_values.get(filepath)
                try:
                    camelot_val = key_to_camelot(key_val)
                except Exception:
                    camelot_val = None
                self.key_label.setText(camelot_val or key_val)
                self.current_temp_key = key_val
                self.save_key_btn.setText("Save Key")
                self.save_key_btn.setEnabled(True)
                self.save_key_btn.setVisible(True)
                self._estimating_key_file = None
            elif not self.is_visible():
                self.key_label.setText("--")
                self.save_key_btn.setVisible(False)
            else:
                self.key_label.setText("Estimating...")
                self._estimating_key_file = filepath
                self.current_temp_key = None
                self.save_key_btn.setVisible(False)
                analysis_manager.submit_key_analysis(filepath, self._finish_key_estimation, self._qt_scheduler)

    def _finish_estimation(self, filepath, bpm) -> None:
        if self._estimating_file != filepath:
            return
        display_bpm = get_display_bpm(bpm)
        if display_bpm:
            self.temporary_bpm_values[filepath] = bpm
            self.bpm_label.setText(display_bpm)
            self.current_temp_bpm = bpm
            self.save_btn.setText("Save BPM")
            self.save_btn.setEnabled(True)
            self.save_btn.setVisible(True)
        else:
            self.bpm_label.setText("--")
            self.save_btn.setVisible(False)
        self._estimating_file = None

    def _finish_key_estimation(self, filepath, key) -> None:
        if self._estimating_key_file != filepath:
            return
        if key:
            self.temporary_key_values[filepath] = key
            idx = self.state.current_index
            current_path = self.state.playlist[idx] if idx is not None and idx < len(self.state.playlist) else None
            try:
                camelot_val = key_to_camelot(key)
            except Exception:
                camelot_val = None
            if current_path and os.path.abspath(current_path) == os.path.abspath(filepath):
                self.key_label.setText(camelot_val or key)
                self.current_temp_key = key
            self.save_key_btn.setText("Save Key")
            self.save_key_btn.setEnabled(True)
            self.save_key_btn.setVisible(True)
        else:
            self.key_label.setText("--")
            self.save_key_btn.setVisible(False)
        self._estimating_key_file = None

    def _clear_info(self) -> None:
        self.bpm_label.setText("--")
        self.key_label.setText("--")
        self.lufs_value = -60.0
        self.overall_lufs_value = -60.0
        self.peak_dbfs = -60.0
        self.limiter_activity = 0.0
        self.energy_level = 0.0
        self.lufs_label.setText("-60.0")
        self.overall_lufs_label.setText("-60.0")
        self.save_btn.setVisible(False)
        self.save_key_btn.setVisible(False)
        self._estimating_file = None
        self.current_temp_bpm = None
        self._estimating_key_file = None
        self.current_temp_key = None
        self._redraw_meters()

    # ---------- BPM save flow ----------

    def _on_bpm_button_click(self) -> None:
        idx = self.state.current_index
        if idx is None or idx >= len(self.state.playlist):
            return
        filepath = self.state.playlist[idx]
        if self.current_temp_bpm is not None:
            self.save_btn.setEnabled(False)
            self.save_btn.setText("Saving...")
            analysis_manager.submit_bpm_save(filepath, self.current_temp_bpm, self._on_bpm_save_complete, self._qt_scheduler)

    def _on_bpm_analysis_complete(self, filepath, bpm_value) -> None:
        if self._estimating_file == filepath:
            self._finish_estimation(filepath, bpm_value)
            return
        if bpm_value is not None:
            self.temporary_bpm_values[filepath] = bpm_value
            idx = self.state.current_index
            current_path = self.state.playlist[idx] if idx is not None and idx < len(self.state.playlist) else None
            if current_path and os.path.abspath(current_path) == os.path.abspath(filepath):
                self.current_temp_bpm = bpm_value
                self.bpm_label.setText(get_display_bpm(bpm_value))
            self.save_btn.setText("Save BPM")
            self.save_btn.setEnabled(True)
            self.save_btn.setVisible(True)
        else:
            self.save_btn.setVisible(False)

    def _reset_bpm_button(self) -> None:
        self.save_btn.setEnabled(True)
        self.save_btn.setText("Save BPM")
        self.current_temp_bpm = None

    def _on_bpm_save_complete(self, filepath, success) -> None:
        if success:
            self.save_btn.setVisible(False)
        else:
            self._reset_bpm_button()

    def _on_bpm_disk_changed(self, filepath):
        if shiboken6.isValid(self):
            self._bpm_disk_changed.emit(filepath)

    def _on_bpm_metadata_changed(self, filepath) -> None:
        idx = self.state.current_index
        if idx is None or idx >= len(self.state.playlist):
            return
        current_path = self.state.playlist[idx]
        if os.path.abspath(current_path) != os.path.abspath(filepath):
            return

        meta = get_metadata(filepath)
        bpm_on_disk = meta.get("bpm")
        if bpm_on_disk is None or bpm_on_disk == "":
            if filepath in self.temporary_bpm_values:
                self.save_btn.setEnabled(True)
                self.save_btn.setText("Save BPM")
                self.save_btn.setVisible(True)
            else:
                self._estimating_file = filepath
                self.bpm_label.setText("Estimating...")
                self.save_btn.setVisible(False)
                analysis_manager.submit_bpm_analysis(filepath, self._on_bpm_analysis_complete, self._qt_scheduler)
        else:
            self.save_btn.setVisible(False)

    # ---------- Key save flow ----------

    def _on_key_button_click(self) -> None:
        idx = self.state.current_index
        if idx is None or idx >= len(self.state.playlist):
            return
        filepath = self.state.playlist[idx]
        if self.current_temp_key is not None:
            self.save_key_btn.setEnabled(False)
            self.save_key_btn.setText("Saving...")
            analysis_manager.submit_key_save(filepath, self.current_temp_key, self._on_key_save_complete, self._qt_scheduler)

    def _on_key_save_complete(self, filepath, success) -> None:
        if success:
            self.save_key_btn.setVisible(False)
        else:
            self._reset_key_button()

    def _reset_key_button(self) -> None:
        self.save_key_btn.setEnabled(True)
        self.save_key_btn.setText("Save Key")
        self.current_temp_key = None

    def _on_key_disk_changed(self, filepath):
        if shiboken6.isValid(self):
            self._key_disk_changed.emit(filepath)

    def _on_key_metadata_changed(self, filepath) -> None:
        idx = self.state.current_index
        if idx is None or idx >= len(self.state.playlist):
            return
        current_path = self.state.playlist[idx]
        if os.path.abspath(current_path) != os.path.abspath(filepath):
            return

        meta = get_metadata(filepath)
        key_on_disk = meta.get("key")
        if key_on_disk is None or key_on_disk == "":
            if filepath in self.temporary_key_values:
                self.save_key_btn.setEnabled(True)
                self.save_key_btn.setText("Save Key")
                self.save_key_btn.setVisible(True)
            else:
                self._estimating_key_file = filepath
                self.key_label.setText("Estimating...")
                self.save_key_btn.setVisible(False)
                analysis_manager.submit_key_analysis(filepath, self._finish_key_estimation, self._qt_scheduler)
        else:
            self.save_key_btn.setVisible(False)

    # ---------- cleanup ----------

    def shutdown(self) -> None:
        metadata_extractor.unregister_bpm_listener(self._on_bpm_disk_changed)
        metadata_extractor.unregister_key_listener(self._on_key_disk_changed)
