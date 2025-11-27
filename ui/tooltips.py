import tkinter as tk
from typing import Callable

class TooltipManager:
    def __init__(self, root, palette):
        self.root = root
        self.palette = palette
        self._tipwindow = None
        self._id = None
        self._label = None
        self._show_after = 600  # ms

    def attach(self, widget: tk.Widget, text_func: Callable[[], str]):
        def enter(event):
            self._schedule_show(widget, text_func)
        def leave(event):
            self._cancel_and_hide()
        widget.bind("<Enter>", enter, add="+")
        widget.bind("<Leave>", leave, add="+")
        widget.bind("<Motion>", enter, add="+")

    def _schedule_show(self, widget, text_func):
        self._cancel_and_hide()
        self._id = self.root.after(self._show_after, lambda: self._show(widget, text_func()))

    def _cancel_and_hide(self):
        if self._id:
            try:
                self.root.after_cancel(self._id)
            except Exception:
                pass
            self._id = None
        if self._tipwindow:
            try:
                self._tipwindow.destroy()
            except Exception:
                pass
            self._tipwindow = None

    def _show(self, widget, text):
        if not text:
            return
        # build tooltip window
        tw = tk.Toplevel(self.root)
        tw.wm_overrideredirect(True)
        # style
        bg = self.palette.get("tooltip_bg", "#ffffe0")
        label = tk.Label(tw, text=text, justify="left", relief="solid", borderwidth=1,
                         font=("Segoe UI", 9), bg=bg, fg=self.palette.get("fg", "#000"))
        label.pack(ipadx=6, ipady=3)
        # position near widget
        try:
            x = widget.winfo_rootx() + 20
            y = widget.winfo_rooty() + widget.winfo_height()
            tw.wm_geometry(f"+{x}+{y}")
        except Exception:
            pass
        self._tipwindow = tw
        self._label = label
