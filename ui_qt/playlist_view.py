"""
Qt port of ui/playlist_view.py.

Most of the original's 1312 lines are hand-rolled drag-reorder math that
exists purely because ttk.Treeview has no native drag-drop reordering —
QTreeWidget's DragDrop mode replaces essentially all of it; only re-syncing
state.playlist to Qt's new visual row order after a move is real logic to
port (see _resync_from_internal_move). The manual queue.SimpleQueue +
root.after() polling pump for background metadata
(ui/playlist_view.py:455-507) is replaced by a plain background thread
emitting a queued-connection signal per batch — Qt's signal/slot crossing
threads natively makes the polling loop itself unnecessary.

Search filtering (ui/playlist_view.py:1245-1267, case-insensitive substring
match against title/artist/album) means a visible row's *position* no
longer equals its *actual playlist index* once a filter is active — same
problem the original solves with its `index_{n}` tag trick
(_get_actual_index_from_tree_item). The Qt equivalent stores the actual
index as item data (Qt.UserRole + 2); every place that used to assume
visual position == index (_actual_index and its callers below) reads that
instead.

Reuses audio.playback's pure list functions (sort/shuffle/move/remove/
play-after-current) and audio.metadata.get_metadata as-is — both already
framework-neutral.
"""

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
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from audio import playback
from audio.metadata import get_display_title, get_metadata

logger = logging.getLogger(__name__)

COLUMNS = ["Title", "Artist", "Album", "Duration"]
COLUMN_WIDTHS = [200, 80, 100, 100]  # matches ui/playlist_view.py's tree.column() widths
BATCH_SIZE = 50
# ui/playlist_view.py:160-163 sets these same floors via ttk's minwidth=:
# Title/Artist/Album all stretch=True with their own minwidth, Duration
# stretch=False. MIN_COLUMN_WIDTHS mirrors that per-column, used as the
# floor in _on_section_resized's compensation math below.
MIN_COLUMN_WIDTHS = [150, 50, 60, 50]


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

    def __init__(self, state, palette: dict, parent=None):
        super().__init__(parent)
        self.state = state
        self.palette = palette
        self._load_id = 0
        self._search_text = ""
        self._pending_selection: List[int] = []
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
        self.search_clear = QPushButton("✕")
        self.search_clear.setObjectName("SearchClear")
        self.search_clear.setFixedSize(20, 20)
        self.search_clear.setCursor(Qt.PointingHandCursor)
        search_row.addWidget(self.search_clear)
        layout.addLayout(search_row)

        self._tree = _PlaylistTree(self)
        self._tree.setObjectName("PlaylistTree")  # frameless — see theme_bridge.py
        self._tree.setHeaderLabels(COLUMNS)
        self._tree.setRootIsDecorated(False)
        self._tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tree.setAlternatingRowColors(True)
        header = self._tree.header()
        # QHeaderView defaults sectionsMovable to True — dragging anywhere
        # on a header label (not just the boundary) reorders that whole
        # column instead of resizing it, which reads exactly like "the
        # whole table moves" if the drag didn't start precisely on the
        # thin resize handle. Not a feature this app wants (ttk's
        # Treeview doesn't support column reordering either); the fixed
        # logical-column-index assumptions elsewhere here (_actual_index's
        # data lives in column 0 specifically) would also break if the
        # visual order could diverge from the logical one.
        header.setSectionsMovable(False)
        # Every attempt so far to give Title a SPECIAL resize mode (Stretch,
        # or a synthetic event-filter-based handle at its boundary with
        # Artist) either lost the ability to drag Title's own boundary at
        # all, or (per direct log evidence from a real interactive session)
        # turned out to not reliably receive real mouse events the way a
        # headless offscreen test suggested it would. ui/playlist_view.py
        # sidesteps all of this by not treating Title specially in the
        # first place: Title/Artist/Album are ALL stretch=True with their
        # own minwidth (ui/playlist_view.py:160-162), Duration alone is
        # stretch=False — ttk's native Treeview handles resize+redistribute
        # entirely internally, no custom per-column-role logic at all.
        # Mirroring that: every column here is plain Interactive — this is
        # the one resize mode PROVEN reliable for real mouse drags in this
        # app (confirmed via the same log evidence: continuous, smooth,
        # pixel-by-pixel sectionResized events for a directly-dragged
        # Interactive column). _on_section_resized below then reacts to
        # sectionResized the same way ttk's stretch pool does — any column
        # being resized transfers the delta to its neighbor so the total
        # stays pinned to the tree's width — but every column keeps its own
        # fully-native, real, working drag handle; nothing here relies on
        # synthesizing one.
        for col in range(len(COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        # QTreeWidget's header defaults stretchLastSection to True (unlike
        # a bare QHeaderView) — without turning it off explicitly, Duration
        # (the last column) stretches instead of being managed by
        # _on_section_resized like the others.
        header.setStretchLastSection(False)
        for col, width in enumerate(COLUMN_WIDTHS):
            self._tree.setColumnWidth(col, width)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)
        self._tree.itemDoubleClicked.connect(self._on_double_clicked)
        layout.addWidget(self._tree)

        self.search_entry.textChanged.connect(self._on_search_text_changed)
        self.search_clear.clicked.connect(self.search_entry.clear)

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

    def refresh(self, select: Optional[List[int]] = None) -> None:
        """Clears and rebuilds the tree, but — matching
        ui/playlist_view.py's _start_progressive_insert docstring ("each
        row appears only once all its columns are ready, so there is never
        a visible empty-column state") — does NOT insert placeholder rows
        with blank Artist/Album/Duration up front. Rows are created by
        _on_metadata_batch only once their real metadata has arrived; an
        earlier version of this method inserted a full blank skeleton
        immediately and filled it in progressively, which is exactly the
        visible-empty-column state the original goes out of its way to
        avoid.

        Since rows no longer exist synchronously after this call returns,
        callers that want to select specific indices post-move (move_up/
        move_down restoring the shifted selection, rather than the
        pre-move one) must pass `select` — calling _select_indices() right
        after refresh() would silently do nothing, since the tree is still
        empty at that point and only catches up once metadata batches
        arrive.
        """
        self._load_id += 1
        load_id = self._load_id

        self._pending_selection = select if select is not None else self.get_selected_indices()
        self._tree.clear()
        self._load_metadata_async(load_id)

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
        for actual_index, path, meta in batch:
            title = meta.get("title") or os.path.basename(path)
            item = QTreeWidgetItem(["", meta.get("artist", ""), meta.get("album", ""), meta.get("duration", "")])
            item.setData(0, Qt.UserRole, path)
            item.setData(0, Qt.UserRole + 1, title)
            item.setData(0, Qt.UserRole + 2, actual_index)
            item.setTextAlignment(3, Qt.AlignCenter)
            # See refresh()'s comment history — without this, a drop
            # squarely on a row nests it as a child instead of reordering,
            # and _resync_from_internal_move only reads top-level items.
            item.setFlags(item.flags() & ~Qt.ItemIsDropEnabled)
            self._tree.addTopLevelItem(item)
        self._adjust_title_column_width()
        self.refresh_highlight()
        self._select_indices(self._pending_selection)

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
        menu.addAction("Remove", lambda: self._context_remove(index))
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _context_play_after_current(self, index: int) -> None:
        new_playlist, new_index = playback.play_after_current(self.state.playlist, [index], self.state.current_index)
        self.state.playlist = new_playlist
        self.state.current_index = new_index
        self.refresh()

    def _context_remove(self, index: int) -> None:
        new_playlist, new_index = playback.remove_selected_from_playlist(self.state.playlist, [index], self.state.current_index)
        self.state.playlist = new_playlist
        self.state.current_index = new_index
        self.refresh()

    def _on_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        self.track_activated.emit(self._actual_index(item))

    # ---------- menu-bar-driven operations (operate on selection) ----------

    def move_up(self) -> None:
        indices = self.get_selected_indices()
        if not indices:
            return
        self.state.playlist = playback.move_selected_up(self.state.playlist, indices)
        self.refresh(select=sorted({(i - 1 if i > 0 else i) for i in indices}))

    def move_down(self) -> None:
        indices = self.get_selected_indices()
        if not indices:
            return
        last = len(self.state.playlist) - 1
        self.state.playlist = playback.move_selected_down(self.state.playlist, indices)
        self.refresh(select=sorted({(i + 1 if i < last else i) for i in indices}))

    def remove_selected(self) -> None:
        indices = self.get_selected_indices()
        if not indices:
            return
        new_playlist, new_index = playback.remove_selected_from_playlist(self.state.playlist, indices, self.state.current_index)
        self.state.playlist = new_playlist
        self.state.current_index = new_index
        self.refresh()

    def play_after_current_selected(self) -> None:
        indices = self.get_selected_indices()
        if not indices:
            return
        new_playlist, new_index = playback.play_after_current(self.state.playlist, indices, self.state.current_index)
        self.state.playlist = new_playlist
        self.state.current_index = new_index
        self.refresh()

    def clear(self) -> None:
        self.state.playlist, self.state.current_index = playback.clear_playlist()
        self.refresh()

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
        # Hooked on this outer panel, not the inner _PlaylistTree: this
        # widget's size only changes when the splitter/window resizes it,
        # never as a side effect of a user dragging a column boundary
        # inside the tree.
        super().resizeEvent(event)
        self._adjust_title_column_width()

    def _adjust_title_column_width(self) -> None:
        """Grow Title to absorb whatever width Artist/Album/Duration don't
        need — called on this panel's own resize (see resizeEvent above)
        and again once rows land (_on_metadata_batch), since a vertical
        scrollbar appearing/disappearing changes the available width
        without resizing the panel itself.

        Computed from self._tree.width(), NOT self._tree.viewport().width():
        confirmed empirically that at the moment resizeEvent fires here,
        tree.width() already reflects the new size but viewport().width()
        can still be stale for an indeterminate number of event-loop
        ticks — tree.width() is reliably synchronous, since it's set
        directly by this panel's own layout as part of processing the
        resize that triggers this method in the first place.

        Wrapped in the same _in_section_resize guard _on_section_resized
        uses for its own programmatic calls: this method's setColumnWidth
        also fires sectionResized(0, ...), and without the guard,
        _on_section_resized would misread "the panel gained leftover
        space, give it to Title" as "the user dragged Title's boundary,
        steal the difference from Artist" — stealing space from Artist
        that never came from Artist in the first place."""
        other_width = sum(self._tree.columnWidth(c) for c in range(1, len(COLUMNS)))
        scrollbar = self._tree.verticalScrollBar()
        scrollbar_reserve = scrollbar.width() if scrollbar.isVisible() else 0
        frame = self._tree.frameWidth() * 2
        available = self._tree.width() - frame - scrollbar_reserve - other_width
        self._in_section_resize = True
        try:
            self._tree.setColumnWidth(0, max(MIN_COLUMN_WIDTHS[0], available))
        finally:
            self._in_section_resize = False

    def _on_section_resized(self, logical_index: int, old_size: int, new_size: int) -> None:
        """A chain, not a star: column N's own left edge is the boundary
        Qt attributes to column N-1 (it always reports the LEFT column of
        whatever boundary was dragged — confirmed via direct log evidence
        from a real session). Column N-1's width is what Qt is genuinely,
        natively changing as the mouse moves — that's what makes the
        boundary under the cursor actually follow the drag. Column N then
        silently absorbs the exact opposite delta, which (since N's own
        left edge = N-1's end, and N-1 just moved by delta) moves N's left
        edge along with the boundary while its OWN right edge — i.e.
        whatever comes after N — stays completely fixed. That's the
        illusion of "column N is being resized from its own left edge,"
        built entirely out of its native left-neighbor's real resize plus
        an equal-and-opposite compensation, chained pairwise: Title(0)
        absorbed-by/gives-to Artist(1) [confirmed working], Artist(1) vs.
        Album(2), Album(2) vs. Duration(3) — so partner is always
        logical_index + 1. Column 3 (Duration) never appears as
        logical_index for a real drag (nothing exists to its right for Qt
        to attribute a boundary to) so it's a no-op below.

        Same net effect as ttk's stretch pool (ui/playlist_view.py:160-163,
        Title/Artist/Album all stretch=True with their own minwidth): the
        four columns' total stays pinned to the tree's width, so a
        horizontal scrollbar never has a reason to appear, while every
        column keeps its own real, native Interactive drag handle — not a
        synthesized one.

        Growing a neighbor past what its partner can spare is capped, not
        just compensated, using MIN_COLUMN_WIDTHS as the floor (same
        per-column minimums as ttk's minwidth), so neither side can be
        squeezed to nothing or fought into unbounded growth.

        _in_section_resize guards against re-entrancy: both branches below
        call setColumnWidth on a column this same method listens to, which
        re-emits this signal for that column — without the guard, that
        echo would get reprocessed as a second, unrelated resize."""
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
