"""Dialog for setting playback time limits on tracks."""
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk


class TimeLimitDialog(ctk.CTkToplevel):
    """Dialog to set a time limit for track playback."""

    def __init__(self, parent, theme, current_limit=None):
        super().__init__(parent)

        self.theme = theme
        self.result = None
        self.current_limit = current_limit

        self.title("Set Playback Time Limit")
        self.geometry("360x280")
        self.resizable(False, False)

        # Make modal
        self.transient(parent)

        self._setup_ui()
        self._center_window()

    def _setup_ui(self):
        """Setup the dialog UI."""
        # Get theme colors
        palette = self.theme.palette if hasattr(self.theme, 'palette') else {}
        bg = palette.get("bg", "#1E1E1E")
        fg = palette.get("fg", "#FFFFFF")
        button_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        button_fg = palette.get("button_fg_color", "#ffffff")
        button_hover = palette.get("button_hover", palette.get("accent_hover", "#106ebe"))
        entry_bg = palette.get("entry_bg", "#2D2D2D")
        frame_bg = palette.get("frame_bg", "#252525")

        # Set dialog background
        self.configure(fg_color=bg)

        # Main container
        self.main_frame = ctk.CTkFrame(self, fg_color=frame_bg)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title label
        self.title_label = ctk.CTkLabel(
            self.main_frame,
            text="Play selected track for:",
            font=("Segoe UI", 14, "bold"),
            text_color=fg
        )
        self.title_label.pack(pady=(0, 15))

        # Preset buttons frame
        self.presets_frame = ctk.CTkFrame(self.main_frame, fg_color=frame_bg)
        self.presets_frame.pack(fill="x", pady=(0, 15))

        # Preset buttons
        presets = [
            ("10 seconds", 10),
            ("30 seconds", 30),
            ("1 minute", 60),
            ("2 minutes", 120)
        ]

        self.preset_buttons = []
        for i, (label, seconds) in enumerate(presets):
            btn = ctk.CTkButton(
                self.presets_frame,
                text=label,
                command=lambda s=seconds: self._preset_to_entry(s),
                width=150,
                height=32,
                fg_color=button_bg,
                text_color=button_fg,
                hover_color=button_hover
            )
            row = i // 2
            col = i % 2
            btn.grid(row=row, column=col, padx=5, pady=5)
            self.preset_buttons.append(btn)

        # Custom value frame
        self.custom_frame = ctk.CTkFrame(self.main_frame, fg_color=frame_bg)
        self.custom_frame.pack(fill="x", pady=(0, 15))

        self.custom_label = ctk.CTkLabel(
            self.custom_frame,
            text="Custom (seconds):",
            font=("Segoe UI", 12),
            text_color=fg
        )
        self.custom_label.pack(side="left", padx=(10, 5))

        self.custom_entry = ctk.CTkEntry(
            self.custom_frame,
            width=80,
            placeholder_text="e.g. 45",
            fg_color=entry_bg,
            text_color=fg,
            border_color=button_bg
        )
        self.custom_entry.pack(side="left", padx=5)

        # If there's a current limit, pre-fill it
        if self.current_limit is not None:
            self.custom_entry.insert(0, str(int(self.current_limit)))

        self.custom_btn = ctk.CTkButton(
            self.custom_frame,
            text="Set",
            command=self._set_custom_limit,
            width=60,
            height=28,
            fg_color=button_bg,
            text_color=button_fg,
            hover_color=button_hover
        )
        self.custom_btn.pack(side="left", padx=5)

        # Clear and Cancel buttons
        self.buttons_frame = ctk.CTkFrame(self.main_frame, fg_color=frame_bg)
        self.buttons_frame.pack(fill="x", pady=(10, 0))

        self.clear_btn = ctk.CTkButton(
            self.buttons_frame,
            text="Clear Limit",
            command=self._clear_limit,
            fg_color=button_bg,
            text_color=button_fg,
            hover_color=button_hover,
            height=32
        )
        self.clear_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.cancel_btn = ctk.CTkButton(
            self.buttons_frame,
            text="Cancel",
            command=self._cancel,
            fg_color=button_bg,
            text_color=button_fg,
            hover_color=button_hover,
            height=32
        )
        self.cancel_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))

        # Bind Enter key to custom entry
        self.custom_entry.bind("<Return>", lambda e: self._set_custom_limit())
        self.custom_entry.bind("<Escape>", lambda e: self._cancel())

    def _center_window(self):
        """Center the dialog on the parent window."""
        self.update_idletasks()
        parent = self.master

        # Get parent window position and size
        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        # Get dialog size
        dialog_width = self.winfo_width()
        dialog_height = self.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        self.geometry(f"+{x}+{y}")

    def update_theme(self):
        """Update colors when theme changes."""
        palette = self.theme.palette if hasattr(self.theme, 'palette') else {}

        bg = palette.get("bg", "#1E1E1E")
        fg = palette.get("fg", "#FFFFFF")
        button_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        button_fg = palette.get("button_fg_color", "#ffffff")
        button_hover = palette.get("button_hover", palette.get("accent_hover", "#106ebe"))
        entry_bg = palette.get("entry_bg", "#2D2D2D")
        frame_bg = palette.get("frame_bg", "#252525")

        # Update dialog background
        self.configure(fg_color=bg)

        # Update frames
        self.main_frame.configure(fg_color=frame_bg)
        self.presets_frame.configure(fg_color=frame_bg)
        self.custom_frame.configure(fg_color=frame_bg)
        self.buttons_frame.configure(fg_color=frame_bg)

        # Update title label
        self.title_label.configure(text_color=fg)

        # Update preset buttons
        for btn in self.preset_buttons:
            btn.configure(fg_color=button_bg, text_color=button_fg, hover_color=button_hover)

        # Update custom label
        self.custom_label.configure(text_color=fg)

        # Update custom entry
        self.custom_entry.configure(fg_color=entry_bg, text_color=fg, border_color=button_bg)

        # Update custom button
        self.custom_btn.configure(fg_color=button_bg, text_color=button_fg, hover_color=button_hover)

        # Update clear and cancel buttons
        self.clear_btn.configure(fg_color=button_bg, text_color=button_fg, hover_color=button_hover)
        self.cancel_btn.configure(fg_color=button_bg, text_color=button_fg, hover_color=button_hover)

    def _preset_to_entry(self, seconds):
        """Populate the custom entry field with a preset value."""
        self.custom_entry.delete(0, "end")
        self.custom_entry.insert(0, str(int(seconds)))
        self.custom_entry.focus()

    def _set_limit(self, seconds):
        """Set the time limit to the specified number of seconds."""
        self.result = float(seconds)
        self.destroy()

    def _set_custom_limit(self):
        """Set a custom time limit from the entry field."""
        try:
            value = self.custom_entry.get().strip()
            if not value:
                return

            seconds = float(value)
            if seconds <= 0:
                return

            self.result = seconds
            self.destroy()
        except ValueError:
            # Invalid input, do nothing
            pass

    def _clear_limit(self):
        """Clear the time limit."""
        self.result = None
        self.destroy()

    def _cancel(self):
        """Cancel the dialog without changes."""
        self.result = "CANCEL"
        self.destroy()

    def get_result(self):
        """Get the result after the dialog is closed."""
        self.wait_window()
        return self.result
