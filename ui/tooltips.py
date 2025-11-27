import logging
import tkinter as tk
from typing import Callable, Optional, Dict, Any

logger = logging.getLogger(__name__)

class TooltipManager:
    def __init__(self, root: tk.Tk, palette: Dict[str, Any]) -> None:
        self.root = root
        self.palette = palette
        self._tipwindow: Optional[tk.Toplevel] = None
        self._id: Optional[str] = None
        self._label: Optional[tk.Label] = None
        self._show_after = 600  # ms

    def attach(self, widget: tk.Widget, text_func: Callable[[], str]) -> None:
        """Attach a tooltip to a widget."""
        def enter(event):
            self._schedule_show(widget, text_func)
        def leave(event):
            self._cancel_and_hide()
        widget.bind("<Enter>", enter, add="+")
        widget.bind("<Leave>", leave, add="+")
        widget.bind("<Motion>", enter, add="+")

    def _schedule_show(self, widget: tk.Widget, text_func: Callable[[], str]) -> None:
        """Schedule showing the tooltip after a delay."""
        self._cancel_and_hide()
        self._id = self.root.after(self._show_after, lambda: self._show(widget, text_func()))

    def _cancel_and_hide(self) -> None:
        """Cancel scheduled tooltip and hide any visible tooltip."""
        if self._id:
            try:
                self.root.after_cancel(self._id)
            except Exception:
                logger.warning("Failed to cancel tooltip timer", exc_info=True)
            self._id = None
        if self._tipwindow:
            try:
                self._tipwindow.destroy()
            except Exception:
                logger.warning("Failed to destroy tooltip window", exc_info=True)
            self._tipwindow = None

    def _show(self, widget: tk.Widget, text: str) -> None:
        """Show the tooltip near the widget."""
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
            logger.warning("Failed to position tooltip", exc_info=True)
        self._tipwindow = tw
        self._label = label
