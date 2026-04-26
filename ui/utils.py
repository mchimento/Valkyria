import sys
import tkinter as tk


def apply_rounded_corners(window):
    """Ask the Windows 11 DWM compositor to round the window corners.

    Uses DWMWA_WINDOW_CORNER_PREFERENCE (attribute 33) introduced in
    Windows 11.  Safe no-op on older Windows and non-Windows platforms.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2  # standard rounded corners
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            hwnd = window.winfo_id()
        value = ctypes.c_int(DWMWCP_ROUND)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
    except Exception:
        pass


def apply_theme_titlebar(window, palette):
    """Color the OS title bar to match the application theme.

    Uses DWMWA_CAPTION_COLOR (35) and DWMWA_TEXT_COLOR (36), introduced in
    Windows 11 build 22000.  Silent no-op on older Windows and non-Windows.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        def _hex_to_colorref(hex_color):
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return r | (g << 8) | (b << 16)

        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            hwnd = window.winfo_id()

        DWMWA_CAPTION_COLOR = 35
        DWMWA_TEXT_COLOR    = 36

        caption_color = _hex_to_colorref(palette.get("menubar_bg", "#323233"))
        text_color    = _hex_to_colorref(palette.get("menubar_text", "#CCCCCC"))

        for attr, value in ((DWMWA_CAPTION_COLOR, caption_color),
                            (DWMWA_TEXT_COLOR, text_color)):
            c_value = ctypes.c_int(value)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(c_value), ctypes.sizeof(c_value)
            )
    except Exception:
        pass


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
