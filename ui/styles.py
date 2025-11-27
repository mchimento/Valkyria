"""
ttk styles generator hooked to a theme palette dictionary.
"""

from tkinter import ttk

def apply_base_styles(root, palette):
    style = ttk.Style(root)
    # Use clam for consistent look across platforms
    try:
        style.theme_use("clam")
    except Exception:
        # fallback to default theme
        pass

    # General widget colors
    style.configure("TFrame", background=palette["bg"])
    style.configure("TLabel", background=palette["bg"], foreground=palette["fg"], font=(palette["ui_font"], 10))
    style.configure(
        "TButton",
        padding=6,
        background=palette.get("button_bg_color", palette["accent"]),
        foreground=palette.get("button_fg_color", "#ffffff"),
        font=("Segoe UI", 10)
    )
    style.map(
        "TButton",
        background=[("active", palette.get("button_hover", palette.get("accent_hover")))],
        foreground=[("active", palette.get("button_fg_color", "#ffffff"))]
    )

    # Treeview
    style.configure("Treeview",
                    background=palette["tree_bg"],
                    foreground=palette["fg"],
                    fieldbackground=palette["tree_bg"],
                    font=(palette["ui_font"], 10),
                    rowheight=25)
    style.configure("Treeview.Heading",
                    background=palette.get("tree_header", palette["bg"]),
                    foreground=palette["fg"],
                    font=(palette["ui_font"], 10, "bold"))
    style.map("Treeview",
              background=[("selected", palette.get("accent"))],
              foreground=[("selected", palette.get("fg"))])      
    style.map('Treeview.Heading',
              background=[('active', palette["tree_header"]), ('pressed', palette["tree_header"])], 
              foreground=[('active', palette["fg"]), ('pressed', palette["fg"])])
    
    # Checkbutton
    style.configure('TCheckbutton',
                    background=palette["bg"],
                    foreground=palette["fg"]
    )
    style.map('TCheckbutton',
              background=[('active', palette["bg"])],
              foreground=[('!disabled', palette["fg"])]
    )

    # Radiobutton
    style.configure('Prefs.TRadiobutton', background=palette["bg"], foreground=palette["fg"])
    style.map('Prefs.TRadiobutton', background=[('active', palette["bg"]), ('selected', palette["bg"])],
            foreground=[('!disabled', palette["fg"])])

    # Scale
    style.configure("Horizontal.TScale", background=palette["bg"])

    # Status bar label
    style.configure(
        "StatusBarMain.TLabel",
        background=palette.get("status_bg", palette["bg"]),
        foreground=palette.get("status_fg", palette["fg"]),
        padding=(5, 2),
        font=(palette["ui_font"], 10, "bold")
    )
    style.configure(
        "StatusBarMeta.TLabel",
        background=palette.get("status_bg", palette["bg"]),
        foreground=palette.get("status_meta_fg", palette["fg"]),
        padding=(5, 2),
        font=(palette["ui_font"], 9)
    )
    style.configure(
        "StatusBar.TFrame",
        borderwidth=2,
        relief="solid",
        background=palette.get("status_bg", palette["bg"]),
        foreground=palette.get("status_meta_fg", palette["fg"]),
        bordercolor=palette["fg"]
    )    
