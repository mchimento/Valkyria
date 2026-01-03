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

        self.configure(bg=self.palette.get("bg", "#ffffff"))

        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Play on double click switch with status label
        switch_frame = ttk.Frame(main_frame)
        switch_frame.pack(anchor='w', pady=10, fill='x')

        self.play_on_double_var = tk.BooleanVar(value=self.app_state.play_on_double)

        self.switch = ctk.CTkSwitch(
            switch_frame,
            text="Play on double-click:",
            variable=self.play_on_double_var,
            command=self._on_play_on_double_change,
            progress_color=self.palette.get("accent", "#0078d4"),
            text_color=self.palette.get("fg", "#000000"),
            bg_color=self.palette.get("bg", "#ffffff"),
            button_color=self.palette.get("accent", "#ffffff"),
            button_hover_color=self.palette.get("button_hover", "#106ebe")
        )
        self.switch.pack(side='left')

        self.switch_status_label = ctk.CTkLabel(
            switch_frame,
            text="Enabled" if self.app_state.play_on_double else "Disabled",
            text_color=self.palette.get("accent", "#0078d4") if self.app_state.play_on_double else self.palette.get("fg", "#808080"),
            font=("Segoe UI", 11, "bold"),
            bg_color=self.palette.get("bg", "#ffffff")
        )
        self.switch_status_label.pack(side='left', padx=(10, 0))

        # Close button
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(side='bottom', fill='x', pady=(20, 0))

        self.close_btn = ctk.CTkButton(
            btn_frame,
            text="Close",
            command=self.destroy,
            width=80,
            height=32,
            fg_color=self.palette.get("button_bg_color", "#0078d4"),
            text_color=self.palette.get("button_fg_color", "#ffffff"),
            hover_color=self.palette.get("button_hover", "#106ebe")
        )
        self.close_btn.pack(side='right')

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

        # Update status label
        self.switch_status_label.configure(
            text="Enabled" if new_value else "Disabled",
            text_color=self.palette.get("accent", "#0078d4") if new_value else self.palette.get("fg", "#808080")
        )

    def _apply_theme(self):
        """Apply theme to widgets."""
        bg = self.palette.get("bg", "#ffffff")
        fg = self.palette.get("fg", "#000000")

        style = ttk.Style(self)
        style.configure("TFrame", background=bg)

        self.configure(bg=bg)

        # Update switch colors
        if hasattr(self, 'switch'):
            self.switch.configure(
                progress_color=self.palette.get("accent", "#0078d4"),
                text_color=fg,
                bg_color=bg,
                button_color=self.palette.get("accent", "#ffffff"),
                button_hover_color=self.palette.get("button_hover", "#106ebe")
            )

        # Update switch status label colors
        if hasattr(self, 'switch_status_label'):
            is_enabled = self.play_on_double_var.get()
            self.switch_status_label.configure(
                text_color=self.palette.get("accent", "#0078d4") if is_enabled else self.palette.get("fg", "#808080"),
                bg_color=bg
            )

        # Update close button colors
        if hasattr(self, 'close_btn'):
            self.close_btn.configure(
                bg_color=bg,
                fg_color=self.palette.get("button_bg_color", "#0078d4"),
                text_color=self.palette.get("button_fg_color", "#ffffff"),
                hover_color=self.palette.get("button_hover", "#106ebe")
            )

        # Recursive restyle
        def restyle(widget):
            if isinstance(widget, ttk.Frame):
                widget.configure(style="TFrame")
            elif isinstance(widget, tk.Frame):
                widget.configure(bg=bg)

            for child in widget.winfo_children():
                if not isinstance(child, (ctk.CTkButton, ctk.CTkLabel, ctk.CTkSwitch)):
                    restyle(child)

        restyle(self)

    def update_theme(self):
        """Update theme when theme changes."""
        self.palette = self.theme_manager.palette
        self._apply_theme()
