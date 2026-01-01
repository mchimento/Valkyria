import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from ui.utils import center_window

class AudioEffectsWindow(tk.Toplevel):
    """
    Audio Effects window with Equalizer, Speed Control, and Stereo settings.
    Uses the application theme palette for styling.
    """
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from ui.utils import center_window

class AudioEffectsWindow(tk.Toplevel):
    """
    Audio Effects window with Equalizer, Speed Control, and Stereo settings.
    Uses the application theme palette for styling.
    """
    def __init__(self, parent, player, theme_manager):
        super().__init__(parent)
        self.player = player
        self.theme_manager = theme_manager

        self.title("Audio Effects")
        self.geometry("750x450")
        self.resizable(False, False)
        self.transient(parent)

        # Hide initially
        self.withdraw()

        center_window(self, parent)

        # EQ Bands (Standard ISO frequencies)
        self.bands = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000]
        self.band_labels = ["60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"]
        self.sliders = []
        self.slider_vars = []

        # State
        self.enabled_var = tk.BooleanVar(value=True)
        # Try to get initial state from player if available
        if hasattr(self.player, 'get_equalizer_enabled'):
            try:
                self.enabled_var.set(self.player.get_equalizer_enabled())
            except:
                pass

        # Playback Rate State
        self.rate_var = tk.DoubleVar(value=1.0)
        if hasattr(self.player, 'get_playback_rate'):
            try:
                self.rate_var.set(self.player.get_playback_rate())
            except:
                pass

        # Stereo Mode State
        self.stereo_mode_var = tk.StringVar(value="stereo")

        # Load initial configs
        self.comp_config = self.player.get_compressor_config() if hasattr(self.player, 'get_compressor_config') else {}
        self.spatial_config = self.player.get_spatializer_config() if hasattr(self.player, 'get_spatializer_config') else {}

        self._create_ui()
        self._apply_theme()

        self.deiconify()

    def _create_ui(self):
        """Build the UI components."""
        # Create Notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Tab 1: Equalizer ---
        self.eq_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.eq_tab, text="Equalizer")

        self.main_frame = ttk.Frame(self.eq_tab)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top Control Bar (Enable Switch + Reset)
        top_frame = ttk.Frame(self.main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 20))

        self.enable_switch = ctk.CTkSwitch(
            top_frame,
            text="Enable Equalizer",
            variable=self.enabled_var,
            command=self._on_enable_toggle,
            width=150
        )
        self.enable_switch.pack(side=tk.LEFT)

        self.reset_btn = ctk.CTkButton(
            top_frame,
            text="Reset Flat",
            width=100,
            height=28,
            command=self._reset_flat
        )
        self.reset_btn.pack(side=tk.RIGHT)

        # EQ Container
        eq_container = ttk.Frame(self.main_frame)
        eq_container.pack(fill=tk.BOTH, expand=True)

        # Preamp Section (Left)
        preamp_frame = ttk.Frame(eq_container)
        preamp_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))

        ttk.Label(preamp_frame, text="Preamp", font=("Segoe UI", 9, "bold")).pack(pady=(0, 10))

        self.preamp_var = tk.DoubleVar(value=0)
        # Try get initial preamp
        if hasattr(self.player, 'get_equalizer_preamp'):
            try:
                self.preamp_var.set(self.player.get_equalizer_preamp())
            except:
                pass

        self.preamp_slider = ctk.CTkSlider(
            preamp_frame,
            from_=20, to=-20,
            orientation="vertical",
            variable=self.preamp_var,
            command=self._on_preamp_change,
            height=200,
            width=20
        )
        self.preamp_slider.pack(pady=5)

        self.preamp_label = ttk.Label(preamp_frame, text="0 dB", font=("Segoe UI", 8), width=10, anchor="center")
        self.preamp_label.pack()

        # Separator
        ttk.Separator(eq_container, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Bands Section (Right)
        bands_frame = ttk.Frame(eq_container)
        bands_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create sliders for each band
        for i, freq_label in enumerate(self.band_labels):
            band_frame = ttk.Frame(bands_frame)
            band_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True)

            # Label
            ttk.Label(band_frame, text=freq_label, font=("Segoe UI", 9)).pack(pady=(0, 10))

            # Value var
            val_var = tk.DoubleVar(value=0)
            if hasattr(self.player, 'get_equalizer_band'):
                try:
                    val_var.set(self.player.get_equalizer_band(i))
                except:
                    pass
            self.slider_vars.append(val_var)

            # Slider
            slider = ctk.CTkSlider(
                band_frame,
                from_=20, to=-20,
                orientation="vertical",
                variable=val_var,
                command=lambda v, idx=i: self._on_band_change(idx, v),
                height=200,
                width=20
            )
            slider.pack(pady=5)
            self.sliders.append(slider)

            # dB Label
            lbl = ttk.Label(band_frame, text="0 dB", font=("Segoe UI", 8), width=10, anchor="center")
            lbl.pack()
            # Store label reference on slider for easy update
            slider.value_label = lbl

        # --- Tab 2: Compressor ---
        self.comp_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.comp_tab, text="Compressor")
        self._create_compressor_ui(self.comp_tab)

        # --- Tab 3: Spatializer ---
        self.spatial_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.spatial_tab, text="Spatializer")
        self._create_spatializer_ui(self.spatial_tab)

        # --- Tab 4: Advanced ---
        self.effects_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.effects_tab, text="Advanced")

        effects_container = ttk.Frame(self.effects_tab)
        effects_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 1. Playback Speed
        speed_frame = ttk.LabelFrame(effects_container, text="Playback Speed", padding=15)
        speed_frame.pack(fill=tk.X, pady=(0, 15))

        self.speed_label = ttk.Label(speed_frame, text=f"{self.rate_var.get():.2f}x", width=6, anchor="center")
        self.speed_label.pack(side=tk.RIGHT, padx=(10, 0))

        self.speed_slider = ctk.CTkSlider(
            speed_frame,
            from_=0.25, to=4.0,
            number_of_steps=15,  # Steps: 0.25, 0.5, 0.75, 1.0, ...
            variable=self.rate_var,
            command=self._on_rate_change
        )
        self.speed_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Reset Speed Button
        self.reset_speed_btn = ctk.CTkButton(
            speed_frame,
            text="Reset (1.0x)",
            width=80,
            height=24,
            font=("Segoe UI", 9),
            command=self._reset_speed
        )
        self.reset_speed_btn.pack(side=tk.RIGHT, padx=(10, 10))

        # 2. Stereo Mode
        stereo_frame = ttk.LabelFrame(effects_container, text="Stereo Mode", padding=15)
        stereo_frame.pack(fill=tk.X, pady=(0, 15))

        modes = [("Stereo", "stereo"), ("Reverse Stereo", "reverse"), ("Left Channel", "left"), ("Right Channel", "right")]

        # Use a grid for radio buttons
        stereo_grid = ttk.Frame(stereo_frame)
        stereo_grid.pack(fill=tk.X)

        for i, (text, mode) in enumerate(modes):
            rb = ttk.Radiobutton(
                stereo_grid,
                text=text,
                value=mode,
                variable=self.stereo_mode_var,
                command=self._on_stereo_mode_change
            )
            rb.pack(side=tk.LEFT, padx=(0, 20))

        # Reset Stereo Button
        self.reset_stereo_btn = ctk.CTkButton(
            stereo_frame,
            text="Reset",
            width=80,
            height=24,
            font=("Segoe UI", 9),
            command=self._reset_stereo
        )
        self.reset_stereo_btn.pack(side=tk.RIGHT, padx=(10, 10))

    def _create_compressor_ui(self, parent):
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Top Frame for Switch and Reset
        top_frame = ttk.Frame(container)
        top_frame.pack(fill=tk.X, pady=(0, 15))

        # Enable Switch
        self.comp_enabled_var = tk.BooleanVar(value=self.comp_config.get('enabled', False))
        switch = ctk.CTkSwitch(
            top_frame, text="Enable Compressor", variable=self.comp_enabled_var,
            command=self._on_comp_enable_toggle
        )
        switch.pack(side=tk.LEFT)
        self.comp_switch = switch

        # Reset Button
        self.reset_comp_btn = ctk.CTkButton(
            top_frame, text="Reset Defaults", width=100, height=24,
            command=self._reset_compressor
        )
        self.reset_comp_btn.pack(side=tk.RIGHT)

        # Sliders Frame
        sliders_frame = ttk.Frame(container)
        sliders_frame.pack(fill=tk.BOTH, expand=True)

        # Define controls: (Label, Key, Min, Max, Resolution)
        controls = [
            ("Makeup Gain (dB)", "makeup_gain", 0.0, 24.0, 0.1),
            ("Threshold (dB)", "threshold", -30.0, 0.0, 0.1),
            ("Ratio (n:1)", "ratio", 1.0, 20.0, 0.1),
            ("Attack (ms)", "attack", 1.5, 400.0, 0.5),
            ("Release (ms)", "release", 2.0, 800.0, 1.0),
            ("Knee (dB)", "knee", 1.0, 10.0, 0.1),
        ]

        self.comp_sliders = {}
        self.comp_vars = {}
        self.comp_labels = {}

        for i, (label, key, min_val, max_val, res) in enumerate(controls):
            row = ttk.Frame(sliders_frame)
            row.pack(fill=tk.X, pady=5)

            ttk.Label(row, text=label, width=20).pack(side=tk.LEFT)

            val = self.comp_config.get(key, min_val)
            var = tk.DoubleVar(value=val)
            self.comp_vars[key] = var

            lbl_val = ttk.Label(row, text=f"{val:.1f}", width=6, anchor="e")
            lbl_val.pack(side=tk.RIGHT, padx=(10, 0))
            self.comp_labels[key] = lbl_val

            slider = ctk.CTkSlider(
                row, from_=min_val, to=max_val, variable=var,
                command=lambda v, k=key, l=lbl_val: self._on_comp_change(k, v, l)
            )
            # Set initial state
            if not self.comp_enabled_var.get():
                slider.configure(state="disabled")
            slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
            self.comp_sliders[key] = slider

        # Apply Button
        self._create_apply_button(container)

    def _create_spatializer_ui(self, parent):
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Top Frame for Switch and Reset
        top_frame = ttk.Frame(container)
        top_frame.pack(fill=tk.X, pady=(0, 15))

        # Enable Switch
        self.spatial_enabled_var = tk.BooleanVar(value=self.spatial_config.get('enabled', False))
        switch = ctk.CTkSwitch(
            top_frame, text="Enable Spatializer", variable=self.spatial_enabled_var,
            command=self._on_spatial_enable_toggle
        )
        switch.pack(side=tk.LEFT)
        self.spatial_switch = switch

        # Reset Button
        self.reset_spatial_btn = ctk.CTkButton(
            top_frame, text="Reset Defaults", width=100, height=24,
            command=self._reset_spatializer
        )
        self.reset_spatial_btn.pack(side=tk.RIGHT)

        # Sliders Frame
        sliders_frame = ttk.Frame(container)
        sliders_frame.pack(fill=tk.BOTH, expand=True)

        # Define controls: (Label, Key, Min, Max)
        controls = [
            ("Room Size", "roomsize", 0.0, 1.1),
            ("Width", "width", 0.0, 1.0),
            ("Wet", "wet", 0.0, 1.0),
            ("Dry", "dry", 0.0, 1.0),
            ("Damp", "damp", 0.0, 1.0),
        ]

        self.spatial_sliders = {}
        self.spatial_vars = {}
        self.spatial_labels = {}

        for i, (label, key, min_val, max_val) in enumerate(controls):
            row = ttk.Frame(sliders_frame)
            row.pack(fill=tk.X, pady=5)

            ttk.Label(row, text=label, width=15).pack(side=tk.LEFT)

            val = self.spatial_config.get(key, min_val)
            var = tk.DoubleVar(value=val)
            self.spatial_vars[key] = var

            lbl_val = ttk.Label(row, text=f"{val:.2f}", width=6, anchor="e")
            lbl_val.pack(side=tk.RIGHT, padx=(10, 0))
            self.spatial_labels[key] = lbl_val

            slider = ctk.CTkSlider(
                row, from_=min_val, to=max_val, variable=var,
                command=lambda v, k=key, l=lbl_val: self._on_spatial_change(k, v, l)
            )
            # Set initial state
            if not self.spatial_enabled_var.get():
                slider.configure(state="disabled")
            slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
            self.spatial_sliders[key] = slider

        # Apply Button
        self._create_apply_button(container)

    def _create_apply_button(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Label(frame, text="Settings apply on next track or Apply.",
                 font=("Segoe UI", 9, "italic")).pack(side=tk.LEFT)

        btn = ctk.CTkButton(
            frame, text="Apply to Current Track", width=150, height=28,
            command=self._apply_effects_now
        )
        btn.pack(side=tk.RIGHT)
        # Store for theming
        if not hasattr(self, 'apply_btns'):
            self.apply_btns = []
        self.apply_btns.append(btn)

    def _apply_effects_now(self):
        if hasattr(self.player, 'apply_effects_now'):
            self.player.apply_effects_now()

    def _on_rate_change(self, value):
        self.speed_label.configure(text=f"{float(value):.2f}x")
        if hasattr(self.player, 'set_playback_rate'):
            self.player.set_playback_rate(float(value))

    def _reset_speed(self):
        self.rate_var.set(1.0)
        self._on_rate_change(1.0)

    def _on_stereo_mode_change(self):
        mode = self.stereo_mode_var.get()
        if hasattr(self.player, 'set_stereo_mode'):
            self.player.set_stereo_mode(mode)

    def _reset_stereo(self):
        self.stereo_mode_var.set("stereo")
        self._on_stereo_mode_change()

    def _on_comp_enable_toggle(self):
        enabled = self.comp_enabled_var.get()
        state = "normal" if enabled else "disabled"

        for slider in self.comp_sliders.values():
            slider.configure(state=state)

        if hasattr(self.player, 'set_compressor_enabled'):
            self.player.set_compressor_enabled(enabled)

    def _on_comp_change(self, key, value, label_widget):
        val = float(value)
        label_widget.configure(text=f"{val:.1f}")
        if hasattr(self.player, 'set_compressor_config'):
            self.player.set_compressor_config(key, val)

    def _reset_compressor(self):
        defaults = {
            'makeup_gain': 6.0, 'threshold': -12.0, 'ratio': 4.0,
            'attack': 25.0, 'release': 100.0, 'knee': 5.0
        }
        for key, val in defaults.items():
            if key in self.comp_vars:
                self.comp_vars[key].set(val)
            if key in self.comp_sliders:
                self.comp_sliders[key].set(val)
            if key in self.comp_labels:
                self.comp_labels[key].configure(text=f"{val:.1f}")
            if hasattr(self.player, 'set_compressor_config'):
                self.player.set_compressor_config(key, val)

    def _on_spatial_enable_toggle(self):
        enabled = self.spatial_enabled_var.get()
        state = "normal" if enabled else "disabled"

        for slider in self.spatial_sliders.values():
            slider.configure(state=state)

        if hasattr(self.player, 'set_spatializer_enabled'):
            self.player.set_spatializer_enabled(enabled)

    def _on_spatial_change(self, key, value, label_widget):
        val = float(value)
        label_widget.configure(text=f"{val:.2f}")
        if hasattr(self.player, 'set_spatializer_config'):
            self.player.set_spatializer_config(key, val)

    def _reset_spatializer(self):
        defaults = {
            'roomsize': 0.85, 'width': 0.5, 'wet': 0.4,
            'dry': 0.5, 'damp': 0.5
        }
        for key, val in defaults.items():
            if key in self.spatial_vars:
                self.spatial_vars[key].set(val)
            if key in self.spatial_sliders:
                self.spatial_sliders[key].set(val)
            if key in self.spatial_labels:
                self.spatial_labels[key].configure(text=f"{val:.2f}")
            if hasattr(self.player, 'set_spatializer_config'):
                self.player.set_spatializer_config(key, val)

    def _apply_theme(self):
        """Apply theme colors from palette."""
        palette = self.theme_manager.palette
        bg = palette.get("bg", "#ffffff")
        fg = palette.get("fg", "#000000")
        accent = palette.get("accent", "#0078d4")
        accent_hover = palette.get("accent_hover", "#106ebe")

        # Window background
        self.configure(bg=bg)

        # TTK Styles
        style = ttk.Style(self)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TLabelframe", background=bg, foreground=fg)
        style.configure("TLabelframe.Label", background=bg, foreground=fg)
        style.configure("TSeparator", background=palette.get("border", "#cccccc"))

        # Notebook style
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=palette.get("tree_bg", "#f0f0f0"), foreground=fg, padding=[10, 5])
        style.map("TNotebook.Tab",
                  background=[("selected", accent)],
                  foreground=[("selected", "#ffffff")])

        # Switch style
        self.enable_switch.configure(
            text_color=fg, progress_color=accent, button_color=accent,
            button_hover_color=accent_hover, fg_color=palette.get("switch_bg", "#939393"), bg_color=bg
        )
        self.comp_switch.configure(text_color=fg, progress_color=accent, button_color=accent, button_hover_color=accent_hover, fg_color=palette.get("switch_bg", "#939393"), bg_color=bg)
        self.spatial_switch.configure(text_color=fg, progress_color=accent, button_color=accent, button_hover_color=accent_hover, fg_color=palette.get("switch_bg", "#939393"), bg_color=bg)

        # Update frames
        for widget in self.winfo_children():
            if isinstance(widget, (ttk.Frame, ttk.LabelFrame)):
                widget.configure(style="TFrame")
                for child in widget.winfo_children():
                    if isinstance(child, (ttk.Frame, ttk.LabelFrame)):
                        child.configure(style="TFrame")

        # CTk Widgets

        # Reset Button
        btn_bg = palette.get("button_bg_color", accent)
        btn_fg = palette.get("button_fg_color", "#ffffff")
        self.reset_btn.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )

        self.reset_speed_btn.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )

        self.reset_comp_btn.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )

        self.reset_spatial_btn.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )

        self.reset_stereo_btn.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )

        # Apply Buttons
        if hasattr(self, 'apply_btns'):
            for btn in self.apply_btns:
                btn.configure(
                    fg_color=btn_bg, text_color=btn_fg,
                    hover_color=accent_hover, bg_color=bg
                )

        # Sliders
        slider_bg = palette.get("slider_bg", "#E0E0E0")
        slider_fg = palette.get("slider_fg", accent)

        self.preamp_slider.configure(
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_fg,
            button_hover_color=accent_hover,
            bg_color=bg
        )

        self.speed_slider.configure(
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_fg,
            button_hover_color=accent_hover,
            bg_color=bg
        )

        for slider in self.sliders:
            slider.configure(
                fg_color=slider_bg,
                progress_color=slider_fg,
                button_color=slider_fg,
                button_hover_color=accent_hover,
                bg_color=bg
            )

        for slider in self.comp_sliders.values():
            slider.configure(
                fg_color=slider_bg, progress_color=slider_fg,
                button_color=slider_fg, button_hover_color=accent_hover,
                bg_color=bg
            )

        for slider in self.spatial_sliders.values():
            slider.configure(
                fg_color=slider_bg, progress_color=slider_fg,
                button_color=slider_fg, button_hover_color=accent_hover,
                bg_color=bg
            )

        # Labels
        self.preamp_label.configure(foreground=fg, background=bg)
        for slider in self.sliders:
            if hasattr(slider, 'value_label'):
                slider.value_label.configure(foreground=fg, background=bg)
        self.speed_label.configure(foreground=fg, background=bg)

    def update_theme(self):
        """Public method to refresh theme."""
        self._apply_theme()

    def _on_enable_toggle(self):
        enabled = self.enabled_var.get()
        state = "normal" if enabled else "disabled"

        # Update UI state
        self.preamp_slider.configure(state=state)
        for slider in self.sliders:
            slider.configure(state=state)

        # Call player
        if hasattr(self.player, 'set_equalizer_enabled'):
            try:
                self.player.set_equalizer_enabled(enabled)
            except Exception as e:
                print(f"Error setting EQ enabled: {e}")

    def _on_preamp_change(self, value):
        val = float(value)
        self.preamp_label.configure(text=f"{val:+.1f} dB")

        if hasattr(self.player, 'set_equalizer_preamp'):
            try:
                self.player.set_equalizer_preamp(val)
            except Exception as e:
                print(f"Error setting preamp: {e}")

    def _on_band_change(self, index, value):
        val = float(value)
        if 0 <= index < len(self.sliders):
            slider = self.sliders[index]
            if hasattr(slider, 'value_label'):
                slider.value_label.configure(text=f"{val:+.1f} dB")

        if hasattr(self.player, 'set_equalizer_band'):
            try:
                self.player.set_equalizer_band(index, val)
            except Exception as e:
                print(f"Error setting EQ band {index}: {e}")

    def _reset_flat(self):
        """Reset all sliders to 0."""
        self.preamp_var.set(0)
        self._on_preamp_change(0)

        for i, var in enumerate(self.slider_vars):
            var.set(0)
            self._on_band_change(i, 0)
    def __init__(self, parent, player, theme_manager, settings=None):
        super().__init__(parent)
        self.player = player
        self.theme_manager = theme_manager
        self.settings = settings
        self._save_timer = None

        self.title("Audio Effects")
        self.geometry("750x450")
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Hide initially
        self.withdraw()

        center_window(self, parent)

        # EQ Bands (Standard ISO frequencies)
        self.bands = [60, 170, 310, 600, 1000, 3000, 6000, 12000, 14000, 16000]
        self.band_labels = ["60", "170", "310", "600", "1K", "3K", "6K", "12K", "14K", "16K"]
        self.sliders = []
        self.slider_vars = []

        # State
        self.enabled_var = tk.BooleanVar(value=True)
        # Try to get initial state from player if available
        if hasattr(self.player, 'get_equalizer_enabled'):
            try:
                self.enabled_var.set(self.player.get_equalizer_enabled())
            except:
                pass

        # Playback Rate State
        self.rate_var = tk.DoubleVar(value=1.0)
        if hasattr(self.player, 'get_playback_rate'):
            try:
                self.rate_var.set(self.player.get_playback_rate())
            except:
                pass

        # Stereo Mode State
        self.stereo_mode_var = tk.StringVar(value="stereo")

        # Load initial configs
        self.comp_config = self.player.get_compressor_config() if hasattr(self.player, 'get_compressor_config') else {}
        self.spatial_config = self.player.get_spatializer_config() if hasattr(self.player, 'get_spatializer_config') else {}

        self._create_ui()
        self._apply_theme()

        self.deiconify()

    def _create_ui(self):
        """Build the UI components."""
        # Create Notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Tab 1: Equalizer ---
        self.eq_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.eq_tab, text="Equalizer")

        self.main_frame = ttk.Frame(self.eq_tab)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Top Control Bar (Enable Switch + Reset)
        top_frame = ttk.Frame(self.main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 20))

        self.enable_switch = ctk.CTkSwitch(
            top_frame,
            text="Enable Equalizer",
            variable=self.enabled_var,
            command=self._on_enable_toggle,
            width=150
        )
        self.enable_switch.pack(side=tk.LEFT)

        self.reset_btn = ctk.CTkButton(
            top_frame,
            text="Reset Flat",
            width=100,
            height=28,
            command=self._reset_flat
        )
        self.reset_btn.pack(side=tk.RIGHT)

        # EQ Container
        eq_container = ttk.Frame(self.main_frame)
        eq_container.pack(fill=tk.BOTH, expand=True)

        # Preamp Section (Left)
        preamp_frame = ttk.Frame(eq_container)
        preamp_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))

        ttk.Label(preamp_frame, text="Preamp", font=("Segoe UI", 9, "bold")).pack(pady=(0, 10))

        self.preamp_var = tk.DoubleVar(value=0)
        # Try get initial preamp
        if hasattr(self.player, 'get_equalizer_preamp'):
            try:
                self.preamp_var.set(self.player.get_equalizer_preamp())
            except:
                pass

        self.preamp_slider = ctk.CTkSlider(
            preamp_frame,
            from_=20, to=-20,
            orientation="vertical",
            variable=self.preamp_var,
            command=self._on_preamp_change,
            height=200,
            width=20
        )
        self.preamp_slider.pack(pady=5)

        self.preamp_label = ttk.Label(preamp_frame, text="0 dB", font=("Segoe UI", 8), width=10, anchor="center")
        self.preamp_label.pack()

        # Separator
        ttk.Separator(eq_container, orient="vertical").pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # Bands Section (Right)
        bands_frame = ttk.Frame(eq_container)
        bands_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Create sliders for each band
        for i, freq_label in enumerate(self.band_labels):
            band_frame = ttk.Frame(bands_frame)
            band_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True)

            # Label
            ttk.Label(band_frame, text=freq_label, font=("Segoe UI", 9)).pack(pady=(0, 10))

            # Value var
            val_var = tk.DoubleVar(value=0)
            if hasattr(self.player, 'get_equalizer_band'):
                try:
                    val_var.set(self.player.get_equalizer_band(i))
                except:
                    pass
            self.slider_vars.append(val_var)

            # Slider
            slider = ctk.CTkSlider(
                band_frame,
                from_=20, to=-20,
                orientation="vertical",
                variable=val_var,
                command=lambda v, idx=i: self._on_band_change(idx, v),
                height=200,
                width=20
            )
            slider.pack(pady=5)
            self.sliders.append(slider)

            # dB Label
            lbl = ttk.Label(band_frame, text="0 dB", font=("Segoe UI", 8), width=10, anchor="center")
            lbl.pack()
            # Store label reference on slider for easy update
            slider.value_label = lbl

        # --- Tab 2: Compressor ---
        self.comp_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.comp_tab, text="Compressor")
        self._create_compressor_ui(self.comp_tab)

        # --- Tab 3: Spatializer ---
        self.spatial_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.spatial_tab, text="Spatializer")
        self._create_spatializer_ui(self.spatial_tab)

        # --- Tab 4: Advanced ---
        self.effects_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.effects_tab, text="Advanced")

        effects_container = ttk.Frame(self.effects_tab)
        effects_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 1. Playback Speed
        speed_frame = ttk.LabelFrame(effects_container, text="Playback Speed", padding=15)
        speed_frame.pack(fill=tk.X, pady=(0, 15))

        self.speed_label = ttk.Label(speed_frame, text=f"{self.rate_var.get():.2f}x", width=6, anchor="center")
        self.speed_label.pack(side=tk.RIGHT, padx=(10, 0))

        self.speed_slider = ctk.CTkSlider(
            speed_frame,
            from_=0.25, to=4.0,
            number_of_steps=15,  # Steps: 0.25, 0.5, 0.75, 1.0, ...
            variable=self.rate_var,
            command=self._on_rate_change
        )
        self.speed_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Reset Speed Button
        self.reset_speed_btn = ctk.CTkButton(
            speed_frame,
            text="Reset (1.0x)",
            width=80,
            height=24,
            font=("Segoe UI", 9),
            command=self._reset_speed
        )
        self.reset_speed_btn.pack(side=tk.RIGHT, padx=(10, 10))

        # 2. Stereo Mode
        stereo_frame = ttk.LabelFrame(effects_container, text="Stereo Mode", padding=15)
        stereo_frame.pack(fill=tk.X, pady=(0, 15))

        modes = [("Stereo", "stereo"), ("Reverse Stereo", "reverse"), ("Left Channel", "left"), ("Right Channel", "right")]

        # Use a grid for radio buttons
        stereo_grid = ttk.Frame(stereo_frame)
        stereo_grid.pack(fill=tk.X)

        for i, (text, mode) in enumerate(modes):
            rb = ttk.Radiobutton(
                stereo_grid,
                text=text,
                value=mode,
                variable=self.stereo_mode_var,
                command=self._on_stereo_mode_change
            )
            rb.pack(side=tk.LEFT, padx=(0, 20))

        # Reset Stereo Button
        self.reset_stereo_btn = ctk.CTkButton(
            stereo_frame,
            text="Reset",
            width=80,
            height=24,
            font=("Segoe UI", 9),
            command=self._reset_stereo
        )
        self.reset_stereo_btn.pack(side=tk.RIGHT, padx=(10, 10))

    def _create_compressor_ui(self, parent):
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Top Frame for Switch and Reset
        top_frame = ttk.Frame(container)
        top_frame.pack(fill=tk.X, pady=(0, 15))

        # Enable Switch
        self.comp_enabled_var = tk.BooleanVar(value=self.comp_config.get('enabled', False))
        switch = ctk.CTkSwitch(
            top_frame, text="Enable Compressor", variable=self.comp_enabled_var,
            command=self._on_comp_enable_toggle
        )
        switch.pack(side=tk.LEFT)
        self.comp_switch = switch

        # Reset Button
        self.reset_comp_btn = ctk.CTkButton(
            top_frame, text="Reset Defaults", width=100, height=24,
            command=self._reset_compressor
        )
        self.reset_comp_btn.pack(side=tk.RIGHT)

        # Sliders Frame
        sliders_frame = ttk.Frame(container)
        sliders_frame.pack(fill=tk.BOTH, expand=True)

        # Define controls: (Label, Key, Min, Max, Resolution)
        controls = [
            ("Makeup Gain (dB)", "makeup_gain", 0.0, 24.0, 0.1),
            ("Threshold (dB)", "threshold", -30.0, 0.0, 0.1),
            ("Ratio (n:1)", "ratio", 1.0, 20.0, 0.1),
            ("Attack (ms)", "attack", 1.5, 400.0, 0.5),
            ("Release (ms)", "release", 2.0, 800.0, 1.0),
            ("Knee (dB)", "knee", 1.0, 10.0, 0.1),
        ]

        self.comp_sliders = {}
        self.comp_vars = {}
        self.comp_labels = {}

        for i, (label, key, min_val, max_val, res) in enumerate(controls):
            row = ttk.Frame(sliders_frame)
            row.pack(fill=tk.X, pady=5)

            ttk.Label(row, text=label, width=20).pack(side=tk.LEFT)

            val = self.comp_config.get(key, min_val)
            var = tk.DoubleVar(value=val)
            self.comp_vars[key] = var

            lbl_val = ttk.Label(row, text=f"{val:.1f}", width=6, anchor="e")
            lbl_val.pack(side=tk.RIGHT, padx=(10, 0))
            self.comp_labels[key] = lbl_val

            slider = ctk.CTkSlider(
                row, from_=min_val, to=max_val, variable=var,
                command=lambda v, k=key, l=lbl_val: self._on_comp_change(k, v, l)
            )
            # Set initial state
            if not self.comp_enabled_var.get():
                slider.configure(state="disabled")
            slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
            self.comp_sliders[key] = slider

        # Apply Button
        self._create_apply_button(container)

    def _create_spatializer_ui(self, parent):
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Top Frame for Switch and Reset
        top_frame = ttk.Frame(container)
        top_frame.pack(fill=tk.X, pady=(0, 15))

        # Enable Switch
        self.spatial_enabled_var = tk.BooleanVar(value=self.spatial_config.get('enabled', False))
        switch = ctk.CTkSwitch(
            top_frame, text="Enable Spatializer", variable=self.spatial_enabled_var,
            command=self._on_spatial_enable_toggle
        )
        switch.pack(side=tk.LEFT)
        self.spatial_switch = switch

        # Reset Button
        self.reset_spatial_btn = ctk.CTkButton(
            top_frame, text="Reset Defaults", width=100, height=24,
            command=self._reset_spatializer
        )
        self.reset_spatial_btn.pack(side=tk.RIGHT)

        # Sliders Frame
        sliders_frame = ttk.Frame(container)
        sliders_frame.pack(fill=tk.BOTH, expand=True)

        # Define controls: (Label, Key, Min, Max)
        controls = [
            ("Room Size", "roomsize", 0.0, 1.1),
            ("Width", "width", 0.0, 1.0),
            ("Wet", "wet", 0.0, 1.0),
            ("Dry", "dry", 0.0, 1.0),
            ("Damp", "damp", 0.0, 1.0),
        ]

        self.spatial_sliders = {}
        self.spatial_vars = {}
        self.spatial_labels = {}

        for i, (label, key, min_val, max_val) in enumerate(controls):
            row = ttk.Frame(sliders_frame)
            row.pack(fill=tk.X, pady=5)

            ttk.Label(row, text=label, width=15).pack(side=tk.LEFT)

            val = self.spatial_config.get(key, min_val)
            var = tk.DoubleVar(value=val)
            self.spatial_vars[key] = var

            lbl_val = ttk.Label(row, text=f"{val:.2f}", width=6, anchor="e")
            lbl_val.pack(side=tk.RIGHT, padx=(10, 0))
            self.spatial_labels[key] = lbl_val

            slider = ctk.CTkSlider(
                row, from_=min_val, to=max_val, variable=var,
                command=lambda v, k=key, l=lbl_val: self._on_spatial_change(k, v, l)
            )
            # Set initial state
            if not self.spatial_enabled_var.get():
                slider.configure(state="disabled")
            slider.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
            self.spatial_sliders[key] = slider

        # Apply Button
        self._create_apply_button(container)

    def _create_apply_button(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Label(frame, text="Settings apply on next track or Apply.",
                 font=("Segoe UI", 9, "italic")).pack(side=tk.LEFT)

        btn = ctk.CTkButton(
            frame, text="Apply to Current Track", width=150, height=28,
            command=self._apply_effects_now
        )
        btn.pack(side=tk.RIGHT)
        # Store for theming
        if not hasattr(self, 'apply_btns'):
            self.apply_btns = []
        self.apply_btns.append(btn)

    def _apply_effects_now(self):
        if hasattr(self.player, 'apply_effects_now'):
            self.player.apply_effects_now()

    def _on_rate_change(self, value):
        self.speed_label.configure(text=f"{float(value):.2f}x")
        if hasattr(self.player, 'set_playback_rate'):
            self.player.set_playback_rate(float(value))
        self._save_settings()

    def _reset_speed(self):
        self.rate_var.set(1.0)
        self._on_rate_change(1.0)

    def _on_stereo_mode_change(self):
        mode = self.stereo_mode_var.get()
        if hasattr(self.player, 'set_stereo_mode'):
            self.player.set_stereo_mode(mode)
        self._save_settings()

    def _reset_stereo(self):
        self.stereo_mode_var.set("stereo")
        self._on_stereo_mode_change()

    def _on_comp_enable_toggle(self):
        enabled = self.comp_enabled_var.get()
        state = "normal" if enabled else "disabled"

        for slider in self.comp_sliders.values():
            slider.configure(state=state)

        if hasattr(self.player, 'set_compressor_enabled'):
            self.player.set_compressor_enabled(enabled)
        self._save_settings()

    def _on_comp_change(self, key, value, label_widget):
        val = float(value)
        label_widget.configure(text=f"{val:.1f}")
        if hasattr(self.player, 'set_compressor_config'):
            self.player.set_compressor_config(key, val)
        self._save_settings()

    def _reset_compressor(self):
        defaults = {
            'makeup_gain': 6.0, 'threshold': -12.0, 'ratio': 4.0,
            'attack': 25.0, 'release': 100.0, 'knee': 5.0
        }
        for key, val in defaults.items():
            if key in self.comp_vars:
                self.comp_vars[key].set(val)
            if key in self.comp_sliders:
                self.comp_sliders[key].set(val)
            if key in self.comp_labels:
                self.comp_labels[key].configure(text=f"{val:.1f}")
            if hasattr(self.player, 'set_compressor_config'):
                self.player.set_compressor_config(key, val)
        self._save_settings()

    def _on_spatial_enable_toggle(self):
        enabled = self.spatial_enabled_var.get()
        state = "normal" if enabled else "disabled"

        for slider in self.spatial_sliders.values():
            slider.configure(state=state)

        if hasattr(self.player, 'set_spatializer_enabled'):
            self.player.set_spatializer_enabled(enabled)
        self._save_settings()

    def _on_spatial_change(self, key, value, label_widget):
        val = float(value)
        label_widget.configure(text=f"{val:.2f}")
        if hasattr(self.player, 'set_spatializer_config'):
            self.player.set_spatializer_config(key, val)
        self._save_settings()

    def _reset_spatializer(self):
        defaults = {
            'roomsize': 0.85, 'width': 0.5, 'wet': 0.4,
            'dry': 0.5, 'damp': 0.5
        }
        for key, val in defaults.items():
            if key in self.spatial_vars:
                self.spatial_vars[key].set(val)
            if key in self.spatial_sliders:
                self.spatial_sliders[key].set(val)
            if key in self.spatial_labels:
                self.spatial_labels[key].configure(text=f"{val:.2f}")
            if hasattr(self.player, 'set_spatializer_config'):
                self.player.set_spatializer_config(key, val)
        self._save_settings()

    def _apply_theme(self):
        """Apply theme colors from palette."""
        palette = self.theme_manager.palette
        bg = palette.get("bg", "#ffffff")
        fg = palette.get("fg", "#000000")
        accent = palette.get("accent", "#0078d4")
        accent_hover = palette.get("accent_hover", "#106ebe")

        # Window background
        self.configure(bg=bg)

        # TTK Styles
        style = ttk.Style(self)
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TLabelframe", background=bg, foreground=fg)
        style.configure("TLabelframe.Label", background=bg, foreground=fg)
        style.configure("TSeparator", background=palette.get("border", "#cccccc"))

        # Notebook style
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=palette.get("tree_bg", "#f0f0f0"), foreground=fg, padding=[10, 5])
        style.map("TNotebook.Tab",
                  background=[("selected", accent)],
                  foreground=[("selected", "#ffffff")])

        # Switch style
        self.enable_switch.configure(
            text_color=fg, progress_color=accent, button_color=accent,
            button_hover_color=accent_hover, fg_color=palette.get("switch_bg", "#939393"), bg_color=bg
        )
        self.comp_switch.configure(text_color=fg, progress_color=accent, button_color=accent, button_hover_color=accent_hover, fg_color=palette.get("switch_bg", "#939393"), bg_color=bg)
        self.spatial_switch.configure(text_color=fg, progress_color=accent, button_color=accent, button_hover_color=accent_hover, fg_color=palette.get("switch_bg", "#939393"), bg_color=bg)

        # Update frames
        for widget in self.winfo_children():
            if isinstance(widget, (ttk.Frame, ttk.LabelFrame)):
                widget.configure(style="TFrame")
                for child in widget.winfo_children():
                    if isinstance(child, (ttk.Frame, ttk.LabelFrame)):
                        child.configure(style="TFrame")

        # CTk Widgets

        # Reset Button
        btn_bg = palette.get("button_bg_color", accent)
        btn_fg = palette.get("button_fg_color", "#ffffff")
        self.reset_btn.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )

        self.reset_speed_btn.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )

        self.reset_comp_btn.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )

        self.reset_spatial_btn.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )

        self.reset_stereo_btn.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )

        # Apply Buttons
        if hasattr(self, 'apply_btns'):
            for btn in self.apply_btns:
                btn.configure(
                    fg_color=btn_bg, text_color=btn_fg,
                    hover_color=accent_hover, bg_color=bg
                )

        # Sliders
        slider_bg = palette.get("slider_bg", "#E0E0E0")
        slider_fg = palette.get("slider_fg", accent)

        self.preamp_slider.configure(
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_fg,
            button_hover_color=accent_hover,
            bg_color=bg
        )

        self.speed_slider.configure(
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_fg,
            button_hover_color=accent_hover,
            bg_color=bg
        )

        for slider in self.sliders:
            slider.configure(
                fg_color=slider_bg,
                progress_color=slider_fg,
                button_color=slider_fg,
                button_hover_color=accent_hover,
                bg_color=bg
            )

        for slider in self.comp_sliders.values():
            slider.configure(
                fg_color=slider_bg, progress_color=slider_fg,
                button_color=slider_fg, button_hover_color=accent_hover,
                bg_color=bg
            )

        for slider in self.spatial_sliders.values():
            slider.configure(
                fg_color=slider_bg, progress_color=slider_fg,
                button_color=slider_fg, button_hover_color=accent_hover,
                bg_color=bg
            )

        # Labels
        self.preamp_label.configure(foreground=fg, background=bg)
        for slider in self.sliders:
            if hasattr(slider, 'value_label'):
                slider.value_label.configure(foreground=fg, background=bg)
        self.speed_label.configure(foreground=fg, background=bg)

    def update_theme(self):
        """Public method to refresh theme."""
        self._apply_theme()

    def _on_enable_toggle(self):
        enabled = self.enabled_var.get()
        state = "normal" if enabled else "disabled"

        # Update UI state
        self.preamp_slider.configure(state=state)
        for slider in self.sliders:
            slider.configure(state=state)

        # Call player
        if hasattr(self.player, 'set_equalizer_enabled'):
            try:
                self.player.set_equalizer_enabled(enabled)
            except Exception as e:
                print(f"Error setting EQ enabled: {e}")
        self._save_settings()

    def _on_preamp_change(self, value):
        val = float(value)
        self.preamp_label.configure(text=f"{val:+.1f} dB")

        if hasattr(self.player, 'set_equalizer_preamp'):
            try:
                self.player.set_equalizer_preamp(val)
            except Exception as e:
                print(f"Error setting preamp: {e}")
        self._save_settings()

    def _on_band_change(self, index, value):
        val = float(value)
        if 0 <= index < len(self.sliders):
            slider = self.sliders[index]
            if hasattr(slider, 'value_label'):
                slider.value_label.configure(text=f"{val:+.1f} dB")

        if hasattr(self.player, 'set_equalizer_band'):
            try:
                self.player.set_equalizer_band(index, val)
            except Exception as e:
                print(f"Error setting EQ band {index}: {e}")
        self._save_settings()

    def _reset_flat(self):
        """Reset all sliders to 0."""
        self.preamp_var.set(0)
        self._on_preamp_change(0)

        for i, var in enumerate(self.slider_vars):
            var.set(0)
            self._on_band_change(i, 0)

    def _save_settings(self):
        """Save current audio settings to persistent storage with debouncing."""
        if not self.settings:
            return

        # Gather current settings
        effects = {
            'equalizer_enabled': self.enabled_var.get(),
            'equalizer_preamp': self.preamp_var.get(),
            'equalizer_bands': [v.get() for v in self.slider_vars],
            'playback_rate': self.rate_var.get(),
            'stereo_mode': self.stereo_mode_var.get(),
            'compressor_config': self.player.get_compressor_config() if hasattr(self.player, 'get_compressor_config') else {},
            'spatializer_config': self.player.get_spatializer_config() if hasattr(self.player, 'get_spatializer_config') else {}
        }

        self.settings.audio_effects = effects

        # Debounce save operation (1 second)
        if self._save_timer:
            self.after_cancel(self._save_timer)
        self._save_timer = self.after(1000, self._perform_save)

    def _perform_save(self):
        try:
            self.settings.save()
        except Exception as e:
            print(f"Error saving settings: {e}")
        self._save_timer = None

    def _on_close(self):
        """Handle window close event."""
        self.destroy()

    def destroy(self):
        """Ensure pending settings are saved when window is closed."""
        if self._save_timer:
            self.after_cancel(self._save_timer)
            self._perform_save()
        super().destroy()
