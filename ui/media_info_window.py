"""
Media Information Window - displays detailed metadata about an audio file.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import os
from pathlib import Path
from audio.metadata import get_file_info, save_metadata
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

        # Hide window initially to prevent flickering during positioning
        self.window.withdraw()

        center_window(self.window, parent)

        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create tabs
        general_frame = ttk.Frame(self.notebook)
        codec_frame = ttk.Frame(self.notebook)
        metadata_frame = ttk.Frame(self.notebook)

        self.notebook.add(general_frame, text="General")
        self.notebook.add(codec_frame, text="Codec")
        self.notebook.add(metadata_frame, text="Metadata")

        # Load file information
        self.file_info = self._get_file_info()

        # Store references to text widgets for theme updates
        self.general_text = None
        self.codec_text = None
        self.close_btn = None
        self.save_btn = None

        # Populate tabs
        self._populate_general_tab(general_frame)
        self._populate_codec_tab(codec_frame)
        self._populate_metadata_tab(metadata_frame)

        # Close button with modern styling
        button_frame = ttk.Frame(self.window)
        button_frame.pack(side=tk.BOTTOM, pady=(0, 10))

        # Get button colors from theme
        palette = self.theme_manager.palette if self.theme_manager else {}
        btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        btn_fg = palette.get("button_fg_color", "#ffffff")
        btn_hover = palette.get("button_hover", palette.get("accent_hover", "#106ebe"))
        bg = palette.get("bg", "#ffffff")

        close_btn = ctk.CTkButton(
            button_frame,
            text="Close",
            command=self.window.destroy,
            font=("Segoe UI", 11),
            width=100,
            height=32,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=btn_hover,
            bg_color=bg
        )
        close_btn.pack()

        # Store reference for theme updates
        self.close_btn = close_btn

        # Bind Escape key to close
        self.window.bind("<Escape>", lambda e: self.window.destroy())

        # Apply initial theme
        self._apply_theme()

        # Store current theme for change detection
        self._current_theme = self.theme_manager.settings.theme if self.theme_manager else None

        # Check for theme changes periodically
        self._check_theme_change()
        
        # Show window after all setup is complete
        self.window.deiconify()

    def _check_theme_change(self):
        """Check if theme has changed and update if needed."""
        if self.theme_manager and hasattr(self.theme_manager, 'settings'):
            current_theme = self.theme_manager.settings.theme
            if current_theme != self._current_theme:
                self._current_theme = current_theme
                self.theme_manager.reload()
                self._apply_theme()

        # Schedule next check if window still exists
        try:
            if self.window.winfo_exists():
                self.window.after(500, self._check_theme_change)
        except:
            pass

    def update_theme(self):
        """Public method to update theme colors."""
        if self.theme_manager:
            self._apply_theme()

    def _apply_theme(self):
        """Apply current theme colors to all widgets."""
        if not self.theme_manager:
            return

        palette = self.theme_manager.palette
        bg = palette.get("bg", "#ffffff")
        fg = palette.get("fg", "#000000")
        accent = palette.get("accent", "#0078d4")
        highlight = palette.get("highlight", "#EB5B00")

        # Update window background
        self.window.configure(bg=bg)

        # Update general tab text widget
        if self.general_text:
            self.general_text.configure(bg=bg, fg=fg, insertbackground=fg)
            # Reconfigure tags
            self.general_text.tag_configure("header", font=("Segoe UI", 16, "bold"), foreground=accent)
            self.general_text.tag_configure("label", font=("Segoe UI", 9), foreground=fg)
            self.general_text.tag_configure("value", font=("Segoe UI", 11))
            self.general_text.tag_configure("value_highlight", font=("Segoe UI", 11, "bold"), foreground=highlight)

        # Update codec tab text widget
        if self.codec_text:
            self.codec_text.configure(bg=bg, fg=fg, insertbackground=fg)
            # Reconfigure tags
            self.codec_text.tag_configure("header", font=("Segoe UI", 16, "bold"), foreground=accent)
            self.codec_text.tag_configure("label", font=("Segoe UI", 9), foreground=fg)
            self.codec_text.tag_configure("value", font=("Segoe UI", 11))
            self.codec_text.tag_configure("value_highlight", font=("Segoe UI", 11, "bold"), foreground=highlight)

        # Update buttons
        btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        btn_fg = palette.get("button_fg_color", "#ffffff")
        btn_hover = palette.get("button_hover", palette.get("accent_hover", "#106ebe"))

        if self.close_btn:
            self.close_btn.configure(fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover, bg_color=bg)

        if self.save_btn:
            self.save_btn.configure(fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover, bg_color=bg)

        # Update notebook (tab bar) styling
        self._update_notebook_style()

    def _update_notebook_style(self):
        """Update notebook tab bar colors based on theme."""
        if not self.theme_manager:
            return

        palette = self.theme_manager.palette
        bg = palette.get("bg", "#ffffff")
        fg = palette.get("fg", "#000000")
        accent = palette.get("accent", "#0078d4")
        tree_bg = palette.get("tree_bg", "#ffffff")

        # Create or get style
        style = ttk.Style(self.window)

        # Configure notebook style
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab",
                       background=tree_bg,
                       foreground=fg,
                       padding=[12, 6],
                       borderwidth=0)

        # Selected tab styling
        style.map("TNotebook.Tab",
                 background=[("selected", accent)],
                 foreground=[("selected", "#ffffff")],
                 expand=[("selected", [1, 1, 1, 0])])

        # Frame background
        style.configure("TFrame", background=bg)

    def _get_file_info(self):
        """Extract all file information using the centralized metadata module."""
        return get_file_info(self.file_path)

    def _populate_general_tab(self, frame):
        container = ttk.Frame(frame, padding=15)
        container.pack(fill=tk.BOTH, expand=True)

        # Create scrollable text widget
        text = tk.Text(container, wrap=tk.WORD, height=20, width=70, font=("Segoe UI", 10))

        # Apply theme if available
        if self.theme_manager:
            palette = self.theme_manager.palette
            bg = palette.get("bg", "#ffffff")
            fg = palette.get("fg", "#000000")
            accent = palette.get("accent", "#0078d4")
            highlight = palette.get("highlight", "#EB5B00")
            text.configure(bg=bg, fg=fg, insertbackground=fg)
        else:
            bg = "#ffffff"
            fg = "#000000"
            accent = "#0078d4"
            highlight = "#EB5B00"

        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Store reference for theme updates
        self.general_text = text

        # Add information with improved formatting
        info = self.file_info

        text.insert(tk.END, "File Information\n\n", "header")

        text.insert(tk.END, "Filename\n", "label")
        text.insert(tk.END, f"{info['filename']}\n\n", "value")

        text.insert(tk.END, "Path\n", "label")
        text.insert(tk.END, f"{info['path']}\n\n", "value")

        # File size
        text.insert(tk.END, "Size\n", "label")
        size_mb = info['size'] / (1024 * 1024)
        size_kb = info['size'] / 1024
        if size_mb >= 1:
            text.insert(tk.END, f"{size_mb:.2f} MB", "value_highlight")
            text.insert(tk.END, f" ({info['size']:,} bytes)\n\n", "value")
        else:
            text.insert(tk.END, f"{size_kb:.2f} KB", "value_highlight")
            text.insert(tk.END, f" ({info['size']:,} bytes)\n\n", "value")

        # Duration
        if info['duration'] > 0:
            text.insert(tk.END, "Duration\n", "label")
            minutes = info['duration'] // 60
            seconds = info['duration'] % 60
            text.insert(tk.END, f"{minutes}:{seconds:02d}", "value_highlight")
            text.insert(tk.END, f" ({info['duration']} seconds)\n\n", "value")

        text.insert(tk.END, "Format\n", "label")
        text.insert(tk.END, f"{info['format']}\n", "value_highlight")

        # Configure tags with improved styling
        text.tag_configure("header", font=("Segoe UI", 16, "bold"), foreground=accent)
        text.tag_configure("label", font=("Segoe UI", 9), foreground=fg)
        text.tag_configure("value", font=("Segoe UI", 11))
        text.tag_configure("value_highlight", font=("Segoe UI", 11, "bold"), foreground=highlight)

        text.configure(state=tk.DISABLED)

    def _populate_codec_tab(self, frame):
        container = ttk.Frame(frame, padding=15)
        container.pack(fill=tk.BOTH, expand=True)

        # Create scrollable text widget
        text = tk.Text(container, wrap=tk.WORD, height=20, width=70, font=("Segoe UI", 10))

        # Apply theme if available
        if self.theme_manager:
            palette = self.theme_manager.palette
            bg = palette.get("bg", "#ffffff")
            fg = palette.get("fg", "#000000")
            accent = palette.get("accent", "#0078d4")
            highlight = palette.get("highlight", "#EB5B00")
            text.configure(bg=bg, fg=fg, insertbackground=fg)
        else:
            bg = "#ffffff"
            fg = "#000000"
            accent = "#0078d4"
            highlight = "#EB5B00"

        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)

        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Store reference for theme updates
        self.codec_text = text

        # Add information with improved formatting
        info = self.file_info

        text.insert(tk.END, "Audio Codec Information\n\n", "header")

        text.insert(tk.END, "Codec\n", "label")
        text.insert(tk.END, f"{info['codec']}\n\n", "value_highlight")

        text.insert(tk.END, "Format\n", "label")
        text.insert(tk.END, f"{info['format']}\n\n", "value_highlight")

        if info['bitrate'] > 0:
            text.insert(tk.END, "Bitrate\n", "label")
            bitrate_kbps = info['bitrate'] // 1000
            text.insert(tk.END, f"{bitrate_kbps} kbps", "value_highlight")
            text.insert(tk.END, f" ({info['bitrate']} bps)\n\n", "value")

        if info['sample_rate'] > 0:
            text.insert(tk.END, "Sample Rate\n", "label")
            sample_rate_khz = info['sample_rate'] / 1000
            text.insert(tk.END, f"{sample_rate_khz:.1f} kHz", "value_highlight")
            text.insert(tk.END, f" ({info['sample_rate']} Hz)\n\n", "value")

        if info['channels'] > 0:
            text.insert(tk.END, "Channels\n", "label")
            channel_text = "Stereo" if info['channels'] == 2 else f"{info['channels']} channels"
            text.insert(tk.END, f"{channel_text}\n", "value_highlight")

        # Configure tags with improved styling
        text.tag_configure("header", font=("Segoe UI", 16, "bold"), foreground=accent)
        text.tag_configure("label", font=("Segoe UI", 9), foreground=fg)
        text.tag_configure("value", font=("Segoe UI", 11))
        text.tag_configure("value_highlight", font=("Segoe UI", 11, "bold"), foreground=highlight)

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

        # Save Button with modern styling
        if self.theme_manager:
            palette = self.theme_manager.palette
            btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
            btn_fg = palette.get("button_fg_color", "#ffffff")
            btn_hover = palette.get("button_hover", palette.get("accent_hover", "#106ebe"))
            bg = palette.get("bg", "#ffffff")
        else:
            btn_bg = "#0078d4"
            btn_fg = "#ffffff"
            btn_hover = "#106ebe"
            bg = "#ffffff"

        save_btn = ctk.CTkButton(
            container,
            text="Save Metadata",
            command=self._save_metadata,
            font=("Segoe UI", 11),
            width=120,
            height=32,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=btn_hover,
            bg_color=bg
        )
        save_btn.grid(row=len(tags), column=1, sticky="e", pady=20)

        # Store reference for theme updates
        self.save_btn = save_btn

    def _save_metadata(self):
        """Save edited metadata back to the file."""
        try:
            # Update tags from entries
            metadata_to_save = {}
            for key, entry in self.entries.items():
                val = entry.get().strip()
                if val:
                    metadata_to_save[key] = val

            success = save_metadata(self.file_path, metadata_to_save)
            if success:
                messagebox.showinfo("Success", "Metadata saved successfully!", parent=self.window)
                # Refresh file info to show updates
                self.file_info = self._get_file_info()
            else:
                messagebox.showerror("Error", "Could not load file for writing.", parent=self.window)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save metadata: {e}", parent=self.window)
