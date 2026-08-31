"""Tests for ui_qt/dj_view.py. Mirrors tests/test_dj_frame_view.py (Tk) for
intent, plus regression coverage for this port's two deliberate fixes: the
overall-LUFS sentinel no longer blanks the live meters, and BPM/Key save
now unifies which cached estimate stays available for re-save."""
from unittest.mock import MagicMock, patch

import pytest

from app.state import AppState
from ui_qt.dj_view import DJViewQt

PALETTE = {"status_fg": "#505050", "status_meta_fg": "#202020", "status_border": "#D0D0D0"}


@pytest.fixture
def state():
    return AppState(playlist=["/tmp/a.mp3", "/tmp/b.mp3"], current_index=0)


@pytest.fixture
def theme():
    t = MagicMock()
    t.palette = PALETTE
    return t


@pytest.fixture
def settings():
    return MagicMock()


@pytest.fixture
def player():
    return MagicMock()


@pytest.fixture
def view(qtbot, state, theme, settings, player):
    v = DJViewQt(state, theme, settings, player)
    qtbot.addWidget(v)
    v.show()
    yield v
    v.shutdown()


def test_registers_metrics_callback_on_construction(view, player):
    player.set_audio_metrics_callback.assert_called_with(view._emit_metrics)


def test_update_meter_values_only_touches_overall_when_passed(view):
    view.update_meter_values(lufs=-10.0, peak_dbfs=-5.0, limiter_activity=0.2)
    assert view.overall_lufs_value == -60.0
    view.update_meter_values(lufs=-10.0, peak_dbfs=-5.0, limiter_activity=0.2, overall_lufs=-8.0)
    assert view.overall_lufs_value == -8.0


def test_metrics_sentinel_leaves_live_meters_unchanged(view):
    view._on_metrics_ready(-12.0, -60.0, -3.0, 0.5, 0.6)
    assert view.lufs_label.text() == "-12.0"

    view._on_metrics_ready(-60.0, -9.4, -60.0, 0.0, 0.0)
    assert view.overall_lufs_label.text() == "-9.4"
    assert view.lufs_label.text() == "-12.0"  # unchanged, not blanked


def test_key_display_prefers_metadata_camelot_over_computed(view):
    # bpm included so the BPM branch is satisfied too and doesn't fall
    # through to a real analysis_manager.submit_bpm_analysis() call.
    meta = {"key": "Am", "camelot": "8A", "bpm": 120}
    with patch("ui_qt.dj_view.get_metadata", return_value=meta), \
         patch("ui_qt.dj_view.get_display_bpm", return_value="120"), \
         patch("ui_qt.dj_view.key_to_camelot", return_value="SHOULD_NOT_BE_USED"):
        view.update_info("/tmp/a.mp3")
    assert view.key_label.text() == "8A"


def test_cached_estimates_reused_without_resubmitting(view):
    view.temporary_bpm_values["/tmp/a.mp3"] = 120.0
    view.temporary_key_values["/tmp/a.mp3"] = "Am"
    meta = {}
    with patch("ui_qt.dj_view.get_metadata", return_value=meta), \
         patch("ui_qt.dj_view.get_display_bpm", side_effect=lambda b: str(b) if b else None), \
         patch("ui_qt.dj_view.analysis_manager") as mock_manager:
        view.update_info("/tmp/a.mp3")
    mock_manager.submit_bpm_analysis.assert_not_called()
    mock_manager.submit_key_analysis.assert_not_called()
    assert view.save_btn.isVisible()
    assert view.save_key_btn.isVisible()


def test_uncached_track_submits_fresh_analysis_with_qt_scheduler(view):
    with patch("ui_qt.dj_view.get_metadata", return_value={}), \
         patch("ui_qt.dj_view.get_display_bpm", return_value=None), \
         patch("ui_qt.dj_view.analysis_manager") as mock_manager:
        view.update_info("/tmp/a.mp3")
    mock_manager.submit_bpm_analysis.assert_called_once_with(
        "/tmp/a.mp3", view._on_bpm_analysis_complete, view._qt_scheduler
    )
    mock_manager.submit_key_analysis.assert_called_once_with(
        "/tmp/a.mp3", view._finish_key_estimation, view._qt_scheduler
    )


def test_hidden_widget_does_not_submit_analysis(qtbot, state, theme, settings, player):
    v = DJViewQt(state, theme, settings, player)
    qtbot.addWidget(v)
    # Deliberately not shown -> is_visible() is False.
    with patch("ui_qt.dj_view.get_metadata", return_value={}), \
         patch("ui_qt.dj_view.get_display_bpm", return_value=None), \
         patch("ui_qt.dj_view.analysis_manager") as mock_manager:
        v.update_info("/tmp/a.mp3")
    mock_manager.submit_bpm_analysis.assert_not_called()
    assert v.bpm_label.text() == "--"
    v.shutdown()


def test_stale_completion_is_dropped(view):
    view._estimating_file = "/tmp/b.mp3"
    view._finish_estimation("/tmp/a.mp3", 128.0)
    assert view.bpm_label.text() != "128"
    assert "/tmp/a.mp3" not in view.temporary_bpm_values


def test_bpm_and_key_both_stay_cached_after_successful_save(view):
    view.temporary_bpm_values["/tmp/a.mp3"] = 120.0
    view.temporary_key_values["/tmp/a.mp3"] = "Am"
    view._on_bpm_save_complete("/tmp/a.mp3", True)
    view._on_key_save_complete("/tmp/a.mp3", True)
    assert "/tmp/a.mp3" in view.temporary_bpm_values
    assert "/tmp/a.mp3" in view.temporary_key_values
    assert not view.save_btn.isVisible()
    assert not view.save_key_btn.isVisible()


def test_analysis_manager_scheduler_is_framework_agnostic():
    """Regression test for the audio/bpm.py root_widget -> scheduler
    refactor: any plain scheduler(func, *args) callable works, decoupled
    from both Tk and Qt."""
    from audio.bpm import AnalysisManager

    manager = AnalysisManager()
    calls = []

    def fake_scheduler(func, *args):
        calls.append((func, args))
        func(*args)

    received = {}

    def callback(filepath, data):
        received["filepath"] = filepath
        received["data"] = data

    manager.callbacks[("analyze_bpm", "/tmp/a.mp3")] = (callback, fake_scheduler)
    manager.output_queue.put(("analyze_bpm", "/tmp/a.mp3", 120.0, None))
    manager.running = True

    # Drain one result synchronously (mirrors _result_listener's own loop body).
    result = manager.output_queue.get(timeout=1.0)
    task_type, filepath, data, error = result
    callback_info = manager.callbacks.pop((task_type, filepath), None)
    cb, scheduler = callback_info
    scheduler(cb, filepath, data)

    assert calls == [(callback, ("/tmp/a.mp3", 120.0))]
    assert received == {"filepath": "/tmp/a.mp3", "data": 120.0}


