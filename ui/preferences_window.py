import tkinter as tk
from tkinter import ttk
import tkinter.font as tkFont
import customtkinter as ctk
from ui.utils import center_window

class PreferencesWindow(tk.Toplevel):
    """
    Updated PreferencesWindow with:
    - Live preview including Save/Cancel buttons
    - Radiobutton layout without gray background
    - Save/Cancel themed buttons
    - Cancel restores original theme fully
    """
    def __init__(self, master, settings, theme_manager, on_apply=None):
        super().__init__(master)

        self.settings = settings
        self.theme_manager = theme_manager
        self.palette = theme_manager.palette
        self.on_apply = on_apply
        self.original_theme = settings.theme

        self.title("Preferences")
        self.geometry("150x150")
        self.resizable(False, False)
        self.transient(master)

        # Hide window initially to prevent flickering during positioning
        self.withdraw()

        center_window(self, master)

        ttk.Label(self, text="Theme").pack(pady=(12, 6))

        # Use lowercase theme consistently
        self.var = tk.StringVar(value=self.settings.theme.lower())
        rb_frame = ttk.Frame(self)
        rb_frame.pack(pady=6, padx=12)

        self.rb_light = ttk.Radiobutton(rb_frame, text="Light", value="light",
                                        variable=self.var, command=self._preview_theme)
        self.rb_light.pack(anchor="w")

        self.rb_dark = ttk.Radiobutton(rb_frame, text="Dark", value="dark",
                                       variable=self.var, command=self._preview_theme)
        self.rb_dark.pack(anchor="w")

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=(8, 12))

        # Get button colors from theme palette (matching controls.py)
        palette = self.theme_manager.palette
        btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        btn_fg = palette.get("button_fg_color", "#ffffff")
        btn_hover = palette.get("button_hover", palette.get("accent_hover", "#106ebe"))

        UI_FONT = (palette.get("ui_font", "Segoe UI"), 12)
        btn_width = 70
        btn_height = 30

        self.cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self._cancel,
            font=UI_FONT,
            width=btn_width,
            height=btn_height,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=btn_hover
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=5)

        self.save_btn = ctk.CTkButton(
            btn_frame,
            text="Save",
            command=self._save,
            font=UI_FONT,
            width=btn_width,
            height=btn_height,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=btn_hover
        )
        self.save_btn.pack(side=tk.RIGHT, padx=5)

        self._apply_theme_to_this_window(self.settings.theme)

        # Show window after all setup is complete
        self.deiconify()

    def _preview_theme(self):
        """Update the preferences window and main window for live preview."""
        preview_theme = self.var.get()
        self.theme_manager.settings.theme = preview_theme
        self.theme_manager.reload()

        # Update preferences window
        self._apply_theme_to_this_window(preview_theme)

        # Notify main window via callback
        if callable(self.on_apply):
            self.on_apply(preview_theme)

    def _apply_theme_to_this_window(self, theme_name):
        """Apply theme to all widgets in this window including padding areas."""
        palette = self.theme_manager.palette
        bg = palette.get("bg", "#ffffff")
        fg = palette.get("fg", "#000000")

        # Toplevel background
        self.configure(bg=bg)

        # Apply global theme to ttk widgets
        self.theme_manager.apply_to(self)
        style = ttk.Style(self)

        # Radiobutton style
        style.layout("Prefs.TRadiobutton", [
            ("Radiobutton.padding", {
                "children": [
                    ("Radiobutton.indicator", {"side": "left", "sticky": ""}),
                    ("Radiobutton.label", {"side": "left", "sticky": ""})
                ],
                "sticky": "nswe"
            })
        ])
        style.configure(
            "Prefs.TRadiobutton",
            background=bg,
            foreground=fg,
            focuscolor=bg,
            indicatorcolor=bg
        )
        self.rb_light.configure(style="Prefs.TRadiobutton")
        self.rb_dark.configure(style="Prefs.TRadiobutton")

        # Frame and label styles
        style.configure("Prefs.TFrame", background=bg)
        style.configure("Prefs.TLabel", background=bg, foreground=fg)

        # Recursive restyle for all widgets
        def restyle(widget):
            if isinstance(widget, (tk.Button, ctk.CTkButton)):
                return  # buttons handled separately
            if isinstance(widget, tk.Frame):
                widget.configure(bg=bg)
            if isinstance(widget, (ttk.Frame, ttk.LabelFrame)):
                widget.configure(style="Prefs.TFrame")
            if isinstance(widget, (ttk.Label, tk.Label)):
                widget.configure(background=bg, foreground=fg)
            for child in widget.winfo_children():
                restyle(child)

        restyle(self)

        # Update buttons
        self._apply_button_theme()
        self.update_idletasks()

    def _apply_button_theme(self):
        palette = self.theme_manager.palette
        btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        btn_fg = palette.get("button_fg_color", "#ffffff")
        btn_hover = palette.get("button_hover", palette.get("accent_hover", "#106ebe"))

        # Match button corner background to the frame background
        bg = palette.get("bg", "#ffffff")

        for btn in (self.save_btn, self.cancel_btn):
            btn.configure(fg_color=btn_bg, text_color=btn_fg,
                         hover_color=btn_hover, bg_color=bg)


    def _save(self):
        new_theme = self.var.get()
        self.settings.theme = new_theme
        self.settings.save()
        if callable(self.on_apply):
            self.on_apply(new_theme)
        self.destroy()

    def _cancel(self):
        self.settings.theme = self.original_theme
        self.settings.save()
        if callable(self.on_apply):
            self.on_apply(self.original_theme)
        self.destroy()
