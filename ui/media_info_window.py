"""
Media Information Window - displays detailed metadata about an audio file.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import os
from pathlib import Path
from mutagen import File as MutagenFile
from ui.utils import center_window


class MediaInfoWindow:
    def __init__(self, parent, file_path, theme_manager=None):
        self.file_path = file_path
        self.theme_manager = theme_manager

        # Create window
        self.window = tk.Toplevel(parent)
        self.window.title("Track Information")
        self.window.geometry("600x500")
        self.window.resizable(True, True)
        self.window.transient(parent)

        center_window(self.window, parent)

        # Create notebook (tabbed interface)
        notebook = ttk.Notebook(self.window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        general_frame = ttk.Frame(notebook)
        codec_frame = ttk.Frame(notebook)
        metadata_frame = ttk.Frame(notebook)

        notebook.add(general_frame, text="General")
        notebook.add(codec_frame, text="Codec")
        notebook.add(metadata_frame, text="Metadata")

        # Load file information
        self.file_info = self._get_file_info()

        # Populate tabs
        self._populate_general_tab(general_frame)
        self._populate_codec_tab(codec_frame)
        self._populate_metadata_tab(metadata_frame)

        # Close button
        button_frame = ttk.Frame(self.window)
        button_frame.pack(side=tk.BOTTOM, pady=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.window.destroy).pack()

        # Bind Escape key to close
        self.window.bind("<Escape>", lambda e: self.window.destroy())

    def _get_file_info(self):
        """Extract all file information using mutagen."""
        info = {
            'path': self.file_path,
            'filename': os.path.basename(self.file_path),
            'size': 0,
            'format': '',
            'duration': 0,
            'bitrate': 0,
            'sample_rate': 0,
            'channels': 0,
            'codec': '',
            'metadata': {}
        }

        try:
            # Get file size
            info['size'] = os.path.getsize(self.file_path)

            # Load with mutagen
            audio = MutagenFile(self.file_path, easy=True)
            if audio is None:
                return info

            # Get audio info
            if hasattr(audio, 'info'):
                audio_info = audio.info

                # Duration
                if hasattr(audio_info, 'length'):
                    info['duration'] = int(audio_info.length)

                # Bitrate
                if hasattr(audio_info, 'bitrate'):
                    info['bitrate'] = int(audio_info.bitrate)

                # Sample rate
                if hasattr(audio_info, 'sample_rate'):
                    info['sample_rate'] = int(audio_info.sample_rate)

                # Channels
                if hasattr(audio_info, 'channels'):
                    info['channels'] = int(audio_info.channels)

            # Determine format/codec
            class_name = audio.__class__.__name__.lower()
            if 'mp3' in class_name:
                info['format'] = 'MP3'
                info['codec'] = 'MPEG Audio Layer 3'
            elif 'flac' in class_name:
                info['format'] = 'FLAC'
                info['codec'] = 'Free Lossless Audio Codec'
            elif 'ogg' in class_name or 'vorbis' in class_name:
                info['format'] = 'OGG'
                info['codec'] = 'Vorbis'
            elif 'm4a' in class_name or 'mp4' in class_name or 'aac' in class_name:
                info['format'] = 'M4A/AAC'
                info['codec'] = 'Advanced Audio Coding'
            elif 'wave' in class_name or 'wav' in class_name:
                info['format'] = 'WAV'
                info['codec'] = 'PCM'
            else:
                ext = os.path.splitext(self.file_path)[1].upper().lstrip('.')
                info['format'] = ext
                info['codec'] = 'Unknown'

            # Get metadata tags
            if audio.tags:
                for key in audio.keys():
                    value = audio[key]
                    if isinstance(value, list) and len(value) > 0:
                        info['metadata'][key] = value[0]
                    else:
                        info['metadata'][key] = str(value)

        except Exception:
            pass

        return info

    def _populate_general_tab(self, frame):
        container = ttk.Frame(frame, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        # Create scrollable text widget
        text = tk.Text(container, wrap=tk.WORD, height=20, width=70)

        # Apply theme if available
        if self.theme_manager:
            palette = self.theme_manager.palette
            bg = palette.get("bg", "#ffffff")
            fg = palette.get("fg", "#000000")
            text.configure(bg=bg, fg=fg, insertbackground=fg)

        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Add information
        info = self.file_info

        text.insert(tk.END, "File Information\n", "header")
        text.insert(tk.END, "=" * 60 + "\n\n")

        text.insert(tk.END, f"Filename: {info['filename']}\n")
        text.insert(tk.END, f"Path: {info['path']}\n\n")

        # File size
        size_mb = info['size'] / (1024 * 1024)
        size_kb = info['size'] / 1024
        if size_mb >= 1:
            text.insert(tk.END, f"Size: {size_mb:.2f} MB ({info['size']:,} bytes)\n")
        else:
            text.insert(tk.END, f"Size: {size_kb:.2f} KB ({info['size']:,} bytes)\n")

        # Duration
        if info['duration'] > 0:
            minutes = info['duration'] // 60
            seconds = info['duration'] % 60
            text.insert(tk.END, f"Duration: {minutes}:{seconds:02d} ({info['duration']} seconds)\n")

        text.insert(tk.END, f"Format: {info['format']}\n")

        # Configure tags
        text.tag_configure("header", font=("TkDefaultFont", 12, "bold"))

        text.configure(state=tk.DISABLED)

    def _populate_codec_tab(self, frame):
        container = ttk.Frame(frame, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        # Create scrollable text widget
        text = tk.Text(container, wrap=tk.WORD, height=20, width=70)

        # Apply theme if available
        if self.theme_manager:
            palette = self.theme_manager.palette
            bg = palette.get("bg", "#ffffff")
            fg = palette.get("fg", "#000000")
            text.configure(bg=bg, fg=fg, insertbackground=fg)

        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Add information
        info = self.file_info

        text.insert(tk.END, "Audio Codec Information\n", "header")
        text.insert(tk.END, "=" * 60 + "\n\n")

        text.insert(tk.END, f"Codec: {info['codec']}\n")
        text.insert(tk.END, f"Format: {info['format']}\n\n")

        if info['bitrate'] > 0:
            bitrate_kbps = info['bitrate'] // 1000
            text.insert(tk.END, f"Bitrate: {bitrate_kbps} kbps ({info['bitrate']} bps)\n")

        if info['sample_rate'] > 0:
            sample_rate_khz = info['sample_rate'] / 1000
            text.insert(tk.END, f"Sample Rate: {sample_rate_khz:.1f} kHz ({info['sample_rate']} Hz)\n")

        if info['channels'] > 0:
            channel_text = "Stereo" if info['channels'] == 2 else f"{info['channels']} channels"
            text.insert(tk.END, f"Channels: {channel_text}\n")

        # Configure tags
        text.tag_configure("header", font=("TkDefaultFont", 12, "bold"))

        text.configure(state=tk.DISABLED)

    def _populate_metadata_tab(self, frame):
        container = ttk.Frame(frame, padding=20)
        container.pack(fill=tk.BOTH, expand=True)

        # Grid configuration
        container.columnconfigure(1, weight=1)

        # Dictionary to store entry widgets
        self.entries = {}

        # Common tags to edit
        tags = [
            ("Title", "title"),
            ("Artist", "artist"),
            ("Album", "album"),
            ("Year", "date"),
            ("Genre", "genre"),
            ("Track Number", "tracknumber")
        ]

        info = self.file_info['metadata']

        for i, (label_text, key) in enumerate(tags):
            ttk.Label(container, text=f"{label_text}:").grid(row=i, column=0, sticky="w", pady=5)

            entry = ttk.Entry(container)
            entry.grid(row=i, column=1, sticky="ew", padx=(10, 0), pady=5)

            # Pre-fill if value exists
            # Map common keys if needed, but mutagen easy=True handles these well
            val = info.get(key, "")
            entry.insert(0, str(val))

            self.entries[key] = entry

        # Save Button
        ttk.Button(container, text="Save Metadata", command=self._save_metadata).grid(row=len(tags), column=1, sticky="e", pady=20)

    def _save_metadata(self):
        """Save edited metadata back to the file."""
        try:
            audio = MutagenFile(self.file_path, easy=True)
            if audio is None:
                messagebox.showerror("Error", "Could not load file for writing.", parent=self.window)
                return

            # Update tags from entries
            for key, entry in self.entries.items():
                val = entry.get().strip()
                if val:
                    audio[key] = [val]
                else:
                    # Remove tag if empty
                    if key in audio:
                        del audio[key]

            audio.save()
            messagebox.showinfo("Success", "Metadata saved successfully!", parent=self.window)

            # Refresh file info to show updates
            self.file_info = self._get_file_info()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save metadata: {e}", parent=self.window)
