"""Tests for ui_qt/booklet_viewer_window.py."""
import struct
import zlib
from unittest.mock import patch

import pytest

from ui_qt.booklet_viewer_window import BookletViewerWindowQt

PALETTE = {"bg": "#1E1E1E", "fg": "#CCCCCB", "tree_bg": "#252526", "border": "#3E3E3E"}


def _png(width=10, height=1):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    raw = zlib.compress(bytes([0]) + bytes([255, 0, 0] * width) * height)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", raw)
        + chunk(b"IEND", b"")
    )


def _make_window(qtbot, images):
    with patch("ui_qt.booklet_viewer_window.get_booklet_images", return_value=images):
        win = BookletViewerWindowQt(None, "/tmp/song.mp3", PALETTE)
    qtbot.addWidget(win)
    win.resize(800, 600)
    win.show()
    qtbot.waitExposed(win)
    return win


def test_zero_images_shows_placeholder_and_disables_nav(qtbot):
    win = _make_window(qtbot, [])
    assert win.image_label.text() == "No booklet images available for this track."
    assert not win.prev_button.isEnabled()
    assert not win.next_button.isEnabled()


def test_single_image_disables_both_nav_buttons(qtbot):
    win = _make_window(qtbot, [(_png(), "Front cover", "APIC Type 3")])
    assert win.counter_label.text() == "Image 1 of 1"
    assert not win.prev_button.isEnabled()
    assert not win.next_button.isEnabled()
    assert win.info_label.text() == "Type: APIC Type 3 | Description: Front cover"


def test_multiple_images_nav_bounds_and_counter(qtbot):
    images = [(_png(), "Front", "APIC Type 3"), (_png(), "Back", "APIC Type 4"), (_png(), "Booklet p1", "Folder Image")]
    win = _make_window(qtbot, images)

    assert win.counter_label.text() == "Image 1 of 3"
    assert not win.prev_button.isEnabled()
    assert win.next_button.isEnabled()

    win._next_image()
    assert win.counter_label.text() == "Image 2 of 3"
    assert win.prev_button.isEnabled()
    assert win.next_button.isEnabled()

    win._next_image()
    assert win.counter_label.text() == "Image 3 of 3"
    assert not win.next_button.isEnabled()

    win._next_image()  # already at last image -> no-op
    assert win.counter_label.text() == "Image 3 of 3"

    win._previous_image()
    assert win.counter_label.text() == "Image 2 of 3"


def test_corrupt_image_shows_error_without_raising(qtbot):
    win = _make_window(qtbot, [(b"not-a-real-image", "desc", "APIC Type 3")])
    assert win.image_label.text() == "Error loading image: image data is corrupted"
    assert win.counter_label.text() == "Image 1 of 1"
    assert not win.prev_button.isEnabled()
    assert not win.next_button.isEnabled()


def test_small_image_is_not_upscaled(qtbot):
    win = _make_window(qtbot, [(_png(width=10, height=1), "desc", "APIC Type 3")])
    pixmap = win.image_label.pixmap()
    assert not pixmap.isNull()
    assert pixmap.width() == 10
    assert pixmap.height() == 1
