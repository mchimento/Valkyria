import io
import os
import platform
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from audio.metadata import get_best_artwork, get_metadata

import logging

logger = logging.getLogger(__name__)


class StatusFrameView(ctk.CTkFrame):
    """Encapsulates the status bar UI"""
    def __init__(self, master, state, theme_manager, settings):
        self.state = state
        self.theme = theme_manager
        self.settings = settings
        self.palette = theme_manager.palette

        is_dark = settings.theme.lower() == "dark"
        initial_bg = self.palette.get("bg", "#1E1E1E" if is_dark else "#FAFAFA")

        super().__init__(master, fg_color=initial_bg, bg_color=initial_bg, corner_radius=0, height=150)

        self.title_var = tk.StringVar(value="")
        self.artist_var = tk.StringVar(value="")
        self.meta_var = tk.StringVar(value="")

        self.current_artwork_image = None
        self.current_artwork_photo = None

        self._status_restore_job = None

        self._build_widgets(is_dark=is_dark, frame_bg=initial_bg)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_widgets(self, is_dark, frame_bg):
        status_bg = self.palette.get("status_bg", "#E8E8E8" if not is_dark else "#2A2A2A")
        status_border = self.palette.get("status_border", "#D0D0D0" if not is_dark else "#3E3E3E")
        status_fg = self.palette.get("status_fg", "#202020" if not is_dark else "#FFFFFF")
        meta_fg = self.palette.get("status_meta_fg", "#505050" if not is_dark else "#E0E0E0")

        self.status_bg = ctk.CTkFrame(
            self,
            corner_radius=6,
            fg_color=status_bg,
            bg_color=frame_bg,
            border_color=status_border,
            border_width=1,
        )
        self.status_bg.pack(fill=tk.X, pady=(3, 0), padx=0)

        self.status_content = ctk.CTkFrame(self.status_bg, fg_color="transparent", height=120)
        self.status_content.pack(fill=tk.X, padx=12, pady=10)
        self.status_content.pack_propagate(False)

        self.artwork_frame = ctk.CTkFrame(self.status_content, fg_color="transparent", width=100, height=100)
        self.artwork_frame.pack(side=tk.LEFT, padx=(0, 12))
        self.artwork_frame.pack_propagate(False)

        self.artwork_label = ctk.CTkLabel(
            self.artwork_frame,
            text="",
            font=ctk.CTkFont(size=40),
            text_color=meta_fg,
            fg_color="transparent",
            anchor="center",
        )
        self.artwork_label.pack(side=tk.TOP, fill=tk.BOTH)

        self.text_frame = ctk.CTkFrame(self.status_content, fg_color="transparent")
        self.text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=(0, 0))

        self.title_label = ctk.CTkLabel(
            self.text_frame,
            textvariable=self.title_var,
            anchor="sw",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=status_fg,
            bg_color=status_bg,
            justify="left",
        )
        self.title_label.pack(side=tk.TOP, fill=tk.X, pady=(15, 5))

        self.artist_label = ctk.CTkLabel(
            self.text_frame,
            textvariable=self.artist_var,
            anchor="nw",
            font=ctk.CTkFont(size=15),
            text_color=status_fg,
            bg_color=status_bg,
            justify="left",
        )
        self.artist_label.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        self.meta_frame = ctk.CTkFrame(self.text_frame, fg_color="transparent")
        self.meta_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 0))

        self.meta_label = ctk.CTkLabel(
            self.meta_frame,
            textvariable=self.meta_var,
            anchor="w",
            font=ctk.CTkFont(size=14),
            text_color=meta_fg,
            bg_color=status_bg,
            justify="left",
            height=1,
        )
        self.meta_label.pack(side=tk.LEFT, fill=tk.X)

    # ------------------------------------------------------------------
    # Public API used by MainWindow
    # ------------------------------------------------------------------
    def set_temporary_status(self, message, duration=3000):
        """Show a temporary message, then restore now-playing display."""
        self.title_var.set(message)
        self._cancel_restore_job()
        self._status_restore_job = self.after(duration, self.restore_status)

    def schedule_restore(self, delay=3000):
        self._cancel_restore_job()
        self._status_restore_job = self.after(delay, self.restore_status)

    def handle_stop(self):
        self._cancel_restore_job()
        self._clear_status()

    def restore_status(self):
        """Restore playing status and populate metadata line."""
        self._cancel_restore_job()

        idx = self.state.current_index
        if idx is None or idx >= len(self.state.playlist):
            self._clear_status()
            return

        path = self.state.playlist[idx]
        name = os.path.basename(path)

        # Ensure artwork frame is visible
        try:
            self.artwork_frame.pack(side=tk.LEFT, padx=(0, 12), before=self.text_frame)
        except Exception:
            pass

        meta = get_metadata(path)

        title = meta.get("title") or name
        artist = meta.get("artist")
        duration_s = meta.get("duration_s")
        bitrate = meta.get("bitrate")

        self._update_artwork(path)

        self.title_var.set(title)
        self.artist_var.set(artist or "")

        parts = []
        if duration_s:
            parts.append(f"{int(duration_s)//60:02d}:{int(duration_s)%60:02d}")
        if bitrate:
            parts.append(f"{bitrate} kbps")

        self.meta_var.set(" • ".join(parts))

    def update_theme(self) -> None:
        self.palette = self.theme.palette
        is_dark = self.settings.theme.lower() == "dark"
        frame_bg = self.palette.get("bg", "#1E1E1E" if is_dark else "#FAFAFA")

        status_bg = self.palette.get("status_bg", "#E8E8E8" if not is_dark else "#2A2A2A")
        status_border = self.palette.get("status_border", "#D0D0D0" if not is_dark else "#3E3E3E")
        status_fg = self.palette.get("status_fg", "#202020" if not is_dark else "#FFFFFF")
        meta_fg = self.palette.get("status_meta_fg", "#505050" if not is_dark else "#E0E0E0")

        self.configure(fg_color=frame_bg, bg_color=frame_bg)
        self.status_bg.configure(fg_color=status_bg, bg_color=frame_bg, border_color=status_border)
        self.title_label.configure(text_color=status_fg, bg_color=status_bg)
        self.artist_label.configure(text_color=status_fg, bg_color=status_bg)
        self.meta_label.configure(text_color=meta_fg, bg_color=status_bg)
        self.artwork_label.configure(text_color=meta_fg)

        # Refresh artwork to update placeholder color if needed
        if self.state.current_index is not None and 0 <= self.state.current_index < len(self.state.playlist):
            self._update_artwork(self.state.playlist[self.state.current_index])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _clear_status(self) -> None:
        self.title_var.set("")
        self.artist_var.set("")
        self.meta_var.set("")
        self.artwork_label.configure(image=None)
        self.artwork_label.image = None
        try:
            self.artwork_frame.pack_forget()
        except Exception:
            pass

    def _cancel_restore_job(self) -> None:
        if self._status_restore_job is not None:
            try:
                self.after_cancel(self._status_restore_job)
            except ValueError:
                pass
            self._status_restore_job = None

    def _create_placeholder_image(self):
        placeholder_image = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
        draw = ImageDraw.Draw(placeholder_image)

        text_color = self.palette.get("status_meta_fg", "#E0E0E0")
        system = platform.system().lower()
        font = None

        if system == "windows":
            font_paths = [
                r"C:\\Windows\\Fonts\\seguisym.ttf",
                r"C:\\Windows\\Fonts\\arial.ttf",
                r"C:\\Windows\\Fonts\\tahoma.ttf",
            ]
        elif system == "darwin":
            font_paths = [
                "/System/Library/Fonts/Apple Symbols.ttf",
                "/Library/Fonts/Arial.ttf",
                "/System/Library/Fonts/Arial.ttf",
            ]
        else:
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/TTF/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            ]

        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, 48)
                break
            except (OSError, IOError):
                continue

        if font is None:
            for font_name in ["Arial", "Helvetica", "DejaVu Sans", "Liberation Sans", "FreeSans"]:
                try:
                    font = ImageFont.truetype(font_name, 48)
                    break
                except (OSError, IOError):
                    continue

        if font is None:
            font = ImageFont.load_default()

        draw.text((50, 45), "♫", fill=text_color, font=font, anchor="mm")
        ctk_image = ctk.CTkImage(placeholder_image, size=(100, 100))
        return ctk_image, placeholder_image

    def _update_artwork(self, filepath: str) -> None:
        try:
            artwork_data = get_best_artwork(filepath)
            if artwork_data:
                image = Image.open(io.BytesIO(artwork_data))
                image = image.resize((100, 100), Image.Resampling.LANCZOS)
                ctk_image = ctk.CTkImage(image, size=(100, 100))
            else:
                ctk_image, image = self._create_placeholder_image()
        except Exception:
            ctk_image, image = self._create_placeholder_image()

        self.artwork_label.configure(image=ctk_image, text="")
        self.artwork_label.image = ctk_image
        self.current_artwork_photo = ctk_image
        self.current_artwork_image = image

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def destroy(self):
        self._cancel_restore_job()
        super().destroy()
