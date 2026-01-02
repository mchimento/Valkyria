import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from ui.utils import center_window

class AudioEffectsWindow(tk.Toplevel):
    """
    Audio Effects window with Equalizer and Speed Control.
    Uses the application theme palette for styling.
    """
    def __init__(self, parent, player, theme_manager):
        super().__init__(parent)
        self.player = player
        self.theme_manager = theme_manager
        self.settings = None  # Initialize settings for compatibility
        self._save_timer = None  # Initialize save timer

        self.title("Audio Effects")
        self.geometry("800x450")
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

        # EQ Presets (Preamp, [Bands])
        self.presets = {
            "Flat": (12, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]),
            "Classical": (12, [0, 0, 0, 0, 0, 0, -7.2, -7.2, -7.2, -9.6]),
            "Club": (6, [0, 0, 8, 5.6, 5.6, 5.6, 3.2, 0, 0, 0]),
            "Dance": (5, [9.6, 7.2, 2.4, 0, 0, -5.6, -7.2, -7.2, 0, 0]),
            "Full Bass": (5, [-6, 9.6, 9.6, 5.6, 1.6, -4, -8, -10.3, -11.2, -11.2]),
            "Full Treble": (3, [-9.6, -9.6, -9.6, -4, 2.4, 11.2, 16, 16, 16, 16.7]),
            "Headphones": (4, [4.8, 11.2, 5.6, -3.2, -2.4, 1.6, 4.8, 9.6, 12.8, 14.4]),
            "Large Hall": (5, [10.3, 10.3, 5.6, 5.6, 0, -4.8, -4.8, -4.8, 0, 0]),
            "Live": (7, [-4.8, 0, 4, 5.6, 5.6, 5.6, 4.0, 2.4, 2.4, 2.4]),
            "Party": (6, [7.2, 7.2, 0, 0, 0, 0, 0, 0, 7.2, 7.2]),
            "Pop": (6, [-1.6, 4.8, 7.2, 8, 5.6, 0, -2.4, -2.4, -1.6, -1.6]),
            "Reggae": (8, [0, 0, 0, -5.6, 0, 6.4, 6.4, 0, 0, 0]),
            "Rock": (5, [8, 4.8, -5.6, -8, -3.2, 4, 8.8, 11.2, 11.2, 11.2]),
            "Ska": (6, [-2.4, -4.8, -4, 0, 4, 5.6, 8.8, 9.6, 11.2, 9.6]),
            "Soft": (5, [4.8, 1.6, 0, -2.4, 0, 4, 8, 9.6, 11.2, 12]),
            "Soft Rock": (7, [4, 4, 2.4, 0, -4, -5.6, -3.2, 0, 2.4, 8.8]),
            "Techno": (5, [8.0, 5.6, 0, -5.6, -4.8, 0, 8, 9.6, 9.6, 8.8])
        }

        # State - default to False
        self.enabled_var = tk.BooleanVar(value=False)
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

        self._create_ui()
        self._apply_theme()

        # Synchronize UI state with initial values
        self._on_enable_toggle()

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

        self.preset_var = tk.StringVar(value="")

        # Frame wrapper for border effect
        self.preset_menu_frame = ctk.CTkFrame(
            top_frame,
            fg_color="transparent",
            border_width=1
        )
        self.preset_menu_frame.pack(side=tk.RIGHT, padx=(0, 10))

        self.preset_menu = ctk.CTkOptionMenu(
            self.preset_menu_frame,
            values=[""] + list(self.presets.keys()),
            command=self._on_preset_change,
            variable=self.preset_var,
            width=116,
            height=26
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

        self.preamp_var = tk.DoubleVar(value=0)
        # Try get initial preamp
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
            button_corner_radius=2
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
                from_=-20, to=20,
                orientation="vertical",
                variable=val_var,
                command=lambda v, idx=i: self._on_band_change(idx, v),
                height=200,
                width=11,
                border_width=0,
                button_length=20,
                corner_radius=4,
                button_corner_radius=2
            )
            slider.pack(pady=5)
            self.sliders.append(slider)

            # dB Label
            lbl = ttk.Label(band_frame, text="0 dB", font=("Segoe UI", 8), width=10, anchor="center")
            lbl.pack()
            # Store label reference on slider for easy update
            slider.value_label = lbl

        # --- Tab 2: Advanced ---
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
            number_of_steps=15,
            variable=self.rate_var,
            command=self._on_rate_change
        )
        self.speed_slider.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.reset_speed_btn = ctk.CTkButton(
            speed_frame,
            text="Reset (1.0x)",
            width=80,
            height=24,
            font=("Segoe UI", 9),
            command=self._reset_speed
        )
        self.reset_speed_btn.pack(side=tk.RIGHT, padx=(10, 10))

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

        # Update frames
        for widget in self.winfo_children():
            if isinstance(widget, (ttk.Frame, ttk.LabelFrame)):
                widget.configure(style="TFrame")
                for child in widget.winfo_children():
                    if isinstance(child, (ttk.Frame, ttk.LabelFrame)):
                        child.configure(style="TFrame")

        # CTk Widgets

        # Preset Menu - Smart recreation only when colors change
        btn_bg = palette.get("button_bg_color", accent)
        btn_fg = palette.get("button_fg_color", "#ffffff")

        # Check if we need to recreate (store previous colors)
        if not hasattr(self, '_last_dropdown_bg') or self._last_dropdown_bg != btn_bg:
            # Store current selection
            current_selection = self.preset_var.get()

            # Recreate frame and dropdown
            self.preset_menu_frame.destroy()
            self.preset_menu_frame = ctk.CTkFrame(
                self.preset_menu_frame.master,
                fg_color="transparent",
                border_width=1
            )
            self.preset_menu_frame.pack(side=tk.RIGHT, padx=(0, 10))

            self.preset_menu = ctk.CTkOptionMenu(
                self.preset_menu_frame,
                values=[""] + list(self.presets.keys()),
                command=self._on_preset_change,
                variable=self.preset_var,
                width=116,
                height=26
            )
            self.preset_menu.pack(padx=2, pady=2)

            # Recreate label to maintain order
            self.preset_label.destroy()
            self.preset_label = ttk.Label(self.preset_label.master, text="Preset", font=("Roboto", 10, "bold"))
            self.preset_label.pack(side=tk.RIGHT, padx=(0, 5))

            # Restore selection
            self.preset_var.set(current_selection)

            # Restore state based on equalizer enabled/disabled
            state = "normal" if self.enabled_var.get() else "disabled"
            self.preset_menu.configure(state=state)

            # Store new color
            self._last_dropdown_bg = btn_bg

        # Apply theme colors
        self.preset_menu_frame.configure(
            border_color=palette.get("border", "#cccccc")
        )

        self.preset_menu.configure(
            fg_color=bg,
            button_color=bg,
            button_hover_color=palette.get("dropdown_hover", "#000000"),
            text_color=palette.get("dropdown_text", "#000000"),
            dropdown_fg_color=palette.get("dropdown_bg", "#000000"),
            dropdown_hover_color=palette.get("dropdown_hover", "#000000"),
            dropdown_text_color=palette.get("dropdown_text", "#000000")
        )

        self.reset_speed_btn.configure(
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

        # Sliders - VLC Style
        slider_bg = palette.get("slider_bg", "#2a2a2a")
        slider_fg = palette.get("slider_bg", accent)
        slider_button = palette.get("accent", "#0078d4")

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

        for slider in self.sliders:
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
        self.preset_label.configure(foreground=fg, background=bg)
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
        self.preset_menu.configure(state=state)

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

    def _on_preset_change(self, choice):
        """Apply selected EQ preset."""
        if choice in self.presets:
            preamp, values = self.presets[choice]

            # Set Preamp
            self.preamp_var.set(preamp)
            self._on_preamp_change(preamp)

            for i, val in enumerate(values):
                if i < len(self.slider_vars):
                    self.slider_vars[i].set(val)
                    self._on_band_change(i, val)

    def _save_settings(self):
        """Save current audio settings to persistent storage with debouncing."""
        if not self.settings:
            return

        # Gather current settings
        effects = {
            'equalizer_enabled': self.enabled_var.get(),
            'equalizer_preamp': self.preamp_var.get(),
            'equalizer_bands': [v.get() for v in self.slider_vars],
            'playback_rate': self.rate_var.get()
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
