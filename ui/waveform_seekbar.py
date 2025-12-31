"""
Waveform Seekbar component for audio visualization and seeking.

Provides a visual representation of audio waveform with interactive seeking capabilities.
"""

import logging
import threading
import customtkinter as ctk
import librosa
import soundfile as sf
from pathlib import Path
from pydub import AudioSegment
import numpy as np
from typing import Optional, Callable

logger = logging.getLogger(__name__)


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
        self.playhead_color = palette.get("waveform_playhead", "#FF6B00")
        self.played_color = palette.get("waveform_played", "#FF6B00")
        self.unplayed_color = palette.get("waveform_unplayed", "#404040")

        # Set canvas background color
        self.configure(bg=self.bg_color, highlightthickness=1, highlightbackground=self.playhead_color)

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
        self.playhead_line = None

        # Bind mouse events
        self.bind('<Button-1>', self._on_click)
        self.bind('<B1-Motion>', self._on_drag)
        self.bind('<ButtonRelease-1>', self._on_release)

        # Also bind to canvas directly for better event capture
        self.bind('<ButtonPress-1>', self._on_click)

        # Start update loop
        self._update_playhead()

        logger.info("WaveformSeekbar initialized")

    def load_waveform(self, audio_file: str):
        """
        Load and generate waveform for the given audio file.

        Args:
            audio_file: Path to the audio file
        """
        if audio_file == self.current_file and self.waveform_data is not None:
            return  # Already loaded

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

        logger.info(f"Started waveform generation for {audio_file}")

    def _generate_waveform_worker(self, audio_file: str):
        """
        Worker function to generate waveform data in background thread.

        Args:
            audio_file: Path to the audio file
        """
        try:
            # Try soundfile first (handles WAV, FLAC, OGG, etc.)
            try:
                y, sr = sf.read(audio_file, dtype='float32', always_2d=False)

                # Convert to mono if stereo
                if y.ndim > 1:
                    y = y.mean(axis=1)

            except (sf.LibsndfileError, RuntimeError):
                # Fallback for MP3 and other formats soundfile can't handle
                # Use pydub which handles MP3 well
                audio = AudioSegment.from_file(audio_file)

                # Convert to mono
                if audio.channels > 1:
                    audio = audio.set_channels(1)

                # Get sample rate
                sr = audio.frame_rate

                # Convert to numpy array
                samples = np.array(audio.get_array_of_samples(), dtype=np.float32)

                # Normalize to -1.0 to 1.0 range
                if audio.sample_width == 1:  # 8-bit
                    y = (samples - 128) / 128.0
                elif audio.sample_width == 2:  # 16-bit
                    y = samples / 32768.0
                elif audio.sample_width == 4:  # 32-bit
                    y = samples / 2147483648.0
                else:
                    y = samples / (2 ** (audio.sample_width * 8 - 1))

            # Calculate amplitude envelope (RMS energy)
            hop_length = 512
            frame_length = 2048
            rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]

            # Normalize to 0-1 range
            if rms.max() > 0:
                rms = rms / rms.max()

            with self.waveform_lock:
                self.waveform_data = rms
                self.audio_length = len(y) / sr * 1000  # Convert to milliseconds

            # Schedule UI update in main thread
            self.after(0, self._draw_waveform)
            logger.info(f"Waveform generated for {audio_file}: {len(rms)} frames")

        except Exception as e:
            logger.error(f"Failed to generate waveform for {audio_file}: {e}")
            # Clear waveform on error
            with self.waveform_lock:
                self.waveform_data = None
            self.after(0, self._clear_waveform)

    def _draw_waveform(self):
        """Draw the waveform on the canvas."""
        # Clear existing waveform
        self._clear_waveform()

        with self.waveform_lock:
            if self.waveform_data is None:
                return

            # Calculate bar width and spacing
            num_frames = len(self.waveform_data)
            bar_width = max(1, self.width // num_frames)
            spacing = 1

            # Draw waveform as vertical bars
            center_y = self.height // 2
            max_height = self.height * 0.8  # Use 80% of canvas height

            for i, amplitude in enumerate(self.waveform_data):
                if i * (bar_width + spacing) >= self.width:
                    break

                x = i * (bar_width + spacing)
                bar_height = amplitude * max_height / 2

                # Draw top and bottom bars (centered)
                top_y = center_y - bar_height
                bottom_y = center_y + bar_height

                # Create bars for played/unplayed sections
                # Initially all are unplayed (gray)
                bar_id = self.create_rectangle(
                    x, top_y, x + bar_width, bottom_y,
                    fill=self.unplayed_color,
                    outline='',
                    tags='waveform'
                )
                self.waveform_items.append(bar_id)

        # Draw playhead
        self._draw_playhead()

    def _clear_waveform(self):
        """Clear all waveform items from canvas."""
        for item in self.waveform_items:
            self.delete(item)
        self.waveform_items.clear()

        if self.playhead_line:
            self.delete(self.playhead_line)
            self.playhead_line = None

    def _draw_playhead(self):
        """Draw or update the playhead line."""
        if self.playhead_line:
            self.delete(self.playhead_line)

        # Draw vertical line at current position
        self.playhead_line = self.create_line(
            self.playhead_x, 0,
            self.playhead_x, self.height,
            fill=self.playhead_color,
            width=2,
            tags='playhead'
        )

        # Update waveform colors for played/unplayed sections
        self._update_waveform_colors()

    def _update_waveform_colors(self):
        """Update waveform bar colors based on playhead position."""
        if not self.waveform_items:
            return

        with self.waveform_lock:
            if self.waveform_data is None:
                return

            num_frames = len(self.waveform_data)
            if num_frames == 0:
                return

            # Calculate which frame corresponds to playhead
            current_time = self.player.get_time()
            if self.audio_length <= 0:
                return

            played_ratio = current_time / self.audio_length
            played_frames = int(played_ratio * num_frames)

            # Update colors
            for i, bar_id in enumerate(self.waveform_items):
                if i < played_frames:
                    color = self.played_color
                else:
                    color = self.unplayed_color

                self.itemconfig(bar_id, fill=color)

    def _update_playhead(self):
        """Update playhead position based on current playback time."""
        # Don't update if user is dragging - prevent conflicts
        if self.is_dragging:
            # Schedule next update but don't change position
            self.after(100, self._update_playhead)
            return

        try:
            current_time = self.player.get_time()
            self.audio_length = self.player.get_length()

            if self.audio_length > 0:
                # Calculate playhead X position
                progress_ratio = current_time / self.audio_length
                self.playhead_x = int(progress_ratio * self.width)
                self.playhead_x = max(0, min(self.playhead_x, self.width))

                # Redraw playhead and update colors
                self._draw_playhead()

        except Exception as e:
            logger.error(f"Error updating playhead: {e}")

        # Schedule next update
        self.after(100, self._update_playhead)  # Update every 100ms

    def _on_click(self, event):
        """Handle mouse click on canvas."""
        self.is_dragging = True
        # Store the target position but don't seek yet
        self._pending_seek_position = event.x
        # Update playhead visually for immediate feedback
        self.playhead_x = event.x
        self._draw_playhead()

    def _on_drag(self, event):
        """Handle mouse drag on canvas."""
        if self.is_dragging:
            # Only update visual position, don't seek yet
            self._pending_seek_position = event.x
            self.playhead_x = event.x
            self._draw_playhead()

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
            self.playhead_color = palette.get("waveform_playhead", "#FF6B00")
            self.played_color = palette.get("waveform_played", "#FF6B00")
            self.unplayed_color = palette.get("waveform_unplayed", "#404040")

            # Update canvas background
            self.configure(bg=self.bg_color, highlightbackground=self.playhead_color)

            # Redraw waveform with new colors
            if self.waveform_data is not None:
                self._draw_waveform()

    def clear(self):
        """Clear the waveform and reset state."""
        self._clear_waveform()

        with self.waveform_lock:
            self.waveform_data = None
            self.current_file = None
            self.audio_length = 0
            self.playhead_x = 0

    def destroy(self):
        """Clean up resources."""
        self.clear()
        super().destroy()
