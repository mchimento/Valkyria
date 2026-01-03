import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from ui.utils import center_window

class PlaybackFeaturesView(tk.Toplevel):
    def __init__(self, master, state, settings, theme_manager):
        super().__init__(master)
        self.app_state = state
        self.settings = settings
        self.theme_manager = theme_manager
        self.palette = theme_manager.palette

        self.title("Playback Features")
        self.geometry("300x150")
        self.resizable(False, False)
        self.transient(master)

        center_window(self, master)

        # Apply theme
        self.configure(bg=self.palette.get("bg", "#ffffff"))

        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Play on double click checkbox
        self.play_on_double_var = tk.BooleanVar(value=self.app_state.play_on_double)

        cb = ttk.Checkbutton(
            main_frame,
            text="Play on double-click",
            variable=self.play_on_double_var,
            command=self._on_play_on_double_change,
            style='TCheckbutton'
        )
        cb.pack(anchor='w', pady=10)

        # Close button
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(side='bottom', fill='x', pady=(20, 0))

        close_btn = ctk.CTkButton(
            btn_frame,
            text="Close",
            command=self.destroy,
            width=80,
            height=32,
            fg_color=self.palette.get("button_bg_color", "#0078d4"),
            text_color=self.palette.get("button_fg_color", "#ffffff"),
            hover_color=self.palette.get("button_hover", "#106ebe")
        )
        close_btn.pack(side='right')

        self._apply_theme()

    def _on_play_on_double_change(self):
        """Handle play on double-click setting change."""
        new_value = self.play_on_double_var.get()

        # Update both settings and state
        if self.settings:
            self.settings.play_on_double = new_value
            try:
                self.settings.save()
            except Exception:
                pass

        # Update state as well since playlist view checks state.play_on_double
        self.app_state.play_on_double = new_value

    def _apply_theme(self):
        """Apply theme to widgets."""
        bg = self.palette.get("bg", "#ffffff")
        fg = self.palette.get("fg", "#000000")

        style = ttk.Style(self)
        style.configure("TFrame", background=bg)
        style.configure("TCheckbutton", background=bg, foreground=fg)

        self.configure(bg=bg)

        # Recursive restyle
        def restyle(widget):
            if isinstance(widget, ttk.Frame):
                widget.configure(style="TFrame")
            elif isinstance(widget, tk.Frame):
                widget.configure(bg=bg)
            elif isinstance(widget, ttk.Checkbutton):
                widget.configure(style="TCheckbutton")

            for child in widget.winfo_children():
                if not isinstance(child, (ctk.CTkButton, ctk.CTkLabel)):
                    restyle(child)

        restyle(self)
