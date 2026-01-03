"""
Generic documentation viewer for markdown files.
"""
import os
import re
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox

from app.paths import get_docs_path


class DocumentationWindow(ctk.CTkToplevel):
    """Generic documentation window that displays markdown files with styled widgets."""

    def __init__(self, parent, theme_manager, settings, doc_filename):
        super().__init__(parent)

        self.theme_manager = theme_manager
        self.settings = settings
        self.doc_filename = doc_filename

        # Extract title from filename (remove .md and capitalize)
        title = doc_filename.replace('.md', '').replace('_', ' ').title()
        self.title(f"{title} - Documentation")

        self.geometry("900x700")
        self.resizable(True, True)

        # Hide window initially to prevent flickering during positioning
        self.withdraw()

        # Center the window
        self.transient(parent)

        # Get theme colors
        palette = self.theme_manager.palette
        is_dark = self.settings.theme.lower() == 'dark'

        self.bg_color = palette.get("bg", "#1E1E1E" if is_dark else "#FAFAFA")
        self.fg_color = palette.get("fg", "#FFFFFF" if is_dark else "#000000")
        self.accent_color = palette.get("accent", "#0078d4")
        self.btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        self.btn_fg_color = palette.get("button_fg_color", "#FFFFFF" if is_dark else "#000000")

        self.configure(fg_color=self.bg_color)

        # Initialize scrollable frame reference
        self.scrollable_frame = None

        # Load and display content
        self._create_content()

        # Center and show window
        self._center_and_show()

    def update_theme(self):
        """Update the window colors when theme changes."""
        # Force theme manager to reload current theme
        try:
            self.theme_manager.reload()
        except:
            pass

        # Small delay to ensure theme is fully loaded
        self.after(50, self._apply_theme_updates)

    def _apply_theme_updates(self):
        """Apply theme updates after a small delay."""
        # Get new theme colors after reload
        palette = self.theme_manager.palette
        is_dark = self.settings.theme.lower() == 'dark'

        # Update CustomTkinter appearance mode
        try:
            ctk.set_appearance_mode("Dark" if is_dark else "Light")
        except:
            pass

        # Update color variables
        self.bg_color = palette.get("bg", "#1E1E1E" if is_dark else "#FAFAFA")
        self.fg_color = palette.get("fg", "#FFFFFF" if is_dark else "#000000")
        self.accent_color = palette.get("accent", "#0078d4")
        self.btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        self.btn_fg_color = palette.get("button_fg_color", "#FFFFFF" if is_dark else "#000000")

        # Update window background
        self.configure(fg_color=self.bg_color)

        # Clear existing content properly
        if self.scrollable_frame:
            # Destroy all widgets in the scrollable frame
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()

        # Recreate content with new theme
        self._create_content()

    def _create_content(self):
        """Load markdown file and parse into styled widgets."""
        # Create scrollable frame only if it doesn't exist
        if not self.scrollable_frame:
            self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color=self.bg_color)
            self.scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        else:
            # Update existing scrollable frame background
            self.scrollable_frame.configure(fg_color=self.bg_color)

        # Calculate dynamic wraplength based on window width
        try:
            window_width = self.winfo_width()
            if window_width > 100:  # Valid window width
                wraplength = window_width - 80  # Account for padding
            else:
                wraplength = 820  # Default for 900px window
        except:
            wraplength = 820  # Default fallback

        # Load markdown content
        docs_path = get_docs_path()
        doc_file = os.path.join(docs_path, self.doc_filename)

        try:
            if not os.path.exists(doc_file):
                raise FileNotFoundError(f"Documentation file not found: {doc_file}")

            with open(doc_file, 'r', encoding='utf-8') as f:
                markdown_content = f.read()

            # Parse and render markdown
            self._render_markdown(markdown_content, wraplength)

            # Close button
            close_button = ctk.CTkButton(
                self.scrollable_frame,
                text="Close",
                font=("Segoe UI", 12),
                fg_color=self.btn_bg,
                hover_color=self.theme_manager.palette.get("accent_hover", "#106ebe"),
                text_color=self.btn_fg_color,
                width=80,
                height=32,
                command=self.destroy
            )
            close_button.pack(pady=20)

        except FileNotFoundError as e:
            # Show error message
            error_label = ctk.CTkLabel(
                self.scrollable_frame,
                text=f"❌ Documentation file not found:\n{self.doc_filename}",
                font=("Segoe UI", 14),
                text_color=self.fg_color,
                fg_color="transparent",
                justify="center"
            )
            error_label.pack(expand=True, pady=50)

        except Exception as e:
            # Show generic error
            error_label = ctk.CTkLabel(
                self.scrollable_frame,
                text=f"❌ Error loading documentation:\n{str(e)}",
                font=("Segoe UI", 14),
                text_color=self.fg_color,
                fg_color="transparent",
                justify="center"
            )
            error_label.pack(expand=True, pady=50)

    def _render_markdown(self, content, wraplength):
        """Parse markdown content and create styled widgets."""
        lines = content.split('\n')
        i = 0
        in_code_block = False
        code_lines = []
        in_list = False
        list_items = []

        while i < len(lines):
            line = lines[i]

            # Code blocks
            if line.strip().startswith('```'):
                if in_code_block:
                    # End code block
                    self._create_code_block('\n'.join(code_lines), wraplength)
                    code_lines = []
                    in_code_block = False
                else:
                    # Start code block
                    in_code_block = True
                i += 1
                continue

            if in_code_block:
                code_lines.append(line)
                i += 1
                continue

            # Flush list items if we're leaving a list
            if in_list and not (line.strip().startswith('-') or line.strip().startswith('*') or
                              re.match(r'^\d+\.', line.strip())):
                self._create_list(list_items, wraplength)
                list_items = []
                in_list = False

            # Headers
            if line.startswith('# '):
                self._create_heading(line[2:], 1, wraplength)
            elif line.startswith('## '):
                self._create_heading(line[3:], 2, wraplength)
            elif line.startswith('### '):
                self._create_heading(line[4:], 3, wraplength)
            elif line.startswith('#### '):
                self._create_heading(line[5:], 4, wraplength)

            # Lists
            elif line.strip().startswith('-') or line.strip().startswith('*'):
                in_list = True
                list_items.append(('bullet', line.strip()[1:].strip()))
            elif re.match(r'^\d+\.', line.strip()):
                in_list = True
                match = re.match(r'^(\d+)\.\s*(.+)', line.strip())
                if match:
                    list_items.append(('numbered', match.group(2)))

            # Horizontal rule
            elif line.strip() in ['---', '***', '___']:
                self._create_separator()

            # Regular paragraph
            elif line.strip():
                # Skip if it was part of a header or list
                if not (line.startswith('#') or line.strip().startswith('-') or
                       line.strip().startswith('*') or re.match(r'^\d+\.', line.strip())):
                    self._create_paragraph(line, wraplength)

            i += 1

        # Flush remaining list items
        if in_list and list_items:
            self._create_list(list_items, wraplength)

    def _create_heading(self, text, level, wraplength):
        """Create a heading widget."""
        sizes = {1: 28, 2: 24, 3: 18, 4: 16}
        size = sizes.get(level, 14)

        # Clean bold/italic markdown
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)

        pady_top = 20 if level <= 2 else 15
        pady_bottom = 10 if level <= 2 else 8

        label = ctk.CTkLabel(
            self.scrollable_frame,
            text=text,
            font=("Segoe UI", size, "bold"),
            text_color=self.accent_color,
            fg_color="transparent",
            wraplength=wraplength,
            justify="left"
        )
        label.pack(pady=(pady_top, pady_bottom), anchor="w")

    def _create_paragraph(self, text, wraplength):
        """Create a paragraph widget."""
        # Clean markdown formatting
        text = self._clean_markdown(text)

        if not text.strip():
            return

        label = ctk.CTkLabel(
            self.scrollable_frame,
            text=text,
            font=("Segoe UI", 14),
            text_color=self.fg_color,
            fg_color="transparent",
            wraplength=wraplength,
            justify="left"
        )
        label.pack(pady=(0, 10), anchor="w")

    def _create_list(self, items, wraplength):
        """Create a list widget."""
        for list_type, text in items:
            # Clean markdown formatting
            text = self._clean_markdown(text)

            if list_type == 'bullet':
                prefix = "  •  "
            else:
                prefix = "  "

            label = ctk.CTkLabel(
                self.scrollable_frame,
                text=f"{prefix}{text}",
                font=("Segoe UI", 14),
                text_color=self.fg_color,
                fg_color="transparent",
                wraplength=wraplength - 40,
                justify="left"
            )
            label.pack(pady=(0, 6), anchor="w", padx=(20, 0))

    def _create_code_block(self, code, wraplength):
        """Create a code block widget."""
        is_dark = self.settings.theme.lower() == 'dark'
        code_bg = "#2A2A2A" if is_dark else "#F0F0F0"
        code_fg = "#D4D4D4" if is_dark else "#333333"

        label = ctk.CTkLabel(
            self.scrollable_frame,
            text=code,
            font=("Consolas", 13),
            text_color=code_fg,
            fg_color=code_bg,
            wraplength=wraplength - 40,
            justify="left",
            corner_radius=6
        )
        label.pack(pady=(5, 15), anchor="w", padx=10, fill=tk.X)

    def _create_separator(self):
        """Create a horizontal separator."""
        frame = ctk.CTkFrame(
            self.scrollable_frame,
            height=1,
            fg_color=self.accent_color
        )
        frame.pack(fill=tk.X, pady=15)

    def _clean_markdown(self, text):
        """Remove markdown formatting from text."""
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)
        # Inline code
        text = re.sub(r'`(.+?)`', r'\1', text)
        # Links [text](url)
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)

        return text

    def _center_and_show(self):
        """Center the window and show it."""
        self.update_idletasks()
        # Get current geometry to use the size set in __init__
        current_geom = self.geometry()
        # Extract width and height (format is "widthxheight+x+y" or "widthxheight")
        if '+' in current_geom:
            size_part = current_geom.split('+')[0]
        else:
            size_part = current_geom

        if 'x' in size_part:
            width, height = map(int, size_part.split('x'))
        else:
            width, height = 900, 700  # fallback

        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.deiconify()
