"""
Bridges audio.audio_player.AudioPlayer's background-thread callbacks into
Qt signals.

AudioPlayer.on_track_end fires from a PortAudio callback-finished thread,
never the Qt UI thread. PlayerBridge is a plain QObject created on the UI
thread; AudioPlayer is given `bridge.track_ended.emit` as its callback.
Calling `.emit()` from a worker thread is safe — Qt detects that the
connected slot's receiver lives on a different thread than the thread
currently calling emit() and auto-queues delivery onto that thread's event
loop, the same mechanism Tk's `root.after(0, fn)` hop was standing in for.
"""

from PySide6.QtCore import QObject, Signal


class PlayerBridge(QObject):
    track_ended = Signal()
