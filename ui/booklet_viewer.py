"""
Album Booklet Viewer Window
Displays booklet/liner-note images extracted from audio file metadata.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import io
from audio.metadata import get_booklet_images


class BookletViewer:
    """Window for viewing booklet/liner-note images from audio files."""
    
    def __init__(self, parent, filepath):
        """
        Initialize the booklet viewer.
        
        Args:
            parent: Parent window
            filepath (str): Path to the audio file
        """
        self.parent = parent
        self.filepath = filepath
        self.images = []
        self.current_index = 0
        self.photo_images = []  # Keep references to prevent garbage collection
        
        # Create the window
        self.window = tk.Toplevel(parent)
        self.window.title("Album Booklet Viewer")
        self.window.geometry("800x600")
        self.window.resizable(True, True)
        
        # Extract images
        self.images = get_booklet_images(filepath)
        
        # Setup UI
        self._setup_ui()
        
        # Load first image or show message
        self._load_current_image()
    
    def _setup_ui(self):
        """Setup the user interface."""
        # Main frame
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Image display area
        self.image_frame = ttk.Frame(main_frame)
        self.image_frame.pack(fill=tk.BOTH, expand=True)
        
        self.image_label = ttk.Label(self.image_frame)
        self.image_label.pack(expand=True)
        
        # Navigation frame
        nav_frame = ttk.Frame(main_frame)
        nav_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Previous button
        self.prev_button = ttk.Button(nav_frame, text="← Previous", command=self._previous_image)
        self.prev_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Image counter
        self.counter_label = ttk.Label(nav_frame, text="")
        self.counter_label.pack(side=tk.LEFT, expand=True)
        
        # Next button
        self.next_button = ttk.Button(nav_frame, text="Next →", command=self._next_image)
        self.next_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Info frame
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.info_label = ttk.Label(info_frame, text="", wraplength=750)
        self.info_label.pack(fill=tk.X)
        
        # Close button
        close_frame = ttk.Frame(main_frame)
        close_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(close_frame, text="Close", command=self.window.destroy).pack(side=tk.RIGHT)
    
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
            
            # Resize image to fit window while maintaining aspect ratio
            window_width = self.image_frame.winfo_width()
            window_height = self.image_frame.winfo_height()
            
            if window_width <= 1 or window_height <= 1:
                # Window hasn't been rendered yet, use default size
                window_width = 780
                window_height = 400
            
            # Calculate scaling
            img_width, img_height = image.size
            scale_x = window_width / img_width
            scale_y = window_height / img_height
            scale = min(scale_x, scale_y, 1.0)  # Don't upscale
            
            if scale < 1.0:
                new_width = int(img_width * scale)
                new_height = int(img_height * scale)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(image)
            
            # Keep reference to prevent garbage collection
            self.photo_images.append(photo)
            
            # Update display
            self.image_label.configure(image=photo)
            
            # Update info
            self.info_label.configure(text=f"Type: {image_type} | Description: {description}")
            
            # Update counter
            self.counter_label.configure(text=f"Image {self.current_index + 1} of {len(self.images)}")
            
            # Update navigation buttons
            self.prev_button.configure(state=tk.NORMAL if self.current_index > 0 else tk.DISABLED)
            self.next_button.configure(state=tk.NORMAL if self.current_index < len(self.images) - 1 else tk.DISABLED)
            
        except Exception as e:
            self.image_label.configure(image="", text=f"Error loading image: {str(e)}")
            self.info_label.configure(text="")
            self.counter_label.configure(text="")
    
    def _show_no_images_message(self):
        """Show message when no booklet images are available."""
        self.image_label.configure(image="", text="No booklet images available for this track.")
        self.info_label.configure(text="")
        self.counter_label.configure(text="")
        self.prev_button.configure(state=tk.DISABLED)
        self.next_button.configure(state=tk.DISABLED)
    
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
    
    def show(self):
        """Display the viewer window."""
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
        
        # Bind window close event
        self.window.protocol("WM_DELETE_WINDOW", self.window.destroy)
        
        # Bind escape key to close
        self.window.bind('<Escape>', lambda e: self.window.destroy())
        
        return self.window
