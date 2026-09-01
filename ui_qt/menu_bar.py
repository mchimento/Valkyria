"""
Data-driven menu bar built on native QMenuBar/QMenu/QAction, plus the
window chrome (min/max/close) and a draggable spacer (startSystemMove()).

add_menu(label, items) builds a menu from a list of item dicts:
    {"label": str, "command": Callable, "state": "normal"|"disabled",
     "accelerator": str, "separator": True, "submenu": [items...],
     "checkbutton": True, "checked": bool,
     "radiobutton": True, "group": str, "value": Any, "checked": bool}
Checkbuttons/radiobuttons carry a plain initial "checked" bool, or a
"group" name (one QActionGroup per group per menu) for radio items.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QHBoxLayout, QMenu, QMenuBar, QPushButton, QSizePolicy, QWidget

logger = logging.getLogger(__name__)


class CustomMenuBarQt(QWidget):
    def __init__(self, parent: QWidget, palette: dict, parent_window: Optional[QWidget] = None):
        super().__init__(parent)
        self.palette = palette
        self.parent_window = parent_window if parent_window is not None else parent

        self.setObjectName("MenuBarContainer")
        # Without this, the area behind the transparent min/max/close
        # buttons and drag spacer falls through to the window's base bg
        # instead of menubar_bg.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._menubar = QMenuBar(self)
        self._menubar.setNativeMenuBar(False)
        layout.addWidget(self._menubar)

        self._drag_spacer = _DragSpacer(self, self.parent_window)
        layout.addWidget(self._drag_spacer, 1)

        self._menus: Dict[str, QMenu] = {}
        self._btn_min: Optional[QPushButton] = None
        self._btn_max: Optional[QPushButton] = None
        self._btn_close: Optional[QPushButton] = None

    # ---------- menu content ----------

    def add_menu(self, label: str, items: List[Dict[str, Any]]) -> QMenu:
        menu = self._menubar.addMenu(label)
        self._populate_menu(menu, items)
        self._menus[label] = menu
        return menu

    def _populate_menu(self, menu: QMenu, items: List[Dict[str, Any]]) -> None:
        groups: Dict[str, QActionGroup] = {}

        for item in items:
            if item.get("separator"):
                menu.addSeparator()
                continue

            label = item.get("label", "")

            if item.get("submenu") is not None:
                submenu = menu.addMenu(label)
                self._populate_menu(submenu, item["submenu"])
                continue

            action = QAction(label, menu)
            command: Optional[Callable[[], None]] = item.get("command")
            accelerator = item.get("accelerator")
            if accelerator:
                action.setShortcut(QKeySequence(accelerator))
            if item.get("state") == "disabled":
                action.setEnabled(False)

            if item.get("checkbutton"):
                action.setCheckable(True)
                action.setChecked(bool(item.get("checked", False)))
            elif item.get("radiobutton"):
                action.setCheckable(True)
                action.setChecked(bool(item.get("checked", False)))
                group_name = item.get("group", label)
                group = groups.setdefault(group_name, QActionGroup(menu))
                group.addAction(action)

            if command is not None:
                action.triggered.connect(lambda checked=False, cmd=command: self._run(cmd))
            else:
                action.triggered.connect(lambda checked=False, lbl=label: self._run_stub(lbl))

            menu.addAction(action)

    def _run(self, command: Callable[[], None]) -> None:
        try:
            command()
        except Exception:
            logger.exception("Menu command failed")

    def _run_stub(self, label: str) -> None:
        logger.info("[ui_qt stub] menu action %r has no command wired up yet", label)

    # ---------- window controls ----------

    def setup_window_controls(self, close_callback: Callable[[], None], show_maximize: bool = True) -> None:
        self._btn_min = QPushButton("−", self)
        self._btn_min.setFixedSize(46, 30)
        self._btn_min.clicked.connect(self._minimize)
        self._menubar_layout().addWidget(self._btn_min)

        if show_maximize:
            self._btn_max = QPushButton("□", self)
            self._btn_max.setFixedSize(46, 30)
            self._btn_max.clicked.connect(self._toggle_maximize)
            self._menubar_layout().addWidget(self._btn_max)

        self._btn_close = QPushButton("✕", self)
        self._btn_close.setObjectName("WinBtnClose")
        self._btn_close.setFixedSize(46, 30)
        self._btn_close.clicked.connect(close_callback)
        self._menubar_layout().addWidget(self._btn_close)

    def _menubar_layout(self) -> QHBoxLayout:
        return self.layout()

    def _minimize(self) -> None:
        if self.parent_window is not None:
            self.parent_window.showMinimized()

    def _toggle_maximize(self) -> None:
        if self.parent_window is None:
            return
        if self.parent_window.isMaximized():
            self.parent_window.showNormal()
        else:
            self.parent_window.showMaximized()
        self.sync_maximize_button()

    def sync_maximize_button(self) -> None:
        if self._btn_max is not None and self.parent_window is not None:
            self._btn_max.setText("❑" if self.parent_window.isMaximized() else "□")


class _DragSpacer(QWidget):
    """Fills the gap between menus and window controls; drag-to-move + double-click maximize."""

    def __init__(self, parent: QWidget, parent_window: QWidget):
        super().__init__(parent)
        self.setObjectName("MenuBarSpacer")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.parent_window = parent_window
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def mousePressEvent(self, event) -> None:
        handle = self.parent_window.windowHandle()
        if handle is not None:
            handle.startSystemMove()

    def mouseDoubleClickEvent(self, event) -> None:
        menubar = self.parent()
        if isinstance(menubar, CustomMenuBarQt):
            menubar._toggle_maximize()
