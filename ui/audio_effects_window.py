import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import json
import logging
from pathlib import Path
from ui.utils import center_window

logger = logging.getLogger(__name__)

# Load audio effects configuration
config_path = Path(__file__).parent.parent / 'audio' / 'audio_effects_config.json'
with open(config_path, 'r') as f:
    AUDIO_CONFIG = json.load(f)

# Load audio effects defaults (for reset functionality)
defaults_path = Path(__file__).parent.parent / 'audio' / 'audio_effect_default.json'
with open(defaults_path, 'r') as f:
    AUDIO_DEFAULTS = json.load(f)

class AudioEffectsWindow(tk.Toplevel):
    """
    Audio Effects window with Equalizer and Speed Control.
    Uses the application theme palette for styling.
    """
    def __init__(self, parent, player, theme_manager):
        super().__init__(parent)
        self.player = player
        self.theme_manager = theme_manager
        self.palette = theme_manager.palette  # Set palette early for callbacks

        self.title("Audio Effects")
        self.geometry("800x500")
        self.resizable(False, False)
        self.transient(parent)

        # Hide initially
        self.withdraw()

        center_window(self, parent)

        # Load EQ configuration and defaults
        self.eq_config = AUDIO_CONFIG['equalizer']
        self.eq_defaults = AUDIO_DEFAULTS['equalizer']

        # Load saved preset
        self.saved_preset = self.eq_config.get('selected_preset', '')

        # EQ Bands (Standard ISO frequencies) - from defaults
        self.bands = self.eq_defaults['bands']
        self.band_labels = self.eq_defaults['band_labels']
        self.sliders = []
        self.slider_vars = []

        # EQ Presets - convert from config format to tuple format
        self.presets = {}
        for preset_name, preset_data in self.eq_defaults['presets'].items():
            self.presets[preset_name] = (preset_data['preamp'], preset_data['gains'])

        # State - load from user config
        self.enabled_var = tk.BooleanVar(value=self.eq_config['enabled'])
        # Try to get initial state from player if available
        if hasattr(self.player, 'get_equalizer_enabled'):
            try:
                self.enabled_var.set(self.player.get_equalizer_enabled())
            except:
                pass

        # Playback Rate State
        playback_config = AUDIO_CONFIG['playback']
        self.rate_var = tk.DoubleVar(value=playback_config['default_rate'])
        if hasattr(self.player, 'get_playback_rate'):
            try:
                self.rate_var.set(self.player.get_playback_rate())
            except:
                pass

        # Compressor State
        comp_config = AUDIO_CONFIG['compressor']

        # Store defaults from file for reset functionality
        self._original_compressor_defaults = AUDIO_DEFAULTS['compressor']

        self.compressor_enabled_var = tk.BooleanVar(value=comp_config['enabled'])
        self.compressor_threshold_var = tk.DoubleVar(value=comp_config['threshold'])
        self.compressor_ratio_var = tk.DoubleVar(value=comp_config['ratio'])
        self.compressor_attack_var = tk.DoubleVar(value=comp_config['attack'])
        self.compressor_release_var = tk.DoubleVar(value=comp_config['release'])
        self.compressor_knee_var = tk.DoubleVar(value=comp_config['knee'])
        self.compressor_makeup_var = tk.DoubleVar(value=comp_config['makeup_gain'])
        self.compressor_rms_mode_var = tk.BooleanVar(value=comp_config['use_rms'])

        # Try to get initial compressor state
        if hasattr(self.player, 'get_compressor_enabled'):
            try:
                self.compressor_enabled_var.set(self.player.get_compressor_enabled())
            except:
                pass

        # Spatializer State
        spat_config = AUDIO_CONFIG.get('spatializer', {})
        spat_defaults = AUDIO_DEFAULTS.get('spatializer', {})
        self._original_spatializer_defaults = spat_defaults

        self.spatializer_enabled_var = tk.BooleanVar(value=spat_config.get('enabled', False))
        self.spat_size_var = tk.DoubleVar(value=spat_config.get('size', 0.85))
        self.spat_width_var = tk.DoubleVar(value=spat_config.get('width', 0.5))
        self.spat_wet_var = tk.DoubleVar(value=spat_config.get('wet', 0.4))
        self.spat_dry_var = tk.DoubleVar(value=spat_config.get('dry', 0.5))
        self.spat_damp_var = tk.DoubleVar(value=spat_config.get('damp', 0.5))

        if hasattr(self.player, 'get_spatializer_enabled'):
            try:
                self.spatializer_enabled_var.set(self.player.get_spatializer_enabled())
            except:
                pass

        # Channel Mode State
        cm_config = AUDIO_CONFIG.get('channel_mode', {})
        self.channel_mode_var = tk.StringVar(value=cm_config.get('mode', 'Stereo'))
        if hasattr(self.player, 'get_channel_mode'):
            try:
                # Capitalize for UI consistency if needed, but the player returns lowercase
                mode = self.player.get_channel_mode()
                mode_map = {
                    'stereo': 'Stereo',
                    'mono': 'Mono',
                    'left channel': 'Left Channel',
                    'right channel': 'Right Channel',
                    'side (diff)': 'Side (Diff)'
                }
                self.channel_mode_var.set(mode_map.get(mode, 'Stereo'))
            except:
                pass

        self._create_ui()

        # Synchronize UI state with initial values
        self._on_enable_toggle()
        self._on_compressor_toggle()
        self._on_spatializer_toggle()

        self.deiconify()

    def _create_ui(self):
        """Build the UI components."""
        palette = self.theme_manager.palette
        bg = palette.get("bg", "#ffffff")
        fg = palette.get("fg", "#000000")
        accent = palette.get("accent", "#0078d4")
        accent_hover = palette.get("accent_hover", "#106ebe")
        slider_bg = palette.get("slider_bg", "#2a2a2a")
        slider_fg = palette.get("slider_bg", accent)
        slider_button = palette.get("accent", "#0078d4")
        btn_bg = palette.get("button_bg_color", accent)
        btn_fg = palette.get("button_fg_color", "#ffffff")

        # Window background
        self.configure(bg=bg)

        # Create Notebook for tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=False, padx=10, pady=(10, 0))

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

        # Update frames
        for widget in self.winfo_children():
            if isinstance(widget, (ttk.Frame, ttk.LabelFrame)):
                widget.configure(style="TFrame")
                for child in widget.winfo_children():
                    if isinstance(child, (ttk.Frame, ttk.LabelFrame)):
                        child.configure(style="TFrame")

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
            text="Equalizer:",
            variable=self.enabled_var,
            command=self._on_enable_toggle,
            width=100,
            text_color=fg,
            progress_color=accent,
            button_color=accent,
            button_hover_color=accent_hover,
            fg_color=palette.get("switch_bg", "#939393"),
            bg_color=bg
        )
        self.enable_switch.pack(side=tk.LEFT)

        self.enable_status_label = ctk.CTkLabel(
            top_frame,
            text="Enabled" if self.enabled_var.get() else "Disabled",
            text_color=accent if self.enabled_var.get() else palette.get("fg", "#808080"),
            font=("Segoe UI", 11, "bold"),
            bg_color=bg
        )
        self.enable_status_label.pack(side=tk.LEFT)

        self.preset_var = tk.StringVar(value=self.saved_preset)

         # Frame wrapper for border effect
        self.preset_menu_frame = ctk.CTkFrame(
            top_frame,
            fg_color="transparent",
            border_width=1,
            corner_radius=0,
            border_color=palette.get("border", "#cccccc")
        )
        self.preset_menu_frame.pack(side=tk.RIGHT, padx=(0, 10))

        self.preset_menu = ctk.CTkOptionMenu(
            self.preset_menu_frame,
            values=[""] + list(self.presets.keys()),
            command=self._on_preset_change,
            variable=self.preset_var,
            width=160,
            height=26,
            fg_color=bg,
            button_color=bg,
            button_hover_color=palette.get("dropdown_hover", "#000000"),
            text_color=palette.get("dropdown_text", "#000000"),
            dropdown_fg_color=palette.get("dropdown_bg", "#000000"),
            dropdown_hover_color=palette.get("dropdown_hover", "#000000"),
            dropdown_text_color=palette.get("dropdown_text", "#000000")
        )
        self.preset_menu.pack(padx=2, pady=2)

        self.preset_label = ttk.Label(top_frame, text="Preset", font=("Roboto", 10, "bold"))
        self.preset_label.pack(side=tk.RIGHT, padx=(0, 5))

        # EQ Container
        eq_container = ttk.Frame(self.main_frame)
        eq_container.pack(fill=tk.BOTH, expand=True)

        # Preamp Section (Left)
        preamp_frame = ttk.Frame(eq_container)
        preamp_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))

        ttk.Label(preamp_frame, text="Preamp", font=("Segoe UI", 9, "bold")).pack(pady=(0, 10))

        self.preamp_var = tk.DoubleVar(value=self.eq_config['preamp'])
        # Try get initial preamp from player
        if hasattr(self.player, 'get_equalizer_preamp'):
            try:
                self.preamp_var.set(self.player.get_equalizer_preamp())
            except:
                pass

        self.preamp_slider = ctk.CTkSlider(
            preamp_frame,
            from_=-20, to=20,
            orientation="vertical",
            variable=self.preamp_var,
            command=self._on_preamp_change,
            height=200,
            width=11,
            border_width=0,
            button_length=20,
            corner_radius=4,
            button_corner_radius=2,
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_button,
            button_hover_color=accent_hover,
            bg_color=bg,
            border_color="transparent"
        )
        self.preamp_slider.pack(pady=5)

        self.preamp_label = ttk.Label(preamp_frame, text=f"{self.preamp_var.get():+.1f} dB", font=("Segoe UI", 8), width=10, anchor="center")
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

            # Value var - initialize with saved config value
            val_var = tk.DoubleVar(value=self.eq_config['gains'][i] if i < len(self.eq_config['gains']) else 0)
            if hasattr(self.player, 'get_equalizer_band'):
                try:
                    val_var.set(self.player.get_equalizer_band(i))
                except:
                    pass
            self.slider_vars.append(val_var)

            # Slider
            slider = ctk.CTkSlider(
                band_frame,
                from_=-20, to=20,
                orientation="vertical",
                variable=val_var,
                command=lambda v, idx=i: self._on_band_change(idx, v),
                height=200,
                width=11,
                border_width=0,
                button_length=20,
                corner_radius=4,
                button_corner_radius=2,
                fg_color=slider_bg,
                progress_color=slider_fg,
                button_color=slider_button,
                button_hover_color=accent_hover,
                bg_color=bg,
                border_color="transparent"
            )
            slider.pack(pady=5)
            self.sliders.append(slider)

            # dB Label - initialize with actual value
            initial_val = val_var.get()
            lbl = ttk.Label(band_frame, text=f"{initial_val:+.1f} dB", font=("Segoe UI", 8), width=10, anchor="center")
            lbl.pack()
            # Store label reference on slider for easy update
            slider.value_label = lbl

        # --- Tab 2: Compressor ---
        self.compressor_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.compressor_tab, text="Compressor")

        self._create_compressor_tab()

        # --- Tab 3: Spatializer ---
        self.spatializer_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.spatializer_tab, text="Spatializer")

        self._create_spatializer_tab()

        # --- Tab 4: Advanced ---
        self.effects_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.effects_tab, text="Advanced")

        effects_container = ttk.Frame(self.effects_tab)
        effects_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 1. Playback Speed
        speed_frame = ttk.LabelFrame(effects_container, text="Playback Speed", padding=15)
        speed_frame.pack(fill=tk.X, pady=(0, 15))

        # Reset Speed Button
        self.reset_speed_btn = ctk.CTkButton(
            speed_frame,
            text="Reset (1.0x)",
            width=80,
            height=24,
            font=("Segoe UI", 9),
            command=self._reset_speed,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )
        self.reset_speed_btn.pack(side=tk.RIGHT, padx=(10, 10))

        self.speed_label = ttk.Label(speed_frame, text=f"{self.rate_var.get():.2f}x", width=6, anchor="center")
        self.speed_label.pack(side=tk.RIGHT, padx=(10, 0))

        self.speed_slider = ctk.CTkSlider(
            speed_frame,
            from_=0.25, to=4.0,
            number_of_steps=15,
            variable=self.rate_var,
            command=self._on_rate_change,
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_button,
            button_hover_color=accent_hover,
            bg_color=bg,
            border_color="transparent"
        )
        self.speed_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 2. Channel Mode (Band Check)
        channel_frame = ttk.LabelFrame(effects_container, text="Channel Mode", padding=15)
        channel_frame.pack(fill=tk.X, pady=(0, 15))

        # Description
        ttk.Label(channel_frame, text="Select channel to analyze mix structure:", font=("Segoe UI", 9, "italic")).pack(anchor="w", pady=(0, 10))

        # Radio Buttons Container
        radio_container = ttk.Frame(channel_frame)
        radio_container.pack(fill=tk.X)

        options = AUDIO_DEFAULTS.get('channel_mode', {}).get('options', ["Stereo", "Mono", "Left Channel", "Right Channel", "Side (Diff)"])
        self.channel_radios = []

        for option in options:
            radio = ctk.CTkRadioButton(
                radio_container,
                text=option,
                variable=self.channel_mode_var,
                value=option,
                command=lambda: self._on_channel_mode_change(self.channel_mode_var.get()),
                text_color=fg,
                fg_color=accent,
                hover_color=accent_hover,
                border_color=palette.get("switch_bg", "#939393"),
                bg_color=bg
            )
            radio.pack(side=tk.LEFT, padx=(0, 15))
            self.channel_radios.append(radio)

        # 3. Vocal Remover
        vocal_frame = ttk.LabelFrame(effects_container, text="Vocal Remover", padding=15)
        vocal_frame.pack(fill=tk.X, pady=(0, 15))

        # Enable Switch with horizontal layout
        vocal_top_frame = ttk.Frame(vocal_frame)
        vocal_top_frame.pack(fill=tk.X, pady=(0, 10))

        self.vocal_remover_var = tk.BooleanVar(value=self.player.get_vocal_remover_enabled())
        self.vocal_remover_switch = ctk.CTkSwitch(
            vocal_top_frame,
            text="Vocal Remover: ",
            variable=self.vocal_remover_var,
            command=self._on_vocal_remover_toggle,
            progress_color=accent,
            button_color=accent,
            button_hover_color=accent_hover,
            fg_color=palette.get("switch_bg", "#939393"),
            bg_color=bg,
            text_color=fg,
            width=120
        )
        self.vocal_remover_switch.pack(side=tk.LEFT)

        self.vocal_status_label = ctk.CTkLabel(
            vocal_top_frame,
            text="Enabled" if self.vocal_remover_var.get() else "Disabled",
            text_color=accent if self.vocal_remover_var.get() else palette.get("fg", "#808080"),
            font=("Segoe UI", 11, "bold"),
            bg_color=bg
        )
        self.vocal_status_label.pack(side=tk.LEFT)

        # Intensity Slider
        intensity_container = ttk.Frame(vocal_frame)
        intensity_container.pack(fill=tk.X)

        ttk.Label(intensity_container, text="Intensity:").pack(side=tk.LEFT, padx=(0, 10))

        self.vocal_intensity_var = tk.DoubleVar(value=self.player.get_vocal_remover_intensity())
        self.vocal_intensity_slider = ctk.CTkSlider(
            intensity_container,
            from_=0.0, to=1.0,
            number_of_steps=20,
            variable=self.vocal_intensity_var,
            command=self._on_vocal_intensity_change,
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_button,
            button_hover_color=accent_hover,
            bg_color=bg,
            border_color="transparent"
        )
        self.vocal_intensity_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.vocal_intensity_label = ttk.Label(intensity_container, text=f"{self.vocal_intensity_var.get():.2f}", width=4)
        self.vocal_intensity_label.pack(side=tk.RIGHT, padx=(10, 0))

        # Reset Vocal Remover Button
        self.reset_vocal_btn = ctk.CTkButton(
            vocal_frame,
            text="Reset",
            width=80,
            height=24,
            font=("Segoe UI", 9),
            command=self._reset_vocal_remover,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )
        self.reset_vocal_btn.pack(side=tk.TOP, anchor="e", pady=(10, 0))

        # Bottom buttons (Save and Close) - added after notebook
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=(10, 10))

        self.close_btn = ctk.CTkButton(
            button_frame,
            text="Close",
            width=80,
            height=50,
            font=("Segoe UI", 10),
            command=self._on_close,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )
        self.close_btn.pack(side=tk.RIGHT)

        self.save_btn = ctk.CTkButton(
            button_frame,
            text="Save",
            width=80,
            height=50,
            font=("Segoe UI", 10),
            command=self._save_to_config,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )
        self.save_btn.pack(side=tk.RIGHT, padx=(0, 10))

    def _create_compressor_tab(self):
        """Create the Compressor tab UI."""
        # Get theme colors for widget creation
        palette = self.theme_manager.palette
        bg = palette.get("bg", "#ffffff")
        fg = palette.get("fg", "#000000")
        accent = palette.get("accent", "#0078d4")
        accent_hover = palette.get("accent_hover", "#106ebe")
        slider_bg = palette.get("slider_bg", "#2a2a2a")
        slider_fg = palette.get("slider_bg", accent)
        slider_button = palette.get("accent", "#0078d4")
        btn_bg = palette.get("button_bg_color", accent)
        btn_fg = palette.get("button_fg_color", "#ffffff")

        container = ttk.Frame(self.compressor_tab)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Enable Switch
        top_frame = ttk.Frame(container)
        top_frame.pack(fill=tk.X, pady=(0, 20))

        self.compressor_enable_switch = ctk.CTkSwitch(
            top_frame,
            text="Compressor:",
            variable=self.compressor_enabled_var,
            command=self._on_compressor_toggle,
            width=120,
            text_color=fg,
            progress_color=accent,
            button_color=accent,
            button_hover_color=accent_hover,
            fg_color=palette.get("switch_bg", "#939393"),
            bg_color=bg
        )
        self.compressor_enable_switch.pack(side=tk.LEFT)

        self.compressor_status_label = ctk.CTkLabel(
            top_frame,
            text="Enabled" if self.compressor_enabled_var.get() else "Disabled",
            text_color=accent if self.compressor_enabled_var.get() else palette.get("fg", "#808080"),
            font=("Segoe UI", 11, "bold"),
            bg_color=bg
        )
        self.compressor_status_label.pack(side=tk.LEFT)

        # Reset button
        self.compressor_reset_btn = ctk.CTkButton(
            top_frame,
            text="Reset to Defaults",
            width=120,
            height=28,
            font=("Segoe UI", 10),
            command=self._reset_compressor,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )
        self.compressor_reset_btn.pack(side=tk.RIGHT)

        # Parameters Frame with vertical sliders
        params_frame = ttk.Frame(container)
        params_frame.pack(fill=tk.BOTH, expand=True)

        # Threshold
        threshold_frame = ttk.Frame(params_frame)
        threshold_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True, padx=10)

        ttk.Label(threshold_frame, text="Threshold", font=("Segoe UI", 9, "bold")).pack(pady=(0, 5))

        self.threshold_slider = ctk.CTkSlider(
            threshold_frame,
            from_=-30, to=0,
            orientation="vertical",
            variable=self.compressor_threshold_var,
            command=self._on_compressor_change,
            height=200,
            width=11,
            border_width=0,
            button_length=20,
            corner_radius=4,
            button_corner_radius=2,
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_button,
            button_hover_color=accent_hover,
            bg_color=bg,
            border_color="transparent"
        )
        self.threshold_slider.pack(pady=5)

        self.threshold_label = ttk.Label(threshold_frame, text=f"{self.compressor_threshold_var.get():.1f} dB", font=("Segoe UI", 8), width=10, anchor="center")
        self.threshold_label.pack()

        # Ratio
        ratio_frame = ttk.Frame(params_frame)
        ratio_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True, padx=10)

        ttk.Label(ratio_frame, text="Ratio", font=("Segoe UI", 9, "bold")).pack(pady=(0, 5))

        self.ratio_slider = ctk.CTkSlider(
            ratio_frame,
            from_=1.0, to=20.0,
            orientation="vertical",
            variable=self.compressor_ratio_var,
            command=self._on_compressor_change,
            height=200,
            width=11,
            border_width=0,
            button_length=20,
            corner_radius=4,
            button_corner_radius=2,
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_button,
            button_hover_color=accent_hover,
            bg_color=bg,
            border_color="transparent"
        )
        self.ratio_slider.pack(pady=5)

        self.ratio_label = ttk.Label(ratio_frame, text=f"{self.compressor_ratio_var.get():.1f}:1", font=("Segoe UI", 8), width=10, anchor="center")
        self.ratio_label.pack()

        # Attack
        attack_frame = ttk.Frame(params_frame)
        attack_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True, padx=10)

        ttk.Label(attack_frame, text="Attack", font=("Segoe UI", 9, "bold")).pack(pady=(0, 5))

        self.attack_slider = ctk.CTkSlider(
            attack_frame,
            from_=1, to=400,
            orientation="vertical",
            variable=self.compressor_attack_var,
            command=self._on_compressor_change,
            height=200,
            width=11,
            border_width=0,
            button_length=20,
            corner_radius=4,
            button_corner_radius=2,
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_button,
            button_hover_color=accent_hover,
            bg_color=bg,
            border_color="transparent"
        )
        self.attack_slider.pack(pady=5)

        self.attack_label = ttk.Label(attack_frame, text=f"{self.compressor_attack_var.get():.1f} ms", font=("Segoe UI", 8), width=10, anchor="center")
        self.attack_label.pack()

        # Release
        release_frame = ttk.Frame(params_frame)
        release_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True, padx=10)

        ttk.Label(release_frame, text="Release", font=("Segoe UI", 9, "bold")).pack(pady=(0, 5))

        self.release_slider = ctk.CTkSlider(
            release_frame,
            from_=1, to=800,
            orientation="vertical",
            variable=self.compressor_release_var,
            command=self._on_compressor_change,
            height=200,
            width=11,
            border_width=0,
            button_length=20,
            corner_radius=4,
            button_corner_radius=2,
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_button,
            button_hover_color=accent_hover,
            bg_color=bg,
            border_color="transparent"
        )
        self.release_slider.pack(pady=5)

        self.release_label = ttk.Label(release_frame, text=f"{self.compressor_release_var.get():.1f} ms", font=("Segoe UI", 8), width=10, anchor="center")
        self.release_label.pack()

        # Knee
        knee_frame = ttk.Frame(params_frame)
        knee_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True, padx=10)

        ttk.Label(knee_frame, text="Knee", font=("Segoe UI", 9, "bold")).pack(pady=(0, 5))

        self.knee_slider = ctk.CTkSlider(
            knee_frame,
            from_=0, to=10.0,
            orientation="vertical",
            variable=self.compressor_knee_var,
            command=self._on_compressor_change,
            height=200,
            width=11,
            border_width=0,
            button_length=20,
            corner_radius=4,
            button_corner_radius=2,
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_button,
            button_hover_color=accent_hover,
            bg_color=bg,
            border_color="transparent"
        )
        self.knee_slider.pack(pady=5)

        self.knee_label = ttk.Label(knee_frame, text=f"{self.compressor_knee_var.get():.1f} dB", font=("Segoe UI", 8), width=10, anchor="center")
        self.knee_label.pack()

        # Makeup Gain
        makeup_frame = ttk.Frame(params_frame)
        makeup_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True, padx=10)

        ttk.Label(makeup_frame, text="Makeup", font=("Segoe UI", 9, "bold")).pack(pady=(0, 5))

        self.makeup_slider = ctk.CTkSlider(
            makeup_frame,
            from_=0, to=24,
            orientation="vertical",
            variable=self.compressor_makeup_var,
            command=self._on_compressor_change,
            height=200,
            width=11,
            border_width=0,
            button_length=20,
            corner_radius=4,
            button_corner_radius=2,
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_button,
            button_hover_color=accent_hover,
            bg_color=bg,
            border_color="transparent"
        )
        self.makeup_slider.pack(pady=5)

        self.makeup_label = ttk.Label(makeup_frame, text=f"{self.compressor_makeup_var.get():+.1f} dB", font=("Segoe UI", 8), width=10, anchor="center")
        self.makeup_label.pack()

        # Detection Mode
        mode_frame = ttk.Frame(params_frame)
        mode_frame.pack(side=tk.LEFT, fill=tk.Y, expand=True, padx=10)

        ttk.Label(mode_frame, text="Detection", font=("Segoe UI", 9, "bold")).pack(pady=(0, 5))

        # Center the switch vertically
        mode_center = ttk.Frame(mode_frame)
        mode_center.pack(expand=True)

        self.rms_mode_switch = ctk.CTkSwitch(
            mode_center,
            text="RMS",
            variable=self.compressor_rms_mode_var,
            command=self._on_compressor_change,
            width=60,
            text_color=fg,
            progress_color=accent,
            button_color=accent,
            button_hover_color=accent_hover,
            fg_color=palette.get("switch_bg", "#939393"),
            bg_color=bg
        )
        self.rms_mode_switch.pack(pady=(80, 5))

        self.mode_label = ttk.Label(mode_center, text="Peak" if not self.compressor_rms_mode_var.get() else "RMS", font=("Segoe UI", 8), width=10, anchor="center")
        self.mode_label.pack()

        # Info Label at bottom
        info_frame = ttk.Frame(container)
        info_frame.pack(fill=tk.X, pady=(20, 0))

        info_label = ttk.Label(
            info_frame,
            text="The compressor reduces dynamic range by attenuating signals above the threshold. Use makeup gain to compensate for volume loss.",
            font=("Segoe UI", 9),
            justify=tk.CENTER,
            wraplength=760
        )
        info_label.pack(pady=(20, 0))

    def _on_compressor_toggle(self):
        """Handle compressor enable/disable."""
        enabled = self.compressor_enabled_var.get()
        state = "normal" if enabled else "disabled"

        # Update UI state
        if hasattr(self, 'threshold_slider'):
            self.threshold_slider.configure(state=state)
            self.ratio_slider.configure(state=state)
            self.attack_slider.configure(state=state)
            self.release_slider.configure(state=state)
            self.makeup_slider.configure(state=state)
            self.knee_slider.configure(state=state)
            self.rms_mode_switch.configure(state=state)

        # Update status label
        if hasattr(self, 'compressor_status_label'):
            self.compressor_status_label.configure(
                text="Enabled" if enabled else "Disabled",
                text_color=self.palette.get("accent", "#0078d4") if enabled else self.palette.get("fg", "#808080")
            )

        # Apply to player
        self._apply_compressor()

    def _on_compressor_change(self, value=None):
        """Handle compressor parameter changes."""
        # Update labels
        if hasattr(self, 'threshold_label'):
            self.threshold_label.configure(text=f"{self.compressor_threshold_var.get():.1f} dB")
            self.ratio_label.configure(text=f"{self.compressor_ratio_var.get():.1f}:1")
            self.attack_label.configure(text=f"{self.compressor_attack_var.get():.1f} ms")
            self.release_label.configure(text=f"{self.compressor_release_var.get():.1f} ms")
            self.makeup_label.configure(text=f"{self.compressor_makeup_var.get():+.1f} dB")
            self.knee_label.configure(text=f"{self.compressor_knee_var.get():.1f} dB")
            self.mode_label.configure(text="RMS" if self.compressor_rms_mode_var.get() else "Peak")

        # Apply to player
        self._apply_compressor()

    def _apply_compressor(self):
        """Apply current compressor settings to player."""
        if hasattr(self.player, 'set_compressor'):
            try:
                self.player.set_compressor(
                    enabled=self.compressor_enabled_var.get(),
                    threshold=self.compressor_threshold_var.get(),
                    ratio=self.compressor_ratio_var.get(),
                    attack=self.compressor_attack_var.get(),
                    release=self.compressor_release_var.get(),
                    makeup_gain=self.compressor_makeup_var.get(),
                    knee=self.compressor_knee_var.get(),
                    use_rms=self.compressor_rms_mode_var.get()
                )
            except Exception as e:
                logger.error(f"Error applying compressor: {e}")

    def _reset_compressor(self):
        """Reset compressor to original default values."""
        defaults = self._original_compressor_defaults
        self.compressor_threshold_var.set(defaults['threshold'])
        self.compressor_ratio_var.set(defaults['ratio'])
        self.compressor_attack_var.set(defaults['attack'])
        self.compressor_release_var.set(defaults['release'])
        self.compressor_makeup_var.set(defaults['makeup_gain'])
        self.compressor_knee_var.set(defaults['knee'])
        self.compressor_rms_mode_var.set(defaults['use_rms'])
        self._on_compressor_change()

    def _create_spatializer_tab(self):
        """Create the Spatializer tab UI."""
        # Get theme colors for widget creation
        palette = self.theme_manager.palette
        bg = palette.get("bg", "#ffffff")
        fg = palette.get("fg", "#000000")
        accent = palette.get("accent", "#0078d4")
        accent_hover = palette.get("accent_hover", "#106ebe")
        slider_bg = palette.get("slider_bg", "#2a2a2a")
        slider_fg = palette.get("slider_bg", accent)
        slider_button = palette.get("accent", "#0078d4")
        btn_bg = palette.get("button_bg_color", accent)
        btn_fg = palette.get("button_fg_color", "#ffffff")
        slider_border = palette.get("border", "#cccccc")

        container = ttk.Frame(self.spatializer_tab)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Enable Switch
        top_frame = ttk.Frame(container)
        top_frame.pack(fill=tk.X, pady=(0, 20))

        self.spatializer_enable_switch = ctk.CTkSwitch(
            top_frame,
            text="Spatializer:",
            variable=self.spatializer_enabled_var,
            command=self._on_spatializer_toggle,
            width=110,
            text_color=fg,
            progress_color=accent,
            button_color=accent,
            button_hover_color=accent_hover,
            fg_color=palette.get("switch_bg", "#939393"),
            bg_color=bg
        )
        self.spatializer_enable_switch.pack(side=tk.LEFT)

        self.spatializer_status_label = ctk.CTkLabel(
            top_frame,
            text="Enabled" if self.spatializer_enabled_var.get() else "Disabled",
            text_color=accent if self.spatializer_enabled_var.get() else palette.get("fg", "#808080"),
            font=("Segoe UI", 11, "bold"),
            bg_color=bg
        )
        self.spatializer_status_label.pack(side=tk.LEFT)

        # Reset button
        self.spatializer_reset_btn = ctk.CTkButton(
            top_frame,
            text="Reset to Defaults",
            width=120,
            height=28,
            font=("Segoe UI", 10),
            command=self._reset_spatializer,
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )
        self.spatializer_reset_btn.pack(side=tk.RIGHT)

        # Parameters Frame with vertical sliders
        params_frame = ttk.Frame(container)
        params_frame.pack(fill=tk.BOTH, expand=True)

        # Helper to create slider
        def create_spat_slider(parent, label, var, from_, to_):
            frame = ttk.Frame(parent)
            frame.pack(side=tk.LEFT, fill=tk.Y, expand=True, padx=10)

            ttk.Label(frame, text=label, font=("Segoe UI", 9, "bold")).pack(pady=(0, 5))

            slider = ctk.CTkSlider(
                frame,
                from_=from_, to=to_,
                orientation="vertical",
                variable=var,
                command=self._on_spatializer_change,
                height=200,
                width=11,
                border_width=1,
                button_length=20,
                corner_radius=4,
                button_corner_radius=2,
                fg_color=slider_bg,
                progress_color=slider_fg,
                button_color=slider_button,
                button_hover_color=accent_hover,
                bg_color=bg,
                border_color=slider_border
            )
            slider.pack(pady=5)

            lbl = ttk.Label(frame, text=f"{var.get():.2f}", font=("Segoe UI", 8), width=10, anchor="center")
            lbl.pack()
            # Store label reference on slider
            slider.value_label = lbl
            return slider

        self.spat_size_slider = create_spat_slider(params_frame, "Size", self.spat_size_var, 0.0, 1.1)
        self.spat_width_slider = create_spat_slider(params_frame, "Width", self.spat_width_var, 0.0, 1.0)
        self.spat_wet_slider = create_spat_slider(params_frame, "Wet", self.spat_wet_var, 0.0, 1.0)
        self.spat_dry_slider = create_spat_slider(params_frame, "Dry", self.spat_dry_var, 0.0, 1.0)
        self.spat_damp_slider = create_spat_slider(params_frame, "Damp", self.spat_damp_var, 0.0, 1.0)

        # Info Label
        info_frame = ttk.Frame(container)
        info_frame.pack(fill=tk.X, pady=(20, 0))

        info_label = ttk.Label(
            info_frame,
            text="Spatializer adds reverb and stereo widening effects to create a sense of space.",
            font=("Segoe UI", 9),
            justify=tk.CENTER,
            wraplength=700
        )
        info_label.pack(pady=(20, 0))

    def _on_spatializer_toggle(self):
        """Handle spatializer enable/disable."""
        enabled = self.spatializer_enabled_var.get()
        state = "normal" if enabled else "disabled"

        # Update UI state
        if hasattr(self, 'spat_size_slider'):
            self.spat_size_slider.configure(state=state)
            self.spat_width_slider.configure(state=state)
            self.spat_wet_slider.configure(state=state)
            self.spat_dry_slider.configure(state=state)
            self.spat_damp_slider.configure(state=state)

        # Update status label
        if hasattr(self, 'spatializer_status_label'):
            self.spatializer_status_label.configure(
                text="Enabled" if enabled else "Disabled",
                text_color=self.palette.get("accent", "#0078d4") if enabled else self.palette.get("fg", "#808080")
            )

        # Apply to player
        self._apply_spatializer()

    def _on_spatializer_change(self, value=None):
        """Handle spatializer parameter changes."""
        # Update labels
        if hasattr(self, 'spat_size_slider'):
            self.spat_size_slider.value_label.configure(text=f"{self.spat_size_var.get():.2f}")
            self.spat_width_slider.value_label.configure(text=f"{self.spat_width_var.get():.2f}")
            self.spat_wet_slider.value_label.configure(text=f"{self.spat_wet_var.get():.2f}")
            self.spat_dry_slider.value_label.configure(text=f"{self.spat_dry_var.get():.2f}")
            self.spat_damp_slider.value_label.configure(text=f"{self.spat_damp_var.get():.2f}")

        # Apply to player
        self._apply_spatializer()

    def _apply_spatializer(self):
        """Apply current spatializer settings to player."""
        if hasattr(self.player, 'set_spatializer'):
            try:
                self.player.set_spatializer(
                    enabled=self.spatializer_enabled_var.get(),
                    size=self.spat_size_var.get(),
                    width=self.spat_width_var.get(),
                    wet=self.spat_wet_var.get(),
                    dry=self.spat_dry_var.get(),
                    damp=self.spat_damp_var.get()
                )
            except Exception as e:
                logger.error(f"Error applying spatializer: {e}")

    def _reset_spatializer(self):
        """Reset spatializer to original default values."""
        defaults = self._original_spatializer_defaults
        self.spat_size_var.set(defaults.get('size', 0.85))
        self.spat_width_var.set(defaults.get('width', 0.5))
        self.spat_wet_var.set(defaults.get('wet', 0.4))
        self.spat_dry_var.set(defaults.get('dry', 0.5))
        self.spat_damp_var.set(defaults.get('damp', 0.5))
        self._on_spatializer_change()

    def _on_rate_change(self, value):
        self.speed_label.configure(text=f"{float(value):.2f}x")
        if hasattr(self.player, 'set_playback_rate'):
            self.player.set_playback_rate(float(value))

    def _reset_speed(self):
        default_rate = AUDIO_DEFAULTS['playback']['default_rate']
        self.rate_var.set(default_rate)
        self._on_rate_change(default_rate)

    def _on_vocal_remover_toggle(self):
        enabled = self.vocal_remover_var.get()
        self.player.set_vocal_remover_enabled(enabled)

        # Update status label
        if hasattr(self, 'vocal_status_label'):
            self.vocal_status_label.configure(
                text="Enabled" if enabled else "Disabled",
                text_color=self.palette.get("accent", "#0078d4") if enabled else self.palette.get("fg", "#808080")
            )

    def _on_channel_mode_change(self, value):
        if hasattr(self.player, 'set_channel_mode'):
            self.player.set_channel_mode(value)

    def _on_vocal_intensity_change(self, value):
        intensity = float(value)
        self.vocal_intensity_label.configure(text=f"{intensity:.2f}")
        self.player.set_vocal_remover_intensity(intensity)

    def _reset_vocal_remover(self):
        default_intensity = 0.5
        self.vocal_remover_var.set(False)
        self.vocal_intensity_var.set(default_intensity)
        self._on_vocal_remover_toggle()
        self._on_vocal_intensity_change(default_intensity)

    def _save_to_config(self):
        """Save current settings as defaults to the JSON configuration file."""
        global AUDIO_CONFIG

        try:
            # Update the config with current values
            config_to_save = {
                "equalizer": {
                    "enabled": self.enabled_var.get(),
                    "gains": [v.get() for v in self.slider_vars],
                    "preamp": self.preamp_var.get(),
                    "selected_preset": self.preset_var.get()
                },
                "compressor": {
                    "enabled": self.compressor_enabled_var.get(),
                    "threshold": self.compressor_threshold_var.get(),
                    "ratio": self.compressor_ratio_var.get(),
                    "attack": self.compressor_attack_var.get(),
                    "release": self.compressor_release_var.get(),
                    "makeup_gain": self.compressor_makeup_var.get(),
                    "knee": self.compressor_knee_var.get(),
                    "use_rms": self.compressor_rms_mode_var.get(),
                    "rms_buffer_size": AUDIO_CONFIG['compressor']['rms_buffer_size']
                },
                "spatializer": {
                    "enabled": self.spatializer_enabled_var.get(),
                    "size": self.spat_size_var.get(),
                    "width": self.spat_width_var.get(),
                    "wet": self.spat_wet_var.get(),
                    "dry": self.spat_dry_var.get(),
                    "damp": self.spat_damp_var.get()
                },
                "playback": {
                    "default_rate": self.rate_var.get(),
                    "min_rate": AUDIO_CONFIG['playback']['min_rate'],
                    "max_rate": AUDIO_CONFIG['playback']['max_rate']
                },
                "vocal_remover": {
                    "enabled": self.vocal_remover_var.get(),
                    "intensity": self.vocal_intensity_var.get()
                },
                "channel_mode": {
                    "mode": self.channel_mode_var.get()
                }
            }

            # Write to file
            config_path = Path(__file__).parent.parent / 'audio' / 'audio_effects_config.json'
            with open(config_path, 'w') as f:
                json.dump(config_to_save, f, indent=2)

            # Update the global config
            AUDIO_CONFIG = config_to_save

        except Exception as e:
            logger.error(f"Error saving configuration: {e}")

    def _on_rate_change(self, value):
        self.speed_label.configure(text=f"{float(value):.2f}x")
        if hasattr(self.player, 'set_playback_rate'):
            self.player.set_playback_rate(float(value))

    def _reset_speed(self):
        self.rate_var.set(1.0)
        self._on_rate_change(1.0)

    def _apply_theme(self):
        """Apply theme colors from palette."""
        palette = self.theme_manager.palette
        bg = palette.get("bg", "#ffffff")
        fg = palette.get("fg", "#000000")
        accent = palette.get("accent", "#0078d4")
        accent_hover = palette.get("accent_hover", "#106ebe")
        slider_bg = palette.get("slider_bg", "#0078d4")
        slider_fg = palette.get("slider_bg", accent)
        slider_button = palette.get("accent", "#0078d4")
        btn_bg = palette.get("button_bg_color", accent)
        btn_fg = palette.get("button_fg_color", "#ffffff")

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

        if hasattr(self, 'vocal_remover_switch'):
            self.vocal_remover_switch.configure(
                text_color=fg, progress_color=accent, button_color=accent,
                button_hover_color=accent_hover, fg_color=palette.get("switch_bg", "#939393"), bg_color=bg
            )

        # Update frames
        for widget in self.winfo_children():
            if isinstance(widget, (ttk.Frame, ttk.LabelFrame)):
                widget.configure(style="TFrame")
                for child in widget.winfo_children():
                    if isinstance(child, (ttk.Frame, ttk.LabelFrame)):
                        child.configure(style="TFrame")

        # CTk Widgets

        # Bottom buttons
        self.reset_speed_btn.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )

        if hasattr(self, 'reset_vocal_btn'):
            self.reset_vocal_btn.configure(
                fg_color=btn_bg,
                text_color=btn_fg,
                hover_color=accent_hover,
                bg_color=bg
            )

        self.compressor_reset_btn.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )

        self.save_btn.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
        )
        self.close_btn.configure(
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
        self.preamp_slider.configure(
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_button,
            button_hover_color=accent_hover,
            bg_color=bg,
            border_color="transparent"
        )

        self.speed_slider.configure(
            fg_color=slider_bg,
            progress_color=slider_fg,
            button_color=slider_button,
            button_hover_color=accent_hover,
            bg_color=bg,
            border_color="transparent"
        )

        if hasattr(self, 'vocal_intensity_slider'):
            self.vocal_intensity_slider.configure(
                fg_color=slider_bg,
                progress_color=slider_fg,
                button_color=slider_button,
                button_hover_color=accent_hover,
                bg_color=bg,
                border_color="transparent"
            )

        for slider in self.sliders:
            slider.configure(
                fg_color=slider_bg,
                progress_color=slider_fg,
                button_color=slider_button,
                button_hover_color=accent_hover,
                bg_color=bg,
                border_color="transparent"
            )

        # Compressor sliders
        if hasattr(self, 'threshold_slider'):
            for slider in [self.threshold_slider, self.ratio_slider, self.attack_slider,
                          self.release_slider, self.makeup_slider, self.knee_slider]:
                slider.configure(
                    fg_color=slider_bg,
                    progress_color=slider_fg,
                    button_color=slider_button,
                    button_hover_color=accent_hover,
                    bg_color=bg,
                    border_color="transparent"
                )

        # Labels
        self.preamp_label.configure(foreground=fg, background=bg)
        for slider in self.sliders:
            if hasattr(slider, 'value_label'):
                slider.value_label.configure(foreground=fg, background=bg)
        self.speed_label.configure(foreground=fg, background=bg)

        # Compressor labels
        if hasattr(self, 'threshold_label'):
            self.threshold_label.configure(foreground=fg, background=bg)
            self.ratio_label.configure(foreground=fg, background=bg)
            self.attack_label.configure(foreground=fg, background=bg)
            self.release_label.configure(foreground=fg, background=bg)
            self.makeup_label.configure(foreground=fg, background=bg)

        # Compressor switch
        if hasattr(self, 'compressor_enable_switch'):
            self.compressor_enable_switch.configure(
                text_color=fg, progress_color=accent, button_color=accent,
                button_hover_color=accent_hover, fg_color=palette.get("switch_bg", "#939393"), bg_color=bg
            )

        # RMS mode switch
        if hasattr(self, 'rms_mode_switch'):
            self.rms_mode_switch.configure(
                text_color=fg, progress_color=accent, button_color=accent,
                button_hover_color=accent_hover, fg_color=palette.get("switch_bg", "#939393"), bg_color=bg
            )

        # Spatializer sliders
        if hasattr(self, 'spat_size_slider'):
            for slider in [self.spat_size_slider, self.spat_width_slider, self.spat_wet_slider,
                          self.spat_dry_slider, self.spat_damp_slider]:
                slider.configure(
                    fg_color=slider_bg,
                    progress_color=slider_fg,
                    button_color=slider_button,
                    button_hover_color=accent_hover,
                    bg_color=bg,
                    border_color="transparent"
                )

        # Spatializer labels
        if hasattr(self, 'spat_size_slider'):
            self.spat_size_slider.value_label.configure(foreground=fg, background=bg)
            self.spat_width_slider.value_label.configure(foreground=fg, background=bg)
            self.spat_wet_slider.value_label.configure(foreground=fg, background=bg)
            self.spat_dry_slider.value_label.configure(foreground=fg, background=bg)
            self.spat_damp_slider.value_label.configure(foreground=fg, background=bg)

        # Spatializer switch
        if hasattr(self, 'spatializer_enable_switch'):
            self.spatializer_enable_switch.configure(
                text_color=fg, progress_color=accent, button_color=accent,
                button_hover_color=accent_hover, fg_color=palette.get("switch_bg", "#939393"), bg_color=bg
            )

        # Spatializer reset button
        if hasattr(self, 'spatializer_reset_btn'):
            self.spatializer_reset_btn.configure(
                fg_color=btn_bg,
                text_color=btn_fg,
                hover_color=accent_hover,
                bg_color=bg
            )

        # Channel Mode Radios
        if hasattr(self, 'channel_radios'):
            for radio in self.channel_radios:
                radio.configure(
                    text_color=fg,
                    fg_color=accent,
                    hover_color=accent_hover,
                    bg_color=bg,
                    border_color=palette.get("switch_bg", "#939393")
                )

        # Update all status labels
        if hasattr(self, 'enable_status_label'):
            is_enabled = self.enabled_var.get()
            self.enable_status_label.configure(
                text_color=accent if is_enabled else palette.get("fg", "#808080"),
                bg_color=bg
            )

        if hasattr(self, 'vocal_status_label'):
            is_enabled = self.vocal_remover_var.get()
            self.vocal_status_label.configure(
                text_color=accent if is_enabled else palette.get("fg", "#808080"),
                bg_color=bg
            )

        if hasattr(self, 'compressor_status_label'):
            is_enabled = self.compressor_enabled_var.get()
            self.compressor_status_label.configure(
                text_color=accent if is_enabled else palette.get("fg", "#808080"),
                bg_color=bg
            )

        if hasattr(self, 'spatializer_status_label'):
            is_enabled = self.spatializer_enabled_var.get()
            self.spatializer_status_label.configure(
                text_color=accent if is_enabled else palette.get("fg", "#808080"),
                bg_color=bg
            )

        # Preset dropdown styling
        if hasattr(self, 'preset_menu'):
            self.preset_menu.configure(
                fg_color=bg,
                button_color=bg,
                button_hover_color=palette.get("dropdown_hover", "#000000"),
                text_color=palette.get("dropdown_text", "#000000"),
                dropdown_fg_color=palette.get("dropdown_bg", "#000000"),
                dropdown_hover_color=palette.get("dropdown_hover", "#000000"),
                dropdown_text_color=palette.get("dropdown_text", "#000000")
            )

        if hasattr(self, 'preset_menu_frame'):
            self.preset_menu_frame.configure(
                fg_color="transparent",
                border_width=2,
                border_color=palette.get("border", "#cccccc"),
                corner_radius=0
            )

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

        # Update status label
        if hasattr(self, 'enable_status_label'):
            self.enable_status_label.configure(
                text="Enabled" if enabled else "Disabled",
                text_color=self.palette.get("accent", "#0078d4") if enabled else self.palette.get("fg", "#808080")
            )

        # Call player
        if hasattr(self.player, 'set_equalizer_enabled'):
            try:
                self.player.set_equalizer_enabled(enabled)
            except Exception as e:
                logger.error(f"Error setting EQ enabled: {e}")

    def _on_preamp_change(self, value):
        val = float(value)
        self.preamp_label.configure(text=f"{val:+.1f} dB")

        if hasattr(self.player, 'set_equalizer_preamp'):
            try:
                self.player.set_equalizer_preamp(val)
            except Exception as e:
                logger.error(f"Error setting preamp: {e}")

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
                logger.error(f"Error setting EQ band {index}: {e}")

    def _reset_flat(self):
        """Reset all sliders to 0."""
        self.preamp_var.set(0)
        self._on_preamp_change(0)

        for i, var in enumerate(self.slider_vars):
            var.set(0)
            self._on_band_change(i, 0)

    def _on_preset_change(self, choice):
        """Apply selected EQ preset."""
        if choice == "":
            choice = "Flat"
            self.preset_var.set("")
            AUDIO_CONFIG['equalizer']['selected_preset'] = ""
        else:
            self.preset_var.set(choice)
            AUDIO_CONFIG['equalizer']['selected_preset'] = choice
        if choice in self.presets:
            preamp, values = self.presets[choice]

            # Set Preamp
            self.preamp_var.set(preamp)
            self._on_preamp_change(preamp)

            for i, val in enumerate(values):
                if i < len(self.slider_vars):
                    self.slider_vars[i].set(val)
                    self._on_band_change(i, val)

    def _on_close(self):
        """Handle window close event."""
        self.destroy()
