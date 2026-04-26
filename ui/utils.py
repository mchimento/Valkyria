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


def make_window_independent(window):
    """Sever the Win32 owner relationship between a Toplevel and its Tk root.

    On Windows, withdrawing the owner (root) silently hides all owned
    Toplevels.  Clearing GWL_HWNDPARENT on the outer HWND makes the window
    fully independent so root.withdraw() leaves it unaffected.
    Also applies WS_EX_APPWINDOW so it gets its own taskbar button.
    Must be called while the window is still hidden (before first deiconify).
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        GWL_HWNDPARENT   = -8
        GWL_EXSTYLE      = -20
        WS_EX_APPWINDOW  = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080

        outer = ctypes.windll.user32.GetParent(window.winfo_id())
        if not outer:
            outer = window.winfo_id()

        ctypes.windll.user32.SetWindowLongW(outer, GWL_HWNDPARENT, 0)

        style = ctypes.windll.user32.GetWindowLongW(outer, GWL_EXSTYLE)
        style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(outer, GWL_EXSTYLE, style)
    except Exception:
        pass


def force_taskbar_presence(window, ico_path=None):
    """Make a frameless (overrideredirect) window appear in the Windows taskbar.

    overrideredirect(True) causes Windows to apply WS_EX_TOOLWINDOW, which hides
    the window from the taskbar. This swaps that for WS_EX_APPWINDOW, then
    briefly withdraws and deiconifies so the shell picks up the new style.

    ico_path: optional path to a .ico file. When provided, the icon is applied
    after deiconify so Tkinter's reshow does not reset it to the Python default.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        GWL_EXSTYLE      = -20
        WS_EX_APPWINDOW  = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080

        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            hwnd = window.winfo_id()

        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

        def _restore():
            window.deiconify()
            if ico_path:
                set_win32_icon(window, ico_path)

        window.withdraw()
        window.after(10, _restore)
    except Exception:
        pass


def set_win32_icon(window, ico_path):
    """Set the window icon via Win32 API so the taskbar button shows the correct image.

    iconphoto() targets the Tk child HWND; the taskbar button is owned by the
    parent HWND.  SendMessage(WM_SETICON) on the parent HWND is the only
    reliable way to update the taskbar and Alt+Tab thumbnail icon.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from pathlib import Path

        if not Path(ico_path).exists():
            return

        IMAGE_ICON     = 1
        LR_LOADFROMFILE = 0x0010
        LR_DEFAULTSIZE  = 0x0040
        WM_SETICON     = 0x0080
        ICON_SMALL     = 0
        ICON_BIG       = 1

        hicon = ctypes.windll.user32.LoadImageW(
            None, str(ico_path), IMAGE_ICON, 0, 0,
            LR_LOADFROMFILE | LR_DEFAULTSIZE,
        )
        if not hicon:
            return

        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        if not hwnd:
            hwnd = window.winfo_id()

        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG,   hicon)
        ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
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
