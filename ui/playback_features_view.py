import json
import logging
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from app.paths import get_user_data_path
from ui.utils import center_window

logger = logging.getLogger(__name__)

class PlaybackFeaturesView(tk.Toplevel):
    def __init__(self, master, state, settings, theme_manager):
        super().__init__(master)
        self.app_state = state
        self.settings = settings
        self.theme_manager = theme_manager
        self.palette = theme_manager.palette
        self.config_path = get_user_data_path() / "playback_features_config.json"

        config_values = self._load_config()
        play_on_double_default = self._get_bool_config_value(
            config_values,
            "play_on_double",
            self.app_state.play_on_double
        )
        crossfade_enabled_default = self._get_bool_config_value(
            config_values,
            "crossfade_enabled",
            getattr(self.settings, "crossfade_enabled", False)
        )
        crossfade_duration_default = self._get_int_config_value(
            config_values,
            "crossfade_duration",
            int(getattr(self.settings, "crossfade_duration", 5)),
            minimum=1,
            maximum=12
        )

        self.app_state.play_on_double = play_on_double_default
        if self.settings:
            self.settings.play_on_double = play_on_double_default
            self.settings.crossfade_enabled = crossfade_enabled_default
            self.settings.crossfade_duration = crossfade_duration_default

        self.title("Playback Features")
        self.geometry("350x350")
        self.resizable(False, False)
        self.transient(master)

        # Hide window initially to prevent flickering during positioning
        self.withdraw()

        center_window(self, master)

        self.configure(bg=self.palette.get("bg", "#ffffff"))

        # Main container
        main_frame = ttk.Frame(self)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Play on double click switch with status label
        switch_frame = ttk.Frame(main_frame)
        switch_frame.pack(anchor='w', pady=10, fill='x')

        self.play_on_double_var = tk.BooleanVar(value=play_on_double_default)

        self.switch = ctk.CTkSwitch(
            switch_frame,
            text="Play on double-click:",
            variable=self.play_on_double_var,
            command=self._on_play_on_double_change,
            progress_color=self.palette.get("accent", "#0078d4"),
            text_color=self.palette.get("fg", "#000000"),
            bg_color=self.palette.get("bg", "#ffffff"),
            button_color=self.palette.get("accent", "#ffffff"),
            button_hover_color=self.palette.get("button_hover", "#106ebe"),
            width=90
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

        # Crossfade section
        crossfade_frame = ttk.Frame(main_frame)
        crossfade_frame.pack(anchor='w', pady=10, fill='x')

        self.crossfade_enabled_var = tk.BooleanVar(value=crossfade_enabled_default)

        cf_switch_frame = ttk.Frame(crossfade_frame)
        cf_switch_frame.pack(anchor='w', pady=(0, 10), fill='x')

        self.crossfade_switch = ctk.CTkSwitch(
            cf_switch_frame,
            text="Crossfade:",
            variable=self.crossfade_enabled_var,
            command=self._toggle_crossfade_slider,
            progress_color=self.palette.get("accent", "#0078d4"),
            text_color=self.palette.get("fg", "#000000"),
            bg_color=self.palette.get("bg", "#ffffff"),
            button_color=self.palette.get("accent", "#ffffff"),
            button_hover_color=self.palette.get("button_hover", "#106ebe"),
            width=90
        )
        self.crossfade_switch.pack(side='left')

        self.crossfade_status_label = ctk.CTkLabel(
            cf_switch_frame,
            text="Enabled" if self.crossfade_enabled_var.get() else "Disabled",
            text_color=self.palette.get("accent", "#0078d4") if self.crossfade_enabled_var.get() else self.palette.get("fg", "#808080"),
            font=("Segoe UI", 11, "bold"),
            bg_color=self.palette.get("bg", "#ffffff")
        )
        self.crossfade_status_label.pack(side='left', padx=(10, 0))

        self.crossfade_duration_var = tk.DoubleVar(value=float(crossfade_duration_default))

        self.cf_slider_frame = ttk.Frame(crossfade_frame)
        self.cf_slider_frame.pack(fill='x', pady=(0, 10))

        ttk.Label(self.cf_slider_frame, text="Duration:",
                foreground=self.palette.get("fg", "#FFFFFF")).pack(anchor='w')

        slider_container = ttk.Frame(self.cf_slider_frame)
        slider_container.pack(fill='x', pady=(5, 0))

        self.lbl_duration = ttk.Label(slider_container, text=f"{int(self.crossfade_duration_var.get())}s", width=4,
                                foreground=self.palette.get("fg", "#FFFFFF"))
        self.lbl_duration.pack(side='right')

        slider_bg = self.palette.get("slider_bg", "#4a4a4a")
        slider_fg = self.palette.get("slider_progress", self.palette.get("accent", "#0078d4"))
        slider_button = self.palette.get("slider_button", "#ffffff")
        accent_hover = self.palette.get("button_hover", "#106ebe")
        bg = self.palette.get("bg", "#ffffff")

        self.slider_duration = ctk.CTkSlider(
            slider_container,
            from_=1, to=12,
            number_of_steps=11,
            variable=self.crossfade_duration_var,
            command=self._update_duration_label,
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_button,
            button_hover_color=accent_hover,
            bg_color=bg,
            border_color="transparent"
        )
        self.slider_duration.pack(side='left', fill='x', expand=True, padx=(0, 10))

        self._toggle_crossfade_slider()

        # Action buttons
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

        self.save_btn = ctk.CTkButton(
            btn_frame,
            text="Save",
            command=self._save_features_config,
            width=80,
            height=32,
            fg_color=self.palette.get("button_bg_color", "#0078d4"),
            text_color=self.palette.get("button_fg_color", "#ffffff"),
            hover_color=self.palette.get("button_hover", "#106ebe")
        )
        self.save_btn.pack(side='right', padx=(0, 10))

        # Show window after all setup is complete
        self.deiconify()

    def _on_play_on_double_change(self):
        """Handle play on double-click setting change."""
        new_value = self.play_on_double_var.get()

        # Update both settings and state
        if self.settings:
            self.settings.play_on_double = new_value

        # Update state as well since playlist view checks state.play_on_double
        self.app_state.play_on_double = new_value

        # Update status label
        self.switch_status_label.configure(
            text="Enabled" if new_value else "Disabled",
            text_color=self.palette.get("accent", "#0078d4") if new_value else self.palette.get("fg", "#808080")
        )


    def _toggle_crossfade_slider(self):
        """Toggle crossfade slider enabled state."""
        enabled = self.crossfade_enabled_var.get()
        state = 'normal' if enabled else 'disabled'

        # Update settings
        if self.settings:
            self.settings.crossfade_enabled = enabled

        # Update status label
        self.crossfade_status_label.configure(
            text="Enabled" if enabled else "Disabled",
            text_color=self.palette.get("accent", "#0078d4") if enabled else self.palette.get("fg", "#808080")
        )

        if state == 'normal':
            label_color = self.palette.get("fg", "#FFFFFF")
        else:
            label_color = self.palette.get("disabled_fg", "#999999")

        # Update CTkSlider state
        if hasattr(self, 'slider_duration'):
            self.slider_duration.configure(state=state)

        for child in self.cf_slider_frame.winfo_children():
            if isinstance(child, ttk.Label):
                try:
                    child.configure(foreground=label_color)
                except:
                    pass

            for subchild in child.winfo_children():
                try:
                    if isinstance(subchild, ttk.Label):
                        subchild.configure(foreground=label_color)
                    elif not isinstance(subchild, ctk.CTkSlider):
                        subchild.configure(state=state)
                except:
                    pass


    def _update_duration_label(self, val):
        """Update crossfade duration label."""
        duration = int(float(val))
        self.lbl_duration.configure(text=f"{duration}s")

        # Update settings
        if self.settings:
            self.settings.crossfade_duration = duration


    def _save_features_config(self):
        """Persist playback feature settings to user config file."""
        data = {
            "play_on_double": self.play_on_double_var.get(),
            "crossfade_enabled": self.crossfade_enabled_var.get(),
            "crossfade_duration": int(self.crossfade_duration_var.get())
        }

        self.app_state.play_on_double = data["play_on_double"]
        if self.settings:
            self.settings.play_on_double = data["play_on_double"]
            self.settings.crossfade_enabled = data["crossfade_enabled"]
            self.settings.crossfade_duration = data["crossfade_duration"]
            try:
                self.settings.save()
            except Exception:
                logger.warning("Failed to save playback settings", exc_info=True)

        if self._write_config_file(data):
            self.saved_values = data.copy()

    def _write_config_file(self, data):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            logger.warning(
                "Failed to persist playback features config to %s",
                self.config_path,
                exc_info=True
            )
            return False

    def _load_config(self):
        """Load persisted playback features configuration."""
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            logger.warning(
                "Failed to load playback features config from %s",
                self.config_path,
                exc_info=True
            )
        return {}

    @staticmethod
    def _get_bool_config_value(data, key, default):
        value = data.get(key)
        return value if isinstance(value, bool) else default

    @staticmethod
    def _get_int_config_value(data, key, default, minimum=None, maximum=None):
        value = data.get(key)
        try:
            int_value = int(value)
        except (TypeError, ValueError):
            int_value = default

        if minimum is not None:
            int_value = max(minimum, int_value)
        if maximum is not None:
            int_value = min(maximum, int_value)
        return int_value

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

        # Update crossfade switch colors
        if hasattr(self, 'crossfade_switch'):
            self.crossfade_switch.configure(
                progress_color=self.palette.get("accent", "#0078d4"),
                text_color=fg,
                bg_color=bg,
                button_color=self.palette.get("accent", "#ffffff"),
                button_hover_color=self.palette.get("button_hover", "#106ebe")
            )

        # Update crossfade status label colors
        if hasattr(self, 'crossfade_status_label'):
            is_enabled = self.crossfade_enabled_var.get()
            self.crossfade_status_label.configure(
                text_color=self.palette.get("accent", "#0078d4") if is_enabled else self.palette.get("fg", "#808080"),
                bg_color=bg
            )

        # Update crossfade slider colors
        if hasattr(self, 'slider_duration'):
            slider_bg = self.palette.get("slider_bg", "#4a4a4a")
            slider_fg = self.palette.get("slider_progress", self.palette.get("accent", "#0078d4"))
            slider_button = self.palette.get("slider_button", "#ffffff")
            accent_hover = self.palette.get("button_hover", "#106ebe")
            self.slider_duration.configure(
                fg_color=slider_bg,
                progress_color=slider_fg,
                button_color=slider_button,
                button_hover_color=accent_hover,
                bg_color=bg
            )

        # Update save button colors
        if hasattr(self, 'save_btn'):
            self.save_btn.configure(
                bg_color=bg,
                fg_color=self.palette.get("button_bg_color", "#0078d4"),
                text_color=self.palette.get("button_fg_color", "#ffffff"),
                hover_color=self.palette.get("button_hover", "#106ebe")
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
