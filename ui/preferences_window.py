import tkinter as tk
from tkinter import ttk
import tkinter.font as tkFont
import customtkinter as ctk
from ui.utils import center_window, apply_theme_titlebar

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
        # Tracks which theme is currently rendered in the main window (may differ
        # from original_theme if the user previewed a different theme)
        self._current_applied_theme = settings.theme


        self.title("Preferences")
        self.geometry("300x400")
        self.resizable(False, False)
        self.transient(master)

        # Hide window initially to prevent flickering during positioning
        self.withdraw()

        center_window(self, master)
        apply_theme_titlebar(self, self.palette)
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

        # Mini Player toggle
        ttk.Label(content_frame, text="Mini Player",
                font=(self.palette.get("ui_font", "Segoe UI"), 10, "bold")).pack(anchor='w', pady=(10, 10))

        # Use CTkFrame for the row to hold switch and status label
        self.mini_player_row = ctk.CTkFrame(content_frame, fg_color="transparent")
        self.mini_player_row.pack(fill='x', pady=(0, 10))

        self.mini_player_var = tk.BooleanVar(value=getattr(self.settings, 'mini_player_enabled', True))

        self.mini_player_switch = ctk.CTkSwitch(
            self.mini_player_row,
            text="Mini player view:",
            variable=self.mini_player_var,
            command=self._on_mini_player_toggle,
            progress_color=self.palette.get("accent", "#0078d4"),
            text_color=self.palette.get("fg", "#000000"),
            fg_color=self.palette.get("switch_bg", "#939393"),
            button_color=self.palette.get("accent", "#ffffff"),
            button_hover_color=self.palette.get("accent_hover", "#106ebe"),
            bg_color="transparent"
        )
        self.mini_player_switch.pack(side='left')

        self.mini_player_status_label = ctk.CTkLabel(
            self.mini_player_row,
            text="Enabled" if self.mini_player_var.get() else "Disabled",
            text_color=self.palette.get("accent", "#0078d4") if self.mini_player_var.get() else self.palette.get("fg", "#808080"),
            font=("Segoe UI", 11, "bold"),
            bg_color="transparent"
        )
        self.mini_player_status_label.pack(side='left', padx=(10, 0))

    def _on_mini_player_toggle(self):
        """Update the mini player status label when toggled."""
        if not hasattr(self, 'mini_player_status_label'):
            return

        is_enabled = self.mini_player_var.get()
        text = "Enabled" if is_enabled else "Disabled"
        text_color = self.palette.get("accent", "#0078d4") if is_enabled else self.palette.get("fg", "#808080")

        self.mini_player_status_label.configure(text=text, text_color=text_color)

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

        # Notify main window via callback and track what is now applied
        if callable(self.on_apply):
            self.on_apply(preview_theme)
        self._current_applied_theme = preview_theme

    def _apply_theme_to_this_window(self, theme_name):
        """Apply theme to all widgets in this window including padding areas."""
        # Update palette reference to current theme
        self.palette = self.theme_manager.palette
        apply_theme_titlebar(self, self.palette)

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
            # Skip buttons as they are handled separately
            if isinstance(widget, (tk.Button, ctk.CTkButton)):
                return

            # Handle CustomTkinter widgets
            if isinstance(widget, ctk.CTkBaseClass):
                # Apply background color
                widget.configure(bg_color=bg)

                # Apply text color to widgets that have text
                if isinstance(widget, (ctk.CTkLabel, ctk.CTkCheckBox, ctk.CTkSwitch, ctk.CTkRadioButton)):
                    # Exclude the mini player status label from generic recoloring
                    if getattr(self, 'mini_player_status_label', None) and widget == self.mini_player_status_label:
                        pass
                    else:
                        widget.configure(text_color=fg)

                # Recurse for children
                for child in widget.winfo_children():
                    restyle(child)
                return

            # Handle Standard Tkinter Widgets
            if isinstance(widget, tk.Frame):
                widget.configure(bg=bg)
            elif isinstance(widget, ttk.Notebook):
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

        # Restore component-specific state (like status labels) after restyle cleanup
        if hasattr(self, 'mini_player_status_label'):
            self._on_mini_player_toggle()

        # Update buttons
        self._apply_button_theme()

        # Update switches
        self._apply_switch_theme()

        self.update_idletasks()

    def _apply_switch_theme(self):
        """Apply theme colors to switch widgets."""
        if not hasattr(self, 'mini_player_switch'):
            return

        palette = self.theme_manager.palette
        progress_color = palette.get("accent", "#0078d4")
        fg_color = palette.get("switch_bg", "#939393")
        button_color = palette.get("accent", "#ffffff")
        button_hover_color = palette.get("accent_hover", "#106ebe")

        self.mini_player_switch.configure(
            progress_color=progress_color,
            fg_color=fg_color,
            button_color=button_color,
            button_hover_color=button_hover_color
        )

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

        bpm_mode_changed = (new_bpm_mode != self.settings.bpm_mode)

        self.settings.theme = new_theme
        self.settings.bpm_mode = new_bpm_mode
        self.settings.mini_player_enabled = getattr(self, 'mini_player_var', tk.BooleanVar(value=True)).get()
        self.settings.save()

        from audio.metadata import set_bpm_preference
        set_bpm_preference(new_bpm_mode)

        if bpm_mode_changed and callable(self.on_bpm_preference_change):
            self.on_bpm_preference_change()

        # Only apply theme if it differs from what is already rendered
        if new_theme != self._current_applied_theme and callable(self.on_apply):
            self.on_apply(new_theme)
        self.destroy()

    def _cancel(self):
        self.settings.theme = self.original_theme
        self.settings.bpm_mode = self.original_bpm_mode
        self.settings.save()

        from audio.metadata import set_bpm_preference
        set_bpm_preference(self.settings.bpm_mode)

        if self.original_bpm_mode != self.settings.bpm_mode and callable(self.on_bpm_preference_change):
            self.on_bpm_preference_change()

        # Only restore theme if a preview changed what is currently rendered
        if self._current_applied_theme != self.original_theme and callable(self.on_apply):
            self.on_apply(self.original_theme)
        self.destroy()
