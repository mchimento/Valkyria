"""
Bridges audio.audio_player.AudioPlayer's background-thread callbacks into
Qt signals.
"""

from PySide6.QtCore import QObject, Signal


class PlayerBridge(QObject):
    track_ended = Signal()
