"""
Waveform seekbar. Peak extraction (soundfile block/seek sampling -> ffmpeg
fallback -> librosa fallback) is pure numpy/soundfile/subprocess logic.
Painting uses QPainter.drawRects() with two batched calls (played/
unplayed) — ~4-6ms/frame, vs. ~110ms/frame building a QPainterPath from
per-bar addRect() calls.
"""

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import warnings
from contextlib import contextmanager

import numpy as np
import shiboken6
import soundfile as sf
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


@contextmanager
def suppress_c_stderr():
    """Suppress C-level stderr output (silences libmpg123 warnings)."""
    try:
        with open(os.devnull, "w") as fnull:
            original_stderr_fd = sys.stderr.fileno()
            saved_stderr_fd = os.dup(original_stderr_fd)
            try:
                os.dup2(fnull.fileno(), original_stderr_fd)
                yield
            finally:
                os.dup2(saved_stderr_fd, original_stderr_fd)
                os.close(saved_stderr_fd)
    except Exception:
        yield


class WaveformSeekbarQt(QWidget):
    peaks_ready = Signal(object)  # np.ndarray

    def __init__(self, player, palette: dict, width: int = 360, height: int = 40, parent=None):
        super().__init__(parent)
        self.player = player
        self.palette = palette
        self.setFixedSize(width, height)
        self.setMouseTracking(True)

        self.waveform_data = None
        self.current_file = None
        self.audio_length = 0
        self.playhead_x = 0
        self.is_dragging = False

        self._waveform_thread = None

        self.apply_palette(palette)

        self.peaks_ready.connect(self._on_peaks_ready, Qt.QueuedConnection)

        self._playhead_timer = QTimer(self)
        self._playhead_timer.setInterval(50)  # 50ms is smoother for DJs (20fps)
        self._playhead_timer.timeout.connect(self._update_playhead)
        self._playhead_timer.start()

    # ---------- loading ----------

    def load_waveform(self, audio_file: str) -> None:
        if audio_file == self.current_file and self.waveform_data is not None:
            return

        self.clear()
        self.current_file = audio_file
        self.audio_length = self.player.get_length()

        if self._waveform_thread and self._waveform_thread.is_alive():
            return

        self._waveform_thread = threading.Thread(
            target=self._generate_waveform_worker, args=(audio_file,), daemon=True
        )
        self._waveform_thread.start()

    def _safe_emit_peaks(self, result) -> None:
        # Runs on the decode thread: if the widget was destroyed while
        # this was still decoding, the underlying C++ QObject is gone and
        # emit() raises RuntimeError rather than silently no-op'ing.
        if shiboken6.isValid(self):
            self.peaks_ready.emit(result)

    def _generate_waveform_worker(self, audio_file: str) -> None:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")

                try:
                    with suppress_c_stderr():
                        sf_f = sf.SoundFile(audio_file)

                    total_frames = len(sf_f)
                    sr = sf_f.samplerate

                    num_pixels = self.width() if self.width() > 0 else 400
                    samples_per_pixel = max(1, total_frames // num_pixels)
                    window = min(2048, samples_per_pixel)
                    peaks = np.zeros(num_pixels, dtype="float32")
                    failed_reads = 0

                    for i in range(num_pixels):
                        start_frame = i * samples_per_pixel
                        try:
                            sf_f.seek(start_frame)
                            data = sf_f.read(window, dtype="float32", always_2d=False)
                        except Exception:
                            data = None

                        if data is None or len(data) == 0:
                            peaks[i] = 0.0
                            failed_reads += 1
                        else:
                            if getattr(data, "ndim", 1) and data.ndim > 1:
                                data = data.mean(axis=1)
                            peaks[i] = float(np.max(np.abs(data))) if len(data) > 0 else 0.0

                    try:
                        sf_f.close()
                    except Exception:
                        pass

                    if failed_reads > 0:
                        # Some libsndfile MP3 decoders can seek() near the
                        # end of a file but silently return empty reads
                        # past some internal point, even though total_frames
                        # looks accurate — falls through to the sequential
                        # (non-seeking) fallback below instead of shipping
                        # a partially-blank waveform.
                        raise RuntimeError(f"{failed_reads} of {num_pixels} seek-based peak reads returned empty")

                    if peaks.max() > 0:
                        peaks = peaks / peaks.max()

                    self._safe_emit_peaks((peaks, (total_frames / sr) * 1000))
                    return

                except (sf.LibsndfileError, RuntimeError, Exception):
                    try:
                        with suppress_c_stderr():
                            y, sr = sf.read(audio_file, dtype="float32", always_2d=False)
                        if y.ndim > 1:
                            y = y.mean(axis=1)
                    except (sf.LibsndfileError, RuntimeError):
                        if shutil.which("ffmpeg"):
                            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                                tmpname = tmp.name
                            try:
                                subprocess.run(
                                    ["ffmpeg", "-y", "-i", audio_file, "-ar", "44100", "-ac", "1", tmpname],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL,
                                    check=True,
                                )
                                try:
                                    y, sr = sf.read(tmpname, dtype="float32", always_2d=False)
                                    if y.ndim > 1:
                                        y = y.mean(axis=1)
                                except Exception:
                                    with suppress_c_stderr():
                                        import librosa

                                        y, sr = librosa.load(tmpname, sr=None, mono=True)
                            finally:
                                try:
                                    os.unlink(tmpname)
                                except Exception:
                                    pass
                        else:
                            with suppress_c_stderr():
                                import librosa

                                y, sr = librosa.load(audio_file, sr=None, mono=True)

                    num_pixels = self.width() if self.width() > 0 else 400
                    samples_per_pixel = len(y) // num_pixels

                    if samples_per_pixel > 0:
                        y_trimmed = y[: num_pixels * samples_per_pixel]
                        chunks = y_trimmed.reshape(num_pixels, samples_per_pixel)
                        peaks = np.max(np.abs(chunks), axis=1)
                    else:
                        peaks = np.abs(y)

                    if peaks.max() > 0:
                        peaks = peaks / peaks.max()

                    self._safe_emit_peaks((peaks, (len(y) / sr) * 1000))

        except Exception as e:
            logger.error(f"Failed to generate waveform for {audio_file}: {e}")
            self._safe_emit_peaks((None, 0))

    def _on_peaks_ready(self, result) -> None:
        peaks, length_ms = result
        self.waveform_data = peaks
        if peaks is not None and length_ms:
            self.audio_length = length_ms
        self.update()

    # ---------- theming ----------

    def apply_palette(self, palette: dict) -> None:
        """Update cached colors and repaint. This widget paints its own
        colors via QPainter rather than QSS, so it can't pick up a
        stylesheet change automatically like everything else in ui_qt —
        this is the one explicit hook a theme change needs."""
        self.palette = palette
        self.bg_color = palette.get("waveform_bg", "#1a1a1a")
        self.played_color = palette.get("waveform_played", "#FF6B00")
        self.unplayed_color = palette.get("waveform_unplayed", "#404040")
        self.border_color = palette.get("waveform_border", "#808080")
        self.update()

    # ---------- painting ----------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)

        w, h = self.width(), self.height()
        painter.fillRect(self.rect(), QColor(self.bg_color))

        if self.waveform_data is None:
            pen_color = QColor(self.unplayed_color)
            painter.setPen(pen_color)
            center_y = h // 2
            painter.drawLine(QPointF(0, center_y), QPointF(w, center_y))
        else:
            n = len(self.waveform_data)
            if n and w > 0:
                center_y = h / 2
                max_h = h * 0.75
                px_w = w / n

                played_rects = []
                unplayed_rects = []
                for i in range(n):
                    amp = self.waveform_data[i]
                    # A minimum height so real silence still draws a thin
                    # bar, rather than a zero-height gap that reads as the
                    # waveform stopping short of the full width.
                    bar_h = max(amp * max_h / 2, 0.5)
                    x = i * px_w
                    rect = QRectF(x, center_y - bar_h, max(px_w, 1.0), bar_h * 2)
                    if x <= self.playhead_x:
                        played_rects.append(rect)
                    else:
                        unplayed_rects.append(rect)

                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(self.unplayed_color))
                painter.drawRects(unplayed_rects)
                painter.setBrush(QColor(self.played_color))
                painter.drawRects(played_rects)

                # Explicit playhead marker: the played/unplayed color split
                # alone is easy to miss on a loud/heavily-compressed track
                # where bars are all near max height and look "solid" either
                # way — a visible line makes progress unmistakable.
                marker_color = QColor(self.played_color).lighter(160)
                painter.setPen(marker_color)
                painter.drawLine(QPointF(self.playhead_x, 0), QPointF(self.playhead_x, h))

        # drawRect() fills with the current brush as well as stroking the
        # outline — without resetting it, this border draw would fill the
        # whole widget with whatever brush color the bars loop left set.
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(self.border_color))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    # ---------- playhead ----------

    def _update_playhead(self) -> None:
        if self.is_dragging:
            return
        try:
            current_time = self.player.get_time()
            total_length = self.player.get_length()
            if total_length > 0:
                self.audio_length = total_length
                progress_ratio = current_time / self.audio_length
                new_x = int(progress_ratio * self.width())
                if new_x != self.playhead_x:
                    self.playhead_x = new_x
                    self.update()
        except Exception as e:
            logger.error(f"Sync error: {e}")

    # ---------- seeking ----------

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.playhead_x = int(event.position().x())
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self.is_dragging:
            self.playhead_x = int(event.position().x())
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.is_dragging:
            self._seek_to_position(int(event.position().x()))
        self.is_dragging = False

    def _seek_to_position(self, x_position: int) -> None:
        try:
            if self.audio_length <= 0:
                self.audio_length = self.player.get_length()
            if self.audio_length <= 0:
                return
            ratio = max(0.0, min(x_position / self.width(), 1.0))
            target_time = int(ratio * self.audio_length)
            self.player.set_time(target_time)
        except Exception as e:
            logger.error(f"Error seeking to position {x_position}: {e}")

    # ---------- state ----------

    def clear(self) -> None:
        self.waveform_data = None
        self.current_file = None
        self.audio_length = 0
        self.playhead_x = 0
        self.update()
