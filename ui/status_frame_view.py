import io
import os
import platform
import threading
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from audio.bpm import analyze_bpm_worker, save_bpm_worker
from audio.metadata import get_best_artwork, get_display_bpm, get_metadata, metadata_extractor

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

        super().__init__(master, fg_color=initial_bg, bg_color=initial_bg, corner_radius=0)

        self.status_var = tk.StringVar(value="")
        self.meta_var = tk.StringVar(value="")

        self.current_artwork_image = None
        self.current_artwork_photo = None

        self._status_restore_job = None

        self.current_temp_bpm = None
        self.temporary_bpm_files = set()
        self.bpm_button_state = "analyze"

        self._build_widgets(is_dark=is_dark, frame_bg=initial_bg)

        # Register BPM listener to refresh status when BPM is calculated
        metadata_extractor.register_bpm_listener(self._on_bpm_updated)

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
        self.status_bg.pack(fill=tk.X, pady=(3, 0), padx=0, expand=True)

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

        self.status_label = ctk.CTkLabel(
            self.text_frame,
            textvariable=self.status_var,
            anchor="w",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=status_fg,
            bg_color=status_bg,
            justify="left",
        )
        self.status_label.pack(side=tk.TOP, fill=tk.X, pady=(15, 40))

        self.meta_frame = ctk.CTkFrame(self.text_frame, fg_color="transparent")
        self.meta_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 2))

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

        self.bpm_control_frame = ctk.CTkFrame(self.meta_frame, fg_color="transparent")
        self.bpm_control_frame.pack(side=tk.LEFT, padx=(8, 0))
        self.bpm_control_frame.pack_forget()

        self.bpm_buttons_frame = ctk.CTkFrame(self.bpm_control_frame, fg_color="transparent")
        self.bpm_buttons_frame.pack(side=tk.LEFT)

        btn_bg = self.palette.get("button_bg_color", self.palette.get("accent", "#0078d4"))
        btn_fg = self.palette.get("button_fg_color", "#ffffff")
        btn_hover = self.palette.get("button_hover", self.palette.get("accent_hover", "#106ebe"))

        self.btn_bpm = ctk.CTkButton(
            self.bpm_buttons_frame,
            text="Analyze BPM",
            command=self._on_bpm_button_click,
            width=100,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color=btn_bg,
            text_color=btn_fg,
            text_color_disabled=btn_fg,
            hover_color=btn_hover,
        )
        self.btn_bpm.pack(side=tk.LEFT)

    # ------------------------------------------------------------------
    # Public API used by MainWindow
    # ------------------------------------------------------------------
    def set_temporary_status(self, message, duration=3000):
        """Show a temporary message, then restore now-playing display."""
        self.status_var.set(message)
        self._cancel_restore_job()
        self._status_restore_job = self.after(duration, self.restore_status)

    def schedule_restore(self, delay=3000):
        self._cancel_restore_job()
        self._status_restore_job = self.after(delay, self.restore_status)

    def handle_stop(self):
        self._cancel_restore_job()
        self._clear_status()
        self.current_temp_bpm = None
        try:
            self.bpm_control_frame.pack_forget()
        except Exception:
            pass

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
        bpm = meta.get("bpm")

        self._update_artwork(path)

        if artist:
            self.status_var.set(f"{title} — {artist}")
        else:
            self.status_var.set(f"{title}")

        parts = []
        if duration_s:
            parts.append(f"{int(duration_s)//60:02d}:{int(duration_s)%60:02d}")
        if bitrate:
            parts.append(f"{bitrate} kbps")

        if bpm:
            bpm_str = f" • {get_display_bpm(bpm)} BPM"
        else:
            bpm_str = " • BPM info missing"

        self.meta_var.set(" • ".join(parts) + bpm_str)

        # BPM controls visibility
        if bpm is None:
            self._show_bpm_controls(state="analyze", text="Analyze BPM")
            self.current_temp_bpm = None
        else:
            if path in self.temporary_bpm_files:
                self._show_bpm_controls(state="save", text="Save BPM")
                cached = metadata_extractor._cache.get(path, {})
                self.current_temp_bpm = cached.get("bpm")
            else:
                self.bpm_control_frame.pack_forget()
                self.current_temp_bpm = None

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
        self.status_label.configure(text_color=status_fg, bg_color=status_bg)
        self.meta_label.configure(text_color=meta_fg, bg_color=status_bg)
        self.artwork_label.configure(text_color=meta_fg)

        btn_bg = self.palette.get("button_bg_color", self.palette.get("accent", "#0078d4"))
        btn_fg = self.palette.get("button_fg_color", "#ffffff")
        btn_hover = self.palette.get("button_hover", self.palette.get("accent_hover", "#106ebe"))
        self.btn_bpm.configure(
            fg_color=btn_bg,
            text_color=btn_fg,
            hover_color=btn_hover,
            text_color_disabled=btn_fg,
        )

        # Refresh artwork to update placeholder color if needed
        if self.state.current_index is not None and 0 <= self.state.current_index < len(self.state.playlist):
            self._update_artwork(self.state.playlist[self.state.current_index])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _clear_status(self) -> None:
        self.status_var.set("")
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

    def _show_bpm_controls(self, state: str, text: str) -> None:
        self.bpm_control_frame.pack(side=tk.LEFT, padx=(8, 0))
        self.bpm_button_state = state
        self.btn_bpm.configure(state="normal", text=text)

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
    # BPM logic
    # ------------------------------------------------------------------
    def _on_bpm_button_click(self) -> None:
        try:
            idx = self.state.current_index
            if idx is None or idx >= len(self.state.playlist):
                return

            filepath = self.state.playlist[idx]

            if self.bpm_button_state == "analyze":
                self.bpm_button_state = "analyzing"
                self.btn_bpm.configure(state="disabled", text="Analyzing...")
                thread = threading.Thread(target=self._analyze_bpm_worker, args=(filepath,), daemon=True)
                thread.start()
            elif self.bpm_button_state == "save":
                if self.current_temp_bpm is not None:
                    self.bpm_button_state = "saving"
                    self.btn_bpm.configure(state="disabled", text="Saving...")
                    thread = threading.Thread(
                        target=self._save_bpm_worker,
                        args=(filepath, self.current_temp_bpm),
                        daemon=True,
                    )
                    thread.start()
        except Exception as exc:
            logger.error("Error in BPM button click: %s", exc)
            self._reset_bpm_button_to_analyze()

    def _analyze_bpm_worker(self, filepath: str) -> None:
        # Use self as the root for after calls
        analyze_bpm_worker(filepath, self, self._on_bpm_analysis_complete)

    def _on_bpm_analysis_complete(self, filepath, bpm_value):
        try:
            if bpm_value is not None:
                self.current_temp_bpm = bpm_value
                self.temporary_bpm_files.add(filepath)
                metadata_extractor._cache.setdefault(filepath, {})["bpm"] = bpm_value
                self._update_meta_with_temp_bpm()
                self._show_bpm_controls(state="save", text="Save BPM")
            else:
                self._reset_bpm_button_to_analyze()
                self.set_temporary_status("BPM analysis failed")
        except Exception as exc:
            logger.error("Error handling BPM analysis completion: %s", exc)
            self._reset_bpm_button_to_analyze()

    def _reset_bpm_button_to_analyze(self) -> None:
        self.bpm_button_state = "analyze"
        self.btn_bpm.configure(state="normal", text="Analyze BPM")
        self.current_temp_bpm = None

    def _update_meta_with_temp_bpm(self) -> None:
        try:
            idx = self.state.current_index
            if idx is None or idx >= len(self.state.playlist):
                return

            path = self.state.playlist[idx]
            meta = get_metadata(path)

            duration_s = meta.get("duration_s")
            bitrate = meta.get("bitrate")
            bpm = meta.get("bpm")

            parts = []
            if duration_s:
                parts.append(f"{int(duration_s)//60:02d}:{int(duration_s)%60:02d}")
            if bitrate:
                parts.append(f"{bitrate} kbps")
            if bpm:
                bpm_str = f" • {get_display_bpm(bpm)} BPM"
            else:
                bpm_str = " • BPM info missing"

            self.meta_var.set(" • ".join(parts) + bpm_str)
            metadata_extractor._notify_bpm_listeners(path)
        except Exception as exc:
            logger.error("Error updating meta with temporary BPM: %s", exc)

    def _save_bpm_worker(self, filepath: str, bpm_value: float) -> None:
        # Use self as the root for after calls
        save_bpm_worker(filepath, bpm_value, self, self._on_bpm_save_complete)

    def _on_bpm_save_complete(self, filepath: str, success: bool) -> None:
        try:
            if success:
                self.current_temp_bpm = None
                self.temporary_bpm_files.discard(filepath)
                self._reset_bpm_button_to_analyze()
                self.set_temporary_status("BPM saved successfully")
            else:
                self.set_temporary_status("Failed to save BPM")
        except Exception as exc:
            logger.error("Error handling BPM save completion: %s", exc)
            self.set_temporary_status("Error saving BPM")

    def _on_bpm_updated(self, filepath: str) -> None:
        try:
            idx = self.state.current_index
            if idx is not None and idx < len(self.state.playlist):
                current_path = self.state.playlist[idx]
                if current_path == filepath:
                    self._update_meta_with_temp_bpm()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def destroy(self):
        self._cancel_restore_job()
        try:
            metadata_extractor.unregister_bpm_listener(self._on_bpm_updated)
        except Exception:
            pass
        super().destroy()
