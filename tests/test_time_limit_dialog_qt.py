"""Tests for ui_qt/time_limit_dialog.py."""
from ui_qt.time_limit_dialog import TimeLimitDialogQt


def test_presets_populate_entry(qtbot):
    dialog = TimeLimitDialogQt(None)
    qtbot.addWidget(dialog)

    dialog._apply_preset(10)
    assert dialog.entry.text() == "10"
    dialog._apply_preset(30)
    assert dialog.entry.text() == "30"
    dialog._apply_preset(60)
    assert dialog.entry.text() == "60"
    dialog._apply_preset(120)
    assert dialog.entry.text() == "120"


def test_set_with_valid_input_accepts_with_result(qtbot):
    dialog = TimeLimitDialogQt(None)
    qtbot.addWidget(dialog)

    dialog.entry.setText("45")
    dialog._on_set()

    assert dialog.result == 45.0


def test_set_with_invalid_input_does_not_close(qtbot):
    dialog = TimeLimitDialogQt(None)
    qtbot.addWidget(dialog)

    dialog.entry.setText("not a number")
    dialog._on_set()
    assert dialog.result == "CANCEL"


def test_set_with_empty_input_does_not_close(qtbot):
    dialog = TimeLimitDialogQt(None)
    qtbot.addWidget(dialog)

    dialog.entry.setText("")
    dialog._on_set()
    assert dialog.result == "CANCEL"


def test_set_with_zero_or_negative_input_does_not_close(qtbot):
    dialog = TimeLimitDialogQt(None)
    qtbot.addWidget(dialog)

    dialog.entry.setText("0")
    dialog._on_set()
    assert dialog.result == "CANCEL"

    dialog.entry.setText("-5")
    dialog._on_set()
    assert dialog.result == "CANCEL"


def test_clear_sets_result_to_none(qtbot):
    dialog = TimeLimitDialogQt(None)
    qtbot.addWidget(dialog)

    dialog._on_clear()
    assert dialog.result is None


def test_cancel_leaves_result_as_cancel_sentinel(qtbot):
    dialog = TimeLimitDialogQt(None)
    qtbot.addWidget(dialog)

    dialog.cancel_btn.click()
    assert dialog.result == "CANCEL"


def test_current_limit_prefills_entry(qtbot):
    dialog = TimeLimitDialogQt(None, current_limit=90.0)
    qtbot.addWidget(dialog)
    assert dialog.entry.text() == "90"


def test_no_current_limit_leaves_entry_empty(qtbot):
    dialog = TimeLimitDialogQt(None, current_limit=None)
    qtbot.addWidget(dialog)
    assert dialog.entry.text() == ""
