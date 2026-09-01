"""Flat file list with drag-drop into the playlist and a preview player
with its own output-device selector."""

import logging
import os
import re
import threading
from typing import List, Optional

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from audio.audio_player import AudioPlayer, filter_selectable_audio_devices

logger = logging.getLogger(__name__)


class _BrowserTree(QTreeWidget):
    """Drag source into the playlist; also reorderable in place."""

    def __init__(self, owner: "BrowserViewQt", parent=None):
        super().__init__(parent)
        self._owner = owner
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)

    def mimeData(self, items):
        # Augment (not replace) Qt's own mimeData, which internal row-move
        # drop handling needs, with a text/uri-list for external drops.
        mime = super().mimeData(items)
        urls = []
        for item in items:
            path = item.data(0, Qt.UserRole)
            if path:
                urls.append(QUrl.fromLocalFile(path))
        mime.setUrls(urls)
        return mime

    def dropEvent(self, event) -> None:
        if event.source() is self:
            super().dropEvent(event)
            self._owner._resync_from_internal_move()
            return
        event.ignore()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_Delete:
            self._owner._remove_selected_from_browser()
            return
        super().keyPressEvent(event)


class BrowserViewQt(QWidget):
    _preview_ended = Signal()

    def __init__(self, state, settings, playlist_view=None, player=None, parent=None):
        super().__init__(parent)
        self.state = state
        self.settings = settings
        self.playlist_view = playlist_view
        self._main_player = player
        self._preview_devices: List[tuple] = []
        self._current_preview_path = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        header = QLabel("Browser")
        header.setObjectName("PanelHeader")
        outer.addWidget(header)

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        outer.addLayout(layout, 1)

        button_col = QVBoxLayout()
        button_col.setSpacing(6)
        button_col.addStretch(1)

        self.btn_open_folder = QPushButton("Folder")
        self.btn_open_files = QPushButton("File")
        self.btn_add = QPushButton("Add")
        self.btn_add_below = QPushButton("Add Below")
        for btn in (self.btn_open_folder, self.btn_open_files, self.btn_add, self.btn_add_below):
            # Wider min-width (vs shared DialogButton) set via QSS, not setMinimumWidth().
            btn.setObjectName("BrowserActionButton")
            button_col.addWidget(btn)

        button_col.addSpacing(8)
        preview_row = QHBoxLayout()
        preview_row.setSpacing(6)
        self.btn_preview_play = QPushButton("▶")
        self.btn_preview_stop = QPushButton("⏹")
        for btn in (self.btn_preview_play, self.btn_preview_stop):
            btn.setObjectName("TransportButton")
            btn.setFixedSize(44, 36)  # matches ControlsBarQt's transport buttons
            preview_row.addWidget(btn)
        button_col.addLayout(preview_row)

        button_col.addStretch(1)
        layout.addLayout(button_col)

        right_col = QVBoxLayout()
        right_col.setSpacing(6)

        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Preview output:"))
        self.preview_device_combo = QComboBox()
        self.preview_device_combo.setMinimumWidth(160)
        device_row.addWidget(self.preview_device_combo, 1)
        right_col.addLayout(device_row)

        self._tree = _BrowserTree(self)
        self._tree.setHeaderLabels(["Name"])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tree.itemDoubleClicked.connect(self._on_double_clicked)
        right_col.addWidget(self._tree, 1)

        layout.addLayout(right_col, 1)

        self.btn_open_folder.clicked.connect(self._on_open_folder)
        self.btn_open_files.clicked.connect(self._on_open_files)
        self.btn_add.clicked.connect(self._on_add_to_playlist)
        self.btn_add_below.clicked.connect(self._on_add_below_to_playlist)
        self.btn_preview_play.clicked.connect(self._on_preview_play_clicked)
        self.btn_preview_stop.clicked.connect(self._preview_stop)
        self.preview_device_combo.currentTextChanged.connect(self._on_preview_device_changed)

        self._preview_player = AudioPlayer(on_track_end=self._preview_ended.emit)
        self._preview_ended.connect(self._on_preview_ended, Qt.QueuedConnection)

        self._refresh_preview_devices()
        self.refresh()

    # ---------- population ----------

    def refresh(self) -> None:
        self._tree.clear()
        for path in self.state.browser_files:
            item = QTreeWidgetItem([os.path.basename(path)])
            item.setData(0, Qt.UserRole, path)
            # Prevents a drop-on-row from nesting instead of reordering.
            item.setFlags(item.flags() & ~Qt.ItemIsDropEnabled)
            self._tree.addTopLevelItem(item)

    def _resync_from_internal_move(self) -> None:
        self.state.browser_files = [
            self._tree.topLevelItem(i).data(0, Qt.UserRole)
            for i in range(self._tree.topLevelItemCount())
        ]

    def _remove_selected_from_browser(self) -> None:
        selected_paths = {item.data(0, Qt.UserRole) for item in self._tree.selectedItems()}
        if not selected_paths:
            return
        self.state.browser_files = [p for p in self.state.browser_files if p not in selected_paths]
        self.refresh()

    def _on_open_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Open Folder")
        if not folder:
            return
        exts = tuple(getattr(self.settings, "supported_extensions", ()) or ())
        files = []
        for root, _dirs, filenames in os.walk(folder):
            for name in filenames:
                if name.lower().endswith(exts):
                    files.append(os.path.join(root, name))
        files.sort()
        self.state.browser_files = files
        self.refresh()

    def _on_open_files(self) -> None:
        exts = getattr(self.settings, "supported_extensions", ()) or ()
        pattern = " ".join(f"*{ext}" for ext in exts) or "*"
        paths, _filter = QFileDialog.getOpenFileNames(self, "Open Files", "", f"Audio Files ({pattern})")
        if paths:
            self.state.browser_files = list(paths)
            self.refresh()

    # ---------- add to playlist ----------

    def _selected_paths(self) -> List[str]:
        return [item.data(0, Qt.UserRole) for item in self._tree.selectedItems()]

    def _on_add_to_playlist(self) -> None:
        paths = self._selected_paths()
        if not paths or self.playlist_view is None:
            return
        self.playlist_view.add_files(paths)  # appended at the end

    def _on_add_below_to_playlist(self) -> None:
        paths = self._selected_paths()
        if not paths or self.playlist_view is None:
            return
        # Prefer the last-selected playlist row; fall back to right after
        # the currently-playing track; then the end.
        insert_pos = len(self.state.playlist)
        pl_selected = self.playlist_view.get_selected_indices()
        if pl_selected:
            insert_pos = max(pl_selected) + 1
        elif self.state.current_index is not None and 0 <= self.state.current_index < len(self.state.playlist):
            insert_pos = self.state.current_index + 1
        self.playlist_view.add_files(paths, insert_pos)

    # ---------- preview output device ----------

    def _get_preview_devices(self) -> List[tuple]:
        """(id, name) pairs available for preview: only devices genuinely
        separate from whatever card the main player is using — never
        anything that would share its actual output."""
        if self._main_player is None:
            return []
        try:
            all_devices = self._main_player.get_audio_devices()
        except Exception:
            return []
        # Same alias-collapsing as the Tools menu, so both lists agree.
        all_devices = filter_selectable_audio_devices(all_devices)

        def hw_card(name: str) -> Optional[str]:
            match = re.search(r"\(hw:(\d+),\d+\)", name)
            return match.group(1) if match else None

        try:
            default_alsa_card, default_description = self._main_player.get_default_output_info()
        except Exception:
            default_alsa_card, default_description = None, None

        # Fallback guess if get_default_output_info() couldn't resolve anything.
        fallback_card = next((hw_card(name) for _did, name in all_devices if hw_card(name) is not None), None)

        # Sentinel distinct from any real (digit-string) card number.
        NON_ALSA = "non-alsa-default"

        def default_effective_card() -> Optional[str]:
            if default_alsa_card is not None:
                return default_alsa_card
            if default_description is not None:
                return NON_ALSA
            return fallback_card

        def effective_card(name: str) -> Optional[str]:
            card = hw_card(name)
            return card if card is not None else default_effective_card()

        main_id = getattr(self._main_player, "_device_id", None)
        if main_id is not None:
            main_card = next(
                (effective_card(name) for did, name in all_devices if did == main_id),
                default_effective_card(),
            )
        else:
            main_card = default_effective_card()

        def displayed_name(device_id: str, name: str) -> str:
            # Mirrors the Tools menu: show what "Default" actually reaches.
            if device_id == "__DEFAULT__" and default_description:
                return f"{name} (currently: {default_description})"
            return name

        return [
            (did, displayed_name(did, name)) for did, name in all_devices
            if effective_card(name) != main_card
        ]

    def _refresh_preview_devices(self) -> None:
        # Preserve the current selection across a refresh if it's still valid.
        previous_selection = self.preview_device_combo.currentText()
        devices = self._get_preview_devices()
        self._preview_devices = devices
        self.preview_device_combo.blockSignals(True)
        self.preview_device_combo.clear()
        if not devices:
            self.preview_device_combo.addItem("No device available")
            self.preview_device_combo.setEnabled(False)
            self.btn_preview_play.setEnabled(False)
            self.btn_preview_stop.setEnabled(False)
        else:
            names = [name for _did, name in devices]
            self.preview_device_combo.addItems(names)
            if previous_selection in names:
                self.preview_device_combo.setCurrentText(previous_selection)
            self.preview_device_combo.setEnabled(True)
            self.btn_preview_play.setEnabled(True)
            self.btn_preview_stop.setEnabled(True)
        self.preview_device_combo.blockSignals(False)

    def refresh_preview_devices(self) -> None:
        """Public entry point — call when the main player's output device changes."""
        self._refresh_preview_devices()

    def _on_preview_device_changed(self, _name: str) -> None:
        if self._current_preview_path is not None:
            self._preview_stop()

    # ---------- preview playback ----------

    def _on_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        path = item.data(0, Qt.UserRole)
        if path == self._current_preview_path:
            self._preview_stop()
        else:
            self._preview_play(path)

    def _on_preview_play_clicked(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        self._preview_play(item.data(0, Qt.UserRole))

    def _preview_play(self, path: str) -> None:
        self._refresh_preview_devices()
        if not self._preview_devices:
            return
        selected_name = self.preview_device_combo.currentText()
        device_id = next((did for did, name in self._preview_devices if name == selected_name), None)
        self._current_preview_path = path

        def _play():
            try:
                self._preview_player.set_audio_device(device_id)
            except Exception:
                logger.exception("Failed to set preview device")
            self._preview_player.play(path)

        threading.Thread(target=_play, daemon=True).start()

    def _preview_stop(self) -> None:
        self._current_preview_path = None
        threading.Thread(target=self._preview_player.stop, daemon=True).start()

    def _on_preview_ended(self) -> None:
        self._current_preview_path = None

    def shutdown(self) -> None:
        try:
            self._preview_player.stop()
        except Exception:
            logger.exception("Failed to stop preview player on shutdown")
