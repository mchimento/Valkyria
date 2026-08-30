"""
Qt port of ui/browser_view.py.

Not a lazy filesystem tree in the original either — just a flat list of
files the user picked via "Open Folder..."/"Open Files...", stored in
state.browser_files. The hand-rolled ButtonPress/B1-Motion drag machinery
and the floating tk.Toplevel drag tooltip (browser_view.py:256-270,
429-642) are replaced by QTreeWidget's native drag support — dragging
selected rows out just needs mimeData() to package file paths as a
standard text/uri-list, which ui_qt/playlist_view.py's drop handling
already reads via QMimeData.urls().

Button column matches the original's layout: a vertically-centered column
on the left (button_frame, browser_view.py:114-159) — Folder/File pickers,
Add/Add Below (drag-drop isn't the only way in), then preview play/stop —
with the tree taking the rest of the width, rather than a row above it.
Above the tree on the right, a "Preview output:" device dropdown
(browser_view.py:168-187, 811-878) lets preview play through a different
device than the main player — it always excludes whatever device the main
player currently has selected, resolved the same way the original does.
"""

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

from audio.audio_player import AudioPlayer

logger = logging.getLogger(__name__)


class _BrowserTree(QTreeWidget):
    """Drag source (out to the playlist) and drop target for reordering
    itself — mirrors ui_qt/playlist_view.py's _PlaylistTree: let Qt perform
    the visual move natively, then resync state.browser_files from the
    result. The browser never accepts drops *from* elsewhere (only the
    playlist accepts external drops), so dropEvent ignores anything whose
    source isn't this same tree."""

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
        # Augment (not replace) Qt's own mimeData: the base implementation
        # already encodes application/x-qabstractitemmodeldatalist, which
        # QAbstractItemView's default dropEvent needs to recognize an
        # internal row-move at all. Building a QMimeData from scratch here
        # (as an earlier version of this method did) produced only
        # text/uri-list — external drops onto the playlist worked, since
        # that side only reads mime.urls(), but internal reordering within
        # this tree silently did nothing, since super().dropEvent() had no
        # row-move data to act on. Confirmed by inspecting mime.formats()
        # before/after this fix.
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
        # Matches ui/browser_view.py:279's tree.bind('<Delete>', ...) — an
        # earlier version had no way to remove a single mistaken entry
        # from the browser's file list at all; only re-browsing a whole
        # folder/file selection (replacing the entire list) could change it.
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

        self.btn_open_folder = QPushButton("📂 Folder")
        self.btn_open_files = QPushButton("🎵 File")
        self.btn_add = QPushButton("➕ Add")
        self.btn_add_below = QPushButton("⬇ Add Below")
        for btn in (self.btn_open_folder, self.btn_open_files, self.btn_add, self.btn_add_below):
            # BrowserActionButton, not the shared DialogButton: its wider
            # min-width (needed so "⬇ Add Below" isn't clipped) is set in
            # theme_bridge.py's QSS, not via setMinimumWidth() here — QSS
            # box-model properties on a styled widget override a Python-
            # side setMinimumWidth() call entirely once the stylesheet is
            # applied, so setting it here would have had no effect.
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
            # See ui_qt/playlist_view.py's refresh() for why: without this,
            # a drop squarely on a row nests it as a child instead of
            # reordering, and _resync_from_internal_move only reads
            # top-level items — a nested row would silently vanish from
            # state.browser_files.
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
        # the currently-playing track; then the end — matches
        # ui/browser_view.py's add_selected_below_playlist.
        insert_pos = len(self.state.playlist)
        pl_selected = self.playlist_view.get_selected_indices()
        if pl_selected:
            insert_pos = max(pl_selected) + 1
        elif self.state.current_index is not None and 0 <= self.state.current_index < len(self.state.playlist):
            insert_pos = self.state.current_index + 1
        self.playlist_view.add_files(paths, insert_pos)

    # ---------- preview output device ----------

    def _get_preview_devices(self) -> List[tuple]:
        """(id, name) pairs available for preview: only devices that are
        genuinely *separate physical hardware* from whatever the main
        player is using (e.g. a second sound card feeding headphones,
        while the main player plays to speakers) — never anything that
        shares the main player's actual output, even if it wouldn't
        technically crash.

        This went through two wrong designs before landing here. First,
        an index-based exclusion (matching ui/browser_view.py:811-833's
        own logic, so this gap is pre-existing there too) only excluded
        the one specific device the main player was using, leaving every
        *other* entry offered — including a raw "hw:X,Y" alias of the
        *same* card, which really did collide with the main player
        ("AlsaOpen" failing). Second, an allowlist of "known-safe" shared
        paths (the system default and an explicit "pipewire" entry, both
        of which route through PipeWire's own mixing and don't crash)
        stopped the crashes, but was still wrong: it let preview and the
        main playlist end up audibly mixed onto the *same* output, which
        defeats the actual point of a preview feature — cueing up a track
        before it goes to the main output, not blending it in. A real
        report confirmed exactly that: "it is still possible to play both
        lists from the same output."

        So this compares *cards*, not raw device identity, and treats
        every name without an explicit "(hw:CARD,DEV)" suffix (Default,
        pipewire, sysdefault, dmix, front, surroundNN) as aliasing
        whichever card the first raw hw: entry in the list names — that's
        always the system's primary/onboard card, since
        get_audio_devices() enumerates in sounddevice's native order and
        none of those alias names route anywhere else on a normal
        desktop. A device (aliased or raw) is offered only when its
        effective card differs from the main player's effective card —
        an earlier version excluded every alias unconditionally
        regardless of which card it actually pointed to, which both hid
        genuinely-safe options (Default Audio Device when the main
        player was pinned to a *different*, non-primary card) and made
        the browser's list look arbitrarily smaller than the Tools menu's
        full device list. If the system has no second sound card, preview
        has nothing safe to offer and correctly comes back empty (see
        _refresh_preview_devices, which disables preview entirely rather
        than showing a device that isn't real separation)."""
        if self._main_player is None:
            return []
        try:
            all_devices = self._main_player.get_audio_devices()
        except Exception:
            return []

        def hw_card(name: str) -> Optional[str]:
            # "HDA Intel PCH: ... (hw:0,0)" -> "0"; None for anything
            # without an explicit hw:CARD,DEV suffix.
            match = re.search(r"\(hw:(\d+),\d+\)", name)
            return match.group(1) if match else None

        # The system's primary card: whichever card the first raw hw:
        # entry names. Every alias without its own hw:CARD,DEV suffix is
        # assumed to resolve to this same card.
        default_card = next((hw_card(name) for _did, name in all_devices if hw_card(name) is not None), None)

        def effective_card(name: str) -> Optional[str]:
            card = hw_card(name)
            return card if card is not None else default_card

        main_id = getattr(self._main_player, "_device_id", None)
        if main_id is not None:
            main_card = next(
                (effective_card(name) for did, name in all_devices if did == main_id), default_card
            )
        else:
            main_card = default_card

        return [
            (did, name) for did, name in all_devices
            if effective_card(name) != main_card
        ]

    def _refresh_preview_devices(self) -> None:
        # Matches ui/browser_view.py:835-850: preserve the user's current
        # selection if it's still present in the refreshed list, only
        # falling back to the first entry if it's genuinely gone. An
        # earlier version always cleared+repopulated unconditionally,
        # which silently reset the combo (and the device _preview_play
        # would actually use) to the first device on every single refresh
        # — including the one _preview_play itself triggers right before
        # reading the selection, so a chosen non-default device was never
        # actually used for preview playback.
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
