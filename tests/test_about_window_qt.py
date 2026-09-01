"""Tests for ui_qt/about_window.py."""
from PySide6.QtWidgets import QLabel, QPushButton

from ui_qt.about_window import AboutWindowQt

PALETTE = {"accent": "#BB86FC"}


def test_shows_without_error(qtbot):
    win = AboutWindowQt(None, PALETTE)
    qtbot.addWidget(win)
    win.show()
    assert win.isVisible()


def test_title_is_about(qtbot):
    win = AboutWindowQt(None, PALETTE)
    qtbot.addWidget(win)
    assert win.windowTitle() == "About"


def test_shows_description_and_version_text(qtbot):
    win = AboutWindowQt(None, PALETTE)
    qtbot.addWidget(win)
    texts = [label.text() for label in win.findChildren(QLabel)]
    assert any("audio player" in t for t in texts)
    assert "Version 1.0.0" in texts


def test_logo_pixmap_loads_from_real_asset(qtbot):
    # Real, unmocked asset load — assets/logo-no-background.png ships with
    # the repo, so this should never fall back to the text-title path.
    win = AboutWindowQt(None, PALETTE)
    qtbot.addWidget(win)
    pixmap_labels = [label for label in win.findChildren(QLabel) if not label.pixmap().isNull()]
    assert len(pixmap_labels) == 1


def test_ok_button_is_default_and_closes_dialog(qtbot):
    win = AboutWindowQt(None, PALETTE)
    qtbot.addWidget(win)
    win.show()
    ok_btn = next(b for b in win.findChildren(QPushButton) if b.text() == "OK")
    assert ok_btn.isDefault() is True

    ok_btn.click()
    assert win.result() == AboutWindowQt.Accepted
