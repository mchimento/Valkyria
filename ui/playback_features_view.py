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
        # Increase default geometry to fit controls and allow vertical resizing
        self.geometry("420x540")
        # Allow vertical resizing so users can expand if content doesn't fit
        self.resizable(False, False)
        self.transient(master)

        # Hide window initially to prevent flickering during positioning
        self.withdraw()

        center_window(self, master)

        self.configure(bg=self.palette.get("bg", "#ffffff"))

        # Main container: use CTkFrame for consistent theming and padding
        self.main_frame = ctk.CTkFrame(self, fg_color=self.palette.get("bg", "#ffffff"))
        self.main_frame.pack(fill='both', expand=True, padx=18, pady=18)
        self.main_frame.pack_propagate(False)

        header_font = ("Segoe UI", 15, "bold")
        section_font = ("Segoe UI", 14, "bold")

        # --- General section ---
        self.general_section = ctk.CTkFrame(self.main_frame, fg_color=self.palette.get("section_bg", self.palette.get("bg", "#ffffff")), corner_radius=6, border_width=1, border_color=self.palette.get("section_border", "#e0e0e0"))
        self.general_section.pack(fill='x', pady=(0, 10))
        self.general_section.pack_propagate(False)

        self.gen_title = ctk.CTkLabel(self.general_section, text="General", font=section_font, text_color=self.palette.get("header_fg", self.palette.get("fg", "#000000")))
        self.gen_title.pack(anchor='w', padx=12, pady=(8, 4))

        # Play on double click row
        self.play_row = ctk.CTkFrame(self.general_section, fg_color="transparent")
        self.play_row.pack(fill='x', padx=12, pady=(0, 12))

        self.play_on_double_var = tk.BooleanVar(value=play_on_double_default)

        self.switch = ctk.CTkSwitch(
            self.play_row,
            text="Play on double-click:",
            variable=self.play_on_double_var,
            command=self._on_play_on_double_change,
            progress_color=self.palette.get("accent", "#0078d4"),
            text_color=self.palette.get("fg", "#000000"),
            bg_color=self.palette.get("bg", "#ffffff"),
            fg_color=self.palette.get("switch_bg", "#939393"),
            button_color=self.palette.get("accent", "#ffffff"),
            button_hover_color=self.palette.get("accent_hover", "#106ebe"),
            width=80
        )
        self.switch.pack(side='left')

        self.switch_status_label = ctk.CTkLabel(
            self.play_row,
            text="Enabled" if self.app_state.play_on_double else "Disabled",
            text_color=self.palette.get("accent", "#0078d4") if self.app_state.play_on_double else self.palette.get("fg", "#808080"),
            font=("Segoe UI", 11, "bold"),
            bg_color=self.palette.get("bg", "#ffffff")
        )
        self.switch_status_label.pack(side='left', padx=(10, 0))

        # --- Crossfade section ---
        self.crossfade_section = ctk.CTkFrame(self.main_frame, fg_color=self.palette.get("section_bg", self.palette.get("bg", "#ffffff")), corner_radius=6, border_width=1, border_color=self.palette.get("section_border", "#e0e0e0"))
        self.crossfade_section.pack(fill='x', pady=(0, 10))
        self.crossfade_section.pack_propagate(False)

        self.cf_row = ctk.CTkFrame(self.crossfade_section, fg_color="transparent")
        self.cf_row.pack(fill='x', padx=12, pady=(8, 4))

        self.crossfade_enabled_var = tk.BooleanVar(value=crossfade_enabled_default)

        self.crossfade_switch = ctk.CTkSwitch(
            self.cf_row,
            text="Crossfade:",
            variable=self.crossfade_enabled_var,
            command=self._toggle_crossfade_slider,
            progress_color=self.palette.get("accent", "#0078d4"),
            text_color=self.palette.get("fg", "#000000"),
            bg_color=self.palette.get("bg", "#ffffff"),
            font=section_font,
            button_color=self.palette.get("accent", "#ffffff"),
            button_hover_color=self.palette.get("button_hover", "#106ebe"),
            width=80
        )
        self.crossfade_switch.pack(side='left')

        self.crossfade_status_label = ctk.CTkLabel(
            self.cf_row,
            text="Enabled" if self.crossfade_enabled_var.get() else "Disabled",
            text_color=self.palette.get("accent", "#0078d4") if self.crossfade_enabled_var.get() else self.palette.get("fg", "#808080"),
            font=("Segoe UI", 11, "bold"),
            bg_color=self.palette.get("bg", "#ffffff")
        )
        self.crossfade_status_label.pack(side='left', padx=(10, 0))

        self.crossfade_duration_var = tk.DoubleVar(value=float(crossfade_duration_default))
        self.cf_slider_frame = ctk.CTkFrame(self.crossfade_section, fg_color="transparent")
        self.cf_slider_frame.pack(fill='x', padx=12, pady=(6, 12))

        duration_label = ctk.CTkLabel(self.cf_slider_frame, text="Duration", text_color=self.palette.get("fg", "#000000"))
        duration_label.pack(side='left')

        self.lbl_duration = ctk.CTkLabel(self.cf_slider_frame, text=f"{int(self.crossfade_duration_var.get())}s", width=4, text_color=self.palette.get("fg", "#000000"))
        self.lbl_duration.pack(side='right')

        slider_container = ctk.CTkFrame(self.cf_slider_frame, fg_color="transparent")
        slider_container.pack(fill='x', expand=True, padx=(8, 8))

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
        self.slider_duration.pack(fill='x', expand=True)

        self._toggle_crossfade_slider()

        # Action buttons (fixed in an Actions section)
        self.actions_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.actions_frame.pack(fill='x', pady=(8, 0))

        self.close_btn = ctk.CTkButton(
            self.actions_frame,
            text="Close",
            command=self.destroy,
            width=88,
            height=36,
            fg_color=self.palette.get("button_bg_color", "#0078d4"),
            text_color=self.palette.get("button_fg_color", "#ffffff"),
            hover_color=self.palette.get("button_hover", "#106ebe"),
            corner_radius=6
        )
        self.close_btn.pack(side='right', padx=(0, 8))

        self.save_btn = ctk.CTkButton(
            self.actions_frame,
            text="Save",
            command=self._save_features_config,
            width=88,
            height=36,
            fg_color=self.palette.get("button_bg_color", "#0078d4"),
            text_color=self.palette.get("button_fg_color", "#ffffff"),
            hover_color=self.palette.get("button_hover", "#106ebe"),
            corner_radius=6
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

        # Update labels in slider frame (supports both ttk.Label & ctk.CTkLabel)
        if hasattr(self, 'cf_slider_frame'):
            for child in self.cf_slider_frame.winfo_children():
                try:
                    # ctk labels use 'text_color'
                    if isinstance(child, ctk.CTkLabel):
                        child.configure(text_color=label_color)
                    elif isinstance(child, ttk.Label):
                        child.configure(foreground=label_color)
                except Exception:
                    pass

                # Descend and update nested children
                for subchild in getattr(child, 'winfo_children', lambda: [])():
                    try:
                        if isinstance(subchild, ctk.CTkLabel):
                            subchild.configure(text_color=label_color)
                        elif isinstance(subchild, ttk.Label):
                            subchild.configure(foreground=label_color)
                        elif not isinstance(subchild, ctk.CTkSlider):
                            try:
                                subchild.configure(state=state)
                            except Exception:
                                pass
                    except Exception:
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

        self.configure(bg=bg)

        # Apply background color to main frame so the main panel follows the palette
        if hasattr(self, 'main_frame'):
            self.main_frame.configure(fg_color=self.palette.get('panel_bg', self.palette.get('bg', bg)))

        # Update switch colors
        if hasattr(self, 'switch'):
            self.switch.configure(
                progress_color=self.palette.get("accent", "#0078d4"),
                text_color=fg,
                bg_color=bg,
                fg_color=self.palette.get("switch_bg", "#939393"),
                button_color=self.palette.get("accent", "#ffffff"),
                button_hover_color=self.palette.get("accent_hover", "#106ebe")
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

        # Update header/title colors and section frames
        if hasattr(self, 'header'):
            try:
                self.header.configure(text_color=self.palette.get('accent', '#0078d4'))
                # Keep header font bold and slightly larger
                try:
                    self.header.configure(font=("Segoe UI", 15, "bold"))
                except Exception:
                    pass
            except Exception:
                pass

        for name in ('gen_title', 'cf_title'):
            if hasattr(self, name):
                try:
                    getattr(self, name).configure(text_color=self.palette.get('header_fg', self.palette.get('fg', '#000000')))
                    try:
                        getattr(self, name).configure(font=("Segoe UI", 12, "bold"))
                    except Exception:
                        pass
                except Exception:
                    pass

        for sec in ('general_section', 'crossfade_section'):
            if hasattr(self, sec):
                try:
                    getattr(self, sec).configure(fg_color=self.palette.get('section_bg', self.palette.get('bg', '#ffffff')), border_color=self.palette.get('section_border', '#e0e0e0'))
                except Exception:
                    pass

        # Style duration label and actions frame
        try:
            if hasattr(self, 'lbl_duration'):
                self.lbl_duration.configure(text_color=self.palette.get('fg', '#000000'))
        except Exception:
            pass

        if hasattr(self, 'actions_frame'):
            try:
                self.actions_frame.configure(fg_color='transparent')
            except Exception:
                pass

        # Recursive restyle
        def restyle(widget):
            for child in widget.winfo_children():
                if not isinstance(child, (ctk.CTkButton, ctk.CTkLabel, ctk.CTkSwitch)):
                    restyle(child)

        restyle(self)

    def update_theme(self):
        """Update theme when theme changes."""
        self.palette = self.theme_manager.palette
        self._apply_theme()
