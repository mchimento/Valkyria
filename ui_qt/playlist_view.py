"""QTreeWidget with native drag-drop reordering, background metadata
loading, and search filtering. When a search filter is active, visual row
position != actual playlist index, so the real index is stored as item
data (Qt.UserRole + 2)."""

import logging
import os
import threading
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from audio import playback
from audio.metadata import get_display_title, get_metadata
from ui_qt import drag_ghost

logger = logging.getLogger(__name__)

COLUMNS = ["Title", "Artist", "Album", "Duration"]
COLUMN_WIDTHS = [200, 80, 100, 100]
BATCH_SIZE = 50
MIN_COLUMN_WIDTHS = [150, 50, 60, 50]  # floors used in _on_section_resized


class _PlaylistTree(QTreeWidget):
    """The actual tree; drop handling is intercepted here and delegated
    back to the owning PlaylistViewQt, which holds the state reference."""

    def __init__(self, owner: "PlaylistViewQt"):
        super().__init__(owner)
        self._owner = owner
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)

    def dragEnterEvent(self, event) -> None:
        drag_ghost.update_position(self.mapToGlobal(event.position().toPoint()))
        super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        # Keeps the browser's floating drag chip (drag_ghost.py) tracking
        # the cursor while it's hovering the playlist.
        drag_ghost.update_position(self.mapToGlobal(event.position().toPoint()))
        super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.source() is self:
            super().dropEvent(event)
            self._owner._resync_from_internal_move()
            return

        mime = event.mimeData()
        if mime.hasUrls():
            paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
            if paths:
                index = self._drop_index(event)
                self._owner._insert_external_files(paths, index)
                event.acceptProposedAction()
                return
        event.ignore()

    def _drop_index(self, event) -> int:
        target = self.itemAt(event.position().toPoint())
        if target is None:
            return len(self._owner.state.playlist)
        row_actual = target.data(0, Qt.UserRole + 2)
        if self.dropIndicatorPosition() == QAbstractItemView.BelowItem:
            return row_actual + 1
        return row_actual


class PlaylistViewQt(QWidget):
    track_activated = Signal(int)  # playlist index, from double-click
    metadata_batch_ready = Signal(int, list)  # load_id, [(path, metadata_dict), ...]
    playlist_changed = Signal()  # fired after every refresh(); keeps menu state in sync
    # Fired after this view stops playback itself (clear/remove current track).
    playback_stopped = Signal()
    selection_changed = Signal()
    show_track_info_requested = Signal(int)  # actual playlist index
    show_booklet_requested = Signal(int)
    set_time_limit_requested = Signal(int)
    clear_time_limit_requested = Signal(int)

    def __init__(self, state, palette: dict, player=None, parent=None):
        super().__init__(parent)
        self.state = state
        self.palette = palette
        self.player = player
        self._load_id = 0
        self._search_text = ""
        self._pending_selection: List[int] = []
        self._pending_scroll_value: Optional[int] = None
        self._in_section_resize = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QLabel("Playback queue")
        header.setObjectName("PanelHeader")
        layout.addWidget(header)

        search_row = QHBoxLayout()
        search_row.addStretch(1)
        search_icon = QLabel("🔍")
        search_icon.setObjectName("SearchIcon")
        search_row.addWidget(search_icon)
        self.search_entry = QLineEdit()
        self.search_entry.setObjectName("SearchEntry")
        self.search_entry.setPlaceholderText("Search")
        self.search_entry.setFixedWidth(180)
        search_row.addWidget(self.search_entry)
        layout.addLayout(search_row)

        self._tree = _PlaylistTree(self)
        self._tree.setObjectName("PlaylistTree")  # frameless — see theme_bridge.py
        self._tree.setHeaderLabels(COLUMNS)
        self._tree.setRootIsDecorated(False)
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setAlternatingRowColors(True)
        header = self._tree.header()
        # Column reordering would break _actual_index's column-0 assumption.
        header.setSectionsMovable(False)
        # All columns stay Interactive (not Stretch) — see CLAUDE.md's
        # QHeaderView.Stretch gotcha for why. _on_section_resized below
        # redistributes width between neighbors, like ttk's stretch pool.
        for col in range(len(COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        header.setStretchLastSection(False)
        for col, width in enumerate(COLUMN_WIDTHS):
            self._tree.setColumnWidth(col, width)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.itemDoubleClicked.connect(self._on_double_clicked)
        self._tree.itemSelectionChanged.connect(self.selection_changed.emit)
        layout.addWidget(self._tree)

        self.search_entry.textChanged.connect(self._on_search_text_changed)

        self.metadata_batch_ready.connect(self._on_metadata_batch, Qt.QueuedConnection)
        header.sectionResized.connect(self._on_section_resized)

        self._adjust_title_column_width()
        self.refresh()

    # ---------- selection ----------

    def _actual_index(self, item: QTreeWidgetItem) -> int:
        return item.data(0, Qt.UserRole + 2)

    def get_selected_indices(self) -> List[int]:
        return sorted(self._actual_index(item) for item in self._tree.selectedItems())

    def _select_indices(self, indices: List[int]) -> None:
        wanted = set(indices)
        self._tree.clearSelection()
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if self._actual_index(item) in wanted:
                item.setSelected(True)

    # ---------- search ----------

    def _on_search_text_changed(self, text: str) -> None:
        self._search_text = text.strip().lower()
        self.refresh()

    def _matches_search(self, path: str, meta: dict) -> bool:
        title = (meta.get("title") or get_display_title(path)).lower()
        artist = (meta.get("artist") or "").lower()
        album = (meta.get("album") or "").lower()
        q = self._search_text
        return q in title or q in artist or q in album

    # ---------- population ----------

    def refresh(self, select: Optional[List[int]] = None, preserve_scroll: bool = False) -> None:
        """Clears and rebuilds the tree. Rows appear only once their real
        metadata has arrived (via _on_metadata_batch), so they don't exist
        synchronously right after this call — pass `select` for indices to
        restore once loaded, rather than calling _select_indices() after.
        `preserve_scroll` keeps the viewport anchored at its current
        position instead of jumping to wherever the reselected row lands."""
        self._load_id += 1
        load_id = self._load_id

        self._pending_selection = select if select is not None else self.get_selected_indices()
        self._pending_scroll_value = self._tree.verticalScrollBar().value() if preserve_scroll else None
        self._tree.clear()
        self._load_metadata_async(load_id)
        self.playlist_changed.emit()

    def _duration_text(self, path: str, meta: dict) -> str:
        # A track with an active play_limits entry shows the limit
        # instead of its real duration in this column.
        if path in self.state.play_limits:
            return f"⏱ {int(self.state.play_limits[path])}s"
        return meta.get("duration", "")

    def refresh_time_limit_display(self, index: int) -> None:
        """Re-renders one row's Duration column after its play_limits entry
        changes, without a full playlist reload."""
        if not (0 <= index < len(self.state.playlist)):
            return
        filepath = self.state.playlist[index]
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if self._actual_index(item) == index:
                item.setText(3, self._duration_text(filepath, get_metadata(filepath)))
                return

    def refresh_highlight(self) -> None:
        highlight = QColor(self.palette.get("highlight", self.palette.get("select_bg", "#FFF59D")))
        transparent = QColor(Qt.transparent)
        normal_fg = QColor(self.palette.get("fg", "#CCCCCB"))
        playing_fg = QColor(self.palette.get("playing_fg", "#000000"))
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            actual = self._actual_index(item)
            self._set_row_display(actual, item)
            is_current = actual == self.state.current_index
            for col in range(len(COLUMNS)):
                item.setBackground(col, highlight if is_current else transparent)
                item.setForeground(col, playing_fg if is_current else normal_fg)

    def _set_row_display(self, index: int, item: QTreeWidgetItem) -> None:
        clean_title = item.data(0, Qt.UserRole + 1) or ""
        prefix = "▶ " if index == self.state.current_index else ""
        item.setText(0, f"{prefix}{clean_title}")

    def _load_metadata_async(self, load_id: int) -> None:
        indexed_paths = list(enumerate(self.state.playlist))  # (actual_index, path)
        search_text = self._search_text

        def worker():
            batch = []
            for actual_index, path in indexed_paths:
                if load_id != self._load_id:
                    return
                try:
                    meta = get_metadata(path)
                except Exception:
                    logger.exception("Failed to read metadata for %s", path)
                    meta = {}
                if search_text and not self._matches_search(path, meta):
                    continue
                batch.append((actual_index, path, meta))
                if len(batch) >= BATCH_SIZE:
                    self.metadata_batch_ready.emit(load_id, batch)
                    batch = []
            if batch and load_id == self._load_id:
                self.metadata_batch_ready.emit(load_id, batch)

        threading.Thread(target=worker, daemon=True).start()

    def _on_metadata_batch(self, load_id: int, batch: list) -> None:
        if load_id != self._load_id:
            return
        # Selects matching rows at creation time instead of a blanket
        # clearSelection()+reselect after every batch — batches keep
        # streaming in well after refresh(), and a global reselect on each
        # later batch would wipe out a selection the user made by hand
        # while earlier batches were still loading.
        wanted = set(self._pending_selection)
        for actual_index, path, meta in batch:
            title = meta.get("title") or os.path.basename(path)
            item = QTreeWidgetItem(["", meta.get("artist", ""), meta.get("album", ""), self._duration_text(path, meta)])
            item.setData(0, Qt.UserRole, path)
            item.setData(0, Qt.UserRole + 1, title)
            item.setData(0, Qt.UserRole + 2, actual_index)
            item.setTextAlignment(3, Qt.AlignCenter)
            # Prevents a drop-on-row from nesting instead of reordering.
            item.setFlags(item.flags() & ~Qt.ItemIsDropEnabled)
            self._tree.addTopLevelItem(item)
            if actual_index in wanted:
                item.setSelected(True)
        self._adjust_title_column_width()
        self.refresh_highlight()
        if self._pending_scroll_value is not None:
            self._tree.verticalScrollBar().setValue(self._pending_scroll_value)

    # ---------- drag-drop ----------

    def _resync_from_internal_move(self) -> None:
        if self._search_text:
            # Reordering a filtered/partial view has no well-defined
            # mapping back onto the full playlist — undo the visual move
            # by rebuilding from the real (unmodified) state instead.
            self.refresh()
            return

        old_current_path: Optional[str] = None
        if self.state.current_index is not None and 0 <= self.state.current_index < len(self.state.playlist):
            old_current_path = self.state.playlist[self.state.current_index]

        new_order = [
            self._tree.topLevelItem(i).data(0, Qt.UserRole)
            for i in range(self._tree.topLevelItemCount())
        ]
        self.state.playlist = new_order

        if old_current_path is not None:
            try:
                self.state.current_index = new_order.index(old_current_path)
            except ValueError:
                self.state.current_index = None
        self.refresh()

    def _insert_external_files(self, paths: List[str], index: int) -> None:
        self.add_files(paths, index)

    def add_files(self, paths: List[str], index: Optional[int] = None) -> None:
        """Insert paths at `index` (default: append at the end). Public —
        used by both the drag-drop path above and BrowserViewQt's
        Add/Add Below buttons (ui_qt/browser_view.py)."""
        if index is None:
            index = len(self.state.playlist)
        for offset, path in enumerate(paths):
            self.state.playlist.insert(index + offset, path)
        if self.state.current_index is not None and self.state.current_index >= index:
            self.state.current_index += len(paths)
        self.refresh()

    # ---------- context menu ----------

    def _show_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if item is None:
            return
        index = self._actual_index(item)
        self._select_indices([index])

        menu = QMenu(self)
        menu.addAction("Play", lambda: self.track_activated.emit(index))
        menu.addAction("Play After Current", lambda: self._context_play_after_current(index))
        menu.addSeparator()
        menu.addAction("Play for time...", lambda: self.set_time_limit_requested.emit(index))
        menu.addAction("Clear time limit", lambda: self.clear_time_limit_requested.emit(index))
        menu.addSeparator()
        menu.addAction("Show Metadata", lambda: self.show_track_info_requested.emit(index))
        menu.addAction("Show Album Booklet", lambda: self.show_booklet_requested.emit(index))
        menu.addSeparator()
        menu.addAction("Remove", lambda: self._context_remove(index))
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _context_play_after_current(self, index: int) -> None:
        if self.state.current_index is None:
            QMessageBox.information(self, "No Track Playing", "Please start playing a track first.")
            return
        new_playlist, new_index = playback.play_after_current(self.state.playlist, [index], self.state.current_index)
        self.state.playlist = new_playlist
        self.state.current_index = new_index
        self.refresh(preserve_scroll=True)

    def _context_remove(self, index: int) -> None:
        new_playlist, new_index = playback.remove_selected_from_playlist(self.state.playlist, [index], self.state.current_index)
        self.state.playlist = new_playlist
        self.state.current_index = new_index
        self._stop_if_current_cleared(new_index)
        # Explicit empty selection — refresh()'s default (reselect whatever
        # was selected before) would reselect by raw index number, which
        # after a removal refers to different, remaining songs that were
        # never actually selected by the user.
        self.refresh(select=[])

    def _on_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if not getattr(self.state, "play_on_double", True):
            return
        self.track_activated.emit(self._actual_index(item))

    # ---------- menu-bar-driven operations (operate on selection) ----------

    def move_up(self) -> None:
        indices = self.get_selected_indices()
        if not indices:
            return
        # move_selected_up no-ops the whole move if any index is already at the top.
        blocked = min(indices) <= 0
        self.state.playlist = playback.move_selected_up(self.state.playlist, indices)
        reselect = indices if blocked else sorted({(i - 1 if i > 0 else i) for i in indices})
        self.refresh(select=sorted(reselect))

    def move_down(self) -> None:
        indices = self.get_selected_indices()
        if not indices:
            return
        last = len(self.state.playlist) - 1
        blocked = max(indices) >= last
        self.state.playlist = playback.move_selected_down(self.state.playlist, indices)
        reselect = indices if blocked else sorted({(i + 1 if i < last else i) for i in indices})
        self.refresh(select=sorted(reselect))

    def remove_selected(self) -> None:
        indices = self.get_selected_indices()
        if not indices:
            return
        new_playlist, new_index = playback.remove_selected_from_playlist(self.state.playlist, indices, self.state.current_index)
        self.state.playlist = new_playlist
        self.state.current_index = new_index
        self._stop_if_current_cleared(new_index)
        # See _context_remove's comment: default reselect would land on
        # whatever remaining songs now occupy the removed rows' old index
        # numbers, not an empty selection.
        self.refresh(select=[])

    def play_after_current_selected(self) -> None:
        indices = self.get_selected_indices()
        if not indices:
            return
        new_playlist, new_index = playback.play_after_current(self.state.playlist, indices, self.state.current_index)
        self.state.playlist = new_playlist
        self.state.current_index = new_index
        self.refresh(preserve_scroll=True)

    def clear(self) -> None:
        if not self.state.playlist:
            return
        reply = QMessageBox.question(
            self, "Clear Playlist", "Are you sure you want to clear the playlist?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        was_playing = self.state.current_index is not None
        self.state.playlist, self.state.current_index = playback.clear_playlist()
        if was_playing and self.player is not None:
            try:
                self.player.stop()
            except Exception:
                logger.exception("player.stop() failed while clearing playlist")
            self.playback_stopped.emit()
        self.refresh()

    def _stop_if_current_cleared(self, new_index: Optional[int]) -> None:
        if new_index is None and self.player is not None:
            try:
                self.player.stop()
            except Exception:
                logger.exception("player.stop() failed after removing current track")
            self.playback_stopped.emit()

    def sort_by_title(self) -> None:
        self.state.playlist, self.state.current_index = playback.sort_playlist_by_title(self.state.playlist, self.state.current_index)
        self.refresh()

    def sort_by_artist(self) -> None:
        self.state.playlist, self.state.current_index = playback.sort_playlist_by_artist(self.state.playlist, self.state.current_index)
        self.refresh()

    def shuffle(self) -> None:
        self.state.playlist, self.state.current_index = playback.shuffle_playlist(self.state.playlist, self.state.current_index)
        self.refresh()

    # ---------- column sizing ----------

    def resizeEvent(self, event) -> None:
        # Hooked on this outer panel, not _PlaylistTree, since column drags
        # shouldn't trigger this too.
        super().resizeEvent(event)
        self._adjust_title_column_width()

    def _adjust_title_column_width(self) -> None:
        """Distributes leftover width (beyond Duration's) across
        Title/Artist/Album proportionally to their current widths. Uses
        tree.width(), not viewport().width() (stale at this point).
        Guarded by _in_section_resize so it doesn't fight
        _on_section_resized's own compensation."""
        stretch_cols = (0, 1, 2)  # Title, Artist, Album
        duration_width = self._tree.columnWidth(3)
        scrollbar = self._tree.verticalScrollBar()
        scrollbar_reserve = scrollbar.width() if scrollbar.isVisible() else 0
        frame = self._tree.frameWidth() * 2
        available = self._tree.width() - frame - scrollbar_reserve - duration_width
        current_total = sum(self._tree.columnWidth(c) for c in stretch_cols)
        if current_total <= 0 or available == current_total:
            return
        extra = available - current_total
        self._in_section_resize = True
        try:
            remaining = extra
            for i, col in enumerate(stretch_cols):
                if i == len(stretch_cols) - 1:
                    share = remaining  # last column absorbs any rounding remainder
                else:
                    share = round(extra * (self._tree.columnWidth(col) / current_total))
                    remaining -= share
                new_width = max(MIN_COLUMN_WIDTHS[col], self._tree.columnWidth(col) + share)
                self._tree.setColumnWidth(col, new_width)
        finally:
            self._in_section_resize = False

    def _on_section_resized(self, logical_index: int, old_size: int, new_size: int) -> None:
        """Qt attributes a dragged boundary to its LEFT column, so this
        chains column N's resize to its right neighbor (partner =
        logical_index + 1), transferring the opposite delta so the total
        width stays pinned to the tree — same net effect as ttk's stretch
        pool, but with every column keeping a real native drag handle.
        Capped at MIN_COLUMN_WIDTHS. _in_section_resize guards re-entrancy
        since the compensation itself re-emits this signal."""
        if self._in_section_resize or logical_index >= len(COLUMNS) - 1:
            return
        partner = logical_index + 1
        self._in_section_resize = True
        try:
            delta = new_size - old_size
            partner_width = self._tree.columnWidth(partner)
            new_partner = partner_width - delta
            floor = MIN_COLUMN_WIDTHS[partner]
            if new_partner < floor:
                max_delta = partner_width - floor
                self._tree.setColumnWidth(logical_index, old_size + max_delta)
                self._tree.setColumnWidth(partner, floor)
            else:
                self._tree.setColumnWidth(partner, new_partner)
        finally:
            self._in_section_resize = False

    # ---------- theming ----------

    def apply_palette(self, palette: dict) -> None:
        self.palette = palette
        self.refresh_highlight()
