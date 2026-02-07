"""
Waveform Seekbar component for audio visualization and seeking.

Provides a visual representation of audio waveform with interactive seeking capabilities.
"""

import logging
import threading
import warnings
import os
import sys
import customtkinter as ctk
import soundfile as sf
import numpy as np
import tempfile
import subprocess
import shutil
from contextlib import contextmanager

logger = logging.getLogger(__name__)

@contextmanager
def suppress_c_stderr():
    """
    Context manager to suppress C-level stderr output.
    Useful for silencing libmpg123 warnings.
    """
    try:
        # Open a null file
        with open(os.devnull, 'w') as fnull:
            # Save the original stderr file descriptor
            original_stderr_fd = sys.stderr.fileno()
            saved_stderr_fd = os.dup(original_stderr_fd)

            try:
                # Redirect stderr to null
                os.dup2(fnull.fileno(), original_stderr_fd)
                yield
            finally:
                # Restore stderr
                os.dup2(saved_stderr_fd, original_stderr_fd)
                os.close(saved_stderr_fd)
    except Exception:
        # If anything goes wrong (e.g. no fileno), just execute code
        yield


class WaveformSeekbar(ctk.CTkCanvas):
    """
    A waveform seekbar that visualizes audio and allows interactive seeking.

    Features:
    - Visual waveform representation using librosa
    - Real-time playhead synchronization
    - Click and drag seeking
    - Visual distinction between played/unplayed sections
    - Background waveform generation to prevent UI freezing
    """

    def __init__(self, master, player, theme, width=400, height=60, **kwargs):
        """
        Initialize the WaveformSeekbar.

        Args:
            master: Parent widget
            player: Audio player instance with get_time() and set_time() methods
            theme: Theme manager instance with palette
            width: Canvas width in pixels
            height: Canvas height in pixels
        """
        # Explicitly filter out all CTk-specific options that aren't supported by standard Canvas
        unsupported_options = ['bg_color', 'fg_color', 'border_width', 'corner_radius',
                              'hover_color', 'text_color', 'font', 'anchor']

        # Create clean kwargs for the parent Canvas
        clean_kwargs = {}
        for key, value in kwargs.items():
            if key not in unsupported_options:
                clean_kwargs[key] = value

        # Initialize with clean kwargs only
        super().__init__(master, width=width, height=height, **clean_kwargs)

        # Get colors from theme palette
        palette = theme.palette if hasattr(theme, 'palette') else {}
        self.bg_color = palette.get("waveform_bg", "#1a1a1a")
        self.played_color = palette.get("waveform_played", "#FF6B00")
        self.unplayed_color = palette.get("waveform_unplayed", "#404040")
        self.border_color = palette.get("waveform_border", "#808080")

        # Set canvas background color
        self.configure(bg=self.bg_color, highlightthickness=1, highlightbackground=self.border_color)

        self.player = player
        self.theme = theme
        self.width = width
        self.height = height

        # Waveform data
        self.waveform_data = None
        self.current_file = None
        self.audio_length = 0

        # UI state
        self.playhead_x = 0
        self.is_dragging = False

        # Threading
        self.waveform_thread = None
        self.waveform_lock = threading.Lock()

        # Canvas items
        self.waveform_items = []
        self.placeholder_line = None

        # Bind mouse events
        self.bind('<Button-1>', self._on_click)
        self.bind('<B1-Motion>', self._on_drag)
        self.bind('<ButtonRelease-1>', self._on_release)

        # Also bind to canvas directly for better event capture
        self.bind('<ButtonPress-1>', self._on_click)

        # Start update loop
        self._update_playhead()

        # Draw initial placeholder line
        self._draw_placeholder_line()

    def load_waveform(self, audio_file: str):
        """
        Load and generate waveform for the given audio file.

        Args:
            audio_file: Path to the audio file
        """
        if audio_file == self.current_file and self.waveform_data is not None:
            return  # Already loaded

        # Clear existing waveform before loading new one
        self._clear_waveform()

        self.current_file = audio_file
        # Update audio length from player
        self.audio_length = self.player.get_length()
        logger.debug(f"Loading waveform for {audio_file}, length: {self.audio_length}ms")

        # Start waveform generation in background thread
        if self.waveform_thread and self.waveform_thread.is_alive():
            return  # Already generating

        self.waveform_thread = threading.Thread(
            target=self._generate_waveform_worker,
            args=(audio_file,),
            daemon=True
        )
        self.waveform_thread.start()

    def _generate_waveform_worker(self, audio_file: str):
        """
        Worker function to generate waveform data in background thread.

        Args:
            audio_file: Path to the audio file
        """
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")

                # Optimized path: use block/seek sampling using SoundFile to avoid decoding entire file
                try:
                    with suppress_c_stderr():
                        sf_f = sf.SoundFile(audio_file)

                    total_frames = len(sf_f)
                    sr = sf_f.samplerate

                    num_pixels = self.width if self.width > 0 else 400
                    samples_per_pixel = max(1, total_frames // num_pixels)

                    # Read only a small window per pixel (reduces I/O & CPU for large files)
                    window = min(2048, samples_per_pixel)
                    peaks = np.zeros(num_pixels, dtype='float32')

                    for i in range(num_pixels):
                        start_frame = i * samples_per_pixel
                        try:
                            sf_f.seek(start_frame)
                            data = sf_f.read(window, dtype='float32', always_2d=False)
                        except Exception:
                            data = None

                        if data is None or len(data) == 0:
                            peaks[i] = 0.0
                        else:
                            if getattr(data, 'ndim', 1) and data.ndim > 1:
                                data = data.mean(axis=1)
                            peaks[i] = float(np.max(np.abs(data))) if len(data) > 0 else 0.0

                    try:
                        sf_f.close()
                    except Exception:
                        pass

                    # Normalize the peaks to 0-1 range based on the track's loudest point
                    if peaks.max() > 0:
                        peaks = peaks / peaks.max()

                    # Save data and update length
                    with self.waveform_lock:
                        self.waveform_data = peaks
                        self.audio_length = (total_frames / sr) * 1000

                    # Schedule UI update
                    self.after(0, self._draw_waveform)
                    return

                except (sf.LibsndfileError, RuntimeError, Exception):
                    # Fall back to the previous logic which tries soundfile full-read, ffmpeg conversion, or librosa
                    try:
                        # Suppress C-level warnings from libmpg123
                        with suppress_c_stderr():
                            y, sr = sf.read(audio_file, dtype='float32', always_2d=False)

                        # Convert to mono if stereo
                        if y.ndim > 1:
                            y = y.mean(axis=1)

                    except (sf.LibsndfileError, RuntimeError):
                        # Fallback: try ffmpeg decode to WAV and read with soundfile
                        if shutil.which('ffmpeg'):
                            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                                tmpname = tmp.name
                            try:
                                # Prevent console window on Windows (PyInstaller)
                                import sys
                                if sys.platform == 'win32':
                                    creationflags = subprocess.CREATE_NO_WINDOW
                                else:
                                    creationflags = 0
                                subprocess.run([
                                    'ffmpeg', '-y', '-i', audio_file,
                                    '-ar', '44100', '-ac', '1', tmpname
                                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, creationflags=creationflags)
                                try:
                                    y, sr = sf.read(tmpname, dtype='float32', always_2d=False)
                                    if y.ndim > 1:
                                        y = y.mean(axis=1)
                                except Exception:
                                    # Fallback to librosa if soundfile can't read decoded WAV
                                    with suppress_c_stderr():
                                        import librosa
                                        y, sr = librosa.load(tmpname, sr=None, mono=True)
                            finally:
                                try:
                                    os.unlink(tmpname)
                                except Exception:
                                    pass
                        else:
                            # Final fallback to librosa (may use audioread)
                            with suppress_c_stderr():
                                import librosa
                                y, sr = librosa.load(audio_file, sr=None, mono=True)

                    # Calculate the max peak for every pixel on the canvas
                    num_pixels = self.width
                    if num_pixels <= 0: num_pixels = 400 # Fallback

                    # Calculate how many audio samples represent one horizontal pixel
                    samples_per_pixel = len(y) // num_pixels

                    if samples_per_pixel > 0:
                        # Reshape the array to (num_pixels, samples_per_pixel)
                        # and find the absolute maximum in each chunk
                        y_trimmed = y[:num_pixels * samples_per_pixel]
                        chunks = y_trimmed.reshape(num_pixels, samples_per_pixel)
                        peaks = np.max(np.abs(chunks), axis=1)
                    else:
                        # For very short files, just use the raw data
                        peaks = np.abs(y)

                    # Normalize the peaks to 0-1 range based on the track's loudest point
                    if peaks.max() > 0:
                        peaks = peaks / peaks.max()

                    # Save data and update length
                    with self.waveform_lock:
                        self.waveform_data = peaks
                        self.audio_length = (len(y) / sr) * 1000

                    # Schedule UI update
                    self.after(0, self._draw_waveform)

        except Exception as e:
            logger.error(f"Failed to generate waveform for {audio_file}: {e}")
            # Clear waveform on error and show placeholder
            with self.waveform_lock:
                self.waveform_data = None
            try:
                self.after(0, self.clear)
            except Exception:
                pass

    def _draw_waveform(self):
        self._clear_waveform()

        # Remove placeholder line when drawing actual waveform
        if self.placeholder_line:
            self.delete(self.placeholder_line)
            self.placeholder_line = None

        with self.waveform_lock:
            if self.waveform_data is None:
                return

            center_y = self.height // 2
            max_height = self.height * 0.75

            # We draw exactly one bar per pixel to match self.width
            for x in range(len(self.waveform_data)):
                amplitude = self.waveform_data[x]
                bar_height = amplitude * max_height / 2

                top_y = center_y - bar_height
                bottom_y = center_y + bar_height

                # Create the rectangle with a generic tag 'waveform'
                # and a specific tag for its x-position 'rx_{x}'
                bar_id = self.create_rectangle(
                    x, top_y, x + 1, bottom_y,
                    fill=self.unplayed_color,
                    outline='',
                    tags=('waveform', f'rx_{x}')
                )
                self.waveform_items.append(bar_id)

        self._update_waveform_colors()

    def _clear_waveform(self):
        """Clear all waveform items from canvas."""
        for item in self.waveform_items:
            self.delete(item)
        self.waveform_items.clear()

    def _draw_placeholder_line(self):
        """Draw a horizontal placeholder line when no waveform is loaded."""
        # Remove existing placeholder line if any
        if self.placeholder_line:
            self.delete(self.placeholder_line)

        # Draw horizontal line at center of canvas
        center_y = self.height // 2
        self.placeholder_line = self.create_line(
            0, center_y,
            self.width, center_y,
            fill=self.unplayed_color,
            width=1,
            tags='placeholder'
        )


    def _update_waveform_colors(self):
        """Update waveform bar colors based on playhead position using area selection."""
        if not self.waveform_items:
            return

        # 1. Reset all bars to 'unplayed' color (optional, but safe for seeking)
        self.itemconfig('waveform', fill=self.unplayed_color)

        # 2. Find all items from X=0 to X=playhead_x
        # find_enclosed or find_overlapping works here
        # We use a small buffer (+1) to ensure we catch the bar under the playhead
        played_items = self.find_overlapping(0, 0, self.playhead_x, self.height)

        for item_id in played_items:
            # Only color items that belong to the 'waveform' group
            tags = self.gettags(item_id)
            if 'waveform' in tags:
                self.itemconfig(item_id, fill=self.played_color)

    def _update_playhead(self):
        if self.is_dragging:
            self.after(100, self._update_playhead)
            return

        try:
            current_time = self.player.get_time()
            # Ensure we always have the latest length from VLC
            total_length = self.player.get_length()

            if total_length > 0:
                self.audio_length = total_length
                progress_ratio = current_time / self.audio_length

                # New pixel position
                new_x = int(progress_ratio * self.width)

                # Only redraw if the playhead has moved at least 1 pixel
                if new_x != self.playhead_x:
                    self.playhead_x = new_x
                    self._update_waveform_colors()
        except Exception as e:
            logger.error(f"Sync error: {e}")

        self.after(50, self._update_playhead) # 50ms is smoother for DJs (20fps)

    def _on_click(self, event):
        """Handle mouse click on canvas."""
        self.is_dragging = True
        # Store the target position but don't seek yet
        self._pending_seek_position = event.x
        # Update playhead position visually for immediate feedback
        self.playhead_x = event.x
        self._update_waveform_colors()

    def _on_drag(self, event):
        """Handle mouse drag on canvas."""
        if self.is_dragging:
            # Only update visual position, don't seek yet
            self._pending_seek_position = event.x
            self.playhead_x = event.x
            self._update_waveform_colors()

    def _on_release(self, event):
        """Handle mouse release - perform the actual seek."""
        if self.is_dragging and hasattr(self, '_pending_seek_position'):
            # Now perform the actual seek
            self._seek_to_position(self._pending_seek_position)
            delattr(self, '_pending_seek_position')
        self.is_dragging = False

    def _seek_to_position(self, x_position: int):
        """
        Seek to the position corresponding to the X coordinate.

        Args:
            x_position: X coordinate on canvas
        """
        try:
            # Get current audio length from player in case it wasn't set
            if self.audio_length <= 0:
                self.audio_length = self.player.get_length()

            if self.audio_length <= 0:
                return

            # Calculate target time from X position
            ratio = x_position / self.width
            ratio = max(0.0, min(ratio, 1.0))  # Clamp to 0-1
            target_time = int(ratio * self.audio_length)

            # Seek the player
            self.player.set_time(target_time)

            # Note: Don't update playhead here - let the real-time update handle it
            # This prevents visual conflicts during the seek operation

        except Exception as e:
            logger.error(f"Error seeking to position {x_position}: {e}")

    def update_theme(self):
        """Update colors when theme changes."""
        if hasattr(self, 'theme') and self.theme:
            palette = self.theme.palette if hasattr(self.theme, 'palette') else {}

            # Update colors from theme palette
            self.bg_color = palette.get("waveform_bg", "#1a1a1a")
            self.played_color = palette.get("waveform_played", "#FF6B00")
            self.unplayed_color = palette.get("waveform_unplayed", "#404040")
            self.border_color = palette.get("waveform_border", "#808080")

            # Update canvas background
            self.configure(bg=self.bg_color, highlightbackground=self.border_color)

            # Redraw waveform with new colors
            if self.waveform_data is not None:
                self._draw_waveform()

    def clear(self):
        """Clear the waveform and reset state."""
        # Clear placeholder line if it exists
        if self.placeholder_line:
            self.delete(self.placeholder_line)
            self.placeholder_line = None

        self._clear_waveform()

        # Draw placeholder line when clearing to empty state
        self._draw_placeholder_line()

        with self.waveform_lock:
            self.waveform_data = None
            self.current_file = None
            self.audio_length = 0
            self.playhead_x = 0

    def destroy(self):
        """Clean up resources."""
        self.clear()
        super().destroy()
