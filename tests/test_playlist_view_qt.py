"""Tests for ui_qt/playlist_view.py."""
import logging

from unittest.mock import patch

import pytest
from PySide6.QtCore import Qt, QMimeData, QPointF, QUrl
from PySide6.QtGui import QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QLabel, QMessageBox

from app.state import AppState
from ui_qt.playlist_view import PlaylistViewQt

logging.disable(logging.CRITICAL)  # get_metadata logs errors for the fake paths used below


class _FakeSourceMixin:
    """QDropEvent/QDragMoveEvent.source() reflects the real QDrag that
    started the drag session — constructing an event by hand (no real
    QDrag) always gives source()=None, which is exactly what dropEvent()
    needs to correctly take the *external*-drop branch (event.source() is
    not self), but can't exercise the *internal*-reorder branch. This
    override lets tests explicitly control it either way."""

    def __init__(self, *args, fake_source=None):
        super().__init__(*args)
        self._fake_source = fake_source

    def source(self):
        return self._fake_source


class _FakeDragMoveEvent(_FakeSourceMixin, QDragMoveEvent):
    pass


class _FakeDropEvent(_FakeSourceMixin, QDropEvent):
    pass

PALETTE = {"highlight": "#FFF59D", "select_bg": "#A279EB"}


@pytest.fixture
def state():
    return AppState(playlist=["/tmp/a.mp3", "/tmp/b.mp3", "/tmp/c.mp3"])


@pytest.fixture
def view(qtbot, state):
    v = PlaylistViewQt(state, PALETTE)
    qtbot.addWidget(v)
    # Rows are only created once their metadata batch arrives via a queued
    # connection (see refresh()'s docstring) — wait for the initial load
    # before handing the view to a test, or topLevelItemCount() would be 0.
    qtbot.waitUntil(lambda: v._tree.topLevelItemCount() == len(state.playlist), timeout=2000)
    return v


def test_refresh_populates_rows(view, state):
    assert view._tree.topLevelItemCount() == len(state.playlist)
    for i, path in enumerate(state.playlist):
        assert view._tree.topLevelItem(i).data(0, Qt.UserRole) == path


def test_double_click_emits_track_activated(qtbot, view):
    item = view._tree.topLevelItem(1)
    with qtbot.waitSignal(view.track_activated, timeout=1000) as blocker:
        view._on_double_clicked(item, 0)
    assert blocker.args == [1]


def test_refresh_highlight_marks_current_row(view, state):
    state.current_index = 1
    view.refresh_highlight()
    assert view._tree.topLevelItem(1).text(0).startswith("▶")
    assert not view._tree.topLevelItem(0).text(0).startswith("▶")
    assert not view._tree.topLevelItem(2).text(0).startswith("▶")


def test_metadata_batch_creates_rows_only_for_ready_data(qtbot):
    """Regression test for the core fix: rows are created by
    _on_metadata_batch only once metadata has actually arrived — never as
    a blank-cell skeleton first. A stale (superseded) batch must not
    create any row at all, matching the load-id cancellation token."""
    empty_state = AppState(playlist=[])
    view = PlaylistViewQt(empty_state, PALETTE)
    qtbot.addWidget(view)

    stale_batch = [(0, "/tmp/b.mp3", {"title": "Stale", "artist": "X", "album": "Y", "duration": "0:01"})]
    view._on_metadata_batch(load_id=999, batch=stale_batch)  # wrong load_id, must be ignored
    assert view._tree.topLevelItemCount() == 0

    real_batch = [(0, "/tmp/b.mp3", {"title": "Real Title", "artist": "Real Artist", "album": "Real Album", "duration": "1:23"})]
    view._on_metadata_batch(load_id=view._load_id, batch=real_batch)
    assert view._tree.topLevelItemCount() == 1
    item = view._tree.topLevelItem(0)
    assert item.text(0) == "Real Title"
    assert item.text(1) == "Real Artist"
    assert item.text(2) == "Real Album"
    assert item.text(3) == "1:23"


def test_get_selected_indices(view):
    view._select_indices([0, 2])
    assert view.get_selected_indices() == [0, 2]


def test_move_up(qtbot, view, state):
    view._select_indices([1])
    view.move_up()
    assert state.playlist == ["/tmp/b.mp3", "/tmp/a.mp3", "/tmp/c.mp3"]
    qtbot.waitUntil(lambda: view.get_selected_indices() == [0], timeout=2000)


def test_move_down(qtbot, view, state):
    view._select_indices([1])
    view.move_down()
    assert state.playlist == ["/tmp/a.mp3", "/tmp/c.mp3", "/tmp/b.mp3"]
    qtbot.waitUntil(lambda: view.get_selected_indices() == [2], timeout=2000)


def test_remove_selected(view, state):
    state.current_index = 2
    view._select_indices([0])
    view.remove_selected()
    assert state.playlist == ["/tmp/b.mp3", "/tmp/c.mp3"]
    assert state.current_index == 1


def test_remove_selected_clears_selection_afterward(qtbot, view, state):
    # Regression: refresh()'s default (no select= passed) reselects by raw
    # index number, which after a removal refers to different remaining
    # songs the user never selected — not an empty selection.
    view._select_indices([0, 1])
    view.remove_selected()
    # Waits for the async row rebuild (and its per-item reselect decision)
    # to actually finish — state.playlist changes synchronously well before
    # that, so waiting on it alone would check selection too early to mean
    # anything either way.
    qtbot.waitUntil(lambda: view._tree.topLevelItemCount() == 1, timeout=2000)
    assert view.get_selected_indices() == []


def test_play_after_current_selected(view, state):
    state.current_index = 0
    view._select_indices([2])
    view.play_after_current_selected()
    assert state.playlist == ["/tmp/a.mp3", "/tmp/c.mp3", "/tmp/b.mp3"]


def test_clear(view, state):
    # clear() confirms via QMessageBox.question first.
    with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
        view.clear()
    assert state.playlist == []
    assert state.current_index is None
    assert view._tree.topLevelItemCount() == 0


def test_clear_cancelled_leaves_playlist_unchanged(view, state):
    original = list(state.playlist)
    with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
        view.clear()
    assert state.playlist == original


def test_sort_by_title_falls_back_to_basename(qtbot):
    # get_display_title falls back to os.path.basename for nonexistent
    # files, so this is deterministic without needing real tagged audio
    # files. Deliberately unsorted input so the test actually exercises
    # reordering (the shared fixture's a/b/c paths are already sorted).
    state = AppState(playlist=["/tmp/charlie.mp3", "/tmp/alpha.mp3", "/tmp/bravo.mp3"])
    view = PlaylistViewQt(state, PALETTE)
    qtbot.addWidget(view)

    view.sort_by_title()

    assert state.playlist == ["/tmp/alpha.mp3", "/tmp/bravo.mp3", "/tmp/charlie.mp3"]


def test_context_remove(view, state):
    state.current_index = None
    view._context_remove(1)
    assert state.playlist == ["/tmp/a.mp3", "/tmp/c.mp3"]


def test_context_remove_clears_selection_afterward(qtbot, view, state):
    view._select_indices([0, 1])
    view._context_remove(1)
    qtbot.waitUntil(lambda: view._tree.topLevelItemCount() == 2, timeout=2000)
    assert view.get_selected_indices() == []


def _build_context_menu_actions(view, row_index):
    # QMenu.exec() blocks on a real event loop waiting for a click that
    # will never come headlessly — mock QMenu entirely so _show_context_menu
    # runs to completion, and capture each addAction(label, callback) call
    # to invoke the one under test directly, same as a real click would.
    with patch("ui_qt.playlist_view.QMenu") as mock_menu_cls:
        mock_menu = mock_menu_cls.return_value
        pos = view._tree.visualItemRect(view._tree.topLevelItem(row_index)).center()
        view._show_context_menu(pos)
    return {call.args[0]: call.args[1] for call in mock_menu.addAction.call_args_list}


def test_context_menu_show_metadata_emits_signal_with_actual_index(qtbot, view):
    actions = _build_context_menu_actions(view, 1)
    with qtbot.waitSignal(view.show_track_info_requested, timeout=1000) as blocker:
        actions["Show Metadata"]()
    assert blocker.args == [1]


def test_context_menu_show_booklet_emits_signal_with_actual_index(qtbot, view):
    actions = _build_context_menu_actions(view, 2)
    with qtbot.waitSignal(view.show_booklet_requested, timeout=1000) as blocker:
        actions["Show Album Booklet"]()
    assert blocker.args == [2]


def test_context_menu_play_for_time_emits_signal_with_actual_index(qtbot, view):
    actions = _build_context_menu_actions(view, 1)
    with qtbot.waitSignal(view.set_time_limit_requested, timeout=1000) as blocker:
        actions["Play for time..."]()
    assert blocker.args == [1]


def test_context_menu_clear_time_limit_emits_signal_with_actual_index(qtbot, view):
    actions = _build_context_menu_actions(view, 2)
    with qtbot.waitSignal(view.clear_time_limit_requested, timeout=1000) as blocker:
        actions["Clear time limit"]()
    assert blocker.args == [2]


def test_row_shows_time_limit_instead_of_duration(qtbot, state):
    state.play_limits["/tmp/b.mp3"] = 45.0
    view = PlaylistViewQt(state, PALETTE)
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view._tree.topLevelItemCount() == 3, timeout=2000)

    row = view._tree.topLevelItem(1)
    assert row.text(3) == "⏱ 45s"


def test_row_shows_real_duration_without_limit(qtbot, view):
    row = view._tree.topLevelItem(0)
    assert "⏱" not in row.text(3)


def test_refresh_time_limit_display_updates_row_after_setting(view, state):
    state.play_limits["/tmp/b.mp3"] = 30.0
    view.refresh_time_limit_display(1)
    row = view._tree.topLevelItem(1)
    assert row.text(3) == "⏱ 30s"


def test_refresh_time_limit_display_updates_row_after_clearing(view, state):
    state.play_limits["/tmp/b.mp3"] = 30.0
    view.refresh_time_limit_display(1)
    del state.play_limits["/tmp/b.mp3"]
    view.refresh_time_limit_display(1)
    row = view._tree.topLevelItem(1)
    assert "⏱" not in row.text(3)


def test_internal_drag_resync_reorders_and_remaps_current_index(view, state):
    state.current_index = 1  # currently playing b.mp3

    # Simulate what Qt's native InternalMove drop already did visually:
    # move b.mp3 to the front.
    item_b = view._tree.takeTopLevelItem(1)
    view._tree.insertTopLevelItem(0, item_b)

    view._resync_from_internal_move()

    assert state.playlist == ["/tmp/b.mp3", "/tmp/a.mp3", "/tmp/c.mp3"]
    assert state.current_index == 0  # followed b.mp3 to its new position


def test_insert_external_files_inserts_at_index_and_shifts_current(view, state):
    state.current_index = 1  # b.mp3

    view._insert_external_files(["/tmp/new1.mp3", "/tmp/new2.mp3"], index=1)

    assert state.playlist == ["/tmp/a.mp3", "/tmp/new1.mp3", "/tmp/new2.mp3", "/tmp/b.mp3", "/tmp/c.mp3"]
    assert state.current_index == 3  # b.mp3 shifted right by 2


def test_add_files_with_no_index_appends_at_end(view, state):
    view.add_files(["/tmp/new.mp3"])
    assert state.playlist == ["/tmp/a.mp3", "/tmp/b.mp3", "/tmp/c.mp3", "/tmp/new.mp3"]


def test_header_label_text(view):
    header = view.findChild(QLabel, "PanelHeader")
    assert header is not None
    assert header.text() == "Playback queue"


def test_search_filters_by_title_substring(qtbot):
    # get_metadata falls back to the basename as "title" for unreadable
    # files (confirmed empirically — see waveform/controls test comments
    # elsewhere), so filtering by a distinctive basename is deterministic
    # without needing real tagged audio files.
    state = AppState(playlist=["/tmp/alpha_song.mp3", "/tmp/bravo_song.mp3", "/tmp/charlie_song.mp3"])
    view = PlaylistViewQt(state, PALETTE)
    qtbot.addWidget(view)

    view.search_entry.setText("bravo")
    qtbot.waitUntil(lambda: view._tree.topLevelItemCount() == 1, timeout=2000)

    assert view._tree.topLevelItem(0).data(0, Qt.UserRole) == "/tmp/bravo_song.mp3"


def test_search_preserves_actual_index_of_filtered_row(qtbot):
    state = AppState(playlist=["/tmp/alpha_song.mp3", "/tmp/bravo_song.mp3", "/tmp/charlie_song.mp3"])
    view = PlaylistViewQt(state, PALETTE)
    qtbot.addWidget(view)

    view.search_entry.setText("charlie")
    qtbot.waitUntil(lambda: view._tree.topLevelItemCount() == 1, timeout=2000)

    row = view._tree.topLevelItem(0)
    assert view._actual_index(row) == 2  # charlie's real position in the full playlist


def test_clearing_search_restores_all_rows(qtbot):
    state = AppState(playlist=["/tmp/alpha_song.mp3", "/tmp/bravo_song.mp3"])
    view = PlaylistViewQt(state, PALETTE)
    qtbot.addWidget(view)

    view.search_entry.setText("alpha")
    qtbot.waitUntil(lambda: view._tree.topLevelItemCount() == 1, timeout=2000)

    view.search_entry.clear()
    qtbot.waitUntil(lambda: view._tree.topLevelItemCount() == 2, timeout=2000)


def test_manual_selection_survives_later_metadata_batch(qtbot):
    # Regression: _on_metadata_batch used to reselect the tree's whole
    # _pending_selection (captured once, before search results existed)
    # after *every* batch, silently wiping out a selection the user made
    # by hand while later batches were still streaming in — as happens
    # with real files, where per-track metadata reads take real time.
    state = AppState(playlist=["/tmp/a.mp3"])
    view = PlaylistViewQt(state, PALETTE)
    qtbot.addWidget(view)
    qtbot.waitUntil(lambda: view._tree.topLevelItemCount() == 1, timeout=2000)

    # Simulate the user clicking the row that arrived in an earlier batch.
    view._select_indices([0])
    assert view.get_selected_indices() == [0]

    # A later batch (e.g. more search results still streaming in for other,
    # not-yet-added tracks) must not clobber that manual selection.
    view._on_metadata_batch(view._load_id, [(1, "/tmp/extra.mp3", {"title": "extra"})])
    assert view.get_selected_indices() == [0]


def test_internal_drag_resync_ignored_while_search_active(qtbot):
    state = AppState(playlist=["/tmp/alpha_song.mp3", "/tmp/bravo_song.mp3", "/tmp/charlie_song.mp3"])
    view = PlaylistViewQt(state, PALETTE)
    qtbot.addWidget(view)
    view.search_entry.setText("song")  # matches all three, but filter is "active"

    view._resync_from_internal_move()  # must not corrupt state.playlist

    assert state.playlist == ["/tmp/alpha_song.mp3", "/tmp/bravo_song.mp3", "/tmp/charlie_song.mp3"]


# ---------- real Qt drop dispatch (not just the post-processing helpers) ----------

def test_items_are_not_drop_enabled_to_prevent_accidental_nesting(view):
    """Regression test: QTreeWidget's default drop handling treats a drop
    squarely on a row (vs. between rows) as "nest as a child" unless the
    item opts out — a real risk for a flat list, since a nested row is
    invisible to _resync_from_internal_move's top-level-only scan and
    would silently vanish from state.playlist. Confirmed empirically by
    toggling this flag and checking dropIndicatorPosition() before this
    fix existed."""
    for i in range(view._tree.topLevelItemCount()):
        item = view._tree.topLevelItem(i)
        assert not (item.flags() & Qt.ItemIsDropEnabled)


def test_external_multi_file_drop_inserts_at_correct_position(qtbot):
    """End-to-end: real QDropEvent dispatched through the actual
    dropEvent() override (not just calling _insert_external_files
    directly), verifying the whole path — indicator computation, drop
    position resolution, multi-file insertion order — together. This path
    doesn't depend on Qt's startDrag()/QDrag lifecycle the way an
    *internal* reorder does (see the module-level _FakeSourceMixin
    docstring), so it can be verified fully synthetically."""
    state = AppState(playlist=["/tmp/x.mp3", "/tmp/y.mp3"])
    view = PlaylistViewQt(state, PALETTE)
    qtbot.addWidget(view)
    view.resize(400, 200)
    view.show()
    qtbot.waitUntil(lambda: view._tree.topLevelItemCount() == 2, timeout=2000)

    tree = view._tree
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile("/tmp/new1.mp3"), QUrl.fromLocalFile("/tmp/new2.mp3")])

    target = tree.topLevelItem(1)  # y.mp3
    rect = tree.visualRect(tree.indexFromItem(target))
    drop_pos = QPointF(rect.center().x(), rect.top() + 2)  # near the top edge -> AboveItem

    move_event = _FakeDragMoveEvent(drop_pos.toPoint(), Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier, fake_source=None)
    tree.dragMoveEvent(move_event)

    drop_event = _FakeDropEvent(drop_pos, Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier, QDropEvent.Type.Drop, fake_source=None)
    tree.dropEvent(drop_event)

    assert state.playlist == ["/tmp/x.mp3", "/tmp/new1.mp3", "/tmp/new2.mp3", "/tmp/y.mp3"]


def test_external_drop_with_no_target_appends_at_end(qtbot):
    state = AppState(playlist=["/tmp/x.mp3"])
    view = PlaylistViewQt(state, PALETTE)
    qtbot.addWidget(view)
    view.resize(400, 200)
    view.show()

    tree = view._tree
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile("/tmp/new.mp3")])
    # well below any real row -> itemAt() returns None
    drop_pos = QPointF(50, 190)

    drop_event = _FakeDropEvent(drop_pos, Qt.MoveAction, mime, Qt.LeftButton, Qt.NoModifier, QDropEvent.Type.Drop, fake_source=None)
    tree.dropEvent(drop_event)

    assert state.playlist == ["/tmp/x.mp3", "/tmp/new.mp3"]
