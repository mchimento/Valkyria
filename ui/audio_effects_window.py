import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from ui.utils import center_window

class EqualizerWindow(tk.Toplevel):
    """
    Equalizer window with 10-band EQ and Preamp control.
    Uses the application theme palette for styling.
    """
    def __init__(self, parent, player, theme_manager):
        super().__init__(parent)
        self.player = player
        self.theme_manager = theme_manager

        self.title("Equalizer")
        self.geometry("750x380")
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

        self._create_ui()
        self._apply_theme()

        self.deiconify()

    def _create_ui(self):
        """Build the UI components."""
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

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
        style.configure("TSeparator", background=palette.get("border", "#cccccc"))

        # Update frames
        for widget in self.winfo_children():
            if isinstance(widget, ttk.Frame):
                widget.configure(style="TFrame")
                for child in widget.winfo_children():
                    if isinstance(child, ttk.Frame):
                        child.configure(style="TFrame")

        # CTk Widgets
        # Switch
        self.enable_switch.configure(
            text_color=fg,
            progress_color=accent,
            button_color=accent,
            button_hover_color=accent_hover,
            fg_color=palette.get("switch_bg", "#939393"),
            bg_color=bg
        )

        # Reset Button
        btn_bg = palette.get("button_bg_color", accent)
        btn_fg = palette.get("button_fg_color", "#ffffff")
        self.reset_btn.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=accent_hover,
            bg_color=bg
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

        for slider in self.sliders:
            slider.configure(
                fg_color=slider_bg,
                progress_color=slider_fg,
                button_color=slider_fg,
                button_hover_color=accent_hover,
                bg_color=bg
            )

        # Labels
        self.preamp_label.configure(foreground=fg, background=bg)
        for slider in self.sliders:
            if hasattr(slider, 'value_label'):
                slider.value_label.configure(foreground=fg, background=bg)

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
