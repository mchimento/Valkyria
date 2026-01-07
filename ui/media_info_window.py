"""
Media Information Window - displays detailed metadata about an audio file.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import customtkinter as ctk
import os
import threading
from audio.metadata import get_file_info, save_metadata, metadata_extractor, analyze_bpm, analyze_key, key_to_camelot
from audio.bpm import analysis_manager
from ui.utils import center_window


class MediaInfoWindow:
    def __init__(self, parent, file_path, theme_manager=None, metadata_saved_callback=None):
        self.file_path = file_path
        self.theme_manager = theme_manager
        self.metadata_saved_callback = metadata_saved_callback

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

        # Register BPM update listener so UI refreshes when bpm is written
        try:
            metadata_extractor.register_bpm_listener(self._on_bpm_updated)
            metadata_extractor.register_key_listener(self._on_key_updated)
        except Exception:
            pass
        # Store references to text widgets for theme updates
        self.general_text = None
        self.codec_text = None
        self.close_btn = None
        self.save_btn = None
        self.bpm_btn = None
        self.key_btn = None

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
        self.window.bind("<Escape>", lambda e: self._on_close())
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

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

        if self.bpm_btn:
            self.bpm_btn.configure(fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover, bg_color=bg)

        if self.key_btn:
            self.key_btn.configure(fg_color=btn_bg, text_color=btn_fg, hover_color=btn_hover, bg_color=bg)

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

        # BPM (if available)
        bpm_val = None
        try:
            bpm_val = info.get('metadata', {}).get('bpm')
        except Exception:
            bpm_val = None

        if bpm_val is not None and bpm_val != "":
            text.insert(tk.END, "BPM\n", "label")
            try:
                raw_bpm = int(round(float(bpm_val)))
                text.insert(tk.END, f"{raw_bpm}\n\n", "value_highlight")
            except (ValueError, TypeError):
                text.insert(tk.END, "\n\n", "value_highlight")

        # Key (if available)
        key_val = None
        try:
            key_val = info.get('metadata', {}).get('key')
        except Exception:
            key_val = None

        if key_val is not None and key_val != "":
            text.insert(tk.END, "Key\n", "label")
            text.insert(tk.END, f"{key_val}\n", "value_highlight")

            # Camelot notation if available; compute from raw key if missing
            camelot_val = info.get('metadata', {}).get('camelot')
            try:
                if not camelot_val and key_val:
                    # Compute on-the-fly for display if needed
                    camelot_val = key_to_camelot(key_val)

                if camelot_val:
                    text.insert(tk.END, f"{camelot_val} (Camelot)\n\n", "value_highlight")
                else:
                    text.insert(tk.END, "\n", "value_highlight")
            except Exception:
                text.insert(tk.END, "\n\n", "value_highlight")

        text.insert(tk.END, "Format\n", "label")
        text.insert(tk.END, f"{info['format']}\n", "value_highlight")

        text.tag_configure("header", font=("Segoe UI", 16, "bold"), foreground=accent)
        text.tag_configure("label", font=("Segoe UI", 9), foreground=fg)
        text.tag_configure("value", font=("Segoe UI", 11))
        text.tag_configure("value_highlight", font=("Segoe UI", 11, "bold"), foreground=highlight)

        text.configure(state=tk.DISABLED)

    def _on_bpm_updated(self, filepath):
        if os.path.abspath(filepath) != os.path.abspath(self.file_path):
            return
        try:
            if self.window.winfo_exists():
                self.window.after(50, self._refresh_bpm)
        except Exception:
            pass

    def _on_key_updated(self, filepath):
        if os.path.abspath(filepath) != os.path.abspath(self.file_path):
            return
        try:
            if self.window.winfo_exists():
                self.window.after(50, self._refresh_general_tab)
        except Exception:
            pass

    def _refresh_general_tab(self):
        """Refresh the general tab with updated file information including Camelot notation."""
        try:
            self.file_info = self._get_file_info()
            if self.general_text:
                try:
                    self.general_text.configure(state=tk.NORMAL)
                    self.general_text.delete('1.0', tk.END)

                    info = self.file_info
                    accent = self.theme_manager.palette.get('accent', '#0078d4') if self.theme_manager else '#0078d4'
                    fg = self.theme_manager.palette.get('fg', '#000000') if self.theme_manager else '#000000'
                    highlight = self.theme_manager.palette.get('highlight', '#EB5B00') if self.theme_manager else '#EB5B00'

                    self.general_text.insert(tk.END, "File Information\n\n", "header")
                    self.general_text.insert(tk.END, "Filename\n", "label")
                    self.general_text.insert(tk.END, f"{info['filename']}\n\n", "value")
                    self.general_text.insert(tk.END, "Path\n", "label")
                    self.general_text.insert(tk.END, f"{info['path']}\n\n", "value")

                    # Size
                    size_mb = info['size'] / (1024 * 1024)
                    size_kb = info['size'] / 1024
                    self.general_text.insert(tk.END, "Size\n", "label")
                    if size_mb >= 1:
                        self.general_text.insert(tk.END, f"{size_mb:.2f} MB", "value_highlight")
                        self.general_text.insert(tk.END, f" ({info['size']:,} bytes)\n\n", "value")
                    else:
                        self.general_text.insert(tk.END, f"{size_kb:.2f} KB", "value_highlight")
                        self.general_text.insert(tk.END, f" ({info['size']:,} bytes)\n\n", "value")

                    # Duration
                    if info['duration'] > 0:
                        minutes = info['duration'] // 60
                        seconds = info['duration'] % 60
                        self.general_text.insert(tk.END, "Duration\n", "label")
                        self.general_text.insert(tk.END, f"{minutes}:{seconds:02d}", "value_highlight")
                        self.general_text.insert(tk.END, f" ({info['duration']} seconds)\n\n", "value")

                    bpm_val = None
                    try:
                        bpm_val = info.get('metadata', {}).get('bpm')
                    except Exception:
                        bpm_val = None

                    # Only show BPM if it's a valid number
                    if bpm_val is not None and bpm_val != "":
                        self.general_text.insert(tk.END, "BPM\n", "label")
                        try:
                            raw_bpm = int(round(float(bpm_val)))
                            self.general_text.insert(tk.END, f"{raw_bpm}\n\n", "value_highlight")
                        except (ValueError, TypeError):
                            self.general_text.insert(tk.END, "\n\n", "value_highlight")

                    # Key with Camelot notation
                    key_val = None
                    try:
                        key_val = info.get('metadata', {}).get('key')
                    except Exception:
                        key_val = None

                    if key_val is not None and key_val != "":
                         self.general_text.insert(tk.END, "Key\n", "label")
                         self.general_text.insert(tk.END, f"{key_val}\n", "value_highlight")

                         # Camelot notation if available; compute from raw key if missing
                         camelot_val = info.get('metadata', {}).get('camelot')
                         try:
                             if not camelot_val and key_val:
                                 # Compute on-the-fly for display if needed
                                 camelot_val = key_to_camelot(key_val)

                             if camelot_val:
                                 self.general_text.insert(tk.END, f"{camelot_val} (Camelot)\n\n", "value_highlight")
                             else:
                                 self.general_text.insert(tk.END, "\n", "value_highlight")
                         except Exception:
                             self.general_text.insert(tk.END, "\n\n", "value_highlight")

                    self.general_text.insert(tk.END, "Format\n", "label")
                    self.general_text.insert(tk.END, f"{info['format']}\n", "value_highlight")

                    self.general_text.tag_configure("header", font=("Segoe UI", 16, "bold"), foreground=accent)
                    self.general_text.tag_configure("label", font=("Segoe UI", 9), foreground=fg)
                    self.general_text.tag_configure("value", font=("Segoe UI", 11))
                    self.general_text.tag_configure("value_highlight", font=("Segoe UI", 11, "bold"), foreground=highlight)

                    self.general_text.configure(state=tk.DISABLED)
                except Exception:
                    pass

            # Also update metadata tab entries if they exist
            try:
                if hasattr(self, 'entries') and 'key' in self.entries:
                    val = self.file_info.get('metadata', {}).get('key')
                    entry = self.entries.get('key')
                    if entry is not None:
                        entry.delete(0, tk.END)
                        if val is not None and val != "":
                            # If raw key exists, compute Camelot and show only the Camelot code in the entry
                            try:
                                camelot_val = key_to_camelot(str(val))
                            except Exception:
                                camelot_val = None

                            if camelot_val:
                                # Display camelot (e.g., '8A') but remember raw key for saving
                                entry.insert(0, f"{camelot_val}")
                                try:
                                    entry.raw_value = str(val)
                                except Exception:
                                    pass
                            else:
                                # No Camelot mapping: show raw key and record as raw
                                entry.insert(0, str(val))
                                try:
                                    entry.raw_value = str(val)
                                except Exception:
                                    pass
                        else:
                            entry.insert(0, "")
                            try:
                                entry.raw_value = None
                            except Exception:
                                pass
                            try:
                                if getattr(self, 'key_camelot_label', None) is not None:
                                    self.key_camelot_label.configure(text="")
                            except Exception:
                                pass
            except Exception:
                pass
        except Exception:
            pass

    def _refresh_bpm(self):
        try:
            self.file_info = self._get_file_info()
            if self.general_text:
                try:
                    self.general_text.configure(state=tk.NORMAL)
                    self.general_text.delete('1.0', tk.END)

                    info = self.file_info
                    accent = self.theme_manager.palette.get('accent', '#0078d4') if self.theme_manager else '#0078d4'
                    fg = self.theme_manager.palette.get('fg', '#000000') if self.theme_manager else '#000000'
                    highlight = self.theme_manager.palette.get('highlight', '#EB5B00') if self.theme_manager else '#EB5B00'

                    self.general_text.insert(tk.END, "File Information\n\n", "header")
                    self.general_text.insert(tk.END, "Filename\n", "label")
                    self.general_text.insert(tk.END, f"{info['filename']}\n\n", "value")
                    self.general_text.insert(tk.END, "Path\n", "label")
                    self.general_text.insert(tk.END, f"{info['path']}\n\n", "value")

                    # Size
                    size_mb = info['size'] / (1024 * 1024)
                    size_kb = info['size'] / 1024
                    self.general_text.insert(tk.END, "Size\n", "label")
                    if size_mb >= 1:
                        self.general_text.insert(tk.END, f"{size_mb:.2f} MB", "value_highlight")
                        self.general_text.insert(tk.END, f" ({info['size']:,} bytes)\n\n", "value")
                    else:
                        self.general_text.insert(tk.END, f"{size_kb:.2f} KB", "value_highlight")
                        self.general_text.insert(tk.END, f" ({info['size']:,} bytes)\n\n", "value")

                    # Duration
                    if info['duration'] > 0:
                        minutes = info['duration'] // 60
                        seconds = info['duration'] % 60
                        self.general_text.insert(tk.END, "Duration\n", "label")
                        self.general_text.insert(tk.END, f"{minutes}:{seconds:02d}", "value_highlight")
                        self.general_text.insert(tk.END, f" ({info['duration']} seconds)\n\n", "value")

                    bpm_val = None
                    try:
                        bpm_val = info.get('metadata', {}).get('bpm')
                    except Exception:
                        bpm_val = None

                    # Only show BPM if it's a valid number
                    if bpm_val is not None and bpm_val != "":
                        self.general_text.insert(tk.END, "BPM\n", "label")
                        try:
                            raw_bpm = int(round(float(bpm_val)))
                            self.general_text.insert(tk.END, f"{raw_bpm}\n\n", "value_highlight")
                        except (ValueError, TypeError):
                            self.general_text.insert(tk.END, "\n\n", "value_highlight")

                    # Key
                    key_val = None
                    try:
                        key_val = info.get('metadata', {}).get('key')
                    except Exception:
                        key_val = None

                    if key_val is not None and key_val != "":
                         self.general_text.insert(tk.END, "Key\n", "label")
                         self.general_text.insert(tk.END, f"{key_val}\n\n", "value_highlight")

                    self.general_text.insert(tk.END, "Format\n", "label")
                    self.general_text.insert(tk.END, f"{info['format']}\n", "value_highlight")

                    self.general_text.tag_configure("header", font=("Segoe UI", 16, "bold"), foreground=accent)
                    self.general_text.tag_configure("label", font=("Segoe UI", 9), foreground=fg)
                    self.general_text.tag_configure("value", font=("Segoe UI", 11))
                    self.general_text.tag_configure("value_highlight", font=("Segoe UI", 11, "bold"), foreground=highlight)

                    self.general_text.configure(state=tk.DISABLED)
                except Exception:
                    pass

            try:
                if hasattr(self, 'entries') and 'bpm' in self.entries:
                    val = self.file_info.get('metadata', {}).get('bpm')
                    entry = self.entries.get('bpm')
                    if entry is not None:
                        entry.delete(0, tk.END)
                        if val is not None and val != "":
                            # Show raw value but store raw value
                            try:
                                raw_bpm = int(round(float(val)))
                                entry.insert(0, str(raw_bpm))
                                entry.raw_value = str(val)
                            except (ValueError, TypeError):
                                entry.insert(0, "")
                                entry.raw_value = str(val)
                        else:
                            entry.insert(0, "")
                            entry.raw_value = None
                            entry.insert(0, "")
                            entry.raw_value = None

                if hasattr(self, 'entries') and 'key' in self.entries:
                    val = self.file_info.get('metadata', {}).get('key')
                    entry = self.entries.get('key')
                    if entry is not None:
                        entry.delete(0, tk.END)
                        if val is not None and val != "":
                            # If raw key exists, compute Camelot and show only the Camelot code in the entry
                            try:
                                camelot_val = key_to_camelot(str(val))
                            except Exception:
                                camelot_val = None

                            if camelot_val:
                                # Display camelot (e.g., '8A') but remember raw key for saving
                                entry.insert(0, f"{camelot_val}")
                                try:
                                    entry.raw_value = str(val)
                                except Exception:
                                    pass
                            else:
                                # No Camelot mapping: show raw key and record as raw
                                entry.insert(0, str(val))
                                try:
                                    entry.raw_value = str(val)
                                except Exception:
                                    pass
                        else:
                            entry.insert(0, "")
                            try:
                                entry.raw_value = None
                            except Exception:
                                pass
                            try:
                                if getattr(self, 'key_camelot_label', None) is not None:
                                    self.key_camelot_label.configure(text="")
                            except Exception:
                                pass
            except Exception:
                pass
        except Exception:
            pass

    def _on_close(self):
        try:
            metadata_extractor.unregister_bpm_listener(self._on_bpm_updated)
        except Exception:
            pass
        try:
            metadata_extractor.unregister_key_listener(self._on_key_updated)
        except Exception:
            pass
        try:
            self.window.destroy()
        except Exception:
            pass

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

        self.codec_text = text
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

        tags = [
            ("Title", "title"),
            ("Artist", "artist"),
            ("Album", "album"),
            ("Year", "date"),
            ("Genre", "genre"),
            ("Track Number", "tracknumber"),
            ("BPM", "bpm"),
            ("Key", "key")
        ]

        info = self.file_info['metadata']

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

        for i, (label_text, key) in enumerate(tags):
            ttk.Label(container, text=f"{label_text}:").grid(row=i, column=0, sticky="w", pady=5)

            if key == 'bpm':
                # Create a frame for BPM entry and button
                bpm_frame = ttk.Frame(container)
                bpm_frame.grid(row=i, column=1, sticky="ew", padx=(10, 0), pady=5)

                entry = ttk.Entry(bpm_frame)
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

                # Add BPM calculation button
                bpm_btn = ctk.CTkButton(
                    bpm_frame,
                    text="Calculate BPM",
                    command=self._calculate_bpm,
                    font=("Segoe UI", 9),
                    width=100,
                    height=28,
                    fg_color=btn_bg,
                    text_color=btn_fg,
                    text_color_disabled=btn_fg,
                    hover_color=btn_hover,
                    bg_color=bg
                )
                bpm_btn.pack(side=tk.RIGHT, padx=(5, 0))

                # Store reference for theme updates
                self.bpm_btn = bpm_btn
            elif key == 'key':
                # Create a frame for Key entry and button
                key_frame = ttk.Frame(container)
                key_frame.grid(row=i, column=1, sticky="ew", padx=(10, 0), pady=5)

                entry = ttk.Entry(key_frame)
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

                # Add Key calculation button
                key_btn = ctk.CTkButton(
                    key_frame,
                    text="Calculate Key",
                    command=self._calculate_key,
                    font=("Segoe UI", 9),
                    width=100,
                    height=28,
                    fg_color=btn_bg,
                    text_color=btn_fg,
                    text_color_disabled=btn_fg,
                    hover_color=btn_hover,
                    bg_color=bg
                )
                key_btn.pack(side=tk.RIGHT, padx=(5, 0))

                # Store reference for theme updates
                self.key_btn = key_btn
            else:
                entry = ttk.Entry(container)
                entry.grid(row=i, column=1, sticky="ew", padx=(10, 0), pady=5)

            # Pre-fill if value exists
            val = info.get(key, "")
            if key == 'bpm' and val:
                try:
                    raw_bpm = int(round(float(val)))
                    entry.insert(0, str(raw_bpm))
                    # Store raw value in entry's data for saving
                    entry.raw_value = str(val)
                except (ValueError, TypeError):
                    entry.insert(0, "")
                    entry.raw_value = str(val)
            elif key == 'key' and val:
                try:
                    camelot_val = key_to_camelot(str(val))
                except Exception:
                    camelot_val = None

                if camelot_val:
                    entry.insert(0, f"{camelot_val}")
                    entry.raw_value = str(val)
                else:
                    entry.insert(0, str(val))
                    entry.raw_value = str(val)
            else:
                if val is None or val == "":
                    entry.insert(0, "")
                else:
                    entry.insert(0, str(val))
                if key == 'bpm':
                    entry.raw_value = None
                elif key == 'key':
                    entry.raw_value = str(val) if val else None

            self.entries[key] = entry

        if 'bpm' in self.entries:
            self.entries['bpm'].bind('<KeyRelease>', lambda e: self._on_bpm_entry_edit())
        if 'key' in self.entries:
            self.entries['key'].bind('<KeyRelease>', lambda e: self._on_key_entry_edit())

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

        self.save_btn = save_btn

    def _save_metadata(self):
        """Save edited metadata back to the file."""
        try:
            metadata_to_save = {}
            for key, entry in self.entries.items():
                val = entry.get().strip()
                if key == 'bpm' and hasattr(entry, 'raw_value'):
                    if entry.raw_value is not None:
                        metadata_to_save[key] = entry.raw_value
                    else:
                        metadata_to_save[key] = val
                else:
                    metadata_to_save[key] = val

            success = save_metadata(self.file_path, metadata_to_save)
            if success:
                messagebox.showinfo("Success", "Metadata saved successfully!", parent=self.window)
                self.file_info = self._get_file_info()

                if self.metadata_saved_callback:
                    try:
                        self.metadata_saved_callback(self.file_path)
                    except Exception:
                        pass
            else:
                messagebox.showerror("Error", "Could not load file for writing.", parent=self.window)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save metadata: {e}", parent=self.window)

    def _calculate_bpm(self):
        """Calculate BPM for the current file in a background thread."""
        try:
            # Disable button during analysis
            if self.bpm_btn:
                self.bpm_btn.configure(state="disabled", text="Calculating...")

            # Use manager for analysis
            analysis_manager.submit_bpm_analysis(self.file_path, self._on_bpm_calculation_complete, self.window)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start BPM analysis: {e}", parent=self.window)
            # Reset button state
            if self.bpm_btn:
                self.bpm_btn.configure(state="normal", text="Calculate BPM")

    def _on_bpm_calculation_complete(self, filepath, bpm_value):
        """Handle BPM calculation completion."""
        try:
            # Check if filepath matches (though unlikely to mismatch in this modal)
            if self.file_path != filepath:
                return

            if bpm_value is not None:
                if hasattr(self, 'entries') and 'bpm' in self.entries:
                    entry = self.entries['bpm']
                    if entry:
                        entry.delete(0, tk.END)
                        try:
                            raw_bpm = int(round(float(bpm_value)))
                            entry.insert(0, str(raw_bpm))
                            entry.raw_value = str(bpm_value)
                        except (ValueError, TypeError):
                            entry.insert(0, str(bpm_value))
                            entry.raw_value = str(bpm_value)
            else:
                pass
                # Silently fail or could show warning, but standard flow is just nothing happens if invalid
                # messagebox.showwarning("BPM Analysis", "Could not calculate BPM for this file.", parent=self.window)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process BPM result: {e}", parent=self.window)

        if self.bpm_btn:
            self.bpm_btn.configure(state="normal", text="Calculate BPM")

    def _on_bpm_calculation_error(self, error_message):
        """Handle BPM calculation error."""
        messagebox.showerror("BPM Analysis Error", f"Failed to calculate BPM: {error_message}", parent=self.window)

        if self.bpm_btn:
            self.bpm_btn.configure(state="normal", text="Calculate BPM")

    def _on_bpm_entry_edit(self):
        """Handle manual editing of BPM entry field."""
        if 'bpm' in self.entries:
            entry = self.entries['bpm']
            if entry and hasattr(entry, 'raw_value'):
                entry.raw_value = None

    def _calculate_key(self):
        """Calculate Key for the current file in a background thread."""
        try:
            # Disable button during analysis
            if self.key_btn:
                self.key_btn.configure(state="disabled", text="Calculating...")

            # Use manager for analysis
            analysis_manager.submit_key_analysis(self.file_path, self._on_key_calculation_complete, self.window)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start Key analysis: {e}", parent=self.window)
            # Reset button state
            if self.key_btn:
                self.key_btn.configure(state="normal", text="Calculate Key")

    def _on_key_calculation_complete(self, filepath, key_value):
        """Handle Key calculation completion."""
        try:
            if self.file_path != filepath:
                return

            if key_value is not None:
                if hasattr(self, 'entries') and 'key' in self.entries:
                    entry = self.entries['key']
                    if entry:
                        entry.delete(0, tk.END)
                        # Compute Camelot and display inside the Key entry as "Key (Camelot)"
                        try:
                            camelot_val = key_to_camelot(str(key_value))
                        except Exception:
                            camelot_val = None

                        if camelot_val:
                            entry.insert(0, f"{camelot_val}")
                        else:
                            entry.insert(0, str(key_value))

                        # Also update General tab immediately
                        try:
                            self._render_general_with_overrides(key_override=str(key_value), camelot_override=camelot_val)
                        except Exception:
                            pass
            else:
                messagebox.showwarning("Key Analysis", "Could not calculate Key for this file.", parent=self.window)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process Key result: {e}", parent=self.window)

        # Render general tab with overrides so calculated key/Camelot are visible immediately
        try:
            if key_value is not None:
                camelot_val = None
                try:
                    camelot_val = key_to_camelot(str(key_value))
                except Exception:
                    camelot_val = None
                self._render_general_with_overrides(key_override=str(key_value), camelot_override=camelot_val)

                # Update inline Camelot label next to Key entry if present
                try:
                    if getattr(self, 'key_camelot_label', None) is not None:
                        if camelot_val:
                            self.key_camelot_label.configure(text=f"{camelot_val}")
                        else:
                            self.key_camelot_label.configure(text="")
                except Exception:
                    pass
        except Exception:
            pass

        if self.key_btn:
            self.key_btn.configure(state="normal", text="Calculate Key")

    def _on_key_calculation_error(self, error_message):
        """Handle Key calculation error."""
        messagebox.showerror("Key Analysis Error", f"Failed to calculate Key: {error_message}", parent=self.window)

        if self.key_btn:
            self.key_btn.configure(state="normal", text="Calculate Key")

    def _on_key_entry_edit(self):
        """Handle manual editing of Key entry field.

        Behavior:
        - If user types a Camelot code (e.g., '8A'), normalize and display it and clear raw_value.
        - If user types a raw key (e.g., 'Am' or 'A minor'), compute Camelot, display Camelot only, and store raw key in entry.raw_value for saving.
        - If no mapping found, leave typed value and store it as raw_value so it can be saved.
        """
        import re
        try:
            if 'key' in self.entries:
                entry = self.entries['key']
                if not entry:
                    return

                full_text = entry.get().strip()

                # Camelot pattern: e.g., '8A' or '11B' (allow spaces and case-insensitive)
                camelot_match = re.fullmatch(r"\s*(\d{1,2})\s*([ABab])\s*", full_text)
                if camelot_match:
                    # User provided Camelot directly; normalize and clear raw_value
                    num = camelot_match.group(1)
                    letter = camelot_match.group(2).upper()
                    camelot_val = f"{int(num)}{letter}"
                    try:
                        entry.delete(0, tk.END)
                        entry.insert(0, camelot_val)
                        entry.raw_value = None
                    except Exception:
                        pass

                    # Update general tab to show the Camelot (no raw key)
                    try:
                        self._render_general_with_overrides(key_override=None, camelot_override=camelot_val)
                    except Exception:
                        pass
                    return

                # Otherwise, treat input as raw key attempt: try to compute Camelot
                raw = full_text
                try:
                    camelot_val = key_to_camelot(raw)
                except Exception:
                    camelot_val = None

                if camelot_val:
                    try:
                        entry.delete(0, tk.END)
                        entry.insert(0, camelot_val)
                        entry.raw_value = raw
                    except Exception:
                        pass

                    # Update General tab with raw+camelot
                    try:
                        self._render_general_with_overrides(key_override=raw, camelot_override=camelot_val)
                    except Exception:
                        pass
                else:
                    # No mapping found; keep the typed raw value and mark it for saving
                    try:
                        entry.raw_value = raw
                    except Exception:
                        pass
                    try:
                        self._render_general_with_overrides(key_override=raw, camelot_override=None)
                    except Exception:
                        pass
        except Exception:
            pass
