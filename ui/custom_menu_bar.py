import tkinter as tk
import customtkinter as ctk
from typing import Callable, List, Dict, Any


class CustomMenuBar(ctk.CTkFrame):
    def __init__(self, parent, theme_manager, **kwargs):
        super().__init__(parent, **kwargs)
        self.theme_manager = theme_manager
        self.parent_window = parent
        self.active_menu = None
        self.menu_buttons = {}
        self.dropdown_menus = {}
        self.menus_data = {}

        root_bg = self._get_root_bg()
        self.configure(
            height=30,
            fg_color=self._get_menubar_bg(),
            bg_color=root_bg,
            corner_radius=0
        )

    def _get_root_bg(self):
        """Get root window background color based on theme."""
        if not self.theme_manager:
            return "#1E1E1E"
        palette = self.theme_manager.palette
        return palette.get("bg", "#1E1E1E")

    def _get_menubar_bg(self):
        if not self.theme_manager:
            return "#323233"
        palette = self.theme_manager.palette
        return palette.get("menubar_bg", "#323233")

    def _get_hover_color(self):
        if not self.theme_manager:
            return "#2A2D2E"
        palette = self.theme_manager.palette
        return palette.get("menubar_hover", "#2A2D2E")

    def _get_text_color(self):
        if not self.theme_manager:
            return "#CCCCCC"
        palette = self.theme_manager.palette
        return palette.get("menubar_text", "#CCCCCC")

    def add_menu(self, label: str, items: List[Dict[str, Any]]):
        # Calculate width based on text length for better fit
        text_width = len(label) * 8 + 20  # Approximate width
        btn = ctk.CTkButton(
            self,
            text=label,
            width=text_width,
            height=28,
            fg_color=self._get_menubar_bg(),
            hover_color=self._get_hover_color(),
            text_color=self._get_text_color(),
            font=("Segoe UI", 13),
            corner_radius=0,
            anchor="center",
            command=lambda l=label: self._toggle_menu(l),
            border_width=0
        )
        btn.pack(side=tk.LEFT, padx=(8, 0))
        self.menu_buttons[label] = btn
        self.menus_data[label] = items

    def _toggle_menu(self, label: str):
        """Toggle dropdown menu visibility."""
        if self.active_menu == label:
            self._close_active_menu()
        else:
            self._close_active_menu()
            self._open_menu(label)

    def _open_menu(self, label: str):
        """Open a dropdown menu."""
        self.active_menu = label
        button = self.menu_buttons[label]
        items = self.menus_data[label]

        dropdown = DropdownMenu(
            self.parent_window,
            items,
            self.theme_manager,
            close_callback=self._close_active_menu
        )

        x = button.winfo_rootx() - self.parent_window.winfo_rootx()
        y = button.winfo_rooty() - self.parent_window.winfo_rooty() + button.winfo_height()

        dropdown.place(x=x, y=y)
        dropdown.lift()

        self.active_dropdown = dropdown

        self.parent_window.bind("<Button-1>", self._check_click_outside, add="+")

    def _close_active_menu(self):
        """Close the currently active menu."""
        if hasattr(self, 'active_dropdown'):
            try:
                self.active_dropdown.destroy()
            except:
                pass
            delattr(self, 'active_dropdown')
        self.active_menu = None
        try:
            self.parent_window.unbind("<Button-1>")
        except:
            pass

    def _check_click_outside(self, event):
        """Check if click was outside the menu and close if so."""
        if hasattr(self, 'active_dropdown'):
            widget = event.widget
            while widget:
                if widget == self.active_dropdown or widget in self.menu_buttons.values():
                    return
                try:
                    widget = widget.master
                except:
                    break
            self._close_active_menu()

    def update_theme(self):
        """Update colors when theme changes."""
        root_bg = self._get_root_bg()
        menubar_bg = self._get_menubar_bg()
        hover_color = self._get_hover_color()
        text_color = self._get_text_color()

        self.configure(
            fg_color=menubar_bg,
            bg_color=root_bg
        )

        for btn in self.menu_buttons.values():
            btn.configure(fg_color=menubar_bg, hover_color=hover_color, text_color=text_color, bg_color=root_bg)


class DropdownMenu(ctk.CTkFrame):
    """Dropdown menu for custom menu bar."""

    def __init__(self, parent, items: List[Dict], theme_manager, close_callback: Callable):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.close_callback = close_callback
        self.items = items
        self.submenu_windows = []

        palette = theme_manager.palette if theme_manager else {}

        # Use theme-based colors for dropdown
        self.bg_color = palette.get("dropdown_bg", "#252526")
        self.hover_color = palette.get("dropdown_hover", "#2A2D2E")
        self.text_color = palette.get("dropdown_text", "#CCCCCC")
        self.disabled_color = palette.get("dropdown_disabled", "#666666")
        self.separator_color = palette.get("dropdown_separator", "#454545")
        self.border_color = palette.get("dropdown_border", "#3E3E42")
        self.shortcut_color = palette.get("dropdown_shortcut", "#858585")

        self.configure(
            fg_color=self.bg_color,
            corner_radius=0,
            border_width=1,
            border_color=self.border_color
        )

        self._build_items()

    def _build_items(self):
        for item in self.items:
            if item.get("separator"):
                # Create a more visible separator using CTkLabel
                sep_container = ctk.CTkFrame(self, fg_color=self.bg_color, height=5)
                sep_container.pack(fill=tk.X, padx=0, pady=0)
                sep_container.pack_propagate(False)

                # Create separator line using CTkLabel with better rendering
                sep_line = ctk.CTkLabel(sep_container, text="", fg_color="transparent",
                                       bg_color=self.separator_color, height=1)
                sep_line.pack(fill=tk.X, padx=0, pady=2)  # Center perfectly to avoid dots
            else:
                self._create_menu_item(item)

    def _create_menu_item(self, item: Dict):
        label = item.get("label", "")
        command = item.get("command")
        state = item.get("state", "normal")
        submenu = item.get("submenu")
        checkbutton = item.get("checkbutton", False)
        variable = item.get("variable")
        radiobutton = item.get("radiobutton", False)
        value = item.get("value")
        accelerator = item.get("accelerator", "")  # Keyboard shortcut

        text_color = self.text_color if state == "normal" else self.disabled_color

        # Create a frame for the menu item to support label + shortcut layout
        item_frame = ctk.CTkFrame(self, fg_color=self.bg_color, corner_radius=0, height=27)
        item_frame.pack(fill=tk.X, padx=0, pady=0)
        item_frame.pack_propagate(False)

        # Build display label with checkmarks/radio indicators
        display_label = label
        if checkbutton and variable:
            display_label = "✓ " + label if variable.get() else "   " + label
        elif radiobutton and variable and value is not None:
            display_label = "● " + label if variable.get() == value else "   " + label

        # Create button for the menu item
        btn = ctk.CTkButton(
            item_frame,
            text=display_label,
            width=1,
            height=27,
            fg_color=self.bg_color,
            hover_color=self.hover_color if state == "normal" else self.bg_color,
            text_color=text_color,
            font=("Segoe UI", 12),
            corner_radius=0,
            anchor="w",
            command=lambda: self._execute_item(item) if state == "normal" else None,
            state=state,
            border_width=0
        )
        btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        # Add keyboard shortcut on the right if provided
        if accelerator:
            shortcut_label = ctk.CTkLabel(
                item_frame,
                text=accelerator,
                text_color=self.shortcut_color,
                font=("Segoe UI", 11),
                anchor="e"
            )
            shortcut_label.pack(side=tk.RIGHT, padx=(0, 12))

        # Add submenu indicator
        if submenu:
            arrow_label = ctk.CTkLabel(
                item_frame,
                text="▶",
                text_color=text_color,
                font=("Segoe UI", 10),
                anchor="e"
            )
            arrow_label.pack(side=tk.RIGHT, padx=(0, 8))

        # Store reference to item_frame for hover detection
        item_frame.item = item
        item_frame.btn = btn

        # Bind hover for submenu
        if submenu and state == "normal":
            item_frame.bind("<Enter>", lambda e, i=item, f=item_frame: self._show_submenu(i, f))
            btn.bind("<Enter>", lambda e, i=item, f=item_frame: self._show_submenu(i, f))

    def _show_submenu(self, item: Dict, widget):
        """Show submenu on hover"""
        submenu_items = item.get("submenu", [])
        if not submenu_items:
            return

        self._close_submenus()

        submenu = DropdownMenu(
            self.master,
            submenu_items,
            self.theme_manager,
            close_callback=self.close_callback
        )

        # Position submenu to the right of the parent menu item
        x = widget.winfo_rootx() - self.master.winfo_rootx() + widget.winfo_width()
        y = widget.winfo_rooty() - self.master.winfo_rooty()

        submenu.place(x=x, y=y)
        submenu.lift()

        self.submenu_windows.append(submenu)

    def _close_submenus(self):
        """Close all submenus."""
        for submenu in self.submenu_windows:
            try:
                submenu.destroy()
            except:
                pass
        self.submenu_windows.clear()

    def _execute_item(self, item: Dict):
        """Execute menu item action."""
        checkbutton = item.get("checkbutton", False)
        variable = item.get("variable")
        radiobutton = item.get("radiobutton", False)
        value = item.get("value")
        command = item.get("command")

        if checkbutton and variable:
            variable.set(not variable.get())

        elif radiobutton and variable and value is not None:
            variable.set(value)

        if command:
            command()

        if self.close_callback:
            self.close_callback()

    def destroy(self):
        """Clean up submenus before destroying."""
        self._close_submenus()
        super().destroy()
