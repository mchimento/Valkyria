import tkinter as tk
import os
from audio.metadata import get_display_title

def center_window(window, parent=None):
    """
    Center a window on the screen or relative to a parent window.

    Args:
        window: The window (Toplevel or Tk) to center.
        parent: Optional parent window to center relative to.
                If None, centers on screen.
    """
    window.update_idletasks()

    width = window.winfo_width()
    height = window.winfo_height()

    if parent:
        # Center relative to parent
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()

        x = parent_x + (parent_width // 2) - (width // 2)
        y = parent_y + (parent_height // 2) - (height // 2)
    else:
        # Center on screen
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

    # Ensure x and y are not negative
    x = max(0, x)
    y = max(0, y)

    window.geometry(f"+{x}+{y}")
