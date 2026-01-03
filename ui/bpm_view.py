import tkinter as tk
import customtkinter as ctk

class BPMAnalysisWindow(ctk.CTkToplevel):
    """Documentation window for BPM Analysis feature."""

    def __init__(self, parent, theme_manager, settings):
        super().__init__(parent)

        self.theme_manager = theme_manager
        self.settings = settings

        self.title("BPM Analysis Documentation")
        self.geometry("700x700")
        self.resizable(True, True)

        # Hide window initially to prevent flickering during positioning
        self.withdraw()

        # Center the window
        self.transient(parent)

        # Get theme colors
        palette = self.theme_manager.palette
        self.bg_color = palette.get("bg", "#1E1E1E" if self.settings.theme == "dark" else "#FAFAFA")
        self.fg_color = palette.get("fg", "#FFFFFF" if self.settings.theme == "dark" else "#000000")
        self.accent_color = palette.get("accent", "#0078d4")
        self.btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        self.btn_fg_color = palette.get("button_fg_color", "#FFFFFF" if self.settings.theme == "dark" else "#000000")

        self.configure(fg_color=self.bg_color)

        # Initialize scrollable frame reference
        self.scrollable_frame = None

        # Create content
        self._create_content()

        # Center and show window
        self._center_and_show()

    def update_theme(self):
        """Update the window colors when theme changes."""
        # Force theme manager to reload current theme
        try:
            self.theme_manager.reload()
        except:
            pass

        # Small delay to ensure theme is fully loaded
        self.after(50, self._apply_theme_updates)

    def _apply_theme_updates(self):
        """Apply theme updates after a small delay."""
        # Get new theme colors after reload
        palette = self.theme_manager.palette
        is_dark = self.settings.theme.lower() == 'dark'

        # Update CustomTkinter appearance mode
        try:
            ctk.set_appearance_mode("Dark" if is_dark else "Light")
        except:
            pass

        # Update color variables with explicit fallbacks
        self.bg_color = palette.get("bg", "#1E1E1E" if is_dark else "#FAFAFA")
        self.fg_color = palette.get("fg", "#FFFFFF" if is_dark else "#000000")
        self.accent_color = palette.get("accent", "#0078d4")
        self.btn_bg = palette.get("button_bg_color", palette.get("accent", "#0078d4"))
        self.btn_fg_color = palette.get("button_fg_color", "#FFFFFF" if is_dark else "#000000")

        # Update window background
        self.configure(fg_color=self.bg_color)

        # Clear existing content properly
        if self.scrollable_frame:
            # Destroy all widgets in the scrollable frame
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()

        # Recreate content with new theme
        self._create_content()

    def _create_content(self):
        """Create the documentation content."""
        # Create scrollable frame only if it doesn't exist
        if not self.scrollable_frame:
            self.scrollable_frame = ctk.CTkScrollableFrame(self, fg_color=self.bg_color)
            self.scrollable_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        else:
            # Update existing scrollable frame background
            self.scrollable_frame.configure(fg_color=self.bg_color)

        # Calculate dynamic wraplength based on window width
        try:
            window_width = self.winfo_width()
            if window_width > 100:  # Valid window width
                wraplength = window_width - 80  # Account for padding
            else:
                wraplength = 600  # Default fallback
        except:
            wraplength = 600  # Default fallback

        # Title
        title_label = ctk.CTkLabel(
            self.scrollable_frame,
            text="🎧 Automatic BPM (Tempo) Analysis",
            font=("Segoe UI", 24, "bold"),
            text_color=self.accent_color,
            fg_color="transparent"
        )
        title_label.pack(pady=(0, 15), anchor="w")

        # Introduction
        intro_text = """Tango Studio can automatically analyze and store the BPM (Beats Per Minute) of your music files. This enables DJ-style features such as tempo sorting, smart playlists, and smooth beat-matched transitions."""

        intro_label = ctk.CTkLabel(
            self.scrollable_frame,
            text=intro_text,
            font=("Segoe UI", 14),
            text_color=self.fg_color,
            fg_color="transparent",
            wraplength=wraplength,
            justify="left"
        )
        intro_label.pack(pady=(0, 15), anchor="w")

        # What is BPM section
        self._create_section(self.scrollable_frame, "What is BPM?",
                            """BPM represents the musical tempo of a track — how fast the beat moves — and is different from audio quality metrics such as kbps. BPM is a musical property and must be computed from the audio signal itself.""", wraplength)

        # How BPM is Calculated section
        self._create_section(self.scrollable_frame, "How BPM is Calculated",
                           """Tango Studio uses the librosa audio analysis library to estimate BPM directly from the sound waveform.""", wraplength)

        # Steps
        steps_title = ctk.CTkLabel(
            self.scrollable_frame,
            text="Analysis Process",
            font=("Segoe UI", 18, "bold"),
            text_color=self.accent_color,
            fg_color="transparent"
        )
        steps_title.pack(pady=(15, 8), anchor="w")

        steps = [
            "Audio Decoding - The audio file is decoded into a mono waveform at a fixed sample rate. For MP3 files, a short segment is first decoded using FFmpeg to ensure reliable analysis.",
            "Onset Strength Detection - librosa computes an onset strength envelope. This highlights moments where musical energy suddenly increases (such as drum hits, kicks, and claps). These peaks represent the rhythmic pulse of the track.",
            "Tempogram Analysis - A tempogram is generated from the onset envelope. The tempogram measures repeating rhythmic patterns over time and reveals the dominant beat periodicities in the song.",
            "Global Tempo Estimation - The strongest rhythmic periodicity is selected from the tempogram. This value is converted into BPM.",
            "Optional Tempo Normalization - Tango Studio can optionally normalize the raw tempo into a musically perceived BPM range. This resolves common half-tempo and double-tempo ambiguities and allows BPM values to match professional DJ software. Normalization is controlled by user preference and can be disabled to expose the raw tempo.",
            "Metadata Storage - The resulting BPM value can be written back into the audio file's metadata using Mutagen. BPM is always stored in its raw form, i.e. not normalized. Once analyzed, BPM is cached inside the file and does not need to be recomputed again."
        ]

        for i, step in enumerate(steps, 1):
            step_label = ctk.CTkLabel(
                self.scrollable_frame,
                text=f"{i}. {step}",
                font=("Segoe UI", 13),
                text_color=self.fg_color,
                fg_color="transparent",
                wraplength=wraplength,
                justify="left"
            )
            step_label.pack(pady=(0, 8), anchor="w", padx=(20, 0))

        # Close button
        close_button = ctk.CTkButton(
            self.scrollable_frame,
            text="Close",
            font=("Segoe UI", 12),
            fg_color=self.btn_bg,
            hover_color=self.theme_manager.palette.get("accent_hover", "#106ebe"),
            text_color=self.btn_fg_color,
            width=80,
            height=32,
            command=self.destroy
        )
        close_button.pack(pady=20)

    def _create_section(self, parent, title, text, wraplength=600):
        """Create a documentation section with title and content."""
        # Section title
        section_title = ctk.CTkLabel(
            parent,
            text=title,
            font=("Segoe UI", 18, "bold"),
            text_color=self.accent_color,
            fg_color="transparent"
        )
        section_title.pack(pady=(15, 8), anchor="w")

        # Section content
        section_label = ctk.CTkLabel(
            parent,
            text=text,
            font=("Segoe UI", 14),
            text_color=self.fg_color,
            fg_color="transparent",
            wraplength=wraplength,
            justify="left"
        )
        section_label.pack(pady=(0, 15), anchor="w")

    def _center_and_show(self):
        """Center the window and show it."""
        self.update_idletasks()
        # Get current geometry to use the size set in __init__
        current_geom = self.geometry()
        # Extract width and height (format is "widthxheight+x+y" or "widthxheight")
        if '+' in current_geom:
            size_part = current_geom.split('+')[0]
        else:
            size_part = current_geom

        if 'x' in size_part:
            width, height = map(int, size_part.split('x'))
        else:
            width, height = 700, 700  # fallback to current defaults

        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.deiconify()
