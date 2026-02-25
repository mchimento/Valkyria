"""
Album Booklet Viewer Window
Displays booklet/liner-note images extracted from audio file metadata.
"""
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from PIL import Image, ImageTk
import io
from audio.metadata import get_booklet_images


class BookletViewer(tk.Toplevel):
    """Window for viewing booklet/liner-note images from audio files."""

    def __init__(self, parent, filepath, theme):
        """
        Initialize the booklet viewer.

        Args:
            parent: Parent window
            filepath (str): Path to the audio file
            theme: Theme manager instance
        """
        super().__init__(parent)
        self.filepath = filepath
        self.theme = theme
        self.images = []
        self.current_index = 0
        self.photo_images = []  # Keep references to prevent garbage collection

        # Get theme colors
        self._setup_theme_colors()

        # Configure window
        self.title("Album Booklet Viewer")
        self.geometry("800x600")
        self.resizable(True, True)
        self.configure(bg=self.frame_bg)

        # Extract images
        self.images = get_booklet_images(filepath)

        # Setup UI
        self._setup_ui()

        # Load first image or show message
        self._load_current_image()

    def _setup_theme_colors(self):
        """Setup theme colors for buttons."""
        palette = self.theme.palette

        # Get button colors from palette
        self.btn_bg = palette["button_bg_color"]
        self.btn_fg = palette["button_fg_color"]
        self.btn_hover = palette["button_hover"]
        self.frame_bg = palette["bg"]
        self.text_fg = palette["fg"]
        self.canvas_bg = palette["tree_bg"]

    def _setup_ui(self):
        """Setup the user interface."""
        # Main frame with grid layout for fixed positioning
        self.main_frame = ctk.CTkFrame(self, fg_color=self.frame_bg)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Configure grid weights - row 0 (image) expands, others fixed
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Image display area - use Canvas for better control
        self.image_frame = ctk.CTkFrame(self.main_frame, fg_color=self.canvas_bg)
        self.image_frame.grid(row=0, column=0, sticky="nsew")

        # Canvas for image display with fixed centering behavior
        self.image_canvas = tk.Canvas(self.image_frame, bg=self.canvas_bg, highlightthickness=0)
        self.image_canvas.pack(fill=tk.BOTH, expand=True)

        # Bind canvas resize to recenter image
        self.image_canvas.bind("<Configure>", self._on_canvas_resize)

        # Navigation frame - fixed at bottom
        self.nav_frame = ctk.CTkFrame(self.main_frame, fg_color=self.frame_bg)
        self.nav_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))

        # Button styling
        btn_font = ("Segoe UI", 14)
        btn_height = 36

        # Previous button - styled like control buttons
        self.prev_button = ctk.CTkButton(
            self.nav_frame,
            text="⏮ Previous",
            command=self._previous_image,
            font=btn_font,
            width=120,
            height=btn_height,
            fg_color=self.btn_bg,
            text_color=self.btn_fg,
            hover_color=self.btn_hover
        )
        self.prev_button.pack(side=tk.LEFT, padx=(10, 5))

        # Image counter - centered with fixed width
        self.counter_label = ctk.CTkLabel(
            self.nav_frame,
            text="",
            width=150,
            text_color=self.text_fg,
            font=("Segoe UI", 14)
        )
        self.counter_label.pack(side=tk.LEFT, expand=True)

        # Next button - styled like control buttons
        self.next_button = ctk.CTkButton(
            self.nav_frame,
            text="Next ⏭",
            command=self._next_image,
            font=btn_font,
            width=120,
            height=btn_height,
            fg_color=self.btn_bg,
            text_color=self.btn_fg,
            hover_color=self.btn_hover
        )
        self.next_button.pack(side=tk.RIGHT, padx=(5, 10))

        # Info frame
        self.info_frame = ctk.CTkFrame(self.main_frame, fg_color=self.frame_bg)
        self.info_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))

        self.info_label = ctk.CTkLabel(
            self.info_frame,
            text="",
            wraplength=750,
            text_color=self.text_fg,
            font=("Segoe UI", 14)
        )
        self.info_label.pack(fill=tk.X)

        # Close button frame
        self.close_frame = ctk.CTkFrame(self.main_frame, fg_color=self.frame_bg)
        self.close_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))

        # Close button - styled like control buttons
        self.close_button = ctk.CTkButton(
            self.close_frame,
            text="Close",
            command=self.destroy,
            font=btn_font,
            width=100,
            height=btn_height,
            fg_color=self.btn_bg,
            text_color=self.btn_fg,
            hover_color=self.btn_hover
        )
        self.close_button.pack(side=tk.RIGHT, padx=(0, 10), pady=(0, 10))

    def _on_canvas_resize(self, event):
        """Handle canvas resize to recenter the current image."""
        if hasattr(self, '_current_photo') and self._current_photo:
            self._display_image_on_canvas()

    def _display_image_on_canvas(self):
        """Display the current photo image centered on the canvas."""
        if not hasattr(self, '_current_photo') or not self._current_photo:
            return

        # Clear canvas
        self.image_canvas.delete("all")

        # Get canvas size
        canvas_width = self.image_canvas.winfo_width()
        canvas_height = self.image_canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            return

        # Center the image
        x = canvas_width // 2
        y = canvas_height // 2

        self.image_canvas.create_image(x, y, image=self._current_photo, anchor="center")

    def _load_current_image(self):
        """Load and display the current image."""
        if not self.images:
            self._show_no_images_message()
            return

        # Get current image data
        image_data, description, image_type = self.images[self.current_index]

        try:
            # Load image
            image = Image.open(io.BytesIO(image_data))

            # Get available canvas size
            canvas_width = self.image_canvas.winfo_width()
            canvas_height = self.image_canvas.winfo_height()

            if canvas_width <= 1 or canvas_height <= 1:
                # Window hasn't been rendered yet, use default size
                canvas_width = 780
                canvas_height = 450

            # Calculate scaling to fit within canvas while maintaining aspect ratio
            img_width, img_height = image.size
            scale_x = canvas_width / img_width
            scale_y = canvas_height / img_height
            scale = min(scale_x, scale_y, 1.0)  # Don't upscale

            if scale < 1.0:
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(image)

            # Keep reference to prevent garbage collection
            self._current_photo = photo
            self.photo_images.append(photo)

            # Display on canvas
            self._display_image_on_canvas()

            # Update info
            self.info_label.configure(text=f"Type: {image_type} | Description: {description}")

            # Update counter
            self.counter_label.configure(text=f"Image {self.current_index + 1} of {len(self.images)}")

            # Update navigation buttons
            self.prev_button.configure(state="normal" if self.current_index > 0 else "disabled")
            self.next_button.configure(state="normal" if self.current_index < len(self.images) - 1 else "disabled")

        except Exception as e:
            self.image_canvas.delete("all")
            self.image_canvas.create_text(
                self.image_canvas.winfo_width() // 2 or 390,
                self.image_canvas.winfo_height() // 2 or 225,
                text="Error loading image: image data is corrupted",
                fill="white",
                anchor="center"
            )
            self._current_photo = None
            self.info_label.configure(text="")
            self.counter_label.configure(text="")

    def _show_no_images_message(self):
        """Show message when no booklet images are available."""
        self.image_canvas.delete("all")
        # Schedule the text creation after canvas is sized
        self.after(10, self._draw_no_images_text)
        self._current_photo = None
        self.info_label.configure(text="")
        self.counter_label.configure(text="")
        self.prev_button.configure(state="disabled")
        self.next_button.configure(state="disabled")

    def _draw_no_images_text(self):
        """Draw the 'no images' message on the canvas."""
        canvas_width = self.image_canvas.winfo_width()
        canvas_height = self.image_canvas.winfo_height()
        if canvas_width > 1 and canvas_height > 1:
            self.image_canvas.create_text(
                canvas_width // 2,
                canvas_height // 2,
                text="No booklet images available for this track.",
                fill="white",
                anchor="center",
                font=("Segoe UI", 12)
            )

    def _previous_image(self):
        """Show the previous image."""
        if self.current_index > 0:
            self.current_index -= 1
            self._load_current_image()

    def _next_image(self):
        """Show the next image."""
        if self.current_index < len(self.images) - 1:
            self.current_index += 1
            self._load_current_image()

    def update_theme(self):
        """Update theme colors when theme changes."""
        # Re-read colors from palette directly like playlist_view does
        palette = self.theme.palette
        self.btn_bg = palette["button_bg_color"]
        self.btn_fg = palette["button_fg_color"]
        self.btn_hover = palette["button_hover"]
        self.frame_bg = palette["bg"]
        self.text_fg = palette["fg"]
        self.canvas_bg = palette["tree_bg"]

        # Update window background
        self.configure(bg=self.frame_bg)

        # Update main frame
        self.main_frame.configure(fg_color=self.frame_bg)

        # Update nav, info, close frames
        self.nav_frame.configure(fg_color=self.frame_bg)
        self.info_frame.configure(fg_color=self.frame_bg)
        self.close_frame.configure(fg_color=self.frame_bg)

        # Update image frame and canvas
        self.image_frame.configure(fg_color=self.canvas_bg)
        self.image_canvas.configure(bg=self.canvas_bg)

        # Update buttons
        self.prev_button.configure(
            fg_color=self.btn_bg,
            text_color=self.btn_fg,
            hover_color=self.btn_hover
        )
        self.next_button.configure(
            fg_color=self.btn_bg,
            text_color=self.btn_fg,
            hover_color=self.btn_hover
        )
        self.close_button.configure(
            fg_color=self.btn_bg,
            text_color=self.btn_fg,
            hover_color=self.btn_hover
        )

        # Update labels
        self.counter_label.configure(text_color=self.text_fg)
        self.info_label.configure(text_color=self.text_fg)

    def show(self):
        """Display the viewer window."""
        self.deiconify()
        self.lift()
        self.focus_force()

        # Bind window close event
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        # Bind escape key to close
        self.bind('<Escape>', lambda e: self.destroy())

        return self
