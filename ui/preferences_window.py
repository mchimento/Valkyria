import tkinter as tk
from tkinter import ttk
import tkinter.font as tkFont
import customtkinter as ctk
from ui.utils import center_window

class PreferencesWindow(tk.Toplevel):
    """
    Proper Preferences window with organized sections:
    - Interface section for theme and UI preferences
    - Audio section for BPM and audio preferences
    - Easily extensible for additional sections
    """
    def __init__(self, master, settings, theme_manager, on_apply=None, on_bpm_preference_change=None):
        super().__init__(master)

        self.settings = settings
        self.theme_manager = theme_manager
        self.palette = theme_manager.palette
        self.on_apply = on_apply
        self.on_bpm_preference_change = on_bpm_preference_change
        self.original_theme = settings.theme
        self.original_bpm_mode = settings.bpm_mode


        self.title("Preferences")
        self.geometry("300x400")
        self.resizable(False, False)
        self.transient(master)

        # Hide window initially to prevent flickering during positioning
        self.withdraw()

        center_window(self, master)

        # Create main container with padding
        main_container = ttk.Frame(self)
        main_container.pack(fill='both', expand=True, padx=20, pady=20)

        # Create notebook for sections
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill='both', expand=True)

        # Create sections
        self._create_interface_section()
        self._create_audio_section()
        # Add more sections here

        # Button frame
        btn_frame = ttk.Frame(main_container)
        btn_frame.pack(fill='x', pady=(20, 0))

        self._create_buttons(btn_frame)

        self._apply_theme_to_this_window(self.settings.theme)

        # Bind window close (X button) to cancel instead of default destroy
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        # Show window after all setup is complete
        self.deiconify()

    def _create_interface_section(self):
        """Create the Interface section with theme preferences."""
        interface_frame = ttk.Frame(self.notebook)
        self.notebook.add(interface_frame, text="Interface")

        # Add padding to the interface frame
        content_frame = ttk.Frame(interface_frame)
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Theme selection
        ttk.Label(content_frame, text="Theme",
                font=(self.palette.get("ui_font", "Segoe UI"), 10, "bold")).pack(anchor='w', pady=(0, 10))

        # Use lowercase theme consistently
        self.var = tk.StringVar(value=self.settings.theme.lower())
        theme_frame = ttk.Frame(content_frame)
        theme_frame.pack(fill='x', pady=(0, 20))

        self.rb_light = ttk.Radiobutton(theme_frame, text="Light", value="light",
                                        variable=self.var, command=self._preview_theme)
        self.rb_light.pack(anchor='w', pady=2)

        self.rb_dark = ttk.Radiobutton(theme_frame, text="Dark", value="dark",
                                       variable=self.var, command=self._preview_theme)
        self.rb_dark.pack(anchor='w', pady=2)

    def _create_audio_section(self):
        audio_frame = ttk.Frame(self.notebook)
        self.notebook.add(audio_frame, text="Audio")

        # Add padding to the audio frame
        content_frame = ttk.Frame(audio_frame)
        content_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # BPM Mode selection
        ttk.Label(content_frame, text="BPM Mode",
                font=(self.palette.get("ui_font", "Segoe UI"), 10, "bold")).pack(anchor='w', pady=(0, 10))

        self.bpm_var = tk.StringVar(value=self.settings.bpm_mode)
        bpm_frame = ttk.Frame(content_frame)
        bpm_frame.pack(fill='x', pady=(0, 5))

        self.rb_perceived = ttk.Radiobutton(bpm_frame, text="Perceived (50-100 BPM)",
                                          value="perceived", variable=self.bpm_var)
        self.rb_perceived.pack(anchor='w', pady=2)

        self.rb_raw = ttk.Radiobutton(bpm_frame, text="Raw (detected tempo)",
                                     value="raw", variable=self.bpm_var)
        self.rb_raw.pack(anchor='w', pady=2)



    def _create_buttons(self, parent_frame):
        """Create Save and Cancel buttons."""
        # Get button colors from theme palette (matching controls.py)
        palette = self.theme_manager.palette
        btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        btn_fg = palette.get("button_fg_color", "#ffffff")
        btn_hover = palette.get("button_hover", palette.get("accent_hover", "#106ebe"))

        UI_FONT = (palette.get("ui_font", "Segoe UI"), 12)
        btn_width = 80
        btn_height = 32

        # Right-align buttons
        button_container = ttk.Frame(parent_frame)
        button_container.pack(anchor='e')

        self.cancel_btn = ctk.CTkButton(
            button_container,
            text="Cancel",
            command=self._cancel,
            font=UI_FONT,
            width=btn_width,
            height=btn_height,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=btn_hover
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=(5, 0))

        self.save_btn = ctk.CTkButton(
            button_container,
            text="Save",
            command=self._save,
            font=UI_FONT,
            width=btn_width,
            height=btn_height,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=btn_hover
        )
        self.save_btn.pack(side=tk.RIGHT)

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
        # Update palette reference to current theme
        self.palette = self.theme_manager.palette

        palette = self.theme_manager.palette
        bg = palette.get("bg", "#ffffff")
        fg = palette.get("fg", "#000000")

        # Toplevel background
        self.configure(bg=bg)

        # Apply global theme to ttk widgets
        self.theme_manager.apply_to(self)
        style = ttk.Style(self)

        # Configure notebook style
        style.configure("Prefs.TNotebook", background=bg, tabmargins=[2, 5, 2, 0])
        style.configure("Prefs.TNotebook.Tab",
                       background=bg,
                       foreground=fg,
                       padding=[12, 8])
        style.map("Prefs.TNotebook.Tab",
                 background=[("selected", palette.get("accent", "#0078d4")),
                           ("active", palette.get("button_hover", "#106ebe"))],
                 foreground=[("selected", "#ffffff"),
                           ("active", fg)],
                 padding=[("selected", [6, 6])])

        # Apply notebook style
        self.notebook.configure(style="Prefs.TNotebook")

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

        # Checkbutton style
        style.layout("Prefs.TCheckbutton", [
            ("Checkbutton.padding", {
                "children": [
                    ("Checkbutton.indicator", {"side": "left", "sticky": ""}),
                    ("Checkbutton.label", {"side": "left", "sticky": ""})
                ],
                "sticky": "nswe"
            })
        ])
        style.configure(
            "Prefs.TCheckbutton",
            background=bg,
            foreground=fg,
            focuscolor=bg,
            indicatorcolor=bg
        )

        # Apply radiobutton style to all radio buttons
        if hasattr(self, 'rb_light'):
            self.rb_light.configure(style="Prefs.TRadiobutton")
            self.rb_dark.configure(style="Prefs.TRadiobutton")
            self.rb_perceived.configure(style="Prefs.TRadiobutton")
            self.rb_raw.configure(style="Prefs.TRadiobutton")

        # Frame and label styles
        style.configure("Prefs.TFrame", background=bg)
        style.configure("Prefs.TLabel", background=bg, foreground=fg)

        # Recursive restyle for all widgets
        def restyle(widget):
            if isinstance(widget, (tk.Button, ctk.CTkButton)):
                return  # buttons handled separately
            if isinstance(widget, tk.Frame):
                widget.configure(bg=bg)
            if isinstance(widget, ttk.Notebook):
                widget.configure(style="Prefs.TNotebook")
            elif isinstance(widget, (ttk.Frame, ttk.LabelFrame)):
                widget.configure(style="Prefs.TFrame")
            elif isinstance(widget, ttk.Label):
                widget.configure(style="Prefs.TLabel")
                # Also apply to any nested labels
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Label):
                        child.configure(style="Prefs.TLabel")
            elif isinstance(widget, tk.Label):
                widget.configure(background=bg, foreground=self.palette.get("fg", "#FFFFFF"))
            elif isinstance(widget, ttk.Radiobutton):
                widget.configure(style="Prefs.TRadiobutton")
            elif isinstance(widget, ttk.Checkbutton):
                widget.configure(style="Prefs.TCheckbutton")

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
        new_bpm_mode = self.bpm_var.get()

        # Check if BPM mode changed
        bpm_mode_changed = (new_bpm_mode != self.settings.bpm_mode)

        self.settings.theme = new_theme
        self.settings.bpm_mode = new_bpm_mode
        self.settings.save()

        # Update global BPM preference
        from audio.metadata import set_bpm_preference
        set_bpm_preference(new_bpm_mode)

        # Trigger BPM refresh if mode changed
        if bpm_mode_changed and callable(self.on_bpm_preference_change):
            self.on_bpm_preference_change()

        if callable(self.on_apply):
            self.on_apply(new_theme)
        self.destroy()

    def _cancel(self):
        self.settings.theme = self.original_theme
        self.settings.bpm_mode = self.original_bpm_mode
        self.settings.save()

        # Restore original BPM mode
        from audio.metadata import set_bpm_preference
        set_bpm_preference(self.settings.bpm_mode)

        # Trigger BPM refresh if mode was different
        if self.original_bpm_mode != self.settings.bpm_mode and callable(self.on_bpm_preference_change):
            self.on_bpm_preference_change()

        if callable(self.on_apply):
            self.on_apply(self.original_theme)
        self.destroy()
